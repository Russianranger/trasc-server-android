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
                INSERT INTO npc_types(id,name,race,gender) VALUES (2000683,'Skif',73,2),(2000684,'Unrelated',1,0);
                INSERT INTO spawngroup(id,name) VALUES (5002829,'Erudin skiff'),(5002830,'Other zone skiff');
                INSERT INTO spawnentry(spawngroupID,npcID,chance) VALUES (5002829,2000683,100),(5002830,2000683,100);
                INSERT INTO spawn2(id,spawngroupID,zone,version,x,y,z) VALUES (2140976,5002829,'erudnext',0,-1402,176,1),(2140977,5002830,'qeynos',0,1,2,3);
                INSERT INTO spawn2_disabled(spawn2_id,instance_id,disabled) VALUES (2140976,0,0),(2140976,7,0);
                CREATE TABLE account (id int PRIMARY KEY,status int) ENGINE=InnoDB;
                CREATE TABLE character_data (id int PRIMARY KEY,name varchar(50)) ENGINE=InnoDB;
                INSERT INTO account VALUES (1,0);INSERT INTO character_data VALUES (1,'Untouched');
            """)
            modules=e.work/'server/quests/lua_modules';modules.mkdir(parents=True)
            (modules/'json.lua').write_text('-- existing JSON module\n')
            (modules/'unrelated.lua').write_text('-- preserve me\n')
            original={t:e.mysql('SELECT * FROM '+t+' ORDER BY '+('id' if t!='launcher_zones' else 'launcher,zone')+';') for t in ('zone','launcher_zones','npc_types','account','character_data','spawn2_disabled')}
            def reject(fn,phrase):
                try:fn()
                except ValueError as error:assert phrase in str(error),(phrase,str(error))
                else:raise AssertionError('Expected rejection: '+phrase)
            def perform(action):return ferry.apply(e,{'token':ferry.preview(e,{'action':action})['token']})
            with patch.object(ferry.server_ferry,'deployed',return_value=False):
                reject(lambda:ferry.preview(e,{'action':'install'}),'Build and deploy')
            with patch.object(ferry.server_ferry,'deployed',return_value=True):
                e.mysql('INSERT INTO spawnentry(spawngroupID,npcID,chance) VALUES (5002829,2000684,50);')
                reject(lambda:ferry.preview(e,{'action':'install'}),'shares a spawn group')
                e.mysql('DELETE FROM spawnentry WHERE npcID=2000684;')
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
                assert e.mysql('SELECT disabled FROM spawn2_disabled WHERE spawn2_id=2140976 ORDER BY instance_id;').splitlines()[1:]==['1','0']
                assert e.mysql('SELECT COUNT(*) FROM spawn2_disabled WHERE spawn2_id=2140977;').splitlines()[1:]==['0']
                e.mysql('UPDATE spawn2_disabled SET disabled=0 WHERE spawn2_id=2140976 AND instance_id=0;')
                reject(lambda:perform('update'),'skiff spawns changed')
                e.mysql('UPDATE spawn2_disabled SET disabled=1 WHERE spawn2_id=2140976 AND instance_id=0;')
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
                # Updating an installed route preserves IDs, player data, and
                # recovery tickets; a failed DB update restores old quest files.
                e.mysql('INSERT INTO data_buckets (`key`,value) VALUES ('+ferry.literal(key)+',\'{"kind":"ride","epoch":"before-update"}\');')
                p=ferry.preview(e,{'action':'update'});before_files={n:(e.work/n).read_bytes() for n in m['files']}
                with patch.object(e,'backup_database',side_effect=racing_backup):
                    reject(lambda:ferry.apply(e,{'token':p['token']}),'did not commit')
                for n,data in before_files.items():assert (e.work/n).read_bytes()==data
                e.mysql(f"UPDATE npc_types SET lastname=NULL WHERE id={ids['ship']};")
                perform('update')
                assert ferry.bucket(e,key)['epoch']=='before-update'
                assert ferry.own_record(e,boat_trial.tables(e))['manifest']['ids']==ids
                assert float(e.mysql(f"SELECT runspeed FROM npc_types WHERE id={ids['ship']};").splitlines()[1])==0.6
                assert '"pause":180' in (modules/'trasc_ferry_config.lua').read_text()
                e.mysql('DELETE FROM data_buckets WHERE BINARY `key`=BINARY '+ferry.literal(key)+';')
                # Saved copies of the disabled skiff must not reappear on boot.
                e.mysql("INSERT INTO zone_state_spawns(zone_id,npc_id,spawn2_id,spawngroup_id,x,y,z,heading,respawn_time,variance) VALUES (24,2000683,2140976,5002829,1,2,3,0,60,0),(1,2000683,2140977,5002830,1,2,3,0,60,0);")
                # The boot reset retains all unrelated state and emits one known starting pose.
                ferry.boot(e);state=ferry.bucket(e,ferry.namespace(m['installation'])+'_state')
                assert (state['phase'],state['point'],state['pose']['z'])==(1,8,-39.5)
                assert e.mysql('SELECT zone_id FROM zone_state_spawns WHERE npc_id=2000683;').splitlines()[1:]==['1']
                snapshot=ferry.diagnostics(e,{})
                assert snapshot['active'] and (e.work/'logs/ferry-state.json').is_file()
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
                # Recreate the 0.5.5 ownership shape: no skiff ownership, older
                # speed and config. Upgrade must work without reinstalling it.
                with patch.object(ferry.route,'HARBOR_SPEED',0.55), patch.object(ferry.route,'PORT_PAUSE',90), patch.object(ferry,'skiff_state',return_value=None):
                    perform('install')
                legacy=ferry.own_record(e,boat_trial.tables(e))['manifest']
                legacy.pop('skiffs',None);legacy.pop('route_revision',None)
                e.mysql('UPDATE '+ferry.REGISTRY+' SET manifest='+ferry.literal(json.dumps(legacy))+' WHERE id=1;')
                assert ferry.status(e,{})['update_available']
                perform('update')
                assert not ferry.status(e,{})['update_available']
                assert ferry.own_record(e,boat_trial.tables(e))['manifest']['ids']==legacy['ids']
                assert e.mysql('SELECT disabled FROM spawn2_disabled WHERE spawn2_id=2140976 ORDER BY instance_id;').splitlines()[1:]==['1','0']
                perform('remove')
                assert e.mysql('SELECT * FROM spawn2_disabled ORDER BY id;')==original['spawn2_disabled']
                print('PASS: real-seed cross-zone install/reset/removal, native build gate, full backups, scoped state, quest rollback, passenger recovery retention, lost-response audit, and original settings restoration',flush=True)
        finally:
            if port:e.mysql('DROP DATABASE IF EXISTS '+e.config['database']+';',database=False)
            e.shutdown()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',required=True);run(p.parse_args().seed)
