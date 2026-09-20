"""Real MariaDB lifecycle and rollback for the cross-zone ferry installer."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import zipfile
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'backend'),'/opt/trasc']
from engine import Engine
import ferry_service as ferry
import boat_trial


def ddl(seed):
    wanted=set(ferry.OWNED)|set(boat_trial.AUX)|{'data_buckets','grid','grid_entries'}
    result={};active=None;lines=[]
    with zipfile.ZipFile(seed) as z,z.open('release-peq.sql') as source:
        for raw in source:
            line=raw.decode();match=re.match(r'CREATE TABLE `([^`]+)`',line)
            if match and match[1] in wanted:active=match[1];lines=[]
            if active:
                lines.append(line)
                if line.startswith(') ENGINE='):
                    result[active]=''.join(lines).replace('utf8mb4_uca1400_ai_ci','utf8mb4_unicode_ci');active=None
    assert set(result)==wanted,wanted-set(result)
    return ''.join(result.values())


def run(seed):
    with tempfile.TemporaryDirectory(prefix='ferry-service-') as temp:
        e=Engine(temp);port=os.environ.get('TRASC_TEST_MYSQL_PORT')
        if port:
            e.config['database']='ferry_test_'+secrets.token_hex(4)
            e.mysql_options.write_text('[client]\nuser=root\npassword=test\nprotocol=tcp\nhost=127.0.0.1\nport='+port+'\ndefault-character-set=utf8mb4\n')
            e.ensure_db=lambda:None
            e.mysql('CREATE DATABASE '+e.config['database']+';',database=False)
        try:
            e.ensure_db();e.config['database_imported']=True
            e.mysql(ddl(seed)+"""
                INSERT INTO zone (id,zoneidnumber,short_name,long_name,version,idle_when_empty) VALUES
                    (1,1,'qeynos','South Qeynos',0,1),(24,24,'erudnext','Erudin',0,0),(98,98,'erudsxing',"Erud's Crossing",0,1),(2,2,'qeynos2','North Qeynos',0,1);
                INSERT INTO launcher_zones VALUES ('trasc','qeynos',7009),('disabled','erudnext',0);
                INSERT INTO npc_types(id,name,race,gender) VALUES (98054,'Golden_Maiden',72,2);
                CREATE TABLE account (id int PRIMARY KEY,status int) ENGINE=InnoDB;
                CREATE TABLE character_data (id int PRIMARY KEY,name varchar(50)) ENGINE=InnoDB;
                INSERT INTO account VALUES (1,0);INSERT INTO character_data VALUES (1,'Untouched');
            """)
            modules=e.work/'server/quests/lua_modules';modules.mkdir(parents=True)
            (modules/'json.lua').write_text('-- existing JSON module\n')
            (modules/'unrelated.lua').write_text('-- preserve me\n')
            original={t:e.mysql('SELECT * FROM '+t+' ORDER BY '+('id' if t!='launcher_zones' else 'launcher,zone')+';') for t in ('zone','launcher_zones','npc_types','account','character_data')}
            def reject(fn,phrase):
                try:fn()
                except ValueError as error:assert phrase in str(error),(phrase,str(error))
                else:raise AssertionError('Expected rejection: '+phrase)
            def perform(action):return ferry.apply(e,{'token':ferry.preview(e,{'action':action})['token']})
            with patch.object(ferry.server_ferry,'deployed',return_value=False):
                reject(lambda:ferry.preview(e,{'action':'install'}),'Build and deploy')
            with patch.object(ferry.server_ferry,'deployed',return_value=True):
                p=ferry.preview(e,{'action':'install'})
                assert not (modules/'trasc_ferry.lua').exists()
                with patch.object(e,'backup_database',side_effect=ValueError('backup failed')):
                    reject(lambda:ferry.apply(e,{'token':p['token']}),'backup failed')
                assert not (modules/'trasc_ferry.lua').exists()
                result=ferry.apply(e,{'token':p['token']});assert Path(temp,result['backup']).stat().st_size
                own=ferry.own_record(e,boat_trial.tables(e));m=own['manifest'];ids=m['ids']
                assert ferry.inspect(e,'reset')['actual']==m['rows']
                assert e.mysql('SELECT idle_when_empty FROM zone WHERE id IN (1,24,98);').splitlines()[1:]==['0','0','0']
                assert len(m['files'])==5 and all(ferry.digest(e.work/n)==v for n,v in m['files'].items())
                reject(lambda:perform('install'),'already installed')
                reject(lambda:ferry.apply(e,{'token':p['token']}),'already used')
                # Intervening owned edits and additional external references are rejected.
                e.mysql(f"UPDATE npc_types SET lastname='Edited' WHERE id={ids['ship']};")
                reject(lambda:perform('reset'),'content, references or quests changed')
                e.mysql(f"UPDATE npc_types SET lastname=NULL WHERE id={ids['ship']};")
                e.mysql(f"INSERT INTO spawnentry(spawngroupID,npcID,chance) VALUES(900,{ids['ship']},100);")
                reject(lambda:perform('remove'),'content, references or quests changed')
                e.mysql(f"DELETE FROM spawnentry WHERE spawngroupID=900;")
                # Guarded transaction failure restores the file half and keeps registration.
                p=ferry.preview(e,{'action':'remove'});backup=e.backup_database
                def racing_backup(args):
                    out=backup(args);e.mysql(f"UPDATE npc_types SET lastname='Race' WHERE id={ids['ship']};");return out
                with patch.object(e,'backup_database',side_effect=racing_backup):
                    reject(lambda:ferry.apply(e,{'token':p['token']}),'did not commit')
                assert (modules/'trasc_ferry.lua').exists()
                e.mysql(f"UPDATE npc_types SET lastname=NULL WHERE id={ids['ship']};")
                # Saved state cleanup is limited to owned IDs, including dynamic ship rows.
                e.mysql(f"""INSERT INTO zone_state_spawns(zone_id,npc_id,spawn2_id,spawngroup_id,x,y,z,heading,respawn_time,variance)
                    VALUES (98,{ids['ship']},0,0,999,0,0,0,60,0),(98,98054,5,5,42,0,0,0,60,0);""")
                key=ferry.namespace(m['installation'])+'_rider_1'
                e.mysql('INSERT INTO data_buckets (`key`,value) VALUES ('+ferry.literal(key)+',\'{"kind":"ride","epoch":"old"}\');')
                reject(lambda:perform('remove'),'passenger has a saved ferry position')
                perform('reset')
                assert e.mysql('SELECT x FROM zone_state_spawns;').splitlines()[1:]==['42']
                assert ferry.bucket(e,key)['kind']=='ride' # Reset retains recovery for login.
                e.mysql('DELETE FROM data_buckets WHERE BINARY `key`=BINARY '+ferry.literal(key)+';')
                # The boot reset retains all unrelated state and emits one known starting pose.
                ferry.boot(e);state=ferry.bucket(e,ferry.namespace(m['installation'])+'_state')
                assert (state['phase'],state['point'],state['pose']['z'])==(1,8,-39.5)
                # Lost COMMIT response is resolved from audit, without restoring removed quests.
                p=ferry.preview(e,{'action':'remove'});mysql=e.mysql
                def lost(sql,**kwargs):
                    out=mysql(sql,**kwargs)
                    if sql.endswith('COMMIT;'):raise ValueError('Lost response')
                    return out
                with patch.object(e,'mysql',side_effect=lost):assert not ferry.apply(e,{'token':p['token']})['active']
                assert not (modules/'trasc_ferry.lua').exists()
                assert (modules/'unrelated.lua').read_text()=='-- preserve me\n'
                for t,expected in original.items():
                    assert e.mysql('SELECT * FROM '+t+' ORDER BY '+('id' if t!='launcher_zones' else 'launcher,zone')+';')==expected,t
                assert e.mysql('SELECT x FROM zone_state_spawns;').splitlines()[1:]==['42']
                assert not (e.work/'run/ferry-change.json').exists()
                print('PASS: real-seed cross-zone install/reset/removal, native build gate, full backups, scoped state, quest rollback, passenger recovery retention, lost-response audit, and original settings restoration',flush=True)
        finally:
            if port:e.mysql('DROP DATABASE IF EXISTS '+e.config['database']+';',database=False)
            e.shutdown()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',required=True);run(p.parse_args().seed)
