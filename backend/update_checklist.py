"""Explicit, read-only review of an isolated world's update components.

A green row means live bytes match a known local source/receipt at scan time.
Independent content repositories, database migrations and generated client data
are never inferred current from the server revision or from folder existence.
This module does not fetch, copy, recover, start a database, or alter game files.
"""
import json
from pathlib import Path
import re
import time

import custom_deployment as deployment
import content_baseline
import quest_sync
import source_updates
import traditional_build
import traditional_content
import takp_build
import takp_runtime

LABELS = {'source': 'Imported server source', 'build': 'Built server',
          'deployed': 'Deployed server', 'quests': 'Quests', 'plugins': 'Perl plugins',
          'lua_modules': 'Lua modules', 'maps': 'Maps', 'assets': 'Server support files',
          'lon': 'Legends of Norrath', 'client_data': 'Generated client data',
          'database': 'Database migrations'}
TARGETS = {'source': 'source-update-check', 'build': 'source-update-build',
           'deployed': 'source-update-deploy', 'quests': 'quest-scan',
           'plugins': 'quest-scan', 'lua_modules': 'quest-scan', 'maps': 'maps-git',
           'assets': 'assets-git', 'lon': 'lon-verify', 'client_data': 'export-client',
           'database': 'load-backups'}
STATES = ('current', 'attention', 'review', 'not_applicable')


def _check(engine):
    method = getattr(engine, 'check_cancel', None)
    if method:
        method()


def _path(engine, relative):
    return deployment.confined(engine, Path(engine.work) / relative)


def _json(engine, relative):
    path = _path(engine, relative)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError('Missing or oversized evidence: ' + relative)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Invalid evidence: ' + relative)
    return value


def _row(key, state, detail, **extra):
    return dict(id=key, label=LABELS[key], state=state, detail=detail,
                action={'target': TARGETS[key], 'section': 'manage', 'label': 'Review'}, **extra)


def _digest(engine, path):
    path = deployment.confined(engine, path)
    if not path.is_file():
        raise ValueError('Missing ordinary file: ' + str(path))
    return deployment.digest(path, lambda: _check(engine))


def _source(engine):
    root = _path(engine, 'sources/current')
    metadata = _json(engine, 'sources/current/trasc-source.json')
    revision = metadata.get('commit')
    if revision is not None and not re.fullmatch('[0-9a-fA-F]{40}', str(revision)):
        raise ValueError('The imported source revision is invalid')
    before = source_updates._stat_tree(root)
    if engine.profile == 'traditional':
        digest = traditional_build._tree_sha(traditional_build._inventory(root, lambda: _check(engine), source=True))
    else:
        digest = source_updates.identity(source_updates.inventory(root, lambda: _check(engine)))
    if before != source_updates._stat_tree(root) or metadata != _json(engine, 'sources/current/trasc-source.json'):
        raise ValueError('Source changed during inspection; scan again')
    return {'revision': revision, 'repository': metadata.get('repo'), 'ref': metadata.get('ref'),
            'tree_sha256': digest, 'metadata': metadata, 'scope': 'imported_source',
            'stat_identity': before}


def _build(engine, directory, source):
    """Verify full binary inventory and the build's actual input digest."""
    try:
        info = _json(engine, directory + '/build-info.json')
    except (OSError, ValueError) as error:
        _check(engine)
        return {'state': 'review', 'revision': None, 'detail': str(error), 'available': False}
    provenance = info.get('source')
    if not isinstance(provenance, dict):
        return {'state': 'review', 'revision': None, 'detail': 'Invalid build source evidence', 'available': True}
    result = {'revision': provenance.get('commit'), 'built': info.get('built'),
              'available': True, 'state': 'review'}
    try:
        if info.get('profile', engine.profile) != engine.profile:
            raise ValueError('The build receipt belongs to a different world profile')
        if not source.get('tree_sha256'):
            raise ValueError('Import and inspect the source before verifying this build')
        expected = info.get('input_sha256') if engine.profile != 'custom' else info.get('source_tree_sha256')
        result['tree_sha256'] = expected
        if not expected:
            raise ValueError('This older build has no complete source fingerprint; build the imported source to establish evidence')
        if expected != source['tree_sha256']:
            result.update(state='attention', detail='Built from different source bytes. Build and deploy the imported source after reviewing local edits.')
            return result
        # TAKP's receipt records qualified source independently of the importer.
        # Traditional also normalizes import metadata, so compare revision only.
        if source.get('revision') and result['revision'] != source['revision']:
            result.update(state='attention', detail='The build revision differs from the imported source revision. Build and deploy the selected source.')
            return result
        if engine.profile == 'traditional':
            report = _json(engine, directory + '/verification.json')
            if info.get('verification_sha256') != traditional_build._digest(report):
                raise ValueError('The binary verification receipt changed')
            traditional_build._verification(report, _path(engine, directory), lambda: _check(engine))
            count = len(traditional_build.BINARIES)
        else:
            expected_names = (takp_build.BINARIES if engine.profile == 'takp' else
                              ('world', 'zone', 'loginserver', 'shared_memory', 'ucs', 'eqlaunch', 'queryserv', 'export_client_files'))
            hashes = info.get('binaries')
            if not isinstance(hashes, dict) or set(hashes) != set(expected_names):
                raise ValueError('The build receipt does not fingerprint every required binary')
            for name in expected_names:
                if _digest(engine, _path(engine, directory + '/' + name)) != hashes[name]:
                    result.update(state='attention', detail='Binary differs from its build receipt: ' + name + '. Rebuild or review deployment.')
                    return result
            count = len(expected_names)
        result.update(state='current', detail=str(count) + ' binary hashes and build inputs match the imported source. Runtime compatibility remains subject to the existing launch checks.')
    except (OSError, ValueError, TypeError, KeyError) as error:
        _check(engine)
        result.update(state='review', detail=str(error))
    return result


def _compare(engine, source, destination, exclude=()):
    left = deployment.inventory(engine, source, exclude)
    right = deployment.inventory(engine, destination, exclude)
    counts = dict(new=0, changed=0, matching=0, runtime_only=0, errors=0)
    for name in set(left) | set(right):
        _check(engine)
        a, b = left.get(name), right.get(name)
        key = ('errors' if (a and a.get('error')) or (b and b.get('error')) else
               'runtime_only' if a is None else 'new' if b is None else
               'matching' if a['sha256'] == b['sha256'] else 'changed')
        counts[key] += 1
    return counts


def _comparison_row(key, counts):
    state = ('review' if counts['errors'] or not sum(counts[name] for name in ('new', 'changed', 'matching')) else
             'attention' if counts['new'] or counts['changed'] else 'current')
    detail = ('{new} missing, {changed} different, {matching} matching, '
              '{runtime_only} runtime-only, {errors} unreadable. ').format(**counts)
    detail += ('Review differences before synchronization; existing edits and runtime-only files are preserved.' if state != 'current' else
               'All imported source files match. Runtime-only files are retained; they are not declared obsolete.')
    return _row(key, state, detail, counts=counts)


def _custom_scripts(engine):
    try:
        root = quest_sync._source(engine)
        grouped = {}
        for group in quest_sync._groups(engine, root):
            key = 'lua_modules' if group['name'].startswith('lua_modules') else group['name']
            counts = _compare(engine, group['source'], group['destination'], group['exclude'])
            total = grouped.setdefault(key, {name: 0 for name in counts})
            for name, value in counts.items():
                total[name] += value
        return [_comparison_row(key, grouped[key]) for key in ('quests', 'plugins', 'lua_modules')]
    except (OSError, ValueError, KeyError, TypeError) as error:
        _check(engine)
        return [_row(key, 'review', str(error)) for key in ('quests', 'plugins', 'lua_modules')]


def _baseline_row(key, evidence, counts=None):
    row = _comparison_row(key, evidence['counts'] if counts is None else counts)
    source = evidence['source']
    label = source.get('repo') or ('archive ' + str(source['archive_sha256'])[:12] if source.get('archive_sha256') else 'recorded component import')
    if source.get('commit'):
        label += ' at ' + str(source['commit'])[:12]
    row['detail'] += ' Compared with ' + label + '; remote freshness is not checked. Server updates do not update this independent component.'
    row['baseline'] = {'tree_sha256': evidence['tree_sha256'], 'source': source}
    return row


def _independent_content(engine):
    rows, checked = [], {}
    if engine.profile == 'traditional':
        components = traditional_content.components(engine)
        for key in ('quests', 'plugins', 'lua_modules'):
            item = components[key]
            record = item.get('source') or {}
            embedded = key == 'quests' or item.get('origin') == 'quests'
            directory = 'server/quests' if embedded else item['path']
            try:
                if directory not in checked:
                    checked[directory] = content_baseline.inspect(engine, _path(engine, directory),
                        'quests' if embedded else key, record)
                evidence = checked[directory]
                row = _baseline_row(key, evidence, evidence['groups'][key] if embedded else evidence['counts'])
            except (OSError, ValueError, TypeError, KeyError) as error:
                _check(engine)
                row = _row(key, 'review' if item.get('imported') else 'attention', str(error))
            row['action']['target'] = 'content-git'
            rows.append(row)
    else:
        try:
            record = _json(engine, 'server/quests/' + takp_runtime.MARKER)
            evidence = content_baseline.inspect(engine, _path(engine, 'server/quests'), 'quests', record)
            rows = [_baseline_row(key, evidence, evidence['groups'][key]) for key in ('quests', 'lua_modules')]
        except (OSError, ValueError, TypeError, KeyError) as error:
            _check(engine)
            rows = [_row(key, 'review', str(error)) for key in ('quests', 'lua_modules')]
        for row in rows:
            row['action']['target'] = 'takp-content-kind'
        rows.insert(1, _row('plugins', 'not_applicable', 'TAKP uses the Lua helpers supplied with its quests; this profile does not deploy the Custom/Traditional Perl plugin component.'))
    return rows


def _assets(engine):
    try:
        root = _path(engine, 'sources/current')
        if engine.profile == 'traditional':
            pairs = traditional_content.assets_plan(root)
            target = _path(engine, 'server/assets')
        elif engine.profile == 'takp':
            pairs = {name: root / relative for name, relative in takp_runtime.ASSETS.items()}
            target = _path(engine, 'server/assets')
        else:
            root = root / 'Release-NMS-Server' if (root / 'Release-NMS-Server').is_dir() else root
            pairs = {}
            for path in root.rglob('*.conf'):
                _check(engine)
                if path.name.startswith(('patch_', 'opcodes', 'mail_opcodes', 'login_opcodes')):
                    if path.name in pairs:
                        raise ValueError('Duplicate source support filename; review configured destinations: ' + path.name)
                    pairs[path.name] = path
            target = _path(engine, 'server')
        if not pairs:
            raise ValueError('Imported source has no comparable support-file set; review its opcode/patch configuration')
        counts = dict(new=0, changed=0, matching=0, runtime_only=0, errors=0)
        for name, path in pairs.items():
            _check(engine)
            destination = deployment.confined(engine, target / name)
            if not destination.exists():
                counts['new'] += 1
            elif _digest(engine, path) == _digest(engine, destination):
                counts['matching'] += 1
            else:
                counts['changed'] += 1
        row = _comparison_row('assets', counts)
        if engine.profile != 'traditional':
            row['action']['target'] = 'source-update-deploy'
            row['detail'] += ' Existing support files may be preserved during deployment; review differences with the file manager before replacing them.'
        return row
    except (OSError, ValueError, KeyError, TypeError) as error:
        _check(engine)
        return _row('assets', 'review', str(error))


def _maps(engine):
    root = _path(engine, 'maps')
    if (engine.work / 'run/maps-import-pending.json').exists():
        row = _row('maps', 'attention', 'A map import did not finish. Review the import error and explicitly retry the selected maps; the previous baseline cannot certify a partial replacement.')
    else:
        try:
            marker = takp_runtime.MARKER if engine.profile == 'takp' else content_baseline.MAPS_MARKER
            record = _json(engine, 'maps/' + marker)
            evidence = content_baseline.inspect(engine, root, 'maps', record)
            row = _baseline_row('maps', evidence)
        except (OSError, ValueError, KeyError, TypeError) as error:
            _check(engine)
            present = root.is_dir() and ((root / 'base').is_dir() if engine.profile != 'takp' else any(root.glob('*.map')))
            row = _row('maps', 'review' if present else 'attention',
                       str(error) + '. Maps have an independent source; folder presence and a server revision cannot prove matching maps. Review or explicitly import the maps to establish a per-file baseline.')
    if engine.profile == 'takp':
        row['action']['target'] = 'takp-content-kind'
    return row


def _client_data(engine, deployed):
    try:
        record = _json(engine, 'logs/client-data-sync.json')
        hashes = record.get('sha256')
        expected = ('spells_us.txt', 'SkillCaps.txt') if engine.profile == 'takp' else ('spells_us.txt', 'dbstr_us.txt', 'SkillCaps.txt', 'BaseData.txt')
        if not isinstance(hashes, dict) or set(hashes) != set(expected) or not record.get('local_client_synced'):
            raise ValueError('No complete local client-data synchronization receipt; export and sync after reviewing database updates')
        roots = ['client/current'] if engine.profile == 'takp' else ['client/current', 'client/current/Resources']
        for name in expected:
            for root in ['server/export', *roots]:
                if _digest(engine, _path(engine, root + '/' + name)) != hashes[name]:
                    return _row('client_data', 'attention', name + ' differs from the last export. Review database changes, then export and sync client data.')
        receipt = _path(engine, 'logs/client-data-sync.json')
        if isinstance(deployed.get('built'), (int, float)) and receipt.stat().st_mtime < deployed['built']:
            return _row('client_data', 'attention', 'The client-data synchronization predates the deployed build. Review database updates, then export and sync.', local_export_matches=True)
        return _row('client_data', 'review', 'Local client files match the last export, but the export has no database-version fingerprint. Review database edits/migrations and export again when needed; matching files do not prove database freshness.', local_export_matches=True)
    except (OSError, ValueError, TypeError) as error:
        _check(engine)
        return _row('client_data', 'review', str(error))


def scan(engine, args=None):
    if engine.profile not in ('custom', 'traditional', 'takp'):
        raise ValueError('Unknown world profile')
    if (args or {}).get('__profile', engine.profile) != engine.profile:
        raise ValueError('World profile changed. Refresh before continuing.')
    _check(engine)
    rows, source = [], {}
    try:
        source = _source(engine)
        rows.append(_row('source', 'current', 'Imported checkout fingerprinted' +
                         (' at ' + source['revision'][:12] if source.get('revision') else ' (archive without a recorded commit)') +
                         '. This scan compares local imported source; use Check source update to inspect remote changes.'))
    except (OSError, ValueError, KeyError, TypeError) as error:
        _check(engine)
        rows.append(_row('source', 'review', str(error)))
    staged = _build(engine, 'server/bin.staged', source)
    deployed = _build(engine, 'server/bin', source)
    build = staged if staged['available'] else deployed
    rows.append(_row('build', build['state'], build['detail'] + (' (Using deployed-build evidence; no separate staged build.)' if not staged['available'] else '')))
    rows.append(_row('deployed', deployed['state'], deployed['detail']))
    if engine.profile == 'custom':
        rows.extend(_custom_scripts(engine))
    else:
        try:
            rows.extend(_independent_content(engine))
        except (OSError, ValueError, KeyError, TypeError) as error:
            _check(engine)
            rows.extend(_row(key, 'review', str(error)) for key in ('quests', 'plugins', 'lua_modules'))
    for key, action in (('maps', lambda: _maps(engine)), ('assets', lambda: _assets(engine)),
                        ('client_data', lambda: _client_data(engine, deployed))):
        try:
            rows.append(action())
        except (OSError, ValueError, KeyError, TypeError) as error:
            _check(engine)
            rows.append(_row(key, 'review', str(error)))
    rows.append(_row('lon', 'review' if engine.profile == 'custom' else 'not_applicable',
                     'Optional Custom feature. Use Verify data & card service to resolve the active data path, validate current cards and inspect service initialization; a previous import receipt alone is insufficient.'
                     if engine.profile == 'custom' else 'Legends of Norrath deployment applies only to the Custom world.'))
    rows.append(_row('database', 'review' if engine.config.get('database_imported') else 'attention',
                     'An imported database is present. Back up before updates, then review migration/startup results for this build. This file scan does not run or certify database migrations.'
                     if engine.config.get('database_imported') else 'Prepare this profile’s database before first launch. Source/content synchronization does not import or migrate a database.'))
    # Detect source replacement/edits during the scan without reading it twice.
    if source.get('stat_identity'):
        try:
            changed = (source_updates._stat_tree(_path(engine, 'sources/current')) != source['stat_identity']
                       or source['metadata'] != _json(engine, 'sources/current/trasc-source.json'))
        except (OSError, ValueError):
            changed = True
        if changed:
            source['changed_during_scan'] = True
            for identity in (staged, deployed):
                if identity['state'] == 'current':
                    identity.update(state='review', detail='Imported source changed during inspection; scan again.')
            for row in rows:
                if row['state'] == 'current':
                    row.update(state='review', detail='Imported source changed during this scan. Scan again before relying on this comparison.')
    _check(engine)
    return {'profile': engine.profile, 'scanned_at': time.time(), 'read_only': True,
            'scope': 'imported_source', 'source': source, 'staged': staged, 'deployed': deployed,
            'rows': rows, 'summary': {state: sum(row['state'] == state for row in rows) for state in STATES},
            'message': 'Snapshot of live files compared with imported source. Review independent content and database steps separately; no files were changed.'}
