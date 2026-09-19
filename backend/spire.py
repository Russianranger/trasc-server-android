"""Schema-aware content browsing and previewed, audited InnoDB edits."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import time
from player_data import ident, rows
from spire_catalog import CATALOG, REFERENCES, PAIRS, bounds, impact

AUDIT = '_trasc_spire_changes'
MAX_TEXT = 32768
TTL = 1800


def literal(value):
    if value is None: return 'NULL'
    return "CONVERT(X'%s' USING utf8mb4)" % str(value).encode('utf-8').hex()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def ready(engine, writing=False):
    if writing and engine.server_running(): raise ValueError('Stop the server before saving Spire changes')
    if not engine.config.get('database_imported'): raise ValueError('Import a server database first')
    engine.ensure_db()


def schema(engine, table):
    if table not in CATALOG: raise ValueError('Unknown Spire content type')
    info = rows(engine, 'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(table)+';')
    if not info: raise ValueError('This database does not contain '+table)
    found = rows(engine, 'SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,IF(COLUMN_DEFAULT IS NULL,0,1),EXTRA,'
        'COALESCE(CHARACTER_MAXIMUM_LENGTH,0) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='
        +literal(table)+' ORDER BY ORDINAL_POSITION;')
    columns = {r[0]: dict(name=r[0], type=r[1], nullable=r[2]=='YES', default=r[3]=='1', extra=r[4], length=int(r[5])) for r in found}
    indexes = rows(engine, 'SELECT INDEX_NAME,COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='
        +literal(table)+' AND NON_UNIQUE=0 ORDER BY (INDEX_NAME=\'PRIMARY\') DESC,INDEX_NAME,SEQ_IN_INDEX;')
    keys = {}
    for index, col in indexes: keys.setdefault(index, []).append(col)
    key = next((cols for cols in keys.values() if all(c in columns and not columns[c]['nullable'] for c in cols)), [])
    editable = [c for c in CATALOG[table]['fields'] if c in columns and c not in key and
                'GENERATED' not in columns[c]['extra'].upper() and supported(columns[c])]
    reason = '' if info[0][0].lower() == 'innodb' and key else 'Browsing only: editing requires an InnoDB table with a non-null unique key.'
    return dict(table=table, engine=info[0][0], columns=columns, key=key, editable=editable, read_only=reason)


def supported(column):
    return bool(re.match(r'^(tinyint|smallint|mediumint|int|bigint|float|double|decimal|varchar|char|tinytext|text|mediumtext|longtext)\b', column['type'], re.I))


def metadata(s):
    table=s['table']; spec=CATALOG[table]
    result={k:s[k] for k in ('table','key','read_only')}
    result.update(label=spec['label'], add=spec['add'] and not s['read_only'], remove=spec['remove'] and not s['read_only'],
                  impact=impact(table), fields=[])
    for name in dict.fromkeys(s['key']+s['editable']):
        c=s['columns'][name]; lo,hi=bounds(table,name)
        result['fields'].append(dict(c, label=name.replace('_',' '), key=name in s['key'], min=lo, max=hi,
            editable=name in s['editable'], required=not c['nullable'] and not c['default'] and 'auto_increment' not in c['extra']))
    return result


def catalog(engine, args):
    ready(engine)
    names={r[0] for r in rows(engine,'SHOW TABLES;')}
    from client_spells import test_record
    return {'entities':[dict(table=t,label=s['label'],available=t in names) for t,s in CATALOG.items()],
            'running':engine.server_running(), 'compatibility':test_record(engine.work).get('state')=='applied',
            **export_status(engine,names)}


def query_rows(engine, s, where='1', columns=None, limit=51, offset=0):
    columns=columns or list(s['columns'])
    expr=','.join(literal(c)+',IF('+ident(c)+" IS NULL,NULL,HEX(CAST("+ident(c)+' AS BINARY)))' for c in columns)
    order=','.join(ident(c) for c in (s['key'] or columns))
    output=engine.mysql('SELECT JSON_OBJECT('+expr+') FROM '+ident(s['table'])+' WHERE '+where+
        ' ORDER BY '+order+f' LIMIT {limit} OFFSET {offset};')
    records=[]
    for line in output.splitlines()[1:]:
        raw=json.loads(line)
        if sum(len(v or '') for v in raw.values())>2*1024*1024: raise ValueError('Record is too large for the focused editor')
        records.append(raw)
    return records


def values(raw):
    if raw is None: return None
    result={}
    for k,v in raw.items():
        if v is None: result[k]=None; continue
        try: result[k]=bytes.fromhex(v).decode('utf-8')
        except UnicodeError: result[k]='[binary data]'
    return result


def validate(table, c, value):
    name=c['name']
    if value is None:
        if not c['nullable']: raise ValueError(name+': a value is required')
        return None
    if not isinstance(value,(str,int,float)) or isinstance(value,bool): raise ValueError(name+': invalid value')
    text=str(value); typ=c['type'].lower()
    integer=re.match(r'^(tinyint|smallint|mediumint|int|bigint)\b',typ)
    if integer:
        if not re.fullmatch(r'-?\d{1,21}',text): raise ValueError(name+': enter a whole number')
        bits={'tinyint':8,'smallint':16,'mediumint':24,'int':32,'bigint':64}[integer[1]]
        lo,hi=(0,2**bits-1) if 'unsigned' in typ else (-2**(bits-1),2**(bits-1)-1)
        number=int(text)
        if not lo<=number<=hi: raise ValueError(f'{name}: database range is {lo} to {hi}')
        text=str(number)
    elif re.match(r'^(float|double|decimal)\b',typ):
        if len(text)>80: raise ValueError(name+': invalid number')
        try: number=Decimal(text)
        except InvalidOperation: raise ValueError(name+': enter a number') from None
        if not number.is_finite(): raise ValueError(name+': enter a finite number')
        max_value=Decimal('3.4028234663852886e38' if typ.startswith('float') else '1.7976931348623157e308')
        minimum=Decimal('1.401298464324817e-45' if typ.startswith('float') else '4.9406564584124654e-324')
        if abs(number)>max_value or ('unsigned' in typ and number<0) or (not typ.startswith('decimal') and number and abs(number)<minimum):
            raise ValueError(name+': number exceeds database range')
        dec=re.match(r'decimal\((\d+),(\d+)\)',typ)
        if dec:
            precision,scale=map(int,dec.groups())
            if abs(number)>=Decimal(10)**(precision-scale) or number.as_tuple().exponent < -scale:
                raise ValueError(name+': value exceeds database decimal precision')
        text=str(number)
    else:
        if not supported(c): raise ValueError(name+': unsupported field type')
        if len(text)>min(c['length'] or MAX_TEXT,MAX_TEXT) or len(text.encode())>MAX_TEXT:
            raise ValueError(name+': text exceeds supported/database length')
        if '\x00' in text: raise ValueError(name+': NUL characters are not supported')
        if table in ('db_str','spells_new') and any(x in text for x in ('^','\r','\n')):
            raise ValueError(name+': caret and line breaks would corrupt client export records')
        return text
    lo,hi=bounds(table,name)
    if (lo is not None and Decimal(text)<Decimal(lo)) or (hi is not None and Decimal(text)>Decimal(hi)):
        raise ValueError(name+': allowed range '+str(lo or 'unbounded')+' to '+str(hi or 'unbounded'))
    return text


def key_where(s, key):
    if not s['key'] or not isinstance(key,dict) or set(key)!=set(s['key']): raise ValueError('Select a record with its complete unique key')
    return ' AND '.join(ident(k)+'='+literal(validate(s['table'],s['columns'][k],key[k])) for k in s['key'])


def search(engine,args):
    ready(engine); s=schema(engine,args.get('table')); spec=CATALOG[s['table']]
    offset=args.get('offset',0)
    if type(offset) is not int or not 0<=offset<=1000000: raise ValueError('Invalid page offset')
    term=str(args.get('query','')).strip()
    if len(term)>160: raise ValueError('Search is too long')
    columns=list(dict.fromkeys(s['key']+[c for c in spec['summary'] if c in s['columns']]))
    where=[]
    filters=args.get('filters',{})
    if not isinstance(filters,dict) or len(filters)>4: raise ValueError('Invalid related-record filter')
    for k,v in filters.items():
        if k not in s['columns'] or k not in set(spec['fields']+spec['summary']+s['key']): raise ValueError('Unsupported filter')
        where.append(ident(k)+'='+literal(validate(s['table'],s['columns'][k],v)))
    if term:
        # LOCATE treats %, _, apostrophes and backslashes as literal search text.
        where.append('('+' OR '.join('LOCATE(LOWER('+literal(term)+'),LOWER(CAST('+ident(c)+' AS CHAR)))>0' for c in columns)+')')
    found=query_rows(engine,s,' AND '.join(where) or '1',columns=columns,offset=offset)
    records=[]
    for raw in found[:50]:
        v=values(raw)
        records.append({'key':{k:v[k] for k in s['key']},'values':v})
    return dict(metadata(s),columns=columns,records=records,offset=offset,next_offset=offset+50 if len(found)>50 else None)


def links(table,v):
    out=[]
    for source,column,target,target_column,empty in REFERENCES:
        if source==table and target in CATALOG and v.get(column) not in (None,''):
            if int(v[column]) not in empty:
                out.append(dict(label=column+' → '+CATALOG[target]['label'],table=target,filters={target_column:v[column]}))
        if target==table and source in CATALOG and v.get(target_column) not in (None,''):
            out.append(dict(label='Used by '+CATALOG[source]['label']+' ('+column+')',table=source,filters={column:v[target_column]}))
    if table=='merchantlist': out.append(dict(label='This merchant inventory',table=table,filters={'merchantid':v['merchantid']}))
    return out


def detail(engine,args):
    ready(engine); s=schema(engine,args.get('table'))
    found=query_rows(engine,s,key_where(s,args.get('key')),limit=2)
    if len(found)!=1: raise ValueError('Record is missing or no longer uniquely identifiable; search again')
    raw=found[0]; v=values(raw)
    return dict(metadata(s),values=v,revision=fingerprint(raw),links=links(s['table'],v),warnings=warnings(s['table'],v))


def warnings(table,v):
    result=[]
    if table=='spells_new' and int(v.get('id') or 0)>=45000:
        result.append('This spell remains in the server database but is excluded from the client when RoF2 compatibility is enabled.')
    for source,column,target,_,empty in REFERENCES:
        if source==table and target=='spells_new' and v.get(column) is not None and int(v[column])>=45000 and int(v[column]) not in empty:
            result.append(column+': this high spell ID is not made RoF2-compatible by saving or exporting.')
    return result


def reference_checks(engine,table,changed,after):
    checks=[]
    for source,col,target,targetcol,empty in REFERENCES:
        if source!=table or col not in changed or after.get(col) is None or int(after[col]) in empty: continue
        condition='EXISTS(SELECT 1 FROM '+ident(target)+' WHERE '+ident(targetcol)+'='+literal(after[col])+')'
        if rows(engine,'SELECT '+condition+';')[0][0]!='1': raise ValueError(col+': referenced '+target+' record does not exist')
        checks.append(condition)
    for low,high in PAIRS:
        if low in changed or high in changed:
            if after.get(low) is not None and after.get(high) is not None:
                # A maximum level of zero means unrestricted in the loot tables.
                if table=='lootdrop_entries' and int(after[high])==0: continue
                if Decimal(after[low])>Decimal(after[high]): raise ValueError(low+' must not exceed '+high)
    if table=='loottable_entries' and ('mindrop' in changed or 'droplimit' in changed):
        if int(after.get('droplimit') or 0)>0 and int(after.get('mindrop') or 0)>int(after['droplimit']):
            raise ValueError('mindrop must not exceed a nonzero droplimit')
    if table=='aa_ranks':
        for c in ('prev_id','next_id'):
            if c in changed and after.get(c)==after.get('id'): raise ValueError(c+': a rank cannot point to itself')
    return checks


def preview(engine,args):
    ready(engine); table=args.get('table'); s=schema(engine,table); spec=CATALOG[table]
    if s['read_only']: raise ValueError(s['read_only'])
    operation=args.get('action','update')
    if operation not in ('update','insert','delete') or (operation=='insert' and not spec['add']) or (operation=='delete' and not spec['remove']):
        raise ValueError('This operation is not supported for '+spec['label'])
    changes=args.get('values',{})
    if not isinstance(changes,dict) or len(changes)>250: raise ValueError('Invalid field changes')
    raw=None; before=None; key=args.get('key',{})
    if operation!='insert':
        found=query_rows(engine,s,key_where(s,key),limit=2)
        if len(found)!=1 or fingerprint(found[0])!=args.get('revision'): raise ValueError('Record changed since it was opened. Reload it and review your edit again.')
        raw=found[0]; before=values(raw)
    if operation=='delete' and changes: raise ValueError('Delete preview must not include field edits')
    allowed=set(s['editable']) | (set(s['key']) if operation=='insert' else set())
    if set(changes)-allowed: raise ValueError('Unsupported or immutable field: '+', '.join(sorted(set(changes)-allowed)))
    normalized={k:validate(table,s['columns'][k],v) for k,v in changes.items()}
    if operation=='update': normalized={k:v for k,v in normalized.items() if v!=before[k]}
    if operation=='update' and not normalized: raise ValueError('No changed fields to save')
    after=None if operation=='delete' else dict(before or {},**normalized)
    if operation=='insert':
        for name,c in s['columns'].items():
            if not c['nullable'] and not c['default'] and not c['extra'] and name not in normalized:
                raise ValueError('Required field '+name+' is missing; this schema may need the SQL workspace')
        if not all(k in normalized for k in s['key']): raise ValueError('Enter every unique key field; IDs are never assigned automatically')
        for low,high in PAIRS:
            if (low in normalized or high in normalized) and low in s['columns'] and high in s['columns'] and not {low,high}<=set(normalized):
                raise ValueError('Enter both '+low+' and '+high+' so their range can be validated')
        key={k:normalized[k] for k in s['key']}
        if query_rows(engine,s,key_where(s,key),columns=s['key'],limit=1): raise ValueError('That record key already exists')
    checks=reference_checks(engine,table,normalized,after or {})
    from engine import atomic_json
    folder=engine.work/'run/spire-previews'; folder.mkdir(exist_ok=True)
    for old in folder.glob('*.json'):
        if time.time()-old.stat().st_mtime>TTL: old.unlink()
    if len(list(folder.glob('*.json')))>=100: raise ValueError('Too many unsaved previews; wait for older previews to expire')
    token=secrets.token_hex(24)
    document=dict(table=table,action=operation,key=key,raw=raw,before=before,after=after,changes=normalized,
                  schema=fingerprint(s),database=engine.config['database'],created=time.time(),checks=checks)
    atomic_json(folder/(token+'.json'),document)
    fields=list(normalized) if operation=='update' else list((before if operation=='delete' else normalized) or {})
    return {'token':token,'table':table,'action':operation,'key':key,'changes':[dict(field=k,before=(before or {}).get(k),after=(after or {}).get(k)) for k in fields],
            'warnings':warnings(table,after or before or {}),'impact':impact(table),
            'message':'Review this change. Saving first creates a full database backup; preview expires in 30 minutes.'}


def audit_exists(engine):
    return bool(rows(engine,'SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(AUDIT)+';'))


def export_status(engine,names=None):
    exists=AUDIT in names if names is not None else audit_exists(engine)
    if not exists: return {'pending_export':0}
    return {'pending_export':int(rows(engine,'SELECT COUNT(*) FROM '+ident(AUDIT)+' WHERE client_data=1 AND exported_file IS NULL;')[0][0])}


def apply(engine,args):
    ready(engine,writing=True)
    token=args.get('token','')
    if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{48}',token): raise ValueError('Review a save preview first')
    path=engine.work/'run/spire-previews'/(token+'.json')
    if not path.is_file() or path.is_symlink(): raise ValueError('Preview is missing or already saved; preview again')
    p=json.loads(path.read_text()); table=p['table']; s=schema(engine,table)
    if time.time()-p['created']>TTL or p['database']!=engine.config['database'] or fingerprint(s)!=p['schema']:
        raise ValueError('Preview expired or database schema changed; reload and preview again')
    current=query_rows(engine,s,key_where(s,p['key']),limit=2)
    if current!=([p['raw']] if p['raw'] is not None else []): raise ValueError('Record changed after preview; reload and preview again')
    checks=reference_checks(engine,table,p['changes'],p['after'] or {})
    backup=engine.backup_database({})['file']
    ready(engine,writing=True); engine.check_cancel()
    # A durable audit entry and the actual edit commit in the same transaction.
    engine.mysql('CREATE TABLE IF NOT EXISTS '+ident(AUDIT)+' (id varchar(48) PRIMARY KEY, created_at datetime(6) NOT NULL,'
        ' content_type varchar(64) NOT NULL, action varchar(16) NOT NULL, payload longtext NOT NULL,'
        ' backup_file text NOT NULL, client_data tinyint NOT NULL, exported_file text NULL) ENGINE=InnoDB;')
    audit_engine=rows(engine,'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='+literal(AUDIT)+';')
    if audit_engine[0][0].lower()!='innodb': raise ValueError('Spire change history must use InnoDB; no edit was saved')
    marker=engine.work/'backups/spire/enabled'; marker.parent.mkdir(exist_ok=True); marker.touch()
    guard='INSERT INTO `_trasc_spire_guard` SELECT 1 WHERE NOT ('
    statements=["SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';",
        'CREATE TEMPORARY TABLE `_trasc_spire_guard` (id int PRIMARY KEY) ENGINE=InnoDB;',
        'INSERT INTO `_trasc_spire_guard` VALUES (1);','START TRANSACTION;']
    for check in checks: statements.append(guard+check+');')
    where=key_where(s,p['key'])
    if p['raw'] is not None:
        # Compare every original column byte-for-byte, including custom fields and NULL.
        where+=' AND '+' AND '.join('BINARY '+ident(k)+' <=> '+('NULL' if v is None else "X'"+v+"'") for k,v in p['raw'].items())
    if p['action']=='update':
        statements.append('UPDATE '+ident(table)+' SET '+','.join(ident(k)+'='+literal(v) for k,v in p['changes'].items())+' WHERE '+where+';')
    elif p['action']=='delete': statements.append('DELETE FROM '+ident(table)+' WHERE '+where+';')
    else:
        statements.append('INSERT INTO '+ident(table)+' ('+','.join(ident(k) for k in p['changes'])+') VALUES ('+','.join(literal(v) for v in p['changes'].values())+');')
    statements.append('SET @spire_affected=ROW_COUNT();')
    statements.append(guard+'@spire_affected=1);')
    payload={k:p[k] for k in ('table','action','key','before','after','changes')}
    statements.append('INSERT INTO '+ident(AUDIT)+' (id,created_at,content_type,action,payload,backup_file,client_data) VALUES ('+
        ','.join((literal(token),'UTC_TIMESTAMP(6)',literal(table),literal(p['action']),literal(json.dumps(payload,ensure_ascii=False)),literal(backup),'1' if CATALOG[table]['export'] else '0'))+');')
    statements.append('COMMIT;')
    try: engine.mysql(''.join(statements),timeout=120)
    except (ValueError,TimeoutError,subprocess.TimeoutExpired) as e:
        # If the response was lost after COMMIT, the durable audit ID resolves the outcome.
        if not rows(engine,'SELECT id FROM '+ident(AUDIT)+' WHERE id='+literal(token)+';'):
            raise ValueError('Save did not commit. The record may have changed or validation failed. Reload and preview again. '+str(e)) from e
    path.unlink(missing_ok=True)
    engine.log('Spire saved '+table+' '+p['action']+'; audit '+token+'; backup '+backup)
    return dict(message='Saved. '+impact(table),backup=backup,id=token,table=table,key=p['key'],action=p['action'],**export_status(engine))


def history(engine,args):
    ready(engine)
    if not audit_exists(engine): return {'entries':[],'next_offset':None,'pending_export':0}
    offset=args.get('offset',0)
    if type(offset) is not int or not 0<=offset<=1000000: raise ValueError('Invalid page offset')
    result=rows(engine,'SELECT id,created_at,HEX(payload),HEX(backup_file),COALESCE(HEX(exported_file),\'\') FROM '+ident(AUDIT)+
        f' ORDER BY created_at DESC,id DESC LIMIT 21 OFFSET {offset};')
    entries=[dict(id=r[0],created=r[1],change=json.loads(bytes.fromhex(r[2])),backup=bytes.fromhex(r[3]).decode(),
                  exported=bytes.fromhex(r[4]).decode() if r[4] else None) for r in result[:20]]
    return dict(entries=entries,next_offset=offset+20 if len(result)>20 else None,**export_status(engine))


def record_export(engine,result):
    if not (engine.work/'backups/spire/enabled').exists() or not audit_exists(engine): return
    engine.mysql('UPDATE '+ident(AUDIT)+' SET exported_file='+literal(result['file'])+' WHERE client_data=1 AND exported_file IS NULL;')


def dispatch(engine,operation,args):
    return {'spire_catalog':catalog,'spire_search':search,'spire_detail':detail,'spire_preview':preview,
            'spire_apply':apply,'spire_history':history}[operation](engine,args)
