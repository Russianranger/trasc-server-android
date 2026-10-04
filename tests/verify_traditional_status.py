"""Measure first and cached adapter status in a qualified ARM64 workspace."""
import argparse
import json
import math
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, '/opt/trasc')
from engine import Engine
import traditional_build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', default='/work')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-seconds', type=float, default=10,
                        help='Use 0 to record latency without enforcing a budget')
    args = parser.parse_args()
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('Traditional status measurement requires native ARM64')
    if not math.isfinite(args.max_seconds) or args.max_seconds < 0:
        raise ValueError('Status latency budget must be a finite nonnegative number')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    engine = Engine(args.work, 'traditional')
    results = []
    try:
        for label in ('first', 'cached'):
            started = time.monotonic()
            status = traditional_build.status(engine)
            elapsed = time.monotonic() - started
            results.append({'request': label, 'seconds': elapsed,
                            'staged_valid': status.get('staged_valid'),
                            'build_allowed': status.get('build_allowed'),
                            'source_supported': status.get('source_supported'),
                            'runtime_ready': status.get('runtime_ready'),
                            'staged_message': status.get('staged_message')})
        budget = args.max_seconds or None
        report = {'format': 1, 'architecture': 'arm64', 'budget_seconds': budget,
                  'requests': results}
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
        if not all(result['staged_valid'] for result in results):
            raise RuntimeError('Qualified staged binaries were not recognized by adapter status')
        if budget is not None and not all(result['seconds'] < budget for result in results):
            raise RuntimeError('Traditional adapter status exceeded its UI request budget')
    finally:
        engine.shutdown()


if __name__ == '__main__': main()
