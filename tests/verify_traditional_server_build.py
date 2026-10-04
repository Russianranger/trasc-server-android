"""Qualify the app's real Traditional import/patch/build path in its ARM64 image.

This is a compilation qualification, with no server process or database launch.
"""
import argparse
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0, '/opt/trasc')
from engine import Engine, atomic_json
import traditional_verify

REPOSITORY = 'https://github.com/Russianranger/Server'
REVISION = '4aceae18b94ffaafc08e2b17bc41cd72c77f795d'


def verify(work, jobs=2):
    if platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('Traditional qualification requires native ARM64 Linux')
    engine = Engine(work, 'traditional')
    try:
        engine.dispatch('import_source', {'url': REPOSITORY, 'ref': REVISION})
        result = engine.dispatch('build', {'jobs': jobs})
        binaries = engine.work / 'server/bin.staged'
        evidence = engine.work / 'traditional-binary-evidence'
        report = traditional_verify.verify(binaries, evidence)
        record = {'result': 'passed', 'profile': 'traditional', 'runtime': 'traditional-1.0',
                  'architecture': platform.machine(), 'repository': REPOSITORY,
                  'revision': REVISION, 'build': result, 'verification': report}
        atomic_json(engine.work / 'traditional-build-verification.json', record)
        print(json.dumps(record, indent=2), flush=True)
    except Exception:
        log = engine.work / 'logs/operation.log'
        if log.exists():
            with log.open('rb') as stream:
                stream.seek(max(0, log.stat().st_size - 24000))
                print(stream.read().decode(errors='replace'), file=sys.stderr, flush=True)
        raise
    finally:
        engine.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', default='/work')
    parser.add_argument('--jobs', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    verify(args.work, args.jobs)
