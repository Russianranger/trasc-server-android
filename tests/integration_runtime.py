"""Run in the ARM64 runtime image. Exercises a real MariaDB, not a mock."""
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0,'/opt/trasc')
from engine import Engine

with tempfile.TemporaryDirectory(prefix='integration-',dir='/work') as work:
    engine=Engine(work)
    try:
        seed='''CREATE DATABASE `oldpeq`; USE `oldpeq`;
CREATE TABLE account (id int PRIMARY KEY, name varchar(64));
CREATE TABLE character_data (id int PRIMARY KEY, name varchar(64));
CREATE TABLE rule_sets (ruleset_id int PRIMARY KEY, name varchar(64));
CREATE TABLE rule_values (ruleset_id int, rule_name varchar(128), rule_value varchar(128), notes varchar(255), PRIMARY KEY(ruleset_id,rule_name));
CREATE TABLE variables (varname varchar(64), value varchar(128));
CREATE TABLE launcher (name varchar(64) PRIMARY KEY, dynamics int);
INSERT INTO account VALUES (1,'test-player');
INSERT INTO rule_sets VALUES (0,'default');
INSERT INTO variables VALUES ('RuleSet','default');
INSERT INTO rule_values VALUES (0,'Character:ExpMultiplier','0.5','seed'),(0,'Zone:StateSavingOnShutdown','true','seed');
'''
        archive=Path(work)/'incoming/database.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('release-peq.sql',seed)
        engine.import_database({'selection':'incoming/database.zip!release-peq.sql'})
        assert engine.config['database_imported']
        assert 'test-player' in engine.sql({'query':'SELECT name FROM account;'})['output']
        settings=engine.gameplay({});assert settings['values']['Character:ExpMultiplier']['value']=='0.5'
        engine.save_gameplay({'ruleset':0,'workers':4,'values':{'Character:ExpMultiplier':2,'Zone:StateSavingOnShutdown':False}})
        assert engine.gameplay({})['values']['Zone:StateSavingOnShutdown']['value']=='false'
        backup=engine.backup_database({})
        assert Path(work,backup['file']).stat().st_size>0
        engine.sql({'query':"UPDATE account SET name='changed';",'write':True})
        engine.restore_database({'file':backup['file']})
        assert 'test-player' in engine.sql({'query':'SELECT name FROM account;'})['output']
        unauth=subprocess.run(['mariadb','--no-defaults','--host=127.0.0.1','--port=13306','--user=root','-e','SELECT 1;'],capture_output=True)
        assert unauth.returncode!=0,'Database root must not accept empty TCP credentials'
        engine.network({'ip':'192.168.1.34'})
        print('PASS: real MariaDB seed import, nested ZIP selection, rules, SQL, backup/restore, root authentication and network settings',flush=True)
    finally:engine.shutdown()
