"""Exercise the ferry lifecycle against MariaDB and the real seed DDL.

Use --seed ZIP and optional TRASC_TEST_MYSQL_PORT for a disposable service;
otherwise run inside the app's ARM64 runtime. No source seed data is imported.
"""
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
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'backend'), '/opt/trasc']
from engine import Engine
import boat_trial as boats


def ddl(seed):
    wanted = set(boats.KEYS)-{boats.REGISTRY, boats.AUDIT} | set(boats.AUX)
    result = {}; active = None; lines = []
    with zipfile.ZipFile(seed) as z, z.open('release-peq.sql') as source:
        for raw in source:
            line = raw.decode(errors='replace'); match = re.match(r'CREATE TABLE `([^`]+)`', line)
            if match and match[1] in wanted: active = match[1]; lines = []
            if active:
                lines.append(line)
                if line.rstrip().endswith(';'):
                    # MariaDB 10.11 supports the data/schema; 11.4's new default
                    # collation name is immaterial to this isolated DDL fixture.
                    result[active] = ''.join(lines).replace('utf8mb4_uca1400_ai_ci', 'utf8mb4_unicode_ci')
                    active = None
    assert set(result) == wanted, wanted-set(result)
    return ''.join(result.values())


def run(seed):
    with tempfile.TemporaryDirectory(prefix='boat-trial-') as temp:
        e = Engine(temp); external = os.environ.get('TRASC_TEST_MYSQL_PORT')
        if external:
            e.config['database'] = 'boat_trial_test_'+secrets.token_hex(4)
            e.mysql_options.write_text('[client]\nuser=root\npassword=test\nprotocol=tcp\nhost=127.0.0.1\nport='+external+'\ndefault-character-set=utf8mb4\n')
            e.ensure_db = lambda: None
            e.mysql('CREATE DATABASE '+e.config['database']+';', database=False)
        try:
            e.ensure_db(); e.config['database_imported'] = True
            e.mysql(ddl(seed)+'''CREATE TABLE zone(zoneidnumber int,short_name varchar(32)) ENGINE=InnoDB;
                INSERT INTO zone VALUES(98,'erudsxing');
                CREATE TABLE account(id int PRIMARY KEY,status int) ENGINE=InnoDB;
                CREATE TABLE character_data(id int PRIMARY KEY,name varchar(40)) ENGINE=InnoDB;
                INSERT INTO account VALUES(1,0); INSERT INTO character_data VALUES(1,'Untouched');
                INSERT INTO npc_types(id,name,race,gender) VALUES(98054,'Golden_Maiden',72,2);
                INSERT INTO spawngroup(id,name) VALUES(100,'Existing');
                INSERT INTO spawnentry(spawngroupID,npcID,chance) VALUES(100,98054,100);
                INSERT INTO spawn2(id,spawngroupID,zone,pathgrid) VALUES(58419,100,'erudsxing',59);
                INSERT INTO spawn2_disabled(spawn2_id,instance_id,disabled) VALUES(58419,0,1);
                INSERT INTO grid(id,zoneid,type,type2) VALUES(59,98,0,1);
                INSERT INTO grid_entries(gridid,zoneid,number) VALUES(59,98,1);
                ''')
            def reject(fn, phrase):
                try: fn()
                except ValueError as error: assert phrase in str(error), (phrase, str(error))
                else: raise AssertionError('Expected rejection: '+phrase)
            def perform(action):
                return boats.apply(e, {'token': boats.preview(e, {'action': action})['token']})
            def snapshot():
                return {t: e.mysql('SELECT * FROM `'+t+'`;') for t in ('account', 'character_data')}
            original_players = snapshot()
            assert not boats.status(e, {})['active']
            p = boats.preview(e, {'action': 'install'})
            assert not boats.status(e, {})['active']  # Preview is read-only.
            with patch.object(e, 'backup_database', side_effect=ValueError('backup failed')):
                reject(lambda: boats.apply(e, {'token': p['token']}), 'backup failed')
            assert not boats.status(e, {})['active']
            installed = boats.apply(e, {'token': p['token']})
            assert Path(temp, installed['backup']).stat().st_size > 0
            assert boats.status(e, {})['active']
            own = boats.registry(e, boats.tables(e)); ids = own['manifest']['ids']
            # Actual database defaults and full snapshots must round-trip.
            state = boats.inspect(e, 'remove')
            assert state['actual'] == own['manifest']['rows']
            assert ids['npc'] != 98054 and ids['spawn'] != 58419 and ids['grid'] != 59
            reject(lambda: perform('install'), 'already installed')
            reject(lambda: boats.apply(e, {'token': p['token']}), 'already used')
            assert snapshot() == original_players
            assert e.mysql('SELECT gender FROM npc_types WHERE id=98054;').splitlines()[1] == '2'
            assert e.mysql('SELECT disabled FROM spawn2_disabled WHERE spawn2_id=58419;').splitlines()[1] == '1'
            # Preserve other zone state. Remove/reset only this trial, including
            # all instances and the current route position saved at shutdown.
            def saved(npc, group, spawn, x, instance=0):
                return ('INSERT INTO zone_state_spawns(zone_id,instance_id,npc_id,spawn2_id,spawngroup_id,x,y,z,heading,respawn_time,variance) '
                        f'VALUES(98,{instance},{npc},{spawn},{group},{x},0,0,0,60,0);')
            e.mysql(saved(98054,100,58419,42)+saved(ids['npc'],ids['group'],ids['spawn'],400)+saved(ids['npc'],ids['group'],ids['spawn'],410,1))
            e.mysql(f"INSERT INTO spawn2_disabled(spawn2_id,instance_id,disabled) VALUES({ids['spawn']},0,1);")
            reset = perform('reset'); assert reset['active']
            assert e.mysql('SELECT x FROM zone_state_spawns;').splitlines()[1:] == ['42']
            assert e.mysql('SELECT spawn2_id FROM spawn2_disabled;').splitlines()[1:] == ['58419']
            # Full-row fingerprints protect edits not present in the preset.
            e.mysql(f"UPDATE npc_types SET lastname='External change' WHERE id={ids['npc']};")
            reject(lambda: boats.preview(e, {'action': 'remove'}), 'content or its references changed')
            original_lastname = boats.values(own['manifest']['rows']['npc_types'][0])['lastname']
            e.mysql(f"UPDATE npc_types SET lastname={boats.literal(original_lastname)} WHERE id={ids['npc']};")
            # Detect reuse of an owned ID by another spawn/entry.
            e.mysql(f"INSERT INTO spawnentry(spawngroupID,npcID,chance) VALUES(100,{ids['npc']},100);")
            reject(lambda: boats.preview(e, {'action': 'remove'}), 'references changed')
            e.mysql(f"DELETE FROM spawnentry WHERE spawngroupID=100 AND npcID={ids['npc']};")
            # A change during backup must fail the transactional guard, preserving
            # both the ownership record and all other trial rows.
            p = boats.preview(e, {'action': 'remove'}); backup = e.backup_database
            def racing_backup(args):
                out = backup(args); e.mysql(f"UPDATE spawn2 SET x=999 WHERE id={ids['spawn']};"); return out
            with patch.object(e, 'backup_database', side_effect=racing_backup):
                reject(lambda: boats.apply(e, {'token': p['token']}), 'did not commit')
            assert boats.status(e, {})['active']
            assert e.mysql(f"SELECT COUNT(*) FROM npc_types WHERE id={ids['npc']};").splitlines()[1] == '1'
            e.mysql(f"UPDATE spawn2 SET x={boats.DOCK['x']} WHERE id={ids['spawn']};")
            # Client loses the response after COMMIT: audit resolves success.
            p = boats.preview(e, {'action': 'reset'}); mysql = e.mysql
            def lost_response(sql, **kwargs):
                out = mysql(sql, **kwargs)
                if sql.endswith('COMMIT;'): raise ValueError('Lost response')
                return out
            with patch.object(e, 'mysql', side_effect=lost_response):
                assert boats.apply(e, {'token': p['token']})['active']
            e.mysql(saved(ids['npc'],ids['group'],ids['spawn'],400))
            assert not perform('remove')['active']
            assert not boats.status(e, {})['active']
            assert snapshot() == original_players
            assert e.mysql('SELECT id FROM npc_types;').splitlines()[1:] == ['98054']
            assert e.mysql('SELECT id FROM spawn2;').splitlines()[1:] == ['58419']
            assert e.mysql('SELECT x FROM zone_state_spawns;').splitlines()[1:] == ['42']
            assert e.mysql('SELECT COUNT(*) FROM '+boats.AUDIT+';').splitlines()[1] == '4'
            # Stale competing install previews cannot allocate duplicate ferries.
            a = boats.preview(e, {'action': 'install'}); b = boats.preview(e, {'action': 'install'})
            boats.apply(e, {'token': a['token']})
            reject(lambda: boats.apply(e, {'token': b['token']}), 'already installed')
            perform('remove')
            print('PASS: real-seed ferry install/reset/removal, backups, immutable ownership, no player/route edits, saved-state scope, race rollback, lost-response recovery and duplicate rejection', flush=True)
        finally:
            if external: e.mysql('DROP DATABASE IF EXISTS '+e.config['database']+';', database=False)
            e.shutdown()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--seed', required=True); run(p.parse_args().seed)
