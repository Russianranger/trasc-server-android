"""Bounded read-only inspection of TAKP's actual X window layout."""
import hashlib
import json
from pathlib import Path
import struct


MARKER = 'TRASC_TAKP_WINDOW_INSPECT_V1'


def start(supervisor, logs, root=None):
    if supervisor.request.get('profile') != 'takp' or supervisor.request.get('mode') != 'client':
        return {}
    try:
        root = Path(root) if root else Path(__file__).parent
        binary = root / 'takp-window-inspect'
        record_path = root / 'takp-window-inspector.json'
        if record_path.is_symlink() or not record_path.is_file() or record_path.stat().st_size > 16*1024:
            raise ValueError('Invalid window inspector build receipt')
        receipt = json.loads(record_path.read_text())
        if not isinstance(receipt, dict):
            raise ValueError('Invalid window inspector receipt object')
        data = binary.read_bytes() if binary.is_file() and not binary.is_symlink() and binary.stat().st_size <= 256*1024 else b''
        if (receipt.get('format') != 1 or receipt.get('marker') != MARKER
                or receipt.get('read_only') is not True or receipt.get('max_seconds') != 300
                or receipt.get('bounded_output_bytes') != 128*1024
                or len(data) != receipt.get('bytes') or len(data) < 64
                or hashlib.sha256(data).hexdigest() != receipt.get('sha256')
                or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183
                or MARKER.encode() not in data):
            raise ValueError('Window inspector differs from qualified read-only ARM64 bytes')
        from log_retention import rotate
        rotate(Path(logs) / 'client-takp-windows.log')
        process = supervisor.spawn([str(binary), '300'], 'client-takp-windows.log')
        supervisor.takp_window_inspector_process = process
        result = {'state': 'started', 'pid': process.pid, 'sha256': receipt['sha256'],
            'read_only': True, 'max_seconds': 300, 'max_log_bytes': 128*1024}
    except (OSError, ValueError, KeyError) as error:
        result = {'state': 'unavailable', 'error': str(error)[:240], 'read_only': True}
    return {'takp_window_inspector': result}


def process_status(supervisor):
    """Return liveness, including after supervised teardown has completed."""
    result = {}
    for attribute, key in (('takp_focus_process', 'takp_focus_recovery'),
                           ('takp_window_inspector_process', 'takp_window_inspector')):
        process = getattr(supervisor, attribute, None)
        if process is not None:
            record = dict(supervisor.status.get(key, {}))
            record['exit_code'] = process.poll()
            record['state'] = 'running' if record['exit_code'] is None else 'exited'
            result[key] = record
    return result
