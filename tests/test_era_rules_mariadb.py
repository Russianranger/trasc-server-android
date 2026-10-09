"""Real MariaDB atomicity/restore checks; opt in with ERARULES_MARIADB=1.

Starts an isolated Unix-socket-only database using PEQ's table shapes. No
existing database, system service, server binary or imported client is used.
ERARULES_MARIADB_PREFIX optionally selects an extracted MariaDB package tree.
"""
import copy
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import era_rules as era
from rule_catalog import metadata


class FixtureEngine:
    profile = 'traditional'
    def __init__(self, case):
        self.case = case
        self.work = case.work
        self.config = {'database': 'peq', 'database_imported': True, 'workers': 3, 'rules_pending_restart': False}
        self.running = False
    def ensure_db(self): pass
    def server_running(self): return self.running
    def save(self): (self.work / 'settings.json').write_text(json.dumps(self.config))
    def mysql(self, query, database=True, timeout=30):
        command = [self.case.tools['mariadb'], '--no-defaults', '--socket=' + str(self.case.socket), '--user=root', '--batch', '--raw']
        if database: command.append('peq')
        result = subprocess.run(command, input=query, text=True, capture_output=True, timeout=timeout, env=self.case.env)
        if result.returncode:
            raise ValueError(result.stderr[-3000:])
        return result.stdout
    def backup_database(self, args):
        target = self.work / 'backups' / ('backup-' + str(len(list((self.work / 'backups').iterdir()))) + '.sql.gz')
        command = [self.case.tools['mariadb-dump'], '--no-defaults', '--socket=' + str(self.case.socket), '--user=root', '--lock-all-tables', 'peq']
        result = subprocess.run(command, capture_output=True, check=True, env=self.case.env)
        with gzip.open(target, 'wb') as output: output.write(result.stdout)
        return {'file': str(target.relative_to(self.work))}


@unittest.skipUnless(os.environ.get('ERARULES_MARIADB') == '1', 'Set ERARULES_MARIADB=1 to run the isolated real database fixture')
class EraMariaDBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='trasc-era-db-')
        cls.root = Path(cls.tmp.name)
        cls.env = os.environ.copy()
        prefix = os.environ.get('ERARULES_MARIADB_PREFIX')
        if prefix:
            basedir = Path(prefix) / 'usr'
            cls.env['LD_LIBRARY_PATH'] = str(basedir / 'lib/x86_64-linux-gnu') + ':' + cls.env.get('LD_LIBRARY_PATH', '')
            cls.tools = {name: str(basedir / ('sbin' if name == 'mariadbd' else 'bin') / name) for name in ('mariadb', 'mariadbd', 'mariadb-install-db', 'mariadb-dump')}
            cls.env['PATH'] = str(basedir / 'bin') + ':' + cls.env['PATH']
        else:
            basedir = Path('/usr')
            cls.tools = {name: shutil.which(name) for name in ('mariadb', 'mariadbd', 'mariadb-install-db', 'mariadb-dump')}
        if not all(cls.tools.values()): raise RuntimeError('MariaDB tools are required for the era integration check')
        data = cls.root / 'data'
        cls.socket = cls.root / 'mysql.sock'
        result = subprocess.run([cls.tools['mariadb-install-db'], '--no-defaults', '--basedir=' + str(basedir), '--datadir=' + str(data), '--auth-root-authentication-method=normal', '--skip-test-db', '--force', '--skip-name-resolve'], env=cls.env, capture_output=True, text=True)
        if result.returncode: raise RuntimeError(result.stdout[-2000:] + result.stderr[-2000:])
        cls.log = (cls.root / 'daemon.log').open('wb')
        command = [cls.tools['mariadbd'], '--no-defaults', '--basedir=' + str(basedir), '--datadir=' + str(data), '--socket=' + str(cls.socket), '--pid-file=' + str(cls.root / 'mysql.pid'), '--skip-networking', '--innodb-use-native-aio=0']
        if os.getuid() == 0: command.append('--user=root')
        cls.daemon = subprocess.Popen(command, env=cls.env, stdout=cls.log, stderr=cls.log)
        for _ in range(100):
            if cls.daemon.poll() is not None:
                cls.log.flush()
                raise RuntimeError((cls.root / 'daemon.log').read_text()[-3000:])
            result = subprocess.run([cls.tools['mariadb'], '--no-defaults', '--socket=' + str(cls.socket), '--user=root', '-e', 'SELECT 1'], env=cls.env, capture_output=True)
            if result.returncode == 0: break
            time.sleep(.1)
        else: raise RuntimeError('The isolated MariaDB did not start')
    @classmethod
    def tearDownClass(cls):
        cls.daemon.terminate()
        cls.daemon.wait(timeout=20)
        cls.log.close()
        cls.tmp.cleanup()
    def setUp(self):
        self.work = self.root / self._testMethodName
        for name in ('run', 'backups', 'logs'): (self.work / name).mkdir(parents=True)
        self.engine = FixtureEngine(self)
        self.engine.mysql("DROP DATABASE IF EXISTS peq; CREATE DATABASE peq CHARACTER SET utf8mb4;", database=False)
        self.engine.mysql("""
        CREATE TABLE rule_sets (ruleset_id TINYINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255) NOT NULL DEFAULT '') ENGINE=InnoDB;
        CREATE TABLE rule_values (ruleset_id TINYINT UNSIGNED NOT NULL DEFAULT 0, rule_name VARCHAR(64) NOT NULL DEFAULT '', rule_value TEXT NOT NULL DEFAULT '', notes TEXT NULL, PRIMARY KEY(ruleset_id,rule_name)) ENGINE=InnoDB;
        CREATE TABLE variables (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, varname VARCHAR(25) NOT NULL DEFAULT '', value TEXT NOT NULL, information TEXT NOT NULL, ts TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP) ENGINE=InnoDB;
        CREATE TABLE zone (id INT NOT NULL PRIMARY KEY, short_name VARCHAR(32) NOT NULL, zoneidnumber INT NOT NULL, version INT NOT NULL, ruleset INT UNSIGNED NOT NULL DEFAULT 0, min_status INT NOT NULL DEFAULT 0) ENGINE=InnoDB;
        CREATE TABLE character_data (id INT PRIMARY KEY, level INT, experience INT) ENGINE=InnoDB;
        INSERT INTO character_data VALUES (1,70,12345678);
        INSERT INTO rule_sets VALUES (1,'default'),(2,'pop+'),(20,'fix_pathing_z');
        INSERT INTO rule_values VALUES (1,'Character:MaxLevel','65',NULL),(1,'Character:ExpMultiplier','1.7','Keep XP'),(1,'Zone:StateSavingOnShutdown','true','Keep state'),(2,'Character:ExpMultiplier','2.25','Raid preference');
        INSERT INTO variables(id,varname,value,information,ts) VALUES (3,'Other','keep','unrelated',NULL);
        INSERT INTO zone VALUES (9,'qeynos',1,0,0,0),(10,'velketor',112,0,1,0),(11,'vexthal',158,0,2,0),(12,'vexthal',158,0,20,7);
        """)
        spec = era.manifest()
        rules = {}
        for preset in spec['presets'].values():
            for name, value in preset['rules'].items():
                item = value['value']
                rules[name] = metadata(name, 'bool' if item in ('true', 'false') else ('int' if item.lstrip('-').isdigit() else 'real'), default=item)
        self.catalog_patch = patch.object(era, 'catalog', return_value=(rules, spec['rule_catalog_sha256']))
        self.catalog_patch.start()
    def tearDown(self): self.catalog_patch.stop()
    def select(self, key):
        preview = era.preview(self.engine, {'era': key})
        result = era.apply(self.engine, {'era': key, 'review_token': preview['review_token']}, restore=key == 'default')
        return preview, result
    def values(self, query): return [line.split('\t') for line in self.engine.mysql(query).splitlines()[1:]]
    def test_all_eras_restore_exact_default_absence_and_zone_overrides(self):
        before = era.snapshot(self.engine)
        for key, cap, expansion in (('velious', '60', '2'), ('luclin', '60', '3'), ('pop', '65', '4')):
            review, result = self.select(key)
            self.assertEqual(result['zone_count'], 4)
            self.assertEqual(self.values("SELECT rule_value FROM rule_values WHERE ruleset_id=1 AND rule_name='Character:MaxLevel';"), [[cap]])
            self.assertEqual(self.values("SELECT rule_value FROM rule_values WHERE ruleset_id=1 AND rule_name='Expansion:CurrentExpansion';"), [[expansion]])
            current = era.snapshot(self.engine)
            self.assertEqual(len(current['own']['baseline']['default_rules']), 47)
            self.assertEqual(self.values('SELECT COUNT(*) FROM zone WHERE ruleset=0;'), [['0']])
        self.select('default')
        after = era.snapshot(self.engine)
        self.assertEqual(before['raw']['variables'], after['raw']['variables'])
        self.assertEqual(before['raw']['zone'], after['raw']['zone'])
        self.assertEqual(before['rule_map'][1], after['rule_map'][1])
        self.assertEqual(self.values('SELECT level,experience FROM character_data;'), [['70', '12345678']])
        self.assertEqual(self.engine.config['workers'], 3)
        self.assertEqual(len(list((self.work / 'backups').glob('*.gz'))), 4)
    def test_composite_customizations_and_reselection_edits_survive(self):
        _, result = self.select('velious')
        state = era.snapshot(self.engine)
        record = state['own']['sets']['velious']
        target = record['composites']['2']
        self.assertEqual(self.values('SELECT rule_value,notes FROM rule_values WHERE ruleset_id=' + str(target) + " AND rule_name='Character:ExpMultiplier';"), [['2.25', 'Raid preference']])
        self.engine.mysql("UPDATE rule_values SET rule_value='54' WHERE ruleset_id=" + str(result['ruleset_id']) + " AND rule_name='Character:MaxLevel';")
        review, again = self.select('velious')
        self.assertTrue(review['manual_edits'])
        self.assertEqual(again['ruleset_id'], result['ruleset_id'])
        self.assertEqual(self.values("SELECT rule_value FROM rule_values WHERE ruleset_id=1 AND rule_name='Character:MaxLevel';"), [['54']])
        self.select('default')
        self.select('velious')
        self.assertEqual(self.values('SELECT rule_value FROM rule_values WHERE ruleset_id=' + str(result['ruleset_id']) + " AND rule_name='Character:MaxLevel';"), [['54']])
    def test_restore_exact_null_timestamp_and_notes_and_original_nondefault_active(self):
        self.engine.mysql("INSERT INTO variables(id,varname,value,information,ts) VALUES (8,'RuleSet','pop+','Original row',NULL); INSERT INTO rule_values VALUES (1,'Expansion:CurrentExpansion','-1','Original filter');")
        before = era.snapshot(self.engine)
        self.select('luclin')
        review = era.preview(self.engine, {'era': 'default', 'mode': 'previous'})
        era.apply(self.engine, {'review_token': review['review_token'], 'mode': 'previous'}, restore=True)
        after = era.snapshot(self.engine)
        self.assertEqual(before['raw']['variables'], after['raw']['variables'])
        self.assertEqual(before['raw']['zone'], after['raw']['zone'])
        self.assertEqual(before['rule_map'][1], after['rule_map'][1])
    def test_stale_review_duplicate_variable_and_zone_conflict_reject(self):
        review = era.preview(self.engine, {'era': 'pop'})
        self.engine.mysql("UPDATE variables SET value='changed' WHERE id=3;")
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            era.apply(self.engine, {'era': 'pop', 'review_token': review['review_token']})
        self.assertEqual(self.values('SELECT COUNT(*) FROM rule_sets;'), [['3']])
        self.engine.mysql("INSERT INTO variables(varname,value,information) VALUES ('RuleSet','default','one'),('ruleset','default','two');")
        with self.assertRaisesRegex(ValueError, 'duplicate RuleSet'):
            era.preview(self.engine, {'era': 'pop'})
        self.engine.mysql("DELETE FROM variables WHERE LOWER(varname)='ruleset';")
        self.select('pop')
        self.engine.mysql('UPDATE zone SET ruleset=2 WHERE id=9;')
        with self.assertRaisesRegex(ValueError, 'managed zone'):
            era.preview(self.engine, {'era': 'default'})
    def test_failure_after_first_writes_rolls_back_every_table(self):
        state = era.snapshot(self.engine)
        result = era.plan(state, 'pop')
        self.engine.mysql('CREATE TABLE ' + era.ident(era.REGISTRY) + ' (id TINYINT UNSIGNED PRIMARY KEY,manifest MEDIUMTEXT NOT NULL) ENGINE=InnoDB;')
        sql = era.transaction(state, result).replace('COMMIT;', 'INSERT INTO _trasc_era_guard VALUES(0); COMMIT;')
        with self.assertRaisesRegex(ValueError, 'CONSTRAINT'):
            self.engine.mysql(sql)
        after = era.snapshot(self.engine)
        for table in era.TABLES: self.assertEqual(state['raw'][table], after['raw'][table])
        self.assertFalse(after['data'][era.REGISTRY])
    def test_atomic_guard_rejects_data_schema_engine_and_trigger_races(self):
        for kind in ('data', 'engine', 'trigger', 'column'):
            with self.subTest(kind=kind):
                state = era.snapshot(self.engine)
                result = era.plan(state, 'pop')
                self.engine.mysql('CREATE TABLE IF NOT EXISTS ' + era.ident(era.REGISTRY) + ' (id TINYINT UNSIGNED PRIMARY KEY,manifest MEDIUMTEXT NOT NULL) ENGINE=InnoDB;')
                if kind == 'data': self.engine.mysql("UPDATE rule_values SET rule_value='66' WHERE ruleset_id=1 AND rule_name='Character:MaxLevel';")
                if kind == 'engine': self.engine.mysql('ALTER TABLE rule_values ENGINE=MyISAM;')
                if kind == 'trigger': self.engine.mysql("CREATE TRIGGER unexpected AFTER INSERT ON rule_sets FOR EACH ROW UPDATE character_data SET experience=0;")
                if kind == 'column': self.engine.mysql('ALTER TABLE variables ADD COLUMN test_extra INT DEFAULT 4;')
                with self.assertRaises(ValueError): self.engine.mysql(era.transaction(state, result))
                self.assertEqual(self.values('SELECT COUNT(*) FROM rule_sets;'), [['3']])
                self.assertEqual(self.values('SELECT experience FROM character_data;'), [['12345678']])
                if kind == 'engine': self.engine.mysql('ALTER TABLE rule_values ENGINE=InnoDB;')
                if kind == 'trigger': self.engine.mysql('DROP TRIGGER unexpected;')
                if kind == 'column': self.engine.mysql('ALTER TABLE variables DROP COLUMN test_extra;')
    def test_myisam_is_rejected_without_a_backup_or_mutation(self):
        self.engine.mysql('ALTER TABLE variables ENGINE=MyISAM;')
        with self.assertRaisesRegex(ValueError, 'InnoDB'):
            era.preview(self.engine, {'era': 'pop'})
        self.assertFalse(list((self.work / 'backups').iterdir()))
    def test_named_default_id_and_signed_tinyint_guards(self):
        self.engine.mysql('UPDATE rule_sets SET ruleset_id=7 WHERE ruleset_id=1; UPDATE rule_values SET ruleset_id=7 WHERE ruleset_id=1; UPDATE zone SET ruleset=7 WHERE ruleset=1;')
        self.select('velious')
        _, result = self.select('default')
        self.assertEqual(result['ruleset_id'], 7)
        self.engine.mysql('ALTER TABLE rule_sets MODIFY ruleset_id TINYINT NOT NULL AUTO_INCREMENT;')
        with self.assertRaisesRegex(ValueError, '0–255'):
            era.preview(self.engine, {'era': 'pop'})


if __name__ == '__main__': unittest.main()
