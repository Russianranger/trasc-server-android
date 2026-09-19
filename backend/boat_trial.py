"""Reversible, single-zone ferry using the device-confirmed solid ship model.

No existing route NPC, player record, quest, privilege or client file is edited.
Owned content and its manifest commit together; cleanup rejects changed content.
"""
import json
import re
import secrets
import subprocess
import time
from player_data import ident, rows
from spire import fingerprint, literal, query_rows, ready, values

NAME = 'TRASC_Ferry'
ZONE = 'erudsxing'
ZONE_ID = 98
DOCK = dict(x=607.125, y=-1782.0, z=-39.5, heading=308.5)
REGISTRY = '_trasc_boat_trial'
AUDIT = '_trasc_boat_changes'
KEYS = {
    'npc_types': ['id'], 'spawngroup': ['id'], 'spawnentry': ['spawngroupID', 'npcID'],
    'spawn2': ['id'], 'grid': ['zoneid', 'id'], 'grid_entries': ['zoneid', 'gridid', 'number'],
    REGISTRY: ['id'], AUDIT: ['id'],
}
AUX = {'spawn2_disabled': ['spawn2_id'], 'respawn_times': ['id'],
       'zone_state_spawns': ['spawn2_id', 'spawngroup_id', 'npc_id']}
TTL = 1800


def layout(engine, table):
    info = rows(engine, 'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(table)+';')
    if not info:
        raise ValueError('The boat trial requires the '+table+' table')
    if info[0][0].lower() != 'innodb':
        raise ValueError(table+' must use InnoDB for a reversible boat trial')
    cols = rows(engine, 'SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA FROM information_schema.COLUMNS '
                'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(table)+' ORDER BY ORDINAL_POSITION;')
    key = [r[0] for r in rows(engine, 'SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() '
                'AND TABLE_NAME='+literal(table)+" AND INDEX_NAME='PRIMARY' ORDER BY SEQ_IN_INDEX;")]
    if table in KEYS and key != KEYS[table]:
        raise ValueError('Unsupported primary key for '+table)
    return dict(table=table, key=key, columns={r[0]: dict(type=r[1], nullable=r[2]=='YES', default=r[3], extra=r[4]) for r in cols})


def tables(engine):
    return {r[0] for r in rows(engine, 'SHOW TABLES;')}


def registry(engine, names):
    if REGISTRY not in names:
        return None
    s = layout(engine, REGISTRY)
    if not {'id', 'revision', 'manifest'} <= s['columns'].keys():
        raise ValueError('Unsupported boat ownership record')
    found = query_rows(engine, s, 'id=1', limit=2)
    if not found:
        return None
    v = values(found[0])
    try:
        m = json.loads(v['manifest'])
        assert m['version'] == 1 and set(m['ids']) == {'npc', 'group', 'spawn', 'grid'}
        assert all(type(n) is int and 0 < n < 2147483647 for n in m['ids'].values())
        assert set(m['rows']) == set(KEYS)-{REGISTRY, AUDIT}
    except (ValueError, KeyError, TypeError, AssertionError):
        raise ValueError('Boat ownership record is invalid; restore its database backup') from None
    return dict(raw=found[0], revision=v['revision'], manifest=m)


def selectors(ids):
    n, g, s, r = (ids[k] for k in ('npc', 'group', 'spawn', 'grid'))
    return {
        'npc_types': f'id={n}', 'spawngroup': f'id={g}',
        # Include unexpected additional references; removal must not orphan them.
        'spawnentry': f'(spawngroupID={g} OR npcID={n})',
        'spawn2': f'(id={s} OR spawngroupID={g} OR (zone={literal(ZONE)} AND pathgrid={r}))',
        'grid': f'zoneid={ZONE_ID} AND id={r}',
        'grid_entries': f'zoneid={ZONE_ID} AND gridid={r}',
        'spawn2_disabled': f'spawn2_id={s}', 'respawn_times': f'id={s}',
        'zone_state_spawns': f'(spawn2_id={s} OR spawngroup_id={g} OR npc_id={n})',
    }


def content(ids):
    n, g, s, r = (ids[k] for k in ('npc', 'group', 'spawn', 'grid'))
    # Size zero matches the successful #spawn's NPCType initialization. Explicit
    # flymode zero also matches that command; do not substitute route defaults.
    return {
        'npc_types': [dict(id=n, name=NAME, level=1, race=72, gender=0, bodytype=1,
            hp=10000, **{'class': 1}, texture=0, size=0, flymode=0, runspeed=0.5, walkspeed=0.5,
            npc_faction_id=0, npc_aggro=0, aggroradius=0, assistradius=0, loottable_id=0,
            merchant_id=0, npc_spells_id=0, npc_spells_effects_id=0, unique_spawn_by_name=1,
            spawn_limit=1, special_abilities='19,1^20,1^24,1', show_name=1, untargetable=0)],
        'spawngroup': [dict(id=g, name=NAME, spawn_limit=1, wp_spawns=0)],
        'spawnentry': [dict(spawngroupID=g, npcID=n, chance=100)],
        'spawn2': [dict(id=s, spawngroupID=g, zone=ZONE, version=0, **DOCK,
                       respawntime=60, variance=0, pathgrid=r, path_when_zone_idle=0)],
        'grid': [dict(id=r, zoneid=ZONE_ID, type=0, type2=1)],
        'grid_entries': [dict(gridid=r, zoneid=ZONE_ID, number=1, **DOCK, pause=90),
                         dict(gridid=r, zoneid=ZONE_ID, number=2, x=407.125, y=DOCK['y'],
                              z=DOCK['z'], heading=-1, pause=15)],
    }


def next_id(engine, table, where='1'):
    n = int(rows(engine, 'SELECT COALESCE(MAX(id),0)+1 FROM '+ident(table)+' WHERE '+where+';')[0][0])
    if not 0 < n < 2147483647:
        raise ValueError('No supported free ID for '+table)
    return n


def describe(active):
    return dict(active=active, name=NAME, zone=ZONE, dock=DOCK, dock_pause=90, far_pause=15,
        message=('Trial installed. Start the server and visit the Erud\'s Crossing dock.' if active else
                 'Install a single-zone ferry using the solid ship model.'))


def status(engine, args):
    ready(engine)
    own = registry(engine, tables(engine))
    return dict(describe(bool(own)), running=engine.server_running())


def inspect(engine, operation):
    ready(engine)
    if operation not in ('install', 'reset', 'remove'):
        raise ValueError('Choose install, reset or remove')
    names = tables(engine)
    own = registry(engine, names)
    if bool(own) != (operation != 'install'):
        raise ValueError('Trial is already installed' if own else 'No managed trial is installed')
    if not rows(engine, 'SELECT 1 FROM zone WHERE zoneidnumber=98 AND short_name='+literal(ZONE)+' LIMIT 1;'):
        raise ValueError('Erud\'s Crossing is not present in this database')
    ids = own['manifest']['ids'] if own else dict(npc=next_id(engine, 'npc_types'),
        group=next_id(engine, 'spawngroup'), spawn=next_id(engine, 'spawn2'),
        grid=next_id(engine, 'grid', 'zoneid=98'))
    intended = content(ids)
    shapes = {t: layout(engine, t) for t in intended}
    for t, records in intended.items():
        supplied = set(records[0])
        if not supplied <= shapes[t]['columns'].keys():
            raise ValueError('Unsupported '+t+' schema for the boat trial')
        for k, c in shapes[t]['columns'].items():
            if k not in supplied and not c['nullable'] and c['default']=='NULL' and not c['extra']:
                raise ValueError('The custom required field '+t+'.'+k+' needs a value; no trial installed')
    for t in (REGISTRY, AUDIT):
        if t in names:
            shapes[t] = layout(engine, t)
    for t, fields in AUX.items():
        if t in names:
            shapes[t] = layout(engine, t)
            if not set(fields) <= shapes[t]['columns'].keys():
                raise ValueError('Unsupported saved-state schema: '+t)
    where = selectors(ids)
    actual = {t: query_rows(engine, shapes[t], where[t], limit=1001) for t in intended}
    if own:
        if actual != own['manifest']['rows']:
            raise ValueError('Trial content or its references changed. Restore its backup or review the edits before removal/reset.')
    elif any(actual.values()) or rows(engine, 'SELECT 1 FROM npc_types WHERE name='+literal(NAME)+' LIMIT 1;') or rows(engine, 'SELECT 1 FROM spawngroup WHERE name='+literal(NAME)+' LIMIT 1;'):
        raise ValueError('The trial name or allocated IDs are already in use; refresh the preview')
    return dict(ids=ids, shapes=shapes, own=own, actual=actual,
                auxiliary={t: int(rows(engine, 'SELECT COUNT(*) FROM '+ident(t)+' WHERE '+where[t]+';')[0][0]) for t in AUX if t in names})


def preview(engine, args):
    from engine import atomic_json
    operation = args.get('action')
    state = inspect(engine, operation)
    token = secrets.token_hex(24)
    document = dict(action=operation, database=engine.config['database'], created=time.time(), state=state)
    atomic_json(engine.work/'run/boat-previews'/(token+'.json'), document)
    summaries = {
        'install': 'Add one solid ferry, one spawn and a two-stop route in Erud\'s Crossing. The ferry pauses 90 seconds at the dock and 15 seconds offshore.',
        'reset': 'Return the managed ferry to its boarding position on the next zone load and restart its dock pause.',
        'remove': 'Remove only the managed ferry, its route and its saved spawn state.',
    }
    return dict(token=token, action=operation, summary=summaries[operation], dock=DOCK,
        message='Stop the server before saving. A full database backup is made first. Existing route boats and player data are preserved.',
        saved_rows=state['auxiliary'], running=engine.server_running())


def raw_match(raw):
    return ' AND '.join('BINARY '+ident(k)+' <=> '+('NULL' if v is None else "X'"+v+"'") for k, v in raw.items())


def json_snapshot(shape, where):
    fields = ','.join(literal(k)+',HEX(CAST('+ident(k)+' AS BINARY))' for k in shape['columns'])
    order = ','.join(ident(k) for k in shape['key'])
    return '(SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT('+fields+') ORDER BY '+order+'),JSON_ARRAY()) FROM '+ident(shape['table'])+' WHERE '+where+')'


def apply(engine, args):
    ready(engine, writing=True)
    token = args.get('token', '')
    if not isinstance(token, str) or not re.fullmatch('[0-9a-f]{48}', token):
        raise ValueError('Review a boat preview first')
    path = engine.work/'run/boat-previews'/(token+'.json')
    if not path.is_file() or path.is_symlink():
        raise ValueError('Preview is missing or already used; preview again')
    p = json.loads(path.read_text())
    if p['database'] != engine.config['database'] or time.time()-p['created'] > TTL:
        raise ValueError('Preview expired or the database changed; preview again')
    state = inspect(engine, p['action'])
    # Transient saved positions may change before the server stops; content and
    # ownership must not. Cleanup remains confined to the owned identifiers.
    stable = lambda s: {k: v for k, v in s.items() if k != 'auxiliary'}
    if fingerprint(stable(state)) != fingerprint(stable(p['state'])):
        raise ValueError('Trial changed after preview; preview again')
    backup = engine.backup_database({})['file']
    ready(engine, writing=True)
    engine.check_cancel()
    engine.mysql('CREATE TABLE IF NOT EXISTS '+ident(REGISTRY)+' (id tinyint PRIMARY KEY, revision char(48) NOT NULL, manifest longtext NOT NULL) ENGINE=InnoDB;'
        'CREATE TABLE IF NOT EXISTS '+ident(AUDIT)+' (id char(48) PRIMARY KEY, action varchar(16) NOT NULL, created_at datetime(6) NOT NULL, backup_file text NOT NULL, payload longtext NOT NULL) ENGINE=InnoDB;')
    for t in (REGISTRY, AUDIT):
        layout(engine, t)
    guard = lambda condition: 'INSERT INTO `_trasc_boat_guard` SELECT 1 WHERE NOT ('+condition+');'
    sql = ["SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';",
           'SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;',
           'CREATE TEMPORARY TABLE `_trasc_boat_guard` (id int PRIMARY KEY) ENGINE=InnoDB;',
           'INSERT INTO `_trasc_boat_guard` VALUES (1);', 'START TRANSACTION;']
    own, ids = state['own'], state['ids']
    where = selectors(ids)
    if own:
        sql.append(guard('(SELECT COUNT(*) FROM '+ident(REGISTRY)+' WHERE id=1 AND '+raw_match(own['raw'])+')=1'))
    else:
        sql.append(guard('(SELECT COUNT(*) FROM '+ident(REGISTRY)+' WHERE id=1)=0'))
        for t in ('npc_types', 'spawngroup'):
            sql.append(guard('(SELECT COUNT(*) FROM '+ident(t)+' WHERE name='+literal(NAME)+')=0'))
    for t, actual in state['actual'].items():
        sql.append(guard('(SELECT COUNT(*) FROM '+ident(t)+' WHERE '+where[t]+')='+str(len(actual))))
        if actual:
            matches = ' OR '.join('('+raw_match(r)+')' for r in actual)
            sql.append(guard('(SELECT COUNT(*) FROM '+ident(t)+' WHERE ('+where[t]+') AND ('+matches+'))='+str(len(actual))))
    if p['action'] == 'install':
        for t, records in content(ids).items():
            for record in records:
                sql.append('INSERT INTO '+ident(t)+' ('+','.join(ident(k) for k in record)+') VALUES ('+','.join(literal(v) for v in record.values())+');')
        manifest = "JSON_OBJECT('version',1,'ids',JSON_EXTRACT("+literal(json.dumps(ids))+",'$'),'rows',JSON_OBJECT("+','.join(literal(t)+','+json_snapshot(state['shapes'][t], where[t]) for t in content(ids))+'))'
        sql.append('INSERT INTO '+ident(REGISTRY)+' VALUES (1,'+literal(token)+','+manifest+');')
    else:
        for t in state['auxiliary']:
            sql.append('DELETE FROM '+ident(t)+' WHERE '+where[t]+';')
        if p['action'] == 'remove':
            for t in ('spawnentry', 'spawn2', 'grid_entries', 'grid', 'spawngroup', 'npc_types'):
                sql.append('DELETE FROM '+ident(t)+' WHERE '+where[t]+';')
            sql.append('DELETE FROM '+ident(REGISTRY)+' WHERE id=1;')
        else:
            sql.append('UPDATE '+ident(REGISTRY)+' SET revision='+literal(token)+' WHERE id=1;')
    payload = dict(ids=ids, action=p['action'], zone=ZONE, dock=DOCK, saved_rows=state['auxiliary'])
    sql.append('INSERT INTO '+ident(AUDIT)+' VALUES ('+literal(token)+','+literal(p['action'])+',UTC_TIMESTAMP(6),'+literal(backup)+','+literal(json.dumps(payload))+');')
    sql.append('COMMIT;')
    try:
        engine.mysql(''.join(sql), timeout=120)
    except (ValueError, TimeoutError, subprocess.TimeoutExpired) as e:
        if not rows(engine, 'SELECT id FROM '+ident(AUDIT)+' WHERE id='+literal(token)+';'):
            raise ValueError('Boat changes did not commit. Content changed or validation failed; preview again. '+str(e)) from e
    path.unlink(missing_ok=True)
    engine.log('Boat trial '+p['action']+'; audit '+token+'; backup '+backup)
    return dict(describe(p['action'] != 'remove'), action=p['action'], backup=backup,
                message={'install': 'Ferry trial installed. Start the server and visit the Erud\'s Crossing dock.',
                         'reset': 'Ferry reset. It will begin at the dock on the next zone load.',
                         'remove': 'Ferry trial removed. Existing routes and player data are preserved.'}[p['action']])


def dispatch(engine, operation, args):
    return {'boat_trial_status': status, 'boat_trial_preview': preview, 'boat_trial_apply': apply}[operation](engine, args)
