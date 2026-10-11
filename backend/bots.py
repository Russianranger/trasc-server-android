"""Character-owned bot rosters and stopped-world, previewed creation.

TAKP's additive records are its native creation path. Modern worlds delegate
creation to the qualified zone utility; the launcher never synthesizes their
appearance, inventory, quest events or state tables with SQL.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time

from player_data import ident, rows

RECEIPTS = 'trasc_bot_creation_receipts'
INSTANCE = '_trasc_bot_manager_identity'
TTL = 1800
MAX_BATCH = 20
CLASSES = {1:'Warrior',2:'Cleric',3:'Paladin',4:'Ranger',5:'Shadow Knight',6:'Druid',7:'Monk',8:'Bard',9:'Rogue',10:'Shaman',11:'Necromancer',12:'Wizard',13:'Magician',14:'Enchanter',15:'Beastlord',16:'Berserker'}
RACES = {1:'Human',2:'Barbarian',3:'Erudite',4:'Wood Elf',5:'High Elf',6:'Dark Elf',7:'Half Elf',8:'Dwarf',9:'Troll',10:'Ogre',11:'Halfling',12:'Gnome',128:'Iksar',130:'Vah Shir',330:'Froglok',522:'Drakkin'}
TAKP_TABLES = ('character_data','character_inventory','takp_bot_schema','takp_bot_data','takp_bot_runtime','takp_bot_inventory','takp_bot_buffs','takp_bot_recasts','takp_bot_settings','takp_bot_supplies','takp_bot_pets','takp_bot_pet_buffs','takp_bot_pet_items','takp_bot_songs','takp_bot_options','takp_bot_spell_settings','takp_bot_blocked_buffs','takp_bot_heal_rotations','takp_bot_heal_rotation_members','takp_bot_heal_rotation_targets','takp_bot_ability_recasts','takp_bot_name_registry','takp_bot_saved_groups','takp_bot_owner_settings')
TAKP_TRIGGERS = {'takp_bot_'+group+'name_'+action for group in ('','player_') for action in ('insert','update','delete')}
# Native player-bot state tables from DatabaseSchema::GetBotTables, excluding
# its read-only command, race/class, spell-list and casting-chance content.
# Never infer writable storage from an arbitrary bot_* prefix.
MODERN_STORAGE_TABLES = ('character_data','bot_data','bot_blocked_buffs','bot_buffs',
    'bot_heal_rotation_members','bot_heal_rotation_targets','bot_heal_rotations',
    'bot_inspect_messages','bot_inventories','bot_owner_options','bot_pet_buffs',
    'bot_pet_inventories','bot_pets','bot_settings','bot_spell_settings','bot_stances',
    'bot_timers','data_buckets')


def _trigger_body(text):
    return re.sub(r'\s+',' ',text.replace('`','').strip().lower())


def _expected_triggers():
    result={}
    for group,table,kind in (('player_','character_data','player'),('','takp_bot_data','bot')):
        insert="INSERT INTO takp_bot_name_registry VALUES(NEW.name,'"+kind+"',NEW.id);"
        delete="DELETE FROM takp_bot_name_registry WHERE kind='"+kind+"' AND entity_id=OLD.id;"
        wrapped="IF NEW.name<>'' THEN "+insert+' END IF;' if group else insert
        result['takp_bot_'+group+'name_insert']=['INSERT',table,'AFTER',_trigger_body('BEGIN '+wrapped+' END')]
        result['takp_bot_'+group+'name_update']=['UPDATE',table,'AFTER',_trigger_body('BEGIN IF NOT (NEW.name<=>OLD.name) THEN '+delete+' '+wrapped+' END IF; END')]
        result['takp_bot_'+group+'name_delete']=['DELETE',table,'AFTER',_trigger_body('BEGIN '+delete+' END')]
    return result


def literal(value):
    return "CONVERT(X'%s' USING utf8mb4)" % str(value).encode().hex()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def positive(value, label='ID'):
    if type(value) is not int or not 1 <= value <= 4294967295:
        raise ValueError('Invalid '+label)
    return value


def _json_rows(engine, query):
    return [json.loads(line) for line in engine.mysql(query).splitlines()[1:] if line]


def require_stopped(engine):
    if engine.server_running():
        raise ValueError('Stop the server and client before changing bots or socials')
    # The native bridge serializes launch with these jobs. Independently reject
    # a running client when a caller reaches the daemon directly.
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit(): continue
        try:
            if directory.stat().st_uid != os.getuid(): continue
            command = (directory/'cmdline').read_bytes().split(b'\0')
            if any(part.endswith(b'/client_runner.py') for part in command):
                raise ValueError('Stop the embedded client before changing bots or socials')
        except (OSError,ProcessLookupError): continue


def _small_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**2:
        raise ValueError('The deployed server build receipt is missing or invalid')
    return json.loads(path.read_text())


def _instance(engine):
    """Keep database incarnation inside database/session backups, never infer it from a name."""
    engine.mysql('CREATE TABLE IF NOT EXISTS '+ident(INSTANCE)+' (id TINYINT UNSIGNED NOT NULL PRIMARY KEY,incarnation CHAR(32) CHARACTER SET ascii NOT NULL) ENGINE=InnoDB;')
    shape = rows(engine,'SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(INSTANCE)+' ORDER BY ORDINAL_POSITION;')
    table = rows(engine,'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(INSTANCE)+';')
    keys = rows(engine,'SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(INSTANCE)+" AND CONSTRAINT_NAME='PRIMARY';")
    if shape != [['id','tinyint(3) unsigned','NO'],['incarnation','char(32)','NO']] or table != [['InnoDB']] or keys != [['id']]:
        raise ValueError('The Bots database identity table has an incompatible schema')
    engine.mysql('INSERT IGNORE INTO '+ident(INSTANCE)+' VALUES(1,'+literal(secrets.token_hex(16))+');')
    values = rows(engine,'SELECT id,incarnation FROM '+ident(INSTANCE)+';')
    if len(values)!=1 or values[0][0]!='1' or not re.fullmatch('[0-9a-f]{32}',values[0][1]):
        raise ValueError('The Bots database identity is invalid')
    return values[0][1]


def _schema(engine):
    takp = engine.profile == 'takp'
    bot = 'takp_bot_data' if takp else 'bot_data'
    combo = 'char_create_combinations' if takp else 'bot_create_combinations'
    required = set(TAKP_TABLES if takp else ('character_data','bot_data'))
    selected = required | {'account',combo,'name_filter','rule_values','rule_sets','variables'}
    names = ','.join(literal(n) for n in sorted(selected))
    tables = dict(rows(engine,'SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('+names+');'))
    missing = (required | {'account',combo}) - tables.keys()
    if missing: raise ValueError('Bots tables are missing: '+', '.join(sorted(missing)))
    columns = rows(engine,'SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COALESCE(EXTRA,\'\') FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('+names+') ORDER BY TABLE_NAME,ORDINAL_POSITION;')
    available = {}
    for row in columns: available.setdefault(row[0],set()).add(row[1])
    needed = {'character_data':{'id','account_id','name','level'},'account':{'id','name'},bot:({'id','owner_character_id','name','class','race','gender'} if takp else {'bot_id','owner_id','name','class','race','gender'}),combo:({'race','class'} if takp else {'race','classes'})}
    if takp: needed['character_data'].add('is_deleted')
    for table,fields in needed.items():
        if fields-available.get(table,set()): raise ValueError('Bots schema mismatch in '+table)
    triggers = []
    if takp:
        if any(tables.get(t)!='InnoDB' for t in required): raise ValueError('TAKP bots require all 24 storage tables to use InnoDB')
        if [int(r[0]) for r in rows(engine,'SELECT version FROM takp_bot_schema ORDER BY version;')] != list(range(1,12)):
            raise ValueError('TAKP bot migrations 001 through 011 must already be installed')
        triggers = rows(engine,'SELECT TRIGGER_NAME,EVENT_MANIPULATION,EVENT_OBJECT_TABLE,ACTION_TIMING,HEX(ACTION_STATEMENT) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE IN (\'character_data\',\'takp_bot_data\',\'takp_bot_name_registry\') ORDER BY TRIGGER_NAME;')
        if {r[0] for r in triggers} != TAKP_TRIGGERS: raise ValueError('The six TAKP shared-name triggers are missing or have unexpected additions')
        expected=_expected_triggers()
        for name,event,table,timing,statement in triggers:
            if [event,table,timing,_trigger_body(bytes.fromhex(statement).decode())]!=expected[name]:
                raise ValueError('The TAKP shared-name trigger changed: '+name)
        collation=rows(engine,"SELECT COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='takp_bot_name_registry' AND COLUMN_NAME='name';")
        if collation != [['utf8mb4_general_ci']]: raise ValueError('TAKP name reservations require the qualified case-insensitive collation')
        registry=rows(engine,"SELECT COUNT(*) FROM (SELECT name,'player' kind,id FROM character_data WHERE name<>'' UNION ALL SELECT name,'bot',id FROM takp_bot_data) n LEFT JOIN takp_bot_name_registry r ON r.kind=n.kind AND r.entity_id=n.id AND r.name=CONVERT(n.name USING utf8mb4) COLLATE utf8mb4_general_ci WHERE r.entity_id IS NULL;")
        if registry != [['0']]: raise ValueError('TAKP shared-name reservations are incomplete; repair the schema separately')
    return dict(tables=tables,columns=columns,column_names={t:sorted(c) for t,c in available.items()},triggers=triggers,bot_table=bot,combo_table=combo)


def _rules(engine, shape):
    result={'Character:GroupInvitesRequireTarget':'true','Bots:AllowCamelCaseNames':'false'}
    if not {'rule_values','rule_sets','variables'} <= shape['tables'].keys(): return result
    active=rows(engine,"SELECT rs.ruleset_id FROM rule_sets rs JOIN variables v ON rs.name=v.value WHERE LOWER(v.varname)='ruleset' LIMIT 2;")
    if len(active)>1: raise ValueError('The active ruleset is ambiguous')
    selected=int(active[0][0]) if active else 1
    for name,value in rows(engine,'SELECT rule_name,rule_value FROM rule_values WHERE ruleset_id IN (0,'+str(selected)+') ORDER BY ruleset_id;'):
        if name.startswith(('Bots:','Character:GroupInvites')): result[name]=value
    return result


def combinations(ctx):
    engine=ctx['engine']; result=set()
    if ctx['profile']=='takp':
        for race,cls in rows(engine,'SELECT DISTINCT race,`class` FROM char_create_combinations ORDER BY race,`class`;'):
            if int(race) in RACES and int(race) not in (330,522) and 1<=int(cls)<=15: result.add((int(race),int(cls)))
    else:
        for race,mask in rows(engine,'SELECT race,classes FROM bot_create_combinations ORDER BY race;'):
            for cls in CLASSES:
                if int(race) in RACES and int(mask)&(1<<(cls-1)): result.add((int(race),cls))
    if not result: raise ValueError('The database contains no supported race/class combinations')
    return sorted(result)


def context(engine,args=None,writing=False):
    args=args or {}
    if args.get('__profile',engine.profile)!=engine.profile: raise ValueError('World profile changed; refresh Bots')
    if writing: require_stopped(engine)
    if not engine.config.get('database_imported'): raise ValueError('Import this world\'s database before using Bots')
    engine.ensure_db(); ident(engine.config['database'])
    if not re.fullmatch('[0-9a-f]{32}',engine.config.get('bot_database_epoch','0'*32)):
        raise ValueError('The Bots database restore identity is invalid')
    shape=_schema(engine); deployment=_small_json(engine.work/'server/bin/build-info.json')
    if engine.profile=='takp' and deployment.get('profile')!='takp': raise ValueError('The deployed server belongs to another world')
    incarnation=_instance(engine)
    identity=fingerprint({'format':1,'profile':engine.profile,'database':engine.config['database'],'instance':incarnation,'restore_epoch':engine.config.get('bot_database_epoch',''),'schema':shape,'deployment':deployment})
    if args.get('identity') is not None and args['identity']!=identity: raise ValueError('The world, database or server deployment changed; refresh Bots')
    ctx=dict(engine=engine,profile=engine.profile,identity=identity,instance=incarnation,shape=shape,deployment=deployment,rules=_rules(engine,shape))
    ctx['combinations']=combinations(ctx)
    return ctx


def _creation(ctx):
    engine=ctx['engine']
    try:
        require_stopped(engine)
        if ctx['profile']=='takp':
            import takp_build
            import takp_runtime
            takp_build.record(engine,'server/bin')
            takp_runtime._bot_command(engine,'--verify')
        else:
            storage=storage_status(ctx)
            if not storage['available']: raise ValueError(storage['reason'])
            if storage['needed']:
                raise ValueError('Review transactional bot storage in Bots, then back up and enable it before generating bots')
            import modern_bot_bridge
            capability=modern_bot_bridge.capabilities(engine,ctx)
            if not capability.get('offline_create'): raise ValueError(capability.get('reason','Rebuild and deploy this server with the offline bot creation utility'))
        return {'available':True,'reason':''}
    except (ValueError,OSError,ImportError) as error:
        return {'available':False,'reason':str(error)}


def status(engine,args):
    try: ctx=context(engine,args)
    except (ValueError,OSError) as error:
        return dict(profile=engine.profile,identity=None,available=False,reason=str(error),creation={'available':False,'reason':str(error)},races=[],genders=[{'id':0,'name':'Male'},{'id':1,'name':'Female'}])
    races=[dict(id=race,name=RACES[race],classes=[{'id':cls,'name':CLASSES[cls]} for r,cls in ctx['combinations'] if r==race]) for race in sorted({r for r,c in ctx['combinations']})]
    import bot_socials
    return dict(profile=ctx['profile'],identity=ctx['identity'],available=True,reason='',creation=_creation(ctx),races=races,genders=[{'id':0,'name':'Male'},{'id':1,'name':'Female'}],limits={'batch':MAX_BATCH,'summon':5,'social_selection':20},social_commands=bot_socials.catalogue(ctx['profile']),rules=ctx['rules'],storage=storage_status(ctx))


def _storage_snapshot(ctx):
    if ctx['profile']=='takp': raise ValueError('TAKP already requires its installed bot storage to use InnoDB')
    engine=ctx['engine']; names=','.join(literal(t) for t in MODERN_STORAGE_TABLES)
    engines=rows(engine,"SELECT TABLE_NAME,ENGINE,TABLE_TYPE,ROW_FORMAT,COALESCE(TABLE_COLLATION,''),COALESCE(CREATE_OPTIONS,'') FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ("+names+') ORDER BY TABLE_NAME;')
    tables={r[0]:{'engine':r[1],'type':r[2],'row_format':r[3],'collation':r[4],'options':r[5]} for r in engines}
    if not {'character_data','bot_data'} <= tables.keys(): raise ValueError('The required character_data and bot_data tables are missing')
    for name,table in tables.items():
        if table['type']!='BASE TABLE' or table['engine'] not in ('InnoDB','MyISAM','Aria'):
            raise ValueError(name+': transactional storage supports existing InnoDB, MyISAM or Aria tables only')
    innodb=rows(engine,"SELECT SUPPORT FROM information_schema.ENGINES WHERE ENGINE='InnoDB';")
    if innodb not in ([['YES']],[['DEFAULT']]): raise ValueError('This database runtime does not support InnoDB')
    columns=rows(engine,"SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,IF(COLUMN_DEFAULT IS NULL,'N',CONCAT('H',HEX(COLUMN_DEFAULT))),COALESCE(EXTRA,''),COALESCE(CHARACTER_SET_NAME,''),COALESCE(COLLATION_NAME,'') FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ("+names+') ORDER BY TABLE_NAME,ORDINAL_POSITION;')
    indexes=rows(engine,"SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME,COALESCE(SUB_PART,0),COALESCE(INDEX_TYPE,'') FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ("+names+') ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX;')
    constraints=rows(engine,"SELECT TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,COALESCE(REFERENCED_TABLE_NAME,''),COALESCE(REFERENCED_COLUMN_NAME,'') FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ("+names+') ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION;')
    triggers=rows(engine,"SELECT EVENT_OBJECT_TABLE,TRIGGER_NAME,EVENT_MANIPULATION,ACTION_TIMING,HEX(ACTION_STATEMENT) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE IN ("+names+') ORDER BY EVENT_OBJECT_TABLE,TRIGGER_NAME;')
    counts={name:int(rows(engine,'SELECT COUNT(*) FROM '+ident(name)+';')[0][0]) for name in tables}
    return dict(tables=tables,columns=columns,indexes=indexes,constraints=constraints,triggers=triggers,counts=counts)


def _storage_changes(snapshot):
    priority={name:index for index,name in enumerate(MODERN_STORAGE_TABLES)}
    return [{'name':name,'from':table['engine'],'to':'InnoDB'} for name,table in sorted(snapshot['tables'].items(),key=lambda pair:priority[pair[0]]) if table['engine']!='InnoDB']


def storage_status(ctx):
    if ctx['profile']=='takp': return {'needed':False,'available':False,'reason':'TAKP storage is qualified with its bot migrations','tables':[]}
    if '_storage_status' in ctx: return ctx['_storage_status']
    try:
        snapshot=_storage_snapshot(ctx); changes=_storage_changes(snapshot)
        try: require_stopped(ctx['engine']); available=True; reason=''
        except ValueError as error: available=False; reason=str(error)
        result=dict(needed=bool(changes),available=available,reason=reason,tables=changes)
    except (ValueError,OSError) as error:
        result=dict(needed=True,available=False,reason=str(error),tables=[])
    ctx['_storage_status']=result
    return result


def _storage_path(engine,token):
    path=engine.work/'run/bot-storage-previews'/(token+'.json')
    if path.parent.is_symlink() or path.is_symlink(): raise ValueError('Bot storage preview paths cannot be symbolic links')
    return path


def storage_preview(engine,args):
    from engine import atomic_json
    ctx=context(engine,args,writing=True)
    snapshot=_storage_snapshot(ctx); changes=_storage_changes(snapshot)
    if not changes: raise ValueError('Transactional bot storage is already enabled; refresh Bots')
    value={'format':1,'identity':ctx['identity'],'profile':ctx['profile'],'snapshot':snapshot,'created':time.time(),'nonce':secrets.token_hex(24),'attempted':False}
    token=fingerprint(value); value['preview_hash']=token
    atomic_json(_storage_path(engine,token),value)
    return dict(identity=ctx['identity'],preview_hash=token,changes=[{'table':c['name'],'from':c['from'],'to':c['to']} for c in changes],backup_required=True,message='Review '+str(len(changes))+' player/bot state tables. Enable makes a full database backup first, then converts each listed table to InnoDB. Each conversion commits separately.')


def _storage_equal_after(previous,current,changed):
    """ALTER ENGINE may change storage options, but cannot silently change player data or columns."""
    if previous['counts']!=current['counts'] or previous['columns']!=current['columns'] or previous['triggers']!=current['triggers']:
        return False
    if previous['constraints']!=current['constraints']: return False
    # An engine can report a different physical index type after conversion;
    # its unique keys, indexed columns, ordering and prefix length must survive.
    if [r[:-1] for r in previous['indexes']]!=[r[:-1] for r in current['indexes']]: return False
    if previous['tables'].keys()!=current['tables'].keys(): return False
    for name,table in previous['tables'].items():
        after=current['tables'][name]
        if name==changed:
            if after['engine']!='InnoDB' or after['type']!=table['type'] or after['collation']!=table['collation']: return False
        elif table!=after: return False
    return True


def storage_enable(engine,args):
    from engine import atomic_json, safe_path
    ctx=context(engine,args,writing=True); token=args.get('preview_hash','')
    if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token): raise ValueError('Review transactional bot storage before enabling it')
    path=_storage_path(engine,token); value=_small_json(path)
    if value.get('profile')!=ctx['profile'] or value.get('identity')!=ctx['identity'] or time.time()-value.get('created',0)>TTL or value.get('attempted'):
        raise ValueError('The storage review expired or was already attempted; make a new review')
    original={k:value[k] for k in ('format','identity','profile','snapshot','created','nonce','attempted')}
    if value.get('preview_hash')!=token or fingerprint(original)!=token or _storage_snapshot(ctx)!=value['snapshot']:
        raise ValueError('Bot storage changed since review; make a new review before converting tables')
    changes=_storage_changes(value['snapshot'])
    if not changes: raise ValueError('Transactional bot storage is already enabled')
    value['attempted']=True; atomic_json(path,value)
    # DDL cannot share a transaction or roll back as a batch. No ALTER is
    # reached until the managed full-database dump/compression completed.
    saved=engine.backup_database({}); backup=saved.get('file') if isinstance(saved,dict) else None
    if not isinstance(backup,str): raise ValueError('A completed full database backup is required; no tables were converted')
    backup_path=safe_path(engine.work,backup,True)
    if not backup_path.is_relative_to(engine.work/'backups') or backup_path.is_symlink() or not backup_path.is_file() or not backup_path.stat().st_size:
        raise ValueError('The completed database backup is missing or invalid; no tables were converted')
    value.update(backup=backup,backup_bytes=backup_path.stat().st_size); atomic_json(path,value)
    require_stopped(engine)
    if context(engine,{'identity':ctx['identity']},writing=True)['identity']!=ctx['identity'] or _storage_snapshot(ctx)!=value['snapshot']:
        raise ValueError('Bot storage changed while backing up; no tables were converted. Backup: '+backup)
    expected=value['snapshot']; error=None
    try:
        for change in changes:
            require_stopped(engine); engine.check_cancel()
            current=_storage_snapshot(ctx)
            if current!=expected: raise ValueError('Bot storage changed during conversion; remaining tables were left unchanged')
            value['last_attempted']=change['name']; atomic_json(path,value)
            engine.mysql('ALTER TABLE '+ident(change['name'])+' ENGINE=InnoDB;',timeout=1800)
            after=_storage_snapshot(ctx)
            if not _storage_equal_after(current,after,change['name']):
                raise ValueError('Table conversion changed unexpected schema or row counts; inspect the backup before continuing')
            expected=after
            value['converted']=[c['name'] for c in changes if after['tables'][c['name']]['engine']=='InnoDB']; atomic_json(path,value)
    except (ValueError,OSError,subprocess.TimeoutExpired) as failure:
        error=str(failure)
    # Query the actual current engines, including an ALTER whose response was
    # lost. Never claim rollback or infer success from the attempted commands.
    uncertain=False
    try:
        actual=_storage_snapshot(ctx)
        converted=[c['name'] for c in changes if actual['tables'].get(c['name'],{}).get('engine')=='InnoDB']
        remaining=_storage_changes(actual)
    except (ValueError,OSError,subprocess.TimeoutExpired) as failure:
        uncertain=True
        converted=value.get('converted',[])
        remaining=[dict(c,unverified=True) for c in changes if c['name'] not in converted]
        error=(error+'; ' if error else '')+'Current storage could not be verified: '+str(failure)
    if converted or uncertain:
        engine.config['bot_database_epoch']=secrets.token_hex(16); engine.save()
    try: new_identity=context(engine)['identity']
    except (ValueError,OSError,subprocess.TimeoutExpired): new_identity=None
    complete=not remaining and error is None and not uncertain
    result=dict(identity=new_identity,backup=backup,complete=complete,converted=converted,remaining=remaining,uncertain=uncertain,
                message=('Transactional bot storage enabled. Refresh Bots before creating a batch.' if complete else 'Storage conversion stopped after '+str(len(converted))+' tables. The completed database backup is retained; review the remaining tables before continuing.'))
    if uncertain: result['message']='Storage conversion could not be fully verified. The completed backup and confirmed conversions are retained; reconnect and review the remaining tables before continuing.'
    if error is not None: result['error']=error
    atomic_json(path,dict(value,result=result,completed=time.time()))
    atomic_json(engine.work/'logs/bot-storage.json',result)
    return result


def _owner_query(ctx,where):
    deleted=' AND c.is_deleted=0' if 'is_deleted' in ctx['shape']['column_names']['character_data'] else ''
    if ctx['profile']!='takp' and 'deleted_at' in ctx['shape']['column_names']['character_data']:
        deleted+=' AND c.deleted_at IS NULL'
    return "SELECT JSON_OBJECT('id',c.id,'account_id',c.account_id,'name',c.name,'level',c.level,'account',COALESCE(a.name,'')) FROM character_data c LEFT JOIN account a ON a.id=c.account_id WHERE "+where+deleted


def owner(ctx,owner_id):
    owner_id=positive(owner_id,'character ID')
    found=_json_rows(ctx['engine'],_owner_query(ctx,'c.id='+str(owner_id))+' LIMIT 2;')
    if len(found)!=1 or not found[0]['name'] or not found[0]['account']:
        raise ValueError('The selected active character or account no longer exists')
    return found[0]


def characters(engine,args):
    ctx=context(engine,args); query=args.get('query','')
    if not isinstance(query,str) or len(query)>80: raise ValueError('Character search must be at most 80 characters')
    query=query.strip().lower()
    where='1' if not query else '(LOCATE('+literal(query)+',LOWER(c.name))>0 OR LOCATE('+literal(query)+",LOWER(COALESCE(a.name,'')))>0)"
    result=_json_rows(engine,_owner_query(ctx,where)+' ORDER BY c.name,c.id LIMIT 201;')
    return dict(identity=ctx['identity'],characters=result[:200],query=query,truncated=len(result)>200)


def roster(ctx,owner_id):
    owner_id=positive(owner_id,'character ID'); takp=ctx['profile']=='takp'
    bot=ctx['shape']['bot_table']; key='id' if takp else 'bot_id'; owner_key='owner_character_id' if takp else 'owner_id'
    result=_json_rows(ctx['engine'],"SELECT JSON_OBJECT('id',"+ident(key)+",'name',name,'class',`class`,'race',race,'gender',gender) FROM "+ident(bot)+' WHERE '+ident(owner_key)+'='+str(owner_id)+' ORDER BY name,'+ident(key)+' LIMIT 5001;')
    if len(result)>5000: raise ValueError('This character has more than 5,000 bots; reduce the roster before using the editor')
    return result


def read_roster(engine,args):
    ctx=context(engine,args); selected=owner(ctx,args.get('owner_id'))
    return dict(identity=ctx['identity'],owner=selected,bots=roster(ctx,selected['id']),creation=_creation(ctx))


def normalize_drafts(ctx,value):
    if not isinstance(value,list) or not 1<=len(value)<=MAX_BATCH: raise ValueError('Generate between 1 and '+str(MAX_BATCH)+' bots per batch')
    result=[]; used=set(); camel=ctx['profile']!='takp' and ctx['rules'].get('Bots:AllowCamelCaseNames','false').lower() in ('true','1')
    for item in value:
        if not isinstance(item,dict): raise ValueError('Invalid bot draft')
        name=item.get('name','')
        if not isinstance(name,str) or not re.fullmatch('[A-Za-z]{4,15}',name): raise ValueError('Bot names must contain 4–15 ASCII letters')
        if re.search(r'(.)\1\1',name.lower()): raise ValueError(name+': a letter cannot repeat three times')
        name=name[0].upper()+name[1:] if camel else name.capitalize()
        if name.lower() in used: raise ValueError('Bot names must be unique within this batch')
        used.add(name.lower()); race=positive(item.get('race'),'race'); cls=positive(item.get('class'),'class'); gender=item.get('gender')
        if type(gender) is not int or gender not in (0,1): raise ValueError('Choose Male or Female')
        if (race,cls) not in ctx['combinations']: raise ValueError(name+': choose a valid race/class combination for this world')
        result.append({'name':name,'class':cls,'race':race,'gender':gender})
    return result


def _name_checks(ctx,drafts):
    engine=ctx['engine']; names=','.join(literal(b['name'].lower()) for b in drafts)
    table=ctx['shape']['bot_table']
    collision=rows(engine,'SELECT name FROM character_data WHERE LOWER(name) IN ('+names+') UNION ALL SELECT name FROM '+ident(table)+' WHERE LOWER(name) IN ('+names+');')
    if collision: raise ValueError('A player or bot already uses '+collision[0][0])
    filters=[]
    if 'name_filter' in ctx['shape']['tables']:
        filters=[str(r[0]).lower() for r in rows(engine,'SELECT name FROM name_filter;') if r[0]]
    for bot in drafts:
        if any(word in bot['name'].lower() for word in filters): raise ValueError(bot['name']+': this name is prohibited by the server name filter')
    return filters


def request_id(args):
    token=args.get('request_id','')
    if not isinstance(token,str) or not re.fullmatch('[A-Za-z0-9_-]{16,64}',token): raise ValueError('A new creation request token is required; preview again')
    return token


def _preview_path(engine,token):
    path=engine.work/'run/bot-previews'/(token+'.json')
    if path.parent.is_symlink() or path.is_symlink(): raise ValueError('Bot preview paths cannot be symbolic links')
    return path


def preview(engine,args):
    from engine import atomic_json
    ctx=context(engine,args,writing=True); selected=owner(ctx,args.get('owner_id')); token=request_id(args)
    creation=_creation(ctx)
    if not creation['available']: raise ValueError(creation['reason'])
    drafts=normalize_drafts(ctx,args.get('drafts')); filters=_name_checks(ctx,drafts)
    state=dict(identity=ctx['identity'],owner=selected,bots=drafts,request_id=token,roster=roster(ctx,selected['id']),rules=ctx['rules'],combinations=ctx['combinations'],name_filters=filters)
    value=dict(state,preview_hash=fingerprint(state),created=time.time(),attempted=False)
    path=_preview_path(engine,token)
    if path.exists():
        previous=_small_json(path)
        if previous.get('preview_hash')!=value['preview_hash'] or previous.get('attempted'):
            raise ValueError('This request token has already been used; start a new preview')
    atomic_json(path,value)
    return dict(identity=ctx['identity'],owner=selected,bots=drafts,request_id=token,preview_hash=value['preview_hash'],message='Review '+str(len(drafts))+' bots for '+selected['name']+'. Creation preserves the existing roster.')


def ensure_receipts(engine):
    engine.mysql('CREATE TABLE IF NOT EXISTS '+ident(RECEIPTS)+' (request_id VARCHAR(64) CHARACTER SET ascii NOT NULL PRIMARY KEY,draft_hash CHAR(64) CHARACTER SET ascii NOT NULL,identity_hash CHAR(64) CHARACTER SET ascii NOT NULL,owner_id INT UNSIGNED NOT NULL,result_json MEDIUMTEXT NOT NULL) ENGINE=InnoDB;')
    shape=rows(engine,'SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(RECEIPTS)+' ORDER BY ORDINAL_POSITION;')
    expected=[['request_id','varchar(64)','NO'],['draft_hash','char(64)','NO'],['identity_hash','char(64)','NO'],['owner_id','int(10) unsigned','NO'],['result_json','mediumtext','NO']]
    table=rows(engine,'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(RECEIPTS)+';')
    keys=rows(engine,'SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(RECEIPTS)+" AND CONSTRAINT_NAME='PRIMARY';")
    if shape!=expected or table!=[['InnoDB']] or keys!=[['request_id']]: raise ValueError('Bot creation receipts require the qualified InnoDB schema')
    triggers=rows(engine,'SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE='+literal(RECEIPTS)+';')
    if triggers: raise ValueError('Unexpected triggers exist on bot creation receipts')


def _receipt(ctx,token,preview_hash,selected,drafts):
    found=_json_rows(ctx['engine'],"SELECT JSON_OBJECT('draft_hash',draft_hash,'identity_hash',identity_hash,'owner_id',owner_id,'result',result_json) FROM "+ident(RECEIPTS)+' WHERE request_id='+literal(token)+';')
    if not found: return None
    record=found[0]
    if record['draft_hash']!=preview_hash or record['identity_hash']!=ctx['identity'] or record['owner_id']!=selected['id']:
        raise ValueError('This creation token belongs to another owner, draft or database')
    result=json.loads(record['result'])
    if result.get('owner')!=selected or not isinstance(result.get('bots'),list): raise ValueError('The saved creation receipt no longer matches the character')
    current={bot['id']:bot for bot in roster(ctx,selected['id'])}
    if len(result['bots'])!=len(drafts): raise ValueError('The saved creation receipt is incomplete')
    for bot,draft in zip(result['bots'],drafts):
        if {k:bot.get(k) for k in draft}!=draft or current.get(bot.get('id'))!=bot:
            raise ValueError('A previously created bot changed or was removed; this request cannot create it again')
    return result


def _guard(expression):
    return 'INSERT INTO _trasc_bot_guard SELECT 1 WHERE NOT COALESCE(('+expression+'),0);'


def takp_transaction(ctx,value):
    """One CLI session: owner lock, live checks, all inserts and receipt commit together."""
    selected=value['owner']; token=value['request_id']; shape=ctx['shape']; tablelist=','.join(literal(t) for t in TAKP_TABLES)
    sql=["SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';",'CREATE TEMPORARY TABLE _trasc_bot_guard(id INT PRIMARY KEY) ENGINE=InnoDB;','INSERT INTO _trasc_bot_guard VALUES(1);','START TRANSACTION;', 'SET @locked_owner=NULL;','SELECT id INTO @locked_owner FROM character_data WHERE id='+str(selected['id'])+' FOR UPDATE;',_guard('@locked_owner='+str(selected['id']))]
    sql.append(_guard('(SELECT COUNT(*) FROM character_data c JOIN account a ON a.id=c.account_id WHERE c.id='+str(selected['id'])+' AND c.account_id='+str(selected['account_id'])+' AND BINARY c.name='+literal(selected['name'])+' AND c.level='+str(selected['level'])+' AND c.is_deleted=0 AND BINARY a.name='+literal(selected['account'])+')=1'))
    sql.append(_guard('(SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('+tablelist+") AND ENGINE='InnoDB')=24"))
    sql.append(_guard('(SELECT incarnation FROM '+ident(INSTANCE)+' WHERE id=1)='+literal(ctx['instance'])))
    sql.append(_guard('(SELECT COUNT(*) FROM takp_bot_schema WHERE version BETWEEN 1 AND 11)=11'))
    trigger_names=','.join(literal(n) for n in sorted(TAKP_TRIGGERS))
    sql.append(_guard('(SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE IN (\'character_data\',\'takp_bot_data\') AND TRIGGER_NAME IN ('+trigger_names+'))=6'))
    sql.append('SET @created_bots=JSON_ARRAY();')
    for bot in value['bots']:
        name=literal(bot['name']); pair='race='+str(bot['race'])+' AND `class`='+str(bot['class'])
        sql.append(_guard('(SELECT COUNT(*) FROM char_create_combinations WHERE '+pair+')>0'))
        sql.append(_guard('(SELECT COUNT(*) FROM character_data WHERE LOWER(name)=LOWER('+name+'))=0 AND (SELECT COUNT(*) FROM takp_bot_data WHERE LOWER(name)=LOWER('+name+'))=0'))
        if 'name_filter' in shape['tables']: sql.append(_guard('(SELECT COUNT(*) FROM name_filter WHERE name<>\'\' AND LOCATE(LOWER(name),LOWER('+name+'))>0)=0'))
        sql.append('INSERT INTO takp_bot_data(owner_character_id,name,`class`,race,gender) VALUES('+','.join((str(selected['id']),name,str(bot['class']),str(bot['race']),str(bot['gender'])))+');')
        sql.append('SET @created_bots=JSON_ARRAY_APPEND(@created_bots,\'$\',JSON_OBJECT(\'id\',LAST_INSERT_ID(),\'name\','+name+',\'class\','+str(bot['class'])+',\'race\','+str(bot['race'])+',\'gender\','+str(bot['gender'])+'));')
    sql.append('INSERT INTO '+ident(RECEIPTS)+' VALUES('+','.join((literal(token),literal(value['preview_hash']),literal(ctx['identity']),str(selected['id']),"JSON_OBJECT('owner',JSON_EXTRACT("+literal(json.dumps(selected))+",'$'),'bots',JSON_EXTRACT(@created_bots,'$'))"))+');')
    sql.append('COMMIT;')
    return ''.join(sql)


def generate(engine,args):
    from engine import atomic_json
    ctx=context(engine,args,writing=True); selected=owner(ctx,args.get('owner_id')); token=request_id(args); drafts=normalize_drafts(ctx,args.get('drafts'))
    preview_hash=args.get('preview_hash','')
    if not isinstance(preview_hash,str) or not re.fullmatch('[0-9a-f]{64}',preview_hash): raise ValueError('Preview this bot batch before generating it')
    ensure_receipts(engine)
    existing=_receipt(ctx,token,preview_hash,selected,drafts)
    if existing: return dict(existing,identity=ctx['identity'],request_id=token,idempotent=True,message='This batch was already created; its saved bots were loaded.')
    path=_preview_path(engine,token); value=_small_json(path)
    if value.get('attempted'): raise ValueError('The creation receipt is missing after an earlier attempt; refresh and make a new preview instead of creating duplicates')
    if time.time()-value.get('created',0)>TTL or value.get('identity')!=ctx['identity'] or value.get('owner')!=selected or value.get('bots')!=drafts or value.get('preview_hash')!=preview_hash:
        raise ValueError('The preview expired or its character/draft changed; preview again')
    state={k:value[k] for k in ('identity','owner','bots','request_id','roster','rules','combinations','name_filters')}
    if fingerprint(state)!=preview_hash or roster(ctx,selected['id'])!=state['roster'] or ctx['rules']!=state['rules'] or ctx['combinations']!=[tuple(p) for p in state['combinations']] or _name_checks(ctx,drafts)!=state['name_filters']:
        raise ValueError('The roster, rules or name validation changed since preview; preview again')
    creation=_creation(ctx)
    if not creation['available']: raise ValueError(creation['reason'])
    value['attempted']=True; atomic_json(path,value)
    try:
        if ctx['profile']=='takp': engine.mysql(takp_transaction(ctx,value),timeout=120)
        else:
            import modern_bot_bridge
            modern_bot_bridge.create(engine,ctx,dict(owner=selected,bots=drafts,request_id=token,draft_hash=preview_hash,identity_hash=ctx['identity']))
    except (ValueError,OSError,subprocess.TimeoutExpired) as error:
        # A lost response after COMMIT is resolved from the database receipt.
        recovered=_receipt(ctx,token,preview_hash,selected,drafts)
        if recovered: return dict(recovered,identity=ctx['identity'],request_id=token,idempotent=True,message='The batch committed successfully; its receipt recovered the response.')
        raise ValueError('Bot creation did not return a committed receipt. No socials were installed. Make a new preview after checking the error: '+str(error)) from error
    result=_receipt(ctx,token,preview_hash,selected,drafts)
    if not result: raise ValueError('Creation finished without a valid receipt; no socials were installed')
    atomic_json(path,dict(value,committed=True,result=result))
    return dict(result,identity=ctx['identity'],request_id=token,idempotent=False,message=str(len(drafts))+' bots created for '+selected['name']+'. Select them to preview their summon socials.')


def dispatch(engine,operation,args):
    if operation!='bots_status' and (not isinstance(args.get('identity'),str) or not re.fullmatch('[0-9a-f]{64}',args['identity'])):
        raise ValueError('Refresh Bots to select the current world and database')
    methods={'bots_status':status,'bots_characters':characters,'bots_roster':read_roster,'bots_preview':preview,'bots_generate':generate,'bots_storage_preview':storage_preview,'bots_storage_enable':storage_enable}
    if operation in methods: return methods[operation](engine,args)
    if operation in ('bots_socials_preview','bots_socials_install','bots_socials_restore'):
        import bot_socials
        ctx=context(engine,args,writing=operation!='bots_socials_preview'); selected=owner(ctx,args.get('owner_id'))
        if operation=='bots_socials_restore': return bot_socials.restore(engine,dict(args,_owner=selected))
        ids=args.get('bot_ids')
        limit=bot_socials.MAX_SELECTED if args.get('actions') is not None else 5
        if not isinstance(ids,list) or not 1<=len(ids)<=limit: raise ValueError(f'Select between one and {limit} distinct owned bots')
        for bot_id in ids: positive(bot_id,'bot ID')
        if len(ids)!=len(set(ids)): raise ValueError('Select distinct owned bots')
        owned={b['id']:b for b in roster(ctx,selected['id'])}
        if any(i not in owned for i in ids): raise ValueError('A selected bot no longer belongs to this character')
        args=dict(args,group_invites_require_target=ctx['rules'].get('Character:GroupInvitesRequireTarget','true').lower() not in ('false','0'))
        function=bot_socials.preview if operation=='bots_socials_preview' else bot_socials.install
        return function(engine,selected,[owned[i] for i in ids],args)
    raise ValueError('Unknown Bots operation')
