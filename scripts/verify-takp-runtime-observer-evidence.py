#!/usr/bin/env python3
"""Verify native observer coverage from already qualified ARM64 CI logs.

This read-only postprocessor preserves the exact fixture source fingerprints
in the original CI receipt. It does not initialize Wine or touch player data.
"""
import argparse
import hashlib
import json
from pathlib import Path

CASES = ('default', 'global-disabled', 'global-enabled',
         'app-disables-global', 'app-enables-global')


def observer_evidence(path):
    result = {'qualified': False}
    try:
        raw = Path(path).read_bytes()
        result['log_sha256'] = hashlib.sha256(raw).hexdigest()
        if len(raw) > 131072:
            raise ValueError('Native observer log exceeds its qualified cap')
        rows = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
        begin, end = rows[0], rows[-1]
        extension = next(row for row in rows if row['record'] == 'extension')
        held = [row for row in rows if row['record'] == 'raw_motion' and row['held_mask']]
        snapshots = [row for row in rows if row['record'] == 'snapshot' and row['pointer_ok']]
        devices = [row for row in rows if row['record'] == 'device']
        valuators = [row for row in rows if row['record'] == 'valuator']
        ancestors = [row for row in rows if row['record'] == 'focus_ancestor']
        signs = {0: set(), 1: set()}
        for row in held:
            for axis, cooked, value in row['axis_value_raw']:
                if axis in signs and value is not None and value:
                    signs[axis].add(1 if value > 0 else -1)
        checks = {'valid_clock_anchors': begin['record'] == 'begin' and
                      begin['marker'] == 'TRASC_TAKP_XINPUT_OBSERVE_V1' and
                      begin['monotonic_ms'] > 0 and begin['epoch_ms'] > 0,
                  'xi2_raw_under_grab_negotiated': extension['xi2'] and
                      extension['raw_grab_delivery_supported'] and
                      (extension['major'], extension['minor']) >= (2, 1) and
                      extension['xerrors'] == 0,
                  'inventory_with_valuators': bool(devices and valuators),
                  'pointer_and_focus_observed': bool(snapshots and ancestors),
                  'held_signed_raw_both_axes': all(signs[axis] == {-1, 1} for axis in signs),
                  'normal_bounded_completion': end['record'] == 'end' and
                      end['reason'] == 'signal' and not end['dropped']}
        result.update(qualified=all(checks.values()), checks=checks, bytes=len(raw),
                      clock_anchors={'monotonic_ms': begin['monotonic_ms'], 'epoch_ms': begin['epoch_ms']},
                      extension=extension, device_count=len(devices), valuator_count=len(valuators),
                      pointer_snapshots=len(snapshots), focus_ancestors=len(ancestors),
                      held_raw_samples=len(held),
                      master_source_ids=sorted({(row['deviceid'], row['sourceid']) for row in held}),
                      raw_axis_signs={axis: sorted(values) for axis, values in signs.items()}, end=end)
    except (OSError, UnicodeError, ValueError, KeyError, IndexError, StopIteration) as failure:
        result['error'] = str(failure)
    return result


def verify(root, output):
    receipts = list(root.rglob('runtime-camera-verification.json'))
    if len(receipts) != 1:
        raise ValueError('Expected one original runtime camera qualification receipt')
    source = json.loads(receipts[0].read_text())
    if not source['all_cases_accepted']:
        raise ValueError('Original ARM64 camera fixture did not pass its controls')
    summaries = {}
    for name in CASES:
        logs = list(root.rglob(name + '/xinput-observer.log'))
        if len(logs) != 1:
            raise ValueError('Expected one native observer log for case ' + name)
        summaries[name] = observer_evidence(logs[0])
    result = {'format': 1, 'run': source['github_run_id'],
              'qualified_source': source['github_commit'],
              'original_runtime_receipt_sha256': hashlib.sha256(receipts[0].read_bytes()).hexdigest(),
              'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'all_observers_qualified': all(row['qualified'] for row in summaries.values()),
              'cases': summaries,
              'scope': 'Actual published ARM64 CI observer logs; fixture source unchanged; physical Thor acceptance remains open'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'all_observers_qualified': result['all_observers_qualified'],
                      'cases': {name: row['qualified'] for name, row in summaries.items()}}, indent=2))
    return 0 if result['all_observers_qualified'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(verify(args.evidence_root.resolve(), args.output.resolve()))
