"""Reviewed, transactional era overlays for the qualified Traditional server.

This changes rules and zone rule routing only. PEQ content stays in place. The
ownership record lives in the same database transaction as the rules it owns,
so a database/session restore carries its original configuration with it.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import time

from player_data import ident, rows
from rule_catalog import parse_source, validate_value

REGISTRY = '_trasc_era_rules'
FORMAT = 'trasc-era-rules-2'
TTL = 1800
LIMIT = 16 * 1024**2
TABLES = ('rule_sets', 'rule_values', 'variables', 'zone')
ZONE_COLUMNS = ('id', 'short_name', 'zoneidnumber', 'version', 'ruleset')
CONTENT_RULE = 'Expansion:CurrentExpansion'
ERAS = ('velious', 'luclin', 'pop')


def literal(value):
    return "CONVERT(X'%s' USING utf8mb4)" % str(value).encode().hex()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def require_profile(engine):
    if engine.profile != 'traditional':
        raise ValueError('Era rulesets are available only in Traditional EQEmu')
    if not engine.config.get('database_imported'):
        raise ValueError('Import the PEQ database before reviewing era rulesets')


def require_stopped(engine):
    require_profile(engine)
    if engine.server_running():
        raise ValueError('Stop the server and client before changing an era ruleset')
    # The native bridge also serializes against client launch and queued era
    # jobs. Check live supervisor processes independently for direct API calls.
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            if directory.stat().st_uid != os.getuid():
                continue
            command = (directory / 'cmdline').read_bytes()
            if any(part.endswith(b'/client_runner.py') for part in command.split(b'\0')):
                raise ValueError('Stop the embedded client before changing an era ruleset')
        except (OSError, ProcessLookupError):
            continue


def manifest():
    path = Path(__file__).with_name('era_presets.json')
    if path.stat().st_size > 1024**2:
        raise ValueError('Era preset manifest exceeds limits')
    result = json.loads(path.read_text())
    if result.get('version') != 1 or set(result.get('presets', {})) != set(ERAS):
        raise ValueError('Unsupported era preset manifest')
    for key, preset in result['presets'].items():
        if type(preset.get('expansion')) is not int or preset['expansion'] not in (2, 3, 4):
            raise ValueError('Invalid era expansion')
        for name, spec in preset['rules'].items():
            if not re.fullmatch(r'[A-Za-z]+:[A-Za-z0-9_]+', name) or not isinstance(spec.get('value'), str):
                raise ValueError('Invalid era rule manifest')
    return result


def catalog(engine, presets):
    import traditional_build
    root = engine.source_root()
    path = root / 'common/ruletypes.h'
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(engine.work)):
        raise ValueError('The era rule catalog cannot follow a source symlink')
    if not path.is_file() or path.stat().st_size > 4 * 1024**2:
        raise ValueError('The imported Traditional rule catalog is missing')
    data = path.read_bytes()
    expected = presets.get('rule_catalog_sha256')
    if not expected or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('The era presets do not match the imported Traditional rule catalog')
    info_path = engine.work / 'server/bin/build-info.json'
    if info_path.is_symlink() or not info_path.is_file() or info_path.stat().st_size > 1024**2:
        raise ValueError('Deploy the already compiled Traditional server before changing eras')
    info = json.loads(info_path.read_text())
    if info.get('format') != 1 or info.get('recipe') != traditional_build.RECIPE:
        raise ValueError('The deployed server does not use the qualified Traditional recipe')
    provenance = info.get('source', {})
    if provenance.get('type') == 'github' and provenance.get('commit') != traditional_build.REVISION:
        raise ValueError('The deployed server source does not match the era preset source')
    return parse_source(data.decode('utf-8')), hashlib.sha256(data).hexdigest()


def schema(engine):
    selected = ','.join(literal(t) for t in (*TABLES, REGISTRY))
    engines = dict(rows(engine, 'SELECT TABLE_NAME,COALESCE(ENGINE,\'VIEW\') FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (' + selected + ');'))
    for table in TABLES:
        if engines.get(table, '').lower() != 'innodb':
            raise ValueError(table + ': era changes require InnoDB for atomic restoration; no storage engine was changed')
    if REGISTRY in engines and engines[REGISTRY].lower() != 'innodb':
        raise ValueError('Unsupported era ownership table storage engine')
    columns = {}
    raw_columns = rows(engine, 'SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COALESCE(EXTRA,\'\') FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (' + selected + ') ORDER BY TABLE_NAME,ORDINAL_POSITION;')
    for table, name, kind, nullable, extra in raw_columns:
        if 'GENERATED' in extra.upper():
            raise ValueError('Era tables cannot contain generated columns')
        columns.setdefault(table, []).append({'name': name, 'type': kind, 'nullable': nullable, 'extra': extra})
    required = {'rule_sets': {'ruleset_id', 'name'}, 'rule_values': {'ruleset_id', 'rule_name', 'rule_value', 'notes'},
                'variables': {'id', 'varname', 'value', 'information', 'ts'}, 'zone': set(ZONE_COLUMNS)}
    for table, names in required.items():
        if not names <= {c['name'] for c in columns.get(table, [])}:
            raise ValueError('Unsupported era table columns: ' + table)
    for table, name in (('rule_sets', 'ruleset_id'), ('rule_values', 'ruleset_id'), ('zone', 'ruleset')):
        kind = next(c['type'] for c in columns[table] if c['name'] == name)
        if not re.fullmatch(r'(?:tinyint(?:\(\d+\))? unsigned|(?:smallint|mediumint|int|bigint)(?:\(\d+\))?(?: unsigned)?)', kind):
            raise ValueError(table + '.' + name + ': era ruleset IDs need an integer column supporting 0–255')
    keys = {}
    key_rows = rows(engine, 'SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND CONSTRAINT_NAME=\'PRIMARY\' AND TABLE_NAME IN (' + selected + ') ORDER BY TABLE_NAME,ORDINAL_POSITION;')
    for table, column in key_rows:
        keys.setdefault(table, []).append(column)
    for table, expected in {'rule_sets': ['ruleset_id'], 'rule_values': ['ruleset_id', 'rule_name'], 'variables': ['id'], 'zone': ['id']}.items():
        if keys.get(table) != expected:
            raise ValueError('Unsupported era table primary key: ' + table)
    if REGISTRY in engines:
        if keys.get(REGISTRY) != ['id'] or {c['name'] for c in columns[REGISTRY]} != {'id', 'manifest'}:
            raise ValueError('An unrelated table occupies the era ownership namespace')
    if rows(engine, 'SELECT TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL AND (TABLE_NAME IN (' + selected + ') OR REFERENCED_TABLE_NAME IN (' + selected + '));'):
        raise ValueError('Era rule tables with foreign keys are not supported')
    if rows(engine, 'SELECT EVENT_OBJECT_TABLE FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE IN (' + selected + ');'):
        raise ValueError('Era rule tables with triggers are not supported')
    return {'engines': engines, 'columns': columns, 'keys': keys, 'column_rows': raw_columns, 'key_rows': key_rows}


def expressions(columns):
    return ["IF(" + ident(c) + " IS NULL,'N',CONCAT('H',HEX(CAST(" + ident(c) + " AS BINARY))))" for c in columns]


def read_table(engine, table, columns):
    expr = expressions(columns)
    data = rows(engine, "SET time_zone='+00:00'; SELECT " + ','.join(expr) + ' FROM ' + ident(table) + ' ORDER BY ' + ','.join(expr) + ';')
    if len(data) > 100000 or sum(sum(map(len, row)) for row in data) > LIMIT:
        raise ValueError('Era snapshot exceeds its safe review limit')
    return data


def decoded(raw, columns):
    return {key: None if item == 'N' else bytes.fromhex(item[1:]).decode('utf-8') for key, item in zip(columns, raw)}


def encoded(record, columns):
    return ['N' if record.get(c) is None else 'H' + str(record[c]).encode().hex().upper() for c in columns]


def snapshot(engine):
    require_profile(engine)
    engine.ensure_db()
    presets = manifest()
    rules, source_hash = catalog(engine, presets)
    shape = schema(engine)
    cols = {t: [c['name'] for c in shape['columns'][t]] for t in TABLES}
    cols['zone'] = list(ZONE_COLUMNS)
    if REGISTRY in shape['engines']:
        cols[REGISTRY] = ['id', 'manifest']
    raw = {t: read_table(engine, t, c) for t, c in cols.items()}
    data = {t: [decoded(r, cols[t]) for r in value] for t, value in raw.items()}
    sets = {int(row['ruleset_id']): row['name'] for row in data['rule_sets']}
    if len(sets) != len(data['rule_sets']) or len({n.casefold() for n in sets.values()}) != len(sets):
        raise ValueError('The database has duplicate ruleset names or IDs')
    defaults = [key for key, name in sets.items() if name == 'default']
    if len(defaults) != 1:
        raise ValueError('The database must have exactly one ruleset named default')
    seen = set()
    rule_map = {}
    for row in data['rule_values']:
        identity = (int(row['ruleset_id']), row['rule_name'].casefold())
        if identity in seen or identity[0] not in sets:
            raise ValueError('Duplicate rule rows or a rule referring to a missing ruleset')
        seen.add(identity)
        rule_map.setdefault(identity[0], {})[row['rule_name']] = row
    active = [r for r in data['variables'] if r['varname'].casefold() == 'ruleset']
    if len(active) > 1:
        raise ValueError('The database contains duplicate RuleSet variables; no changes were made')
    active_row = active[0] if active else None
    active_name = active_row['value'] if active_row else 'default'
    active_id = next((i for i, name in sets.items() if name == active_name), None)
    if active_id is None:
        raise ValueError('The RuleSet variable refers to an unknown ruleset')
    for zone in data['zone']:
        if int(zone['ruleset']) and int(zone['ruleset']) not in sets:
            raise ValueError('A zone refers to a missing ruleset: ' + zone['short_name'])
    own = None
    registry_rows = data.get(REGISTRY, [])
    if registry_rows:
        if len(registry_rows) != 1 or registry_rows[0]['id'] != '1':
            raise ValueError('An unrelated record occupies the era ownership namespace')
        try:
            own = json.loads(registry_rows[0]['manifest'])
            assert own['format'] == FORMAT and type(own['sets']) is dict
            assert own['default_id'] == defaults[0]
            assert own.get('active') in (None, *ERAS)
            owned_ids = []
            for era, record in own['sets'].items():
                assert era in ERAS and type(record['main']) is int
                era_ids = {record['main'], *[int(value) for value in record['composites'].values()]}
                assert len(era_ids) == 1 + len(record['composites'])
                assert {int(key) for key in record['names']} == era_ids
                for identity, name in record['names'].items():
                    assert sets[int(identity)] == name and name.startswith('TRASC_Era_')
                    owned_ids.append(int(identity))
            assert len(owned_ids) == len(set(owned_ids))
            if own.get('active'):
                assert type(own['baseline']) is dict
                assert own['baseline_sha256'] == digest(own['baseline'])
                assert set(own['baseline']) == {'zones', 'default_rules', 'active'}
                assert type(own['baseline']['default_rules']) is dict
                assert set(own['default_expected']) == set(own['baseline']['default_rules'])
                for name, original in own['baseline']['default_rules'].items():
                    assert re.fullmatch(r'[A-Za-z]+:[A-Za-z0-9_]+', name)
                    for value in (original, own['default_expected'][name]):
                        if value is not None:
                            assert set(value) == set(cols['rule_values'])
                            assert int(value['ruleset_id']) == defaults[0] and value['rule_name'] == name
                originals = own['baseline']['zones']
                assert type(originals) is list and len({r['id'] for r in originals}) == len(originals)
                assert all(set(r) == set(ZONE_COLUMNS) and int(r['ruleset']) in (0, *sets) for r in originals)
                if own['baseline']['active'] is not None:
                    assert set(own['baseline']['active']) == set(cols['variables'])
                    assert own['baseline']['active']['varname'].casefold() == 'ruleset'
        except (AssertionError, KeyError, ValueError, TypeError):
            raise ValueError('Era ownership no longer matches this database; restore its matching backup') from None
    state = {'shape': shape, 'columns': cols, 'raw': raw, 'data': data, 'sets': sets,
             'rule_map': rule_map, 'default_id': defaults[0], 'active_id': active_id, 'active_row': active_row,
             'own': own, 'presets': presets, 'catalog': rules, 'source_hash': source_hash}
    state['revision'] = digest({'schema': shape, 'raw': raw, 'presets': presets, 'source': source_hash})
    return state


def baseline(state):
    names = set().union(*(p['rules'].keys() for p in state['presets']['presets'].values()))
    return {'zones': copy.deepcopy(state['data']['zone']),
            'default_rules': {name: copy.deepcopy(state['rule_map'].get(state['default_id'], {}).get(name)) for name in sorted(names)},
            'active': copy.deepcopy(state['active_row'])}


def validate_managed(state):
    own = state['own']
    if not own or not own.get('active'):
        return
    record = own['sets'][own['active']]
    if state['active_id'] != record['main']:
        raise ValueError('The active RuleSet changed outside the era selector; restore the matching backup or review that edit')
    current = {r['id']: r for r in state['data']['zone']}
    before = {r['id']: r for r in own['baseline']['zones']}
    if current.keys() != before.keys():
        raise ValueError('Zone rows were added or removed during the era overlay; review them before restoring')
    for key, original in before.items():
        now = current[key]
        route = routed(original, record, state['default_id'])
        if any(now[c] != original[c] for c in ZONE_COLUMNS if c != 'ruleset') or int(now['ruleset']) != route:
            raise ValueError('A managed zone rule route changed: ' + original['short_name'])
    for name, expected in own['default_expected'].items():
        actual = state['rule_map'].get(state['default_id'], {}).get(name)
        if actual != expected:
            raise ValueError('A managed default startup rule changed outside the era selector: ' + name)


def routed(zone, record, default_id):
    source = int(zone['ruleset'])
    return record['main'] if source in (0, default_id) else int(record['composites'][str(source)])


def supported_rules(state, era):
    rules, omitted = {}, []
    for name, spec in state['presets']['presets'][era]['rules'].items():
        if name not in state['catalog']:
            if spec.get('required', True):
                raise ValueError('The deployed source does not support required era rule ' + name)
            omitted.append({'rule': name, 'reason': 'Not supported by the deployed rule catalog'})
            continue
        rules[name] = validate_value(name, spec['value'], state['catalog'][name], 65535)
    if CONTENT_RULE not in rules:
        raise ValueError('The era needs a supported world content expansion rule')
    return rules, omitted


def rule_row(state, identity, name, value, notes):
    result = {c: None for c in state['columns']['rule_values']}
    result.update(ruleset_id=str(identity), rule_name=name, rule_value=value, notes=notes)
    if set(result) != {'ruleset_id', 'rule_name', 'rule_value', 'notes'}:
        raise ValueError('Additional rule value columns need explicit era compatibility support')
    return result


def plan(state, era, mode='default'):
    if era not in (*ERAS, 'default') or mode not in ('default', 'previous'):
        raise ValueError('Choose Velious, Luclin, Planes of Power or Default')
    validate_managed(state)
    own = copy.deepcopy(state['own'] or {'format': FORMAT, 'default_id': state['default_id'], 'sets': {}, 'active': None, 'baseline': None})
    old_baseline = own['baseline'] if own.get('active') else baseline(state)
    changes, set_rows, new_rules, manual, omitted = [], [], [], [], []
    record = None
    if era != 'default':
        configured, omitted = supported_rules(state, era)
        record = own['sets'].get(era)
        if not record:
            used = set(state['sets'])
            maximum = 255
            free = iter(i for i in range(1, maximum + 1) if i not in used)
            source_ids = sorted({int(r['ruleset']) for r in old_baseline['zones']} - {0, state['default_id']})
            try:
                main = next(free)
                composites = {str(source): next(free) for source in source_ids}
            except StopIteration:
                raise ValueError('Not enough free ruleset IDs for the era and existing zone overrides') from None
            label = {'velious': 'Velious', 'luclin': 'Luclin', 'pop': 'PoP'}[era]
            names = {str(main): 'TRASC_Era_' + label}
            names.update({str(value): 'TRASC_Era_' + label + '_Zone_' + key for key, value in composites.items()})
            if any(name.casefold() in {n.casefold() for n in state['sets'].values()} for name in names.values()):
                raise ValueError('An unowned ruleset already uses an era name; it was not overwritten')
            record = {'main': main, 'composites': composites, 'names': names, 'preset_revision': state['presets']['revision']}
            own['sets'][era] = record
            for identity, name in names.items():
                set_rows.append({'ruleset_id': identity, 'name': name})
                source = next((int(s) for s, target in composites.items() if int(target) == int(identity)), None)
                baseline_name = old_baseline['active']['value'] if old_baseline['active'] else 'default'
                baseline_id = next(i for i, n in state['sets'].items() if n == baseline_name)
                inherited_source = source if source is not None else (baseline_id if baseline_id != state['default_id'] else None)
                content = copy.deepcopy(state['rule_map'].get(inherited_source, {}))
                for rule, value in configured.items():
                    content[rule] = rule_row(state, int(identity), rule, value, 'TRASC era preset ' + era)
                for rule, row in sorted(content.items()):
                    row['ruleset_id'] = identity
                    new_rules.append(row)
                    if rule in configured:
                        effective = state['rule_map'].get(source if source is not None else state['active_id'], {}).get(rule)
                        effective = effective or state['rule_map'].get(state['default_id'], {}).get(rule)
                        before = effective['rule_value'] if effective else state['catalog'].get(rule, {}).get('default')
                        changes.append({'scope': 'rules', 'ruleset': name, 'rule': rule, 'before': before,
                                        'after': row['rule_value'], 'reason': state['presets']['presets'][era]['rules'][rule].get('reason', '')})
        else:
            # Re-selection chooses this user's existing set without regeneration.
            sources = {str(int(r['ruleset'])) for r in old_baseline['zones']} - {'0', str(state['default_id'])}
            if not sources <= record['composites'].keys():
                raise ValueError('New zone override sources need a reviewed new era installation; existing managed sets were preserved')
            for identity, name in record['names'].items():
                for rule, value in configured.items():
                    actual = state['rule_map'].get(int(identity), {}).get(rule)
                    after = actual['rule_value'] if actual else state['rule_map'].get(state['default_id'], {}).get(rule, {}).get('rule_value', state['catalog'][rule].get('default'))
                    if after != value:
                        manual.append({'ruleset': name, 'rule': rule, 'preset': value, 'value': after})
        target_id, target_name = record['main'], record['names'][str(record['main'])]
        if not configured.keys() <= old_baseline['default_rules'].keys():
            raise ValueError('The era preset adds startup rules; restore the previous overlay before reviewing an updated preset')
        next_default_rules = copy.deepcopy(old_baseline['default_rules'])
        for name, value in configured.items():
            if not set_rows:
                actual = state['rule_map'].get(record['main'], {}).get(name)
                if actual is None:
                    next_default_rules[name] = copy.deepcopy(old_baseline['default_rules'][name])
                    continue
                value = validate_value(name, actual['rule_value'], state['catalog'][name], 65535)
            before = state['rule_map'].get(state['default_id'], {}).get(name)
            row = copy.deepcopy(before) if before else rule_row(state, state['default_id'], name, '', 'TRASC era startup overlay')
            row['rule_value'] = value
            next_default_rules[name] = row
        own.update(active=era, baseline=old_baseline, baseline_sha256=digest(old_baseline), default_expected=next_default_rules)
    else:
        target_id, target_name = state['default_id'], 'default'
        next_default_rules = old_baseline['default_rules'] if own.get('active') else {}
        if mode == 'previous' and own.get('active'):
            prior = old_baseline['active']
            target_name = prior['value'] if prior else 'default'
            target_id = next((i for i, name in state['sets'].items() if name == target_name), None)
            if target_id is None:
                raise ValueError('The original active ruleset no longer exists')
        own.update(active=None, baseline=None)
        own.pop('default_expected', None)
        own.pop('baseline_sha256', None)
    restore_exact = era == 'default' and state['own'] and state['own'].get('active') and (mode == 'previous' or old_baseline['active'] is None or old_baseline['active']['value'] == 'default')
    if restore_exact:
        next_active = copy.deepcopy(old_baseline['active'])
    else:
        next_active = copy.deepcopy(state['active_row']) if state['active_row'] else {
            'id': str(max((int(r['id']) for r in state['data']['variables']), default=0) + 1),
            'varname': 'RuleSet', 'value': '', 'information': 'TRASC era selector', 'ts': None}
        if set(next_active) != set(state['columns']['variables']):
            raise ValueError('Additional variable columns need explicit era compatibility support')
        next_active['value'] = target_name
    for name, row in sorted(next_default_rules.items()):
        before = state['rule_map'].get(state['default_id'], {}).get(name)
        changes.append({'scope': 'world_content', 'ruleset': 'default', 'rule': name,
                        'before': before['rule_value'] if before else None,
                        'after': row['rule_value'] if row else None,
                        'reason': 'The pinned world, zone and shared-memory startup reload default rules; preserve this original row or absence for restoration.'})
    changes.append({'scope': 'active_ruleset', 'ruleset': 'variables', 'rule': 'RuleSet',
                    'before': state['active_row']['value'] if state['active_row'] else None,
                    'after': next_active['value'] if next_active else None, 'reason': 'Select the named ruleset; a missing variable uses default.'})
    now = {r['id']: r for r in state['data']['zone']}
    zone_changes = []
    for old in old_baseline['zones']:
        after = routed(old, record, state['default_id']) if record else int(old['ruleset'])
        before = int(now[old['id']]['ruleset'])
        if before != after:
            zone_changes.append({'id': int(old['id']), 'zone': old['short_name'], 'version': int(old['version']), 'before': before, 'after': after})
    result = {'era': era, 'mode': mode, 'label': state['presets']['presets'][era]['label'] if era != 'default' else 'Default',
              'revision': state['revision'], 'ruleset_id': target_id, 'changes': changes, 'zone_changes': zone_changes,
              'zone_counts': {'total': len(now), 'routed': len(zone_changes), 'existing_overrides': sum(int(r['ruleset']) != 0 for r in old_baseline['zones'])},
              'omissions': omitted, 'manual_edits': manual, 'requires_restart': True,
              'limitations': state['presets']['presets'][era].get('limitations', []) if era != 'default' else [],
              'set_rows': set_rows, 'new_rules': new_rules, 'next_default_rules': next_default_rules, 'next_active': next_active,
              'new_variable': not restore_exact and state['active_row'] is None, 'ownership': own}
    result['review_token'] = digest({'revision': state['revision'], 'plan': result})
    if len(json.dumps(own, separators=(',', ':')).encode()) > LIMIT // 2:
        raise ValueError('The reversible era ownership record exceeds its supported size')
    return result


def public_plan(result):
    return {k: v for k, v in result.items() if k not in ('set_rows', 'new_rules', 'next_default_rules', 'next_active', 'new_variable', 'ownership')}


def status(engine, args=None):
    state = snapshot(engine)
    own = state['own']
    current = own['active'] if own and own.get('active') and state['active_id'] == own['sets'][own['active']]['main'] else ('default' if state['active_id'] == state['default_id'] else 'custom')
    customized = False
    if current in ERAS:
        preset, omitted = supported_rules(state, current)
        configured = state['rule_map'].get(state['active_id'], {})
        customized = any(configured.get(name, {}).get('rule_value') != value for name, value in preset.items())
    return {'profile': 'traditional', 'revision': state['revision'],
            'current': {'era': current, 'label': state['sets'][state['active_id']], 'ruleset': state['active_id'], 'customized': customized},
            'default_ruleset': {'id': state['default_id'], 'name': 'default'},
            'managed': [{'era': key, 'ruleset_id': value['main'], 'composites': value['composites']} for key, value in (own['sets'] if own else {}).items()],
            'available': [{'key': key, 'label': state['presets']['presets'][key]['label']} for key in ERAS] + [{'key': 'default', 'label': 'Default'}],
            'pending_restart': bool(engine.config.get('rules_pending_restart')),
            'limitations': ['The RoF2 client and PEQ content remain installed. Expansion tags, GM and bypass flags affect zone access.',
                            'Era switches preserve zone-specific unrelated rules through composite rulesets. Restart; do not reload rules live.']}


def preview(engine, args):
    state = snapshot(engine)
    result = plan(state, args.get('era'), args.get('mode', 'default'))
    from engine import atomic_json
    path = engine.work / 'run' / ('era-review-' + result['review_token'] + '.json')
    atomic_json(path, {'created': time.time(), 'token': result['review_token']})
    path.chmod(0o600)
    return public_plan(result)


def hash_expression(table, columns):
    expr = expressions(columns)
    return "(SELECT SHA2(COALESCE(GROUP_CONCAT(CONCAT_WS(CHAR(9)," + ','.join(expr) + ') ORDER BY ' + ','.join(expr) + " SEPARATOR '\n'),''),256) FROM " + ident(table) + ')'


def row_sql(record, columns):
    return ','.join('NULL' if record[c] is None else literal(record[c]) for c in columns)


def transaction(state, result):
    sql = ["SET time_zone='+00:00'; SET SESSION check_constraint_checks=ON; SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'; SET SESSION group_concat_max_len=" + str(LIMIT * 2) + ';',
           'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE; START TRANSACTION;',
           'CREATE TEMPORARY TABLE _trasc_era_guard (ok INT NOT NULL CHECK(ok=1));']
    # SERIALIZABLE aggregate reads retain shared next-key locks until COMMIT.
    # A failed CHECK stops the batch; disconnect rolls the complete TX back.
    for table, columns in state['columns'].items():
        expected = hashlib.sha256('\n'.join('\t'.join(r) for r in state['raw'][table]).encode()).hexdigest()
        sql.append('INSERT INTO _trasc_era_guard VALUES (IF(' + hash_expression(table, columns) + '=' + literal(expected) + ',1,0));')
    if REGISTRY not in state['columns']:
        sql.append('INSERT INTO _trasc_era_guard VALUES (IF((SELECT COUNT(*) FROM ' + ident(REGISTRY) + ')=0,1,0));')
    # Reads above hold metadata locks on every affected table. Confirm engines
    # after acquiring those locks, so an ALTER between preview and TX cannot
    # turn any later write into a nontransactional one.
    selected = ','.join(literal(t) for t in (*TABLES, REGISTRY))
    sql.append('INSERT INTO _trasc_era_guard VALUES (IF((SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (' + selected + ") AND ENGINE='InnoDB')=5,1,0));")
    sql.append('INSERT INTO _trasc_era_guard VALUES (IF((SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE IN (' + selected + '))=0,1,0));')
    sql.append('INSERT INTO _trasc_era_guard VALUES (IF((SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL AND (TABLE_NAME IN (' + selected + ') OR REFERENCED_TABLE_NAME IN (' + selected + ')))=0,1,0));')
    sql.append('INSERT INTO _trasc_era_guard VALUES (IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=' + literal(REGISTRY) + " AND ((COLUMN_NAME='id' AND DATA_TYPE='tinyint' AND IS_NULLABLE='NO') OR (COLUMN_NAME='manifest' AND DATA_TYPE='mediumtext' AND IS_NULLABLE='NO')))=2 AND (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=" + literal(REGISTRY) + ")=2 AND (SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=" + literal(REGISTRY) + " AND CONSTRAINT_NAME='PRIMARY' AND COLUMN_NAME='id')=1,1,0));")
    for source, table, columns, where, ordering in (
        (state['shape']['column_rows'], 'COLUMNS', ('TABLE_NAME', 'COLUMN_NAME', 'COLUMN_TYPE', 'IS_NULLABLE', 'EXTRA'), '', 'TABLE_NAME,ORDINAL_POSITION'),
        (state['shape']['key_rows'], 'KEY_COLUMN_USAGE', ('TABLE_NAME', 'COLUMN_NAME'), " AND CONSTRAINT_NAME='PRIMARY'", 'TABLE_NAME,ORDINAL_POSITION')):
        checked_tables = ','.join(literal(t) for t in state['shape']['engines'])
        expr = ["CONCAT('H',HEX(COALESCE(" + ident(c) + ",'')))" for c in columns]
        expected = hashlib.sha256('\n'.join('\t'.join('H' + v.encode().hex().upper() for v in row) for row in source).encode()).hexdigest()
        actual = "(SELECT SHA2(COALESCE(GROUP_CONCAT(CONCAT_WS(CHAR(9)," + ','.join(expr) + ') ORDER BY ' + ordering + " SEPARATOR '\n'),''),256) FROM information_schema." + ident(table) + ' WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (' + checked_tables + ')' + where + ')'
        sql.append('INSERT INTO _trasc_era_guard VALUES (IF(' + actual + '=' + literal(expected) + ',1,0));')
    for row in result['set_rows']:
        sql.append('INSERT INTO rule_sets (ruleset_id,name) VALUES (' + row['ruleset_id'] + ',' + literal(row['name']) + ');')
    for row in result['new_rules']:
        columns = state['columns']['rule_values']
        sql.append('INSERT INTO rule_values (' + ','.join(map(ident, columns)) + ') VALUES (' + row_sql(row, columns) + ');')
    for name, row in sorted(result['next_default_rules'].items()):
        sql.append('DELETE FROM rule_values WHERE ruleset_id=' + str(state['default_id']) + ' AND BINARY rule_name=BINARY ' + literal(name) + ';')
        if row:
            columns = state['columns']['rule_values']
            sql.append('INSERT INTO rule_values (' + ','.join(map(ident, columns)) + ') VALUES (' + row_sql(row, columns) + ');')
    if state['active_row']:
        sql.append('DELETE FROM variables WHERE id=' + str(int(state['active_row']['id'])) + ';')
    if result['next_active']:
        columns = state['columns']['variables']
        if result['new_variable']:
            columns = [c for c in columns if c != 'ts']
        sql.append('INSERT INTO variables (' + ','.join(map(ident, columns)) + ') VALUES (' + row_sql(result['next_active'], columns) + ');')
    for zone in result['zone_changes']:
        sql.append('UPDATE zone SET ruleset=' + str(zone['after']) + ' WHERE id=' + str(zone['id']) + ';')
    sql.append('DELETE FROM ' + ident(REGISTRY) + '; INSERT INTO ' + ident(REGISTRY) + ' (id,manifest) VALUES (1,' + literal(json.dumps(result['ownership'], sort_keys=True, separators=(',', ':'))) + ');')
    sql.append('COMMIT;')
    return '\n'.join(sql)


def apply(engine, args, restore=False):
    require_stopped(engine)
    token = args.get('review_token', '')
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValueError('Preview the era changes before applying them')
    path = engine.work / 'run' / ('era-review-' + token + '.json')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024:
        raise ValueError('Preview the era changes before applying them')
    review = json.loads(path.read_text())
    if time.time() - review['created'] > TTL or review['token'] != token:
        raise ValueError('The era preview expired; preview it again')
    state = snapshot(engine)
    result = plan(state, 'default' if restore else args.get('era'), args.get('mode', 'default'))
    if result['review_token'] != token:
        raise ValueError('The database or era preset changed since preview; review a fresh diff')
    backup = engine.backup_database({})['file']
    # Back up before the registry DDL. It is the only DDL; all user table data
    # and the complete ownership manifest are committed atomically afterward.
    if REGISTRY not in state['shape']['engines']:
        engine.mysql('CREATE TABLE ' + ident(REGISTRY) + ' (id TINYINT UNSIGNED NOT NULL PRIMARY KEY, manifest MEDIUMTEXT NOT NULL) ENGINE=InnoDB;')
    require_stopped(engine)
    try:
        engine.mysql(transaction(state, result), timeout=120)
    except Exception:
        # A freshly created empty registry is harmless. It can be reused; it
        # never claims ownership of partially written rules or zone routing.
        raise
    engine.config['rules_pending_restart'] = True
    engine.save()
    path.unlink(missing_ok=True)
    return {'message': result['label'] + ' rules selected. Start the server to load the world content filter and all zone rules consistently.',
            'backup': backup, 'restart_required': True, 'era': result['era'], 'ruleset_id': result['ruleset_id'],
            'zone_count': len(result['zone_changes']), 'manual_edits_preserved': len(result['manual_edits'])}


def dispatch(engine, operation, args):
    if operation == 'era_status':
        return status(engine, args)
    if operation == 'era_preview':
        return preview(engine, args)
    if operation == 'era_apply':
        return apply(engine, args)
    if operation == 'era_restore':
        return apply(engine, args, restore=True)
    raise ValueError('Unknown era operation')
