"""Scoped native-focus recovery for TAKP; never edits the existing Wine prefix."""
import hashlib
import json
from pathlib import Path
import struct


MARKER = 'TRASC_TAKP_X_FOCUS_RECOVERY_V2'


def start(supervisor, logs, root=None):
    if supervisor.request.get('profile') != 'takp' or supervisor.request.get('mode') != 'client':
        return {}
    settings = supervisor.status.get('takp_input_settings', {})
    if settings.get('grab_pointer_enabled') is not True:
        return {'takp_focus_recovery': {'state': 'preserved_configuration',
            'reason': 'Capture configuration is disabled or unknown; no focus changes',
            'prefix_settings_changed': False}}
    try:
        root = Path(root) if root else Path(__file__).parent
        binary = root / 'takp-xinput-focus'
        record_path = root / 'takp-input-focus.json'
        if record_path.is_symlink() or not record_path.is_file() or record_path.stat().st_size > 16*1024:
            raise ValueError('Invalid native-focus build receipt')
        receipt = json.loads(record_path.read_text())
        if not isinstance(receipt, dict):
            raise ValueError('Invalid native-focus build receipt object')
        data = binary.read_bytes() if binary.is_file() and not binary.is_symlink() and binary.stat().st_size <= 256*1024 else b''
        if (receipt.get('format') != 1 or receipt.get('marker') != MARKER
                or len(data) != receipt.get('bytes') or len(data) < 64
                or hashlib.sha256(data).hexdigest() != receipt.get('sha256')
                or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183
                or MARKER.encode() not in data
                or receipt.get('bounded_output_bytes') != 128*1024
                or receipt.get('window_titles') != ['EqW-TAKP', 'Client1']
                or receipt.get('window_class') != 'eqgame.exe'):
            raise ValueError('Native-focus helper differs from qualified ARM64 bytes')
        from log_retention import rotate
        rotate(Path(logs) / 'client-takp-focus.log')
        process = supervisor.spawn([str(binary)], 'client-takp-focus.log')
        supervisor.takp_focus_process = process
        result = {'state': 'started', 'pid': process.pid, 'sha256': receipt['sha256'],
            'prefix_settings_changed': False, 'guard': 'held_right_button_and_pointer_over_named_game_with_no_native_focus',
            'max_log_bytes': 128*1024}
    except (OSError, ValueError, KeyError) as error:
        result = {'state': 'unavailable', 'error': str(error)[:240], 'prefix_settings_changed': False}
    return {'takp_focus_recovery': result}
