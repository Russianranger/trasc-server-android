"""Run in the ARM64 runtime image. Exercises a real MariaDB, not a mock."""
import gzip
import shutil
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
        # Real PEQ seeds can omit variables.RuleSet and put default at a nonzero ID.
        # A numerically smaller override must still win over default values.
        engine.mysql("UPDATE rule_sets SET ruleset_id=7 WHERE ruleset_id=0; UPDATE rule_values SET ruleset_id=7 WHERE ruleset_id=0; DELETE FROM variables WHERE varname='RuleSet'; INSERT INTO rule_sets VALUES (3,'custom'); INSERT INTO rule_values VALUES (3,'Character:ExpMultiplier','3','override');")
        assert engine.gameplay({})['selected']==7
        custom=engine.gameplay({'ruleset':3})
        assert custom['values']['Character:ExpMultiplier']=={'value':'3','ruleset':3}
        assert custom['values']['Zone:StateSavingOnShutdown']=={'value':'false','ruleset':7}
        engine.mysql("INSERT INTO variables VALUES ('RuleSet','custom');")
        assert engine.gameplay({})['selected']==3
        unauth=subprocess.run(['mariadb','--no-defaults','--host=127.0.0.1','--port=13306','--user=root','-e','SELECT 1;'],capture_output=True)
        assert unauth.returncode!=0,'Database root must not accept empty TCP credentials'
        engine.network({'ip':'192.168.1.34'})
        # Full editor: imported source defines types; DB-only rules remain visible.
        src=Path(work)/'sources/current'
        (src/'common').mkdir(parents=True);(src/'zone').mkdir()
        (src/'CMakeLists.txt').write_text('project(test)')
        (src/'common/ruletypes.h').write_text('''RULE_INT(World, MaxClientsPerIP, -1, "-1 disables the cap")
RULE_REAL(Character, RaidExpMultiplier, 0.3, "Raid penalty fraction")
RULE_REAL(Character, TradeskillUpMinChance, 25.0, "Cannot go below 2.5")
RULE_STRING(Custom, Greeting, "hello", "Greeting text")
''')
        engine.mysql("INSERT INTO rule_values VALUES (7,'Custom:UnknownDatabaseRule','keep me','DB-only rule');")
        all_rules=engine.gameplay({'ruleset':3})
        assert 'Custom:UnknownDatabaseRule' in all_rules['values']
        assert all_rules['values']['World:MaxClientsPerIP']['value']=='-1'
        assert all_rules['metadata']['World:MaxClientsPerIP']['type']=='int'
        engine.save_gameplay({'ruleset':3,'values':{'World:MaxClientsPerIP':'-1','Custom:Greeting':'Hello\tworld\nnext line'}})
        rules=engine.gameplay({'ruleset':3})
        assert rules['values']['Custom:Greeting']['value']=='Hello\tworld\nnext line'
        assert rules['values']['Custom:UnknownDatabaseRule']['ruleset']==7
        try:
            engine.save_gameplay({'ruleset':3,'values':{'Character:ExpMultiplier':'9','Character:RaidExpMultiplier':'1.1','Character:TradeskillUpMinChance':'2'}})
            raise AssertionError('Out-of-bounds rules must fail')
        except ValueError as error:
            assert 'Character:RaidExpMultiplier' in str(error) and 'Character:TradeskillUpMinChance' in str(error)
        assert engine.gameplay({'ruleset':3})['values']['Character:ExpMultiplier']['value']=='3','Invalid batches must not partially save'
        prepared=engine.prepare_session_backup({})
        assert prepared['snapshot'] and engine.db is None
        # Cold physical DB restore into a new workspace, same runtime; no SQL reimport.
        with tempfile.TemporaryDirectory(prefix='restored-',dir='/work') as restored_work:
            shutil.copytree(Path(work)/'database',Path(restored_work)/'database')
            shutil.copy2(Path(work)/'settings.json',Path(restored_work)/'settings.json')
            restored=Engine(restored_work)
            try:
                assert 'test-player' in restored.sql({'query':'SELECT name FROM account;'})['output']
                assert restored.gameplay({'ruleset':3})['values']['Custom:Greeting']['value']=='Hello\tworld\nnext line'
            finally: restored.shutdown()
        print('PASS: real MariaDB seed import, nested ZIP selection, nonzero default ruleset and override inheritance, SQL, backup/restore, root authentication and network settings',flush=True)
        print('PASS: complete rule catalog, atomic invalid-batch rejection, escaped values, clean backup preparation and physical database restore',flush=True)
    finally:engine.shutdown()
