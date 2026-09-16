"""Portable data-only player snapshots, with staged schema-aware restore."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import time
import zipfile
from player_tables import PLAYER_TABLES

MAX_BYTES = 8*1024**3
MAX_ROW = 16*1024**2


def ident(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,64}', value): raise ValueError('Invalid database identifier')
    return '`'+value+'`'


def table_names(engine):
    names = set(PLAYER_TABLES)
    try:
        source = engine.source_root()
        server = source/'Release-NMS-Server' if (source/'Release-NMS-Server').is_dir() else source
        header = server/'common/database_schema.h'
    except ValueError: return names
    if header.is_file() and not header.is_symlink() and header.stat().st_size < 1024**2:
        text = header.read_text(errors='replace')
        if 'GetPlayerTables()' in text:
            section = text.split('GetPlayerTables()',1)[1].split('};',1)[0]
            names.update(re.findall(r'"([a-z0-9_]+)"',section))
    return names


def binary_type(column):
    return bool(re.match(r'^(?:tinyblob|blob|mediumblob|longblob|binary|varbinary|bit)\b', column['type'], re.I))


def rows(engine, sql):
    return [line.split('\t') for line in engine.mysql(sql).splitlines()[1:]]


def schema(engine):
    db = engine.config['database']; ident(db)
    tables = {r[0]:r[1] for r in rows(engine, "SELECT TABLE_NAME,COALESCE(ENGINE,'VIEW') FROM information_schema.TABLES WHERE TABLE_SCHEMA='"+db+"';")}
    cols = {}
    for r in rows(engine,"SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,IF(COLUMN_DEFAULT IS NULL,'<NULL>','<SET>'),EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='"+db+"' ORDER BY TABLE_NAME,ORDINAL_POSITION;"):
        cols.setdefault(r[0],[]).append({'name':r[1],'type':r[2],'nullable':r[3],'default':r[4],'extra':r[5]})
    return tables,cols


def stopped(engine):
    if engine.server_running(): raise ValueError('Stop the server before transferring player data')
    engine.ensure_db()
    if not engine.config['database_imported']: raise ValueError('Import a server database first')


def export_players(engine, args):
    from engine import atomic_json
    from managed_content import digest
    stopped(engine)
    tables, columns = schema(engine); names = sorted(table_names(engine) & tables.keys())
    if not {'account','character_data'} <= set(names): raise ValueError('Player tables are missing')
    stamp = time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)
    target = engine.work/'backups'/('players-'+stamp+'.zip')
    temp = engine.work/'run'/('player-export-'+stamp); temp.mkdir()
    manifest = {'format':'trasc-players-1','created_at':time.time(),'database_source':engine.config.get('database_source'), 'tables':{}}
    total = 0
    try:
        with zipfile.ZipFile(target.with_suffix('.part'),'w',zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
            for name in names:
                engine.check_cancel(); ident(name)
                cols = [c for c in columns[name] if 'GENERATED' not in c['extra'].upper()]
                expressions = []
                for c in cols:
                    column=ident(c["name"])
                    value="CAST("+column+" AS BINARY)" if binary_type(c) else "CONVERT("+column+" USING utf8mb4)"
                    expressions.append("IF("+column+" IS NULL,'N',CONCAT('H',HEX("+value+")))")
                query = temp/'query.sql'; data = temp/'rows.tsv'
                query.write_text("SET time_zone='+00:00'; SELECT "+','.join(expressions)+' FROM '+ident(name)+';\n')
                engine.run(['mariadb','--defaults-extra-file='+str(engine.mysql_options),'--batch','--raw','--skip-column-names','--quick',engine.config['database']], input_file=query,output_file=data,private=True)
                count=0
                with data.open('rb') as stream:
                    for line in stream:
                        count+=1
                        if len(line)>MAX_ROW: raise ValueError('Player row exceeds supported size')
                total += data.stat().st_size
                if total > MAX_BYTES: raise ValueError('Player snapshot is too large')
                member='tables/'+name+'.tsv'; archive.write(data,member)
                manifest['tables'][name]={'columns':cols,'rows':count,'sha256':digest(data),'bytes':data.stat().st_size,'member':member}
            archive.writestr('manifest.json', json.dumps(manifest))
        target.with_suffix('.part').replace(target)
        result={'file':str(target.relative_to(engine.work)),'tables':len(names),
                'accounts':manifest['tables']['account']['rows'],'characters':manifest['tables']['character_data']['rows'],
                'message':'Player/account snapshot saved. It includes all accounts, characters, inventory and related progression; no world content or table definitions.'}
        atomic_json(engine.work/'logs/player-export.json',result)
        return result
    finally:
        target.with_suffix('.part').unlink(missing_ok=True); shutil.rmtree(temp)


def read_snapshot(engine, filename):
    from engine import safe_path
    from managed_content import digest
    path = safe_path(engine.work,filename,True)
    if not any(path.is_relative_to(engine.work/p) for p in ('incoming','backups')) or not path.is_file():
        raise ValueError('Choose a player snapshot ZIP or a local player backup')
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist(); names = [x.filename for x in members]
        if len(names)!=len(set(names)) or len(names)>1001 or sum(x.file_size for x in members)>MAX_BYTES:
            raise ValueError('Invalid or oversized player snapshot')
        if archive.getinfo('manifest.json').file_size>2*1024**2: raise ValueError('Oversized player manifest')
        manifest=json.loads(archive.read('manifest.json'))
        if manifest.get('format')!='trasc-players-1' or not isinstance(manifest.get('tables'),dict): raise ValueError('Not a TRASC player snapshot')
        if not {'account','character_data'}<=manifest['tables'].keys(): raise ValueError('Incomplete player snapshot')
        for table,item in manifest['tables'].items():
            ident(table)
            if table not in table_names(engine): raise ValueError('Unknown player table: '+table+'. Import matching source before restoring')
            expected='tables/'+table+'.tsv'
            if item.get('member')!=expected or item.get('bytes')!=archive.getinfo(expected).file_size: raise ValueError('Invalid player table entry')
            if not isinstance(item.get('rows'),int) or item['rows']<0: raise ValueError('Invalid player row count')
            columns=item.get('columns')
            if not isinstance(columns,list) or not columns or len(columns)>1024: raise ValueError('Invalid player columns')
            for col in columns: ident(col['name'])
            if len({c['name'] for c in columns})!=len(columns): raise ValueError('Duplicate player column')
        if set(names) != {'manifest.json', *('tables/'+n+'.tsv' for n in manifest['tables'])}: raise ValueError('Unexpected snapshot members')
    return path,manifest,digest(path)


def foreign_keys(engine, selected):
    """Read current relationships; only a complete player-only graph can swap."""
    db=engine.config['database']; ident(db)
    query="""SELECT k.TABLE_SCHEMA,k.TABLE_NAME,k.CONSTRAINT_NAME,k.COLUMN_NAME,
k.REFERENCED_TABLE_SCHEMA,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,r.UPDATE_RULE,r.DELETE_RULE
FROM information_schema.KEY_COLUMN_USAGE k
JOIN information_schema.REFERENTIAL_CONSTRAINTS r
ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.TABLE_NAME=k.TABLE_NAME AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME
WHERE k.REFERENCED_TABLE_NAME IS NOT NULL AND (k.TABLE_SCHEMA='"""+db+"' OR k.REFERENCED_TABLE_SCHEMA='"+db+"') ORDER BY k.TABLE_SCHEMA,k.TABLE_NAME,k.CONSTRAINT_NAME,k.ORDINAL_POSITION;"
    grouped={};problems=[]
    for schema_name,table,name,column,ref_schema,parent,ref_column,update,delete in rows(engine,query):
        if not ((schema_name==db and table in selected) or (ref_schema==db and parent in selected)): continue
        if schema_name!=db or ref_schema!=db or table not in selected or parent not in selected:
            problems.append('Foreign key crosses the player snapshot boundary: '+table+' -> '+parent);continue
        if update not in ('RESTRICT','NO ACTION','CASCADE','SET NULL') or delete not in ('RESTRICT','NO ACTION','CASCADE','SET NULL'):
            problems.append('Unsupported foreign-key action: '+table);continue
        for value in (table,parent,column,ref_column): ident(value)
        key=(table,name)
        item=grouped.setdefault(key,{'table':table,'parent':parent,'columns':[],'references':[],'update':update,'delete':delete})
        item['columns'].append(column);item['references'].append(ref_column)
    return list(grouped.values()),sorted(set(problems))


def preview_players(engine,args):
    stopped(engine)
    path,manifest,sha=read_snapshot(engine,args['file'])
    tables,columns=schema(engine); problems=[]; changes=[]
    for name,item in manifest['tables'].items():
        if name not in tables:
            problems.append('Missing table: '+name); continue
        if tables[name] not in ('InnoDB','Aria','MyISAM'): problems.append('Unsupported table engine: '+name)
        old={c['name']:c for c in item['columns']}; new={c['name']:c for c in columns[name]}
        removed=old.keys()-new.keys()
        if removed and item['rows']: problems.append(name+': removed columns '+', '.join(sorted(removed)))
        for col in new.keys()-old.keys():
            c=new[col]
            if item['rows'] and c['nullable']=='NO' and c['default']=='<NULL>' and not c['extra']:
                problems.append(name+': new required column '+col)
            else: changes.append(name+': new column '+col+' uses current default')
        for col in old.keys() & new.keys():
            if old[col]['type'] != new[col]['type']: changes.append(name+'.'+col+': type changed; strict staged validation required')
    # Relationships inside the complete snapshot are rebuilt against staging tables.
    db=engine.config['database']
    relationships,key_problems=foreign_keys(engine,manifest['tables']);problems.extend(key_problems)
    for (table,) in rows(engine,"SELECT EVENT_OBJECT_TABLE FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='"+db+"';"):
        if table in manifest['tables']: problems.append('Trigger migration required: '+table)
    return {'file':str(path.relative_to(engine.work)),'sha256':sha,'accounts':manifest['tables']['account']['rows'],
            'characters':manifest['tables']['character_data']['rows'],'tables':len(manifest['tables']),
            'table_names':sorted(manifest['tables']),'foreign_keys':relationships,'compatible':not problems,'problems':problems,'changes':changes,
            'message':'Ready to stage and validate player restore.' if not problems else 'Restore blocked: schema changes need review.'}


def restore_players(engine,args):
    from engine import atomic_json
    stopped(engine)
    preview=preview_players(engine,args)
    if args.get('sha256')!=preview['sha256'] or args.get('replace') is not True: raise ValueError('Review this snapshot and enable replacement first')
    if not preview['compatible']: raise ValueError('; '.join(preview['problems']))
    path,manifest,_=read_snapshot(engine,args['file']); _,columns=schema(engine)
    backup=engine.backup_database({})['file']
    token=secrets.token_hex(6); journal=engine.work/'backups'/('player-restore-'+token+'.json')
    record={'state':'staging','snapshot':preview['file'],'sha256':preview['sha256'],'database_backup':backup,'tables':{}}
    atomic_json(journal,record); script=engine.work/'run'/('player-restore-'+token+'.sql')
    staged=[]; swapped=False
    try:
        with zipfile.ZipFile(path) as archive:
            for i,(name,item) in enumerate(manifest['tables'].items()):
                engine.check_cancel()
                stage='_trascp_'+token+'_'+str(i); old=stage+'_old'
                engine.mysql('CREATE TABLE '+ident(stage)+' LIKE '+ident(name)+';'); staged.append(stage)
                record['tables'][name]={'staged':stage,'previous':old}; atomic_json(journal,record)
                available={c['name'] for c in columns[name] if 'GENERATED' not in c['extra'].upper()}
                source_cols=[c['name'] for c in item['columns']]
                keep=[j for j,c in enumerate(source_cols) if c in available]
                insert='INSERT INTO '+ident(stage)+' ('+','.join(ident(source_cols[j]) for j in keep)+') VALUES '
                count=0; hasher=hashlib.sha256()
                with archive.open(item['member']) as data, script.open('w') as out:
                    out.write("SET time_zone='+00:00'; SET SESSION sql_mode='STRICT_ALL_TABLES,NO_AUTO_VALUE_ON_ZERO';\n")
                    while True:
                        line=data.readline(MAX_ROW+1)
                        if not line: break
                        engine.check_cancel()
                        if len(line)>MAX_ROW or not line.endswith(b'\n'): raise ValueError('Invalid player row')
                        hasher.update(line); fields=line[:-1].split(b'\t')
                        if len(fields)!=len(source_cols): raise ValueError('Player column count mismatch')
                        values=[]
                        for index,value in enumerate(fields):
                            if value==b'N': values.append('NULL')
                            elif value.startswith(b'H') and len(value)%2==1 and re.fullmatch(rb'H[0-9A-F]*',value):
                                literal="X'"+value[1:].decode('ascii')+"'"
                                values.append(literal if binary_type(item['columns'][index]) else "CONVERT("+literal+" USING utf8mb4)")
                            else: raise ValueError('Invalid player field encoding')
                        out.write(insert+'('+','.join(values[j] for j in keep)+');\n'); count+=1
                if count!=item['rows'] or hasher.hexdigest()!=item['sha256']: raise ValueError('Player snapshot checksum or row count failed')
                engine.run(['mariadb','--defaults-extra-file='+str(engine.mysql_options),engine.config['database']],input_file=script,private=True)
                if int(rows(engine,'SELECT COUNT(*) FROM '+ident(stage)+';')[0][0])!=count: raise ValueError('Staged player row count mismatch')
        # LIKE does not retain foreign keys. Rebuild them after loading every
        # table, with checks enabled, so orphaned data never reaches live tables.
        for i,key in enumerate(preview['foreign_keys']):
            engine.check_cancel()
            child=record['tables'][key['table']]['staged'];parent=record['tables'][key['parent']]['staged']
            engine.mysql('SET SESSION foreign_key_checks=1; ALTER TABLE '+ident(child)+' ADD CONSTRAINT '+ident('_trascf_'+token+'_'+str(i))+
                         ' FOREIGN KEY ('+','.join(ident(c) for c in key['columns'])+') REFERENCES '+ident(parent)+
                         ' ('+','.join(ident(c) for c in key['references'])+') ON UPDATE '+key['update']+' ON DELETE '+key['delete']+';',timeout=120)
        engine.check_cancel()
        record['state']='ready';atomic_json(journal,record)
        renames=[]
        for name,entry in record['tables'].items():
            renames += [ident(name)+' TO '+ident(entry['previous']),ident(entry['staged'])+' TO '+ident(name)]
        # One atomic multi-table rename: no partial account/character replacement.
        engine.mysql('RENAME TABLE '+','.join(renames)+';',timeout=120); swapped=True
        record['state']='restored';atomic_json(journal,record)
        engine.mysql('SET SESSION foreign_key_checks=0; DROP TABLE '+','.join(ident(x['previous']) for x in record['tables'].values())+';',timeout=120)
        return {'message':'Player/account data restored against the current schema. World content retained. Recovery backup: '+backup+'.',
                'database_backup':backup,'accounts':preview['accounts'],'characters':preview['characters'],'tables':preview['tables']}
    except Exception:
        if not swapped and staged: engine.mysql('SET SESSION foreign_key_checks=0; DROP TABLE IF EXISTS '+','.join(ident(x) for x in staged)+';',timeout=120)
        raise
    finally: script.unlink(missing_ok=True)
