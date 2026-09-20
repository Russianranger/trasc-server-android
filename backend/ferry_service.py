"""Backed-up, owned installation of the Qeynos–Erudin ferry service."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
import boat_trial as trial
import ferry_route as route
import server_ferry
from player_data import ident, rows
from spire import ready, literal, query_rows, values, fingerprint

REGISTRY = '_trasc_ferry_service'
AUDIT = '_trasc_ferry_changes'
OWNED = ('npc_types', 'spawngroup', 'spawnentry', 'spawn2', 'launcher_zones', 'zone')
ZONES = (1, 98, 24)
TTL = 1800


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def own_record(engine, names):
    if REGISTRY not in names:
        return None
    shape = trial.layout(engine, REGISTRY)
    if shape['key'] != ['id'] or not {'id','revision','manifest'} <= shape['columns'].keys():
        raise ValueError('Unsupported ferry ownership table')
    found = query_rows(engine, shape, 'id=1', limit=2)
    if not found:
        return None
    try:
        m = json.loads(values(found[0])['manifest'])
        assert m['version'] == 1 and re.fullmatch('[0-9a-f]{24}',m['installation'])
        assert set(m['rows']) == set(OWNED) and set(m['before']) == set(OWNED)
        assert set(m['ids']) == {'ship','controllers','groups','spawns'}
        assert type(m['ids']['ship']) is int and 0 < m['ids']['ship'] < 2147483647
        for key in ('controllers','groups','spawns'):
            assert set(m['ids'][key]) == {str(n) for n in ZONES}
            assert all(type(n) is int and 0<n<2147483647 for n in m['ids'][key].values())
        assert set(m['files']) == set(files_for(m['ids'], m['installation']))
    except (AssertionError, KeyError, ValueError, TypeError):
        raise ValueError('Invalid ferry ownership record; restore its database backup') from None
    return dict(raw=found[0], manifest=m)


def selectors(ids):
    ns = ','.join(map(str,[ids['ship'],*ids['controllers'].values()]))
    gs = ','.join(map(str,ids['groups'].values()))
    ss = ','.join(map(str,ids['spawns'].values()))
    return dict(npc_types='id IN ('+ns+')', spawngroup='id IN ('+gs+')',
        spawnentry='(spawngroupID IN ('+gs+') OR npcID IN ('+ns+'))',
        spawn2='(id IN ('+ss+') OR spawngroupID IN ('+gs+'))',
        launcher_zones="launcher='trasc' AND zone IN ('qeynos','erudsxing','erudnext')",
        zone='zoneidnumber IN (1,98,24) AND version=0',
        zone_state_spawns='(npc_id IN ('+ns+') OR spawngroup_id IN ('+gs+') OR spawn2_id IN ('+ss+'))',
        spawn2_disabled='spawn2_id IN ('+ss+')', respawn_times='id IN ('+ss+')')


def allocated(engine):
    n=trial.next_id(engine,'npc_types')
    g=trial.next_id(engine,'spawngroup');s=trial.next_id(engine,'spawn2')
    if max(n+3,g+2,s+2)>=2147483647:
        raise ValueError('No supported free IDs for the ferry')
    return dict(ship=n,controllers={str(z):n+i+1 for i,z in enumerate(ZONES)},
        groups={str(z):g+i for i,z in enumerate(ZONES)},spawns={str(z):s+i for i,z in enumerate(ZONES)})


def content(ids):
    ship=trial.content(dict(npc=ids['ship'],group=1,spawn=1,grid=1))['npc_types'][0]
    ship.update(name=route.NAME,runspeed=route.HARBOR_SPEED,walkspeed=route.HARBOR_SPEED)
    result=dict(npc_types=[ship],spawngroup=[],spawnentry=[],spawn2=[])
    for zone in ZONES:
        key=str(zone);name='TRASC_Ferry_Control_'+route.ZONES[zone]
        controller=dict(ship,id=ids['controllers'][key],name=name,race=240,gender=2,
                        bodytype=11,size=1,runspeed=0,walkspeed=0,show_name=0,untargetable=1)
        result['npc_types'].append(controller)
        result['spawngroup'].append(dict(id=ids['groups'][key],name=name,spawn_limit=1,wp_spawns=0))
        result['spawnentry'].append(dict(spawngroupID=ids['groups'][key],npcID=controller['id'],chance=100))
        x,y,z,h=route.SHORE[zone]
        result['spawn2'].append(dict(id=ids['spawns'][key],spawngroupID=ids['groups'][key],
            zone=route.ZONES[zone],version=0,x=x,y=y,z=z,heading=h,respawntime=60,
            variance=0,pathgrid=0,path_when_zone_idle=1))
    return result


def files_for(ids, installation):
    cfg=json.dumps(route.config(ids,installation),separators=(',',':'))
    result={
        'server/quests/lua_modules/trasc_ferry.lua':Path(__file__).with_suffix('.lua').read_text(),
        'server/quests/lua_modules/trasc_ferry_config.lua':
            'return require("json").decode([=['+cfg+']=])\n',
    }
    for zone in ZONES:
        result[f'server/quests/{route.ZONES[zone]}/{ids["controllers"][str(zone)]}.lua']=(
            'local ferry=require("trasc_ferry")\n'
            f'function event_spawn(e) ferry.spawn(e,{zone}) end\n'
            f'function event_timer(e) ferry.tick(e,{zone}) end\n')
    return result


def safe_file(engine, path):
    from engine import safe_path
    return safe_path(engine.work,path)


def file_state(engine, paths):
    result={}
    for name in paths:
        p=safe_file(engine,name)
        if p.exists() and not p.is_file():
            raise ValueError('Ferry quest path is not a regular file: '+name)
        result[name]=digest(p) if p.exists() else None
    return result


def namespace(installation):
    return 'trasc_ferry_'+installation


def bucket_where(installation):
    # Escape LIKE underscores; all namespace characters are generated, not input.
    return "BINARY `key` LIKE BINARY "+literal(namespace(installation).replace('_','\\_')+'\\_%')


def bucket(engine,key):
    found=rows(engine,'SELECT value FROM data_buckets WHERE BINARY `key`=BINARY '+literal(key)+' AND character_id=0 AND account_id=0 AND npc_id=0 AND bot_id=0 AND zone_id=0 AND instance_id=0;')
    return json.loads(found[0][0]) if found else None


def state_sql(installation, state):
    key=namespace(installation)+'_state'
    return ('DELETE FROM data_buckets WHERE BINARY `key`=BINARY '+literal(key)+';'
            'INSERT INTO data_buckets (`key`,value,expires) VALUES ('+literal(key)+','+literal(json.dumps(state))+',0);')


def initial_state(installation):
    p=route.phases()[0]['points'][7]
    return dict(version=1,installation=installation,epoch=secrets.token_hex(12),
        phase=1,point=8,status='pause',sequence=0,
        wait_until=int(time.time())+route.PORT_PAUSE,updated=int(time.time()),riders=[],history=[],
        pose=dict(x=p['x'],y=p['y'],z=p['z'],h=0))


def skiff_state(engine, own):
    """Own only Erudin version-zero skiff spawn disables, preserving prior rows."""
    old=own['manifest'].get('skiffs') if own else None
    if old:
        spawn_ids=[int(values(r)['id']) for r in old['spawns']]
        npc_ids=old['npc_ids']
    else:
        found=rows(engine,"SELECT DISTINCT s.id,n.id FROM spawn2 s JOIN spawnentry e ON e.spawngroupID=s.spawngroupID JOIN npc_types n ON n.id=e.npcID WHERE s.zone='erudnext' AND s.version=0 AND n.race=73;")
        spawn_ids=sorted({int(r[0]) for r in found});npc_ids=sorted({int(r[1]) for r in found})
    where='id IN ('+','.join(map(str,spawn_ids))+')' if spawn_ids else '1=0'
    disabled_where='instance_id=0 AND spawn2_id IN ('+','.join(map(str,spawn_ids))+')' if spawn_ids else '1=0'
    shapes={t:trial.layout(engine,t) for t in ('spawn2','spawn2_disabled')}
    spawns=query_rows(engine,shapes['spawn2'],where,limit=1001)
    disabled=query_rows(engine,shapes['spawn2_disabled'],disabled_where,limit=1001)
    if old and (spawns!=old['spawns'] or disabled!=old['disabled']):
        raise ValueError('Managed Erudin skiff spawns changed; review those edits before changing the route')
    if spawn_ids:
        # Never disable a mixed spawn group that can also produce unrelated NPCs.
        mixed=rows(engine,'SELECT 1 FROM spawnentry e LEFT JOIN npc_types n ON n.id=e.npcID WHERE e.spawngroupID IN (SELECT spawngroupID FROM spawn2 WHERE '+where+') AND (n.id IS NULL OR n.race<>73) LIMIT 1;')
        if mixed:raise ValueError('An Erudin skiff shares a spawn group with other NPCs; no spawns were disabled')
    return dict(spawns=spawns,disabled=disabled,before=old['before'] if old else disabled,
                npc_ids=npc_ids,where=where,disabled_where=disabled_where)


def skiff_cleanup(skiffs, tables):
    if not skiffs or not skiffs['npc_ids'] or 'zone_state_spawns' not in tables:return ''
    return 'DELETE FROM zone_state_spawns WHERE zone_id=24 AND npc_id IN ('+','.join(map(str,skiffs['npc_ids']))+');'


def inspect(engine,action,installation=None):
    ready(engine)
    if action not in ('install','update','reset','remove'):
        raise ValueError('Choose install, update, reset or remove')
    names=trial.tables(engine);own=own_record(engine,names)
    if bool(own)!=(action!='install'):
        raise ValueError('Route is already installed' if own else 'No managed route is installed')
    if action=='install' and trial.registry(engine,names):
        raise ValueError('Remove the completed Erud\'s Crossing trial first using its Preview removal button')
    if action!='remove' and not server_ferry.deployed(engine):
        raise ValueError('Build and deploy the server with this app version before installing/resetting the route')
    ids=own['manifest']['ids'] if own else allocated(engine)
    installation=own['manifest']['installation'] if own else (installation or secrets.token_hex(12))
    if not re.fullmatch('[0-9a-f]{24}',installation): raise ValueError('Invalid installation identity')
    where=selectors(ids);shapes={t:trial.layout(engine,t) for t in OWNED}
    shapes['data_buckets']=trial.layout(engine,'data_buckets')
    if not {'key','value','expires','character_id','account_id','npc_id','bot_id','zone_id','instance_id'} <= shapes['data_buckets']['columns'].keys():
        raise ValueError('Server database needs its normal schema update before route installation')
    for t in (REGISTRY,AUDIT):
        if t in names:shapes[t]=trial.layout(engine,t)
    actual={t:query_rows(engine,shapes[t],where[t],limit=1001) for t in OWNED}
    if len(actual['zone'])!=3 or any(values(r)['short_name']!=route.ZONES[int(values(r)['zoneidnumber'])] for r in actual['zone']):
        raise ValueError('Qeynos, Erud\'s Crossing and Erudin version-zero zones are required')
    if 'idle_when_empty' not in shapes['zone']['columns']:
        raise ValueError('Unsupported zone idle settings schema')
    intended=files_for(ids,installation);files=file_state(engine,intended)
    if own:
        if actual!=own['manifest']['rows'] or files!=own['manifest']['files']:
            raise ValueError('Managed route content, references or quests changed; review those edits before reset/removal')
    else:
        if any(actual[t] for t in ('npc_types','spawngroup','spawnentry','spawn2')) or any(files.values()):
            raise ValueError('The route IDs or reserved quest files are already in use')
        if rows(engine,"SELECT 1 FROM npc_types WHERE name LIKE 'TRASC\\_Voyager%' OR name LIKE 'TRASC\\_Ferry\\_Control\\_%' LIMIT 1;"):
            raise ValueError('Managed route NPC names are already in use')
        if not safe_file(engine,'server/quests/lua_modules/json.lua').is_file():
            raise ValueError('Deploy the imported server quests before installing the route')
        for t,records in content(ids).items():
            if not set(records[0]) <= shapes[t]['columns'].keys():
                raise ValueError('Unsupported ferry content schema: '+t)
    auxiliary={}
    for t,required in trial.AUX.items():
        if t in names:
            shapes[t]=trial.layout(engine,t)
            if not set(required)<=shapes[t]['columns'].keys():raise ValueError('Unsupported saved state: '+t)
            auxiliary[t]=int(rows(engine,'SELECT COUNT(*) FROM '+ident(t)+' WHERE '+where[t]+';')[0][0])
    if action=='remove' and rows(engine,'SELECT 1 FROM data_buckets WHERE '+bucket_where(installation)+" AND BINARY `key`<>BINARY "+literal(namespace(installation)+'_state')+' LIMIT 1;'):
        raise ValueError('A passenger has a saved ferry position. Start the server, log that character in and disembark before removing the route. Reset can recover interrupted riders to the dock.')
    skiffs=skiff_state(engine,own) if action in ('install','update') or (own and own['manifest'].get('skiffs')) else None
    return dict(ids=ids,installation=installation,own=own,shapes=shapes,actual=actual,files=files,auxiliary=auxiliary,skiffs=skiffs)


def status(engine,args):
    ready(engine);recover(engine)
    own=own_record(engine,trial.tables(engine))
    return dict(active=bool(own),server_ready=server_ferry.deployed(engine),running=engine.server_running(),
        update_available=bool(own and own['manifest'].get('route_revision',1)<2),
        route=bucket(engine,namespace(own['manifest']['installation'])+'_state') if own else None,
        message='Qeynos–Erudin service installed.' if own else 'Install a ferry through Erud\'s Crossing, with passenger handoff at each boundary.')


def preview(engine,args):
    from engine import atomic_json
    recover(engine)
    action=args.get('action');state=inspect(engine,action)
    token=secrets.token_hex(24)
    atomic_json(engine.work/'run/ferry-previews'/(token+'.json'),dict(action=action,database=engine.config['database'],created=time.time(),state=state))
    summaries={
        'install':'Install one Qeynos–Erudin service via Erud\'s Crossing, three route controllers and owned quests. Keep these three zones running for coordinated transfers.',
        'update':'Update the installed route: offshore Erudin departure, 180-second port stops, speed 0.60, and disable Erudin skiff spawns. Restart at Qeynos; retain interrupted-rider recovery.',
        'reset':'Restart the route at Qeynos. Interrupted passengers are recovered to their zone\'s dock on login.',
        'remove':'Remove the managed service and quests, and restore the previous zone-idle and launcher settings.',
    }
    return dict(token=token,action=action,summary=summaries[action],running=engine.server_running(),
        message='Stop the server before saving. A full database backup and quest-file journal are created first. Erudin skiff spawns affected: '+str(len((state['skiffs'] or {}).get('spawns',[])))+'. Removing this service restores their previous spawn settings. Ordinary zone lines are preserved.')


def recover(engine):
    """Complete or roll back the file half of an interrupted DB/file operation."""
    journal=engine.work/'run/ferry-change.json'
    if not journal.exists():return
    record=json.loads(journal.read_text());names=trial.tables(engine)
    committed=AUDIT in names and bool(rows(engine,'SELECT id FROM '+ident(AUDIT)+' WHERE id='+literal(record['token'])+';'))
    for item in record['files']:
        p=safe_file(engine,item['path']);current=digest(p) if p.is_file() else None
        expected=item['after'] if committed else item['before']
        if current==expected:continue
        if committed or current!=item['after']:
            raise ValueError('Interrupted ferry operation found an edited quest file: '+item['path'])
        if expected is None:p.unlink(missing_ok=True)
        else:
            saved=safe_file(engine,item['saved'])
            if digest(saved)!=expected:raise ValueError('Ferry quest backup checksum failed')
            p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(saved,p)
    journal.unlink()


def change_files(engine,token,before,after):
    from engine import atomic_json
    entries=[]
    for name,old in before.items():
        p=safe_file(engine,name);saved=engine.work/'backups/ferry-quests'/token/name
        if old:
            saved.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,saved)
        new=hashlib.sha256(after[name].encode()).hexdigest() if name in after else None
        entries.append(dict(path=name,before=old,after=new,saved=str(saved.relative_to(engine.work))))
    atomic_json(engine.work/'run/ferry-change.json',dict(token=token,files=entries))
    for item in entries:
        p=safe_file(engine,item['path'])
        if item['after'] is None:p.unlink(missing_ok=True)
        else:
            p.parent.mkdir(parents=True,exist_ok=True)
            temp=p.with_name(p.name+'.'+token+'.tmp')
            with temp.open('x') as f:f.write(after[item['path']])
            temp.replace(p)


def apply(engine,args):
    ready(engine,writing=True);recover(engine)
    token=args.get('token','')
    if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{48}',token):raise ValueError('Review a route preview first')
    path=engine.work/'run/ferry-previews'/(token+'.json')
    if path.is_symlink() or not path.is_file():raise ValueError('Preview is missing or already used')
    p=json.loads(path.read_text())
    if p['database']!=engine.config['database'] or time.time()-p['created']>TTL:raise ValueError('Preview expired; preview again')
    s=inspect(engine,p['action'],p['state']['installation'])
    stable=lambda v:{k:value for k,value in v.items() if k!='auxiliary'}
    if fingerprint(stable(s))!=fingerprint(stable(p['state'])):raise ValueError('Route changed after preview')
    backup=engine.backup_database({})['file']
    ready(engine,writing=True);engine.check_cancel()
    if file_state(engine,s['files'])!=s['files']:raise ValueError('Route quest files changed during backup')
    engine.mysql('CREATE TABLE IF NOT EXISTS '+ident(REGISTRY)+' (id tinyint PRIMARY KEY,revision char(48) NOT NULL,manifest longtext NOT NULL) ENGINE=InnoDB;'
        'CREATE TABLE IF NOT EXISTS '+ident(AUDIT)+' (id char(48) PRIMARY KEY,action varchar(16) NOT NULL,created_at datetime(6) NOT NULL,backup_file text NOT NULL,payload longtext NOT NULL) ENGINE=InnoDB;')
    for t in (REGISTRY,AUDIT):trial.layout(engine,t)
    guard=lambda test:'INSERT INTO `_trasc_ferry_guard` SELECT 1 WHERE NOT ('+test+');'
    sql=["SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';",'SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;',
         'CREATE TEMPORARY TABLE `_trasc_ferry_guard` (id int PRIMARY KEY) ENGINE=InnoDB;',
         'INSERT INTO `_trasc_ferry_guard` VALUES (1);','START TRANSACTION;']
    own=s['own'];ids=s['ids'];where=selectors(ids);installation=s['installation']
    if own:sql.append(guard('(SELECT COUNT(*) FROM '+ident(REGISTRY)+' WHERE id=1 AND '+trial.raw_match(own['raw'])+')=1'))
    else:sql.append(guard('(SELECT COUNT(*) FROM '+ident(REGISTRY)+' WHERE id=1)=0'))
    for t,actual in s['actual'].items():
        sql.append(guard('(SELECT COUNT(*) FROM '+ident(t)+' WHERE '+where[t]+')='+str(len(actual))))
        if actual:
            sql.append(guard('(SELECT COUNT(*) FROM '+ident(t)+' WHERE ('+where[t]+') AND ('+' OR '.join('('+trial.raw_match(r)+')' for r in actual)+'))='+str(len(actual))))
    action=p['action'];after=files_for(ids,installation) if action in ('install','update') else {}
    skiffs=s['skiffs']
    if skiffs:
        for table,key,condition in [('spawn2','spawns',skiffs['where']),('spawn2_disabled','disabled',skiffs['disabled_where'])]:
            actual=skiffs[key]
            sql.append(guard('(SELECT COUNT(*) FROM '+ident(table)+' WHERE '+condition+')='+str(len(actual))))
            if actual:sql.append(guard('(SELECT COUNT(*) FROM '+ident(table)+' WHERE ('+condition+') AND ('+' OR '.join('('+trial.raw_match(r)+')' for r in actual)+'))='+str(len(actual))))
        if action in ('install','update'):
            for raw in skiffs['spawns']:
                spawn_id=int(values(raw)['id'])
                if any(int(values(r)['spawn2_id'])==spawn_id for r in skiffs['disabled']):
                    sql.append('UPDATE spawn2_disabled SET disabled=1 WHERE instance_id=0 AND spawn2_id='+str(spawn_id)+';')
                else:sql.append('INSERT INTO spawn2_disabled (spawn2_id,instance_id,disabled) VALUES ('+str(spawn_id)+',0,1);')
        elif action=='remove':
            sql.append('DELETE FROM spawn2_disabled WHERE '+skiffs['disabled_where']+';')
            for raw in skiffs['before']:
                r=values(raw)
                sql.append('INSERT INTO spawn2_disabled ('+','.join(ident(k) for k in r)+') VALUES ('+','.join(literal(v) for v in r.values())+');')
        sql.append(skiff_cleanup(skiffs,s['auxiliary']))
    if action=='install':
        sql.append(guard("(SELECT COUNT(*) FROM npc_types WHERE name LIKE 'TRASC\\_Voyager%' OR name LIKE 'TRASC\\_Ferry\\_Control\\_%')=0"))
        for t,records in content(ids).items():
            for r in records:
                sql.append('INSERT INTO '+ident(t)+' ('+','.join(ident(k) for k in r)+') VALUES ('+','.join(literal(v) for v in r.values())+');')
        existing={values(r)['zone'] for r in s['actual']['launcher_zones']}
        for zone in route.ZONES.values():
            if zone not in existing:sql.append("INSERT INTO launcher_zones (launcher,zone,port) VALUES ('trasc',"+literal(zone)+',0);')
        sql.append('UPDATE zone SET idle_when_empty=0 WHERE '+where['zone']+';')
        m=dict(version=1,route_revision=2,installation=installation,ids=ids,before=s['actual'],
               files={name:hashlib.sha256(data.encode()).hexdigest() for name,data in after.items()})
        m['skiffs']=skiffs
        manifest="JSON_SET("+literal(json.dumps(m))+",'$.rows',JSON_OBJECT("+','.join(literal(t)+','+trial.json_snapshot(s['shapes'][t],where[t]) for t in OWNED)+'))'
        if skiffs:manifest="JSON_SET("+manifest+",'$.skiffs.disabled',"+trial.json_snapshot(trial.layout(engine,'spawn2_disabled'),skiffs['disabled_where'])+')'
        sql.append('INSERT INTO '+ident(REGISTRY)+' VALUES (1,'+literal(token)+','+manifest+');')
    else:
        for t in s['auxiliary']:sql.append('DELETE FROM '+ident(t)+' WHERE '+where[t]+';')
        if action=='remove':
            sql.append(guard('(SELECT COUNT(*) FROM data_buckets WHERE '+bucket_where(installation)+' AND BINARY `key`<>BINARY '+literal(namespace(installation)+'_state')+')=0'))
            for t in ('spawnentry','spawn2','spawngroup','npc_types'):sql.append('DELETE FROM '+ident(t)+' WHERE '+where[t]+';')
            old_zones={values(r)['zone'] for r in own['manifest']['before']['launcher_zones']}
            for zone in route.ZONES.values():
                if zone not in old_zones:sql.append("DELETE FROM launcher_zones WHERE launcher='trasc' AND zone="+literal(zone)+';')
            for raw in own['manifest']['before']['zone']:
                r=values(raw)
                sql.append('UPDATE zone SET idle_when_empty='+literal(r['idle_when_empty'])+' WHERE id='+literal(r['id'])+';')
            sql.append('DELETE FROM data_buckets WHERE '+bucket_where(installation)+';')
            sql.append('DELETE FROM '+ident(REGISTRY)+' WHERE id=1;')
        elif action=='update':
            sql.append('UPDATE npc_types SET runspeed='+literal(route.HARBOR_SPEED)+',walkspeed='+literal(route.HARBOR_SPEED)+' WHERE id='+str(ids['ship'])+';')
            m=dict(own['manifest'],route_revision=2,skiffs=skiffs,
                files={name:hashlib.sha256(data.encode()).hexdigest() for name,data in after.items()})
            manifest="JSON_SET("+literal(json.dumps(m))+",'$.rows',JSON_OBJECT("+','.join(literal(t)+','+trial.json_snapshot(s['shapes'][t],where[t]) for t in OWNED)+'))'
            if skiffs:manifest="JSON_SET("+manifest+",'$.skiffs.disabled',"+trial.json_snapshot(trial.layout(engine,'spawn2_disabled'),skiffs['disabled_where'])+')'
            sql.append('UPDATE '+ident(REGISTRY)+' SET revision='+literal(token)+',manifest='+manifest+' WHERE id=1;')
        else:sql.append('UPDATE '+ident(REGISTRY)+' SET revision='+literal(token)+' WHERE id=1;')
    if action!='remove':sql.append(state_sql(installation,initial_state(installation)))
    sql.append('INSERT INTO '+ident(AUDIT)+' VALUES ('+literal(token)+','+literal(action)+',UTC_TIMESTAMP(6),'+literal(backup)+','+literal(json.dumps(dict(ids=ids,installation=installation)))+');COMMIT;')
    try:
        if action!='reset':change_files(engine,token,s['files'],after)
        engine.mysql(''.join(sql),timeout=120)
    except (ValueError,OSError,TimeoutError,subprocess.TimeoutExpired) as error:
        committed=bool(rows(engine,'SELECT id FROM '+ident(AUDIT)+' WHERE id='+literal(token)+';'))
        recover(engine)
        if not committed:raise ValueError('Ferry change did not commit; preview again. '+str(error)) from error
    recover(engine);path.unlink(missing_ok=True)
    engine.log('Ferry service '+action+'; audit '+token+'; backup '+backup)
    return dict(active=action!='remove',backup=backup,action=action,
        message={'install':'Qeynos–Erudin service installed. Start the server and board TRASC_Voyager at South Qeynos.',
                 'update':'Route updated: offshore Erudin departure, 180-second port stops, speed 0.60, and Erudin skiffs disabled. Start the server at Qeynos.',
                 'reset':'Route reset to Qeynos. Interrupted riders will return to their local dock.',
                 'remove':'Route removed; previous launcher and zone-idle settings restored.'}[action])


def boot(engine):
    """Start each server session from one known ship and retain rider recovery."""
    recover(engine);own=own_record(engine,trial.tables(engine))
    if not own:return
    s=inspect(engine,'reset');where=selectors(s['ids'])
    cleanup=''.join('DELETE FROM '+ident(t)+' WHERE '+where[t]+';' for t in s['auxiliary'])
    cleanup+=skiff_cleanup(s['skiffs'],s['auxiliary'])
    engine.mysql('START TRANSACTION;'+cleanup+state_sql(s['installation'],initial_state(s['installation']))+'COMMIT;')


def diagnostics(engine,args):
    """A read-only DB snapshot for the native Android export path."""
    from engine import atomic_json
    own=own_record(engine,trial.tables(engine)) if engine.config.get('database_imported') else None
    snapshot=dict(captured_utc=time.time(),active=bool(own),
        route=bucket(engine,namespace(own['manifest']['installation'])+'_state') if own else None)
    atomic_json(engine.work/'logs/ferry-state.json',snapshot)
    return snapshot


def dispatch(engine,op,args):
    return {'ferry_service_status':status,'ferry_service_preview':preview,'ferry_service_apply':apply}[op](engine,args)
