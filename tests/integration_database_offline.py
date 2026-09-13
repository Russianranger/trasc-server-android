"""Reproduce the Thor bootstrap failure, then import the real seed without DNS.

Run in the published ARM64 runtime with --network none, --hostname localhost,
an empty /etc/hosts and an unusable resolver. No player rows are printed.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, '/opt/trasc')
from engine import Engine, atomic_json


def verify(seed, work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    # This must fail for the same reason as the device before exercising the fix.
    failed = subprocess.run([
        'mariadb-install-db', '--datadir=' + str(work / 'database'),
        '--auth-root-authentication-method=normal', '--skip-test-db',
    ], capture_output=True, text=True, timeout=240)
    output = failed.stdout + failed.stderr
    if failed.returncode == 0 or 'Neither host' not in output:
        raise AssertionError('The test did not reproduce the hostname failure: ' + output[-4000:])
    print('PASS: reproduced the original localhost resolution failure', flush=True)
    engine = Engine(work)
    try:
        # Retry the same workspace, just as an existing installation will.
        archive = work / 'sources/current/Release-NMS-Server/database/release-peq.zip'
        archive.parent.mkdir(parents=True)
        shutil.copyfile(seed, archive)
        selection = str(archive.relative_to(work)) + '!release-peq.sql'
        engine.import_database({'selection': selection})
        assert engine.config['database_imported']
        assert 'release_peq' not in engine.mysql('SHOW DATABASES;', database=False).splitlines()
        tables = engine.mysql('SHOW TABLES;').splitlines()[1:]
        counts = {}
        for table in ('items', 'npc_types', 'zone', 'spells_new', 'rule_values'):
            counts[table] = int(engine.mysql(f'SELECT COUNT(*) FROM `{table}`;').splitlines()[1])
            assert counts[table] > 0, table + ' is empty'
        rules = engine.gameplay({})
        assert rules['values'], 'Gameplay controls must read the imported rules'
        assert rules['selected'] == 1, 'This pinned seed uses default ruleset ID 1'
        unauth = subprocess.run([
            'mariadb', '--no-defaults', '--host=127.0.0.1', '--port=13306',
            '--user=root', '-e', 'SELECT 1;',
        ], capture_output=True)
        assert unauth.returncode != 0, 'Root must still require authentication'
        engine.shutdown()
        engine = Engine(work)
        engine.ensure_db()
        assert engine.config['database_imported']
        assert int(engine.mysql('SELECT COUNT(*) FROM items;').splitlines()[1]) == counts['items']
        report = {
            'result': 'passed', 'offline': True, 'original_failure_reproduced': True,
            'selection': selection, 'table_count': len(tables), 'row_counts': counts,
            'active_ruleset': rules['selected'], 'restart_preserved_database': True,
        }
        atomic_json(work / 'database-verification.json', report)
        print(json.dumps(report, indent=2), flush=True)
    except Exception:
        for name in ('operation.log', 'mariadb.log'):
            log = work / 'logs' / name
            if log.exists():
                with log.open('rb') as f:
                    f.seek(max(0, log.stat().st_size - 16000))
                    print(name + '\n' + f.read().decode(errors='replace'), file=sys.stderr, flush=True)
        raise
    finally:
        engine.shutdown()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--seed', required=True)
    p.add_argument('--work', default='/work')
    args = p.parse_args()
    verify(args.seed, args.work)
