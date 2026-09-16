"""ROF2 client spell-table compatibility; never changes server database rows."""
import hashlib
import io
import json
import re
import secrets
import time
from pathlib import Path
from client_display import atomic_bytes

# ROF2 graphics/effects cannot safely load IDs at/above this boundary.
# EQEmu/common/patches/rof2_limits.h and the developer-confirmed reproduction:
# https://www.eqemulator.org/forums/showthread.php?t=40999
ROF2_SPELL_LIMIT = 45000
MAX_TABLE_BYTES = 64 * 1024 * 1024
MAX_ROW_BYTES = 128 * 1024
EFFECT_FIELDS = {120: 'casting_animation', 121: 'target_animation',
                 122: 'travel_type', 123: 'spell_affect_index', 145: 'spell_animation'}


def inspect_data(data, output=None, include_names=False):
    """Validate every row before publication; preserve retained bytes exactly.

    Diagnostics omit names by default. Compatibility reports may include a
    bounded list of excluded names, never spell descriptions/client settings.
    """
    if not data or len(data) > MAX_TABLE_BYTES or b'\0' in data:
        raise ValueError('Invalid or oversized spell table')
    report = {'format': 1, 'limit_exclusive': ROF2_SPELL_LIMIT, 'rows': 0,
              'kept_rows': 0, 'removed_rows': 0, 'removed_ids': [],
              'max_id_before': None, 'max_id_after': None, 'reported_spells': {},
              'source_sha256': hashlib.sha256(data).hexdigest()}
    if include_names: report['removed_spells'] = []
    bom = data.startswith(b'\xef\xbb\xbf')
    if bom:
        if output is not None: output.write(data[:3])
        data = data[3:]
    seen = set(); field_count = None; result_hash = hashlib.sha256()
    if bom: result_hash.update(b'\xef\xbb\xbf')
    for line in io.BytesIO(data):
        if len(line) > MAX_ROW_BYTES: raise ValueError('Oversized spell row')
        if not line.strip():
            if output is not None: output.write(line)
            result_hash.update(line)
            continue
        fields = line.rstrip(b'\r\n').split(b'^')
        if not re.fullmatch(rb'[0-9]{1,10}', fields[0]) or len(fields) < 146:
            raise ValueError('Malformed spell row')
        if field_count is None: field_count = len(fields)
        if len(fields) != field_count: raise ValueError('Inconsistent spell field count')
        spell_id = int(fields[0])
        if spell_id > 0xffffffff or spell_id in seen: raise ValueError('Invalid or duplicate spell ID')
        seen.add(spell_id)
        report['rows'] += 1
        if report['rows'] > 100000: raise ValueError('Too many spell rows')
        report['max_id_before'] = max(spell_id, report['max_id_before'] or 0)
        if spell_id in (26, 200):
            selected = {}
            for index, label in EFFECT_FIELDS.items():
                if re.fullmatch(rb'-?[0-9]{1,10}', fields[index]): selected[label] = int(fields[index])
            report['reported_spells'][str(spell_id)] = selected
        if spell_id >= ROF2_SPELL_LIMIT:
            report['removed_rows'] += 1
            if len(report['removed_ids']) < 64:
                report['removed_ids'].append(spell_id)
                if include_names:
                    name = fields[1][:96].decode('cp1252', errors='replace')
                    report['removed_spells'].append({'id': spell_id, 'name': ''.join(c for c in name if c.isprintable())})
        else:
            report['kept_rows'] += 1
            report['max_id_after'] = max(spell_id, report['max_id_after'] or 0)
            if output is not None: output.write(line)
            result_hash.update(line)
    if not report['kept_rows']: raise ValueError('No supported ROF2 spells in table')
    report['field_count'] = field_count
    report['removed_ids_truncated'] = report['removed_rows'] > len(report['removed_ids'])
    report['compatible_sha256'] = result_hash.hexdigest()
    return report


def read_table(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_TABLE_BYTES:
        raise ValueError('Spell table must be a bounded regular file')
    with path.open('rb') as source: return source.read(MAX_TABLE_BYTES + 1)


def prepare_export(path):
    """Filter only generated client data; retain the complete original export."""
    path = Path(path)
    original = read_table(path)
    output = io.BytesIO()
    report = inspect_data(original, output, include_names=True)
    full = path.with_name('spells_us.unfiltered.txt')
    if full.is_symlink() or (full.exists() and not full.is_file()):
        raise ValueError('Unfiltered spell export must be a regular file')
    atomic_bytes(full, original)
    if report['removed_rows']: atomic_bytes(path, output.getvalue())
    return report


# Keep the journal path and operation names for upgrades from the eight-ID
# comparison. An existing applied record opts into the persistent policy.


def test_record(work):
    marker = Path(work) / 'backups/client-spell-test/current.json'
    if not marker.exists(): return {}
    if marker.is_symlink() or marker.stat().st_size > 65536:
        raise ValueError('Invalid spell test journal')
    record = json.loads(marker.read_text())
    if record.get('format') != 1 or record.get('state') not in ('applying', 'applied', 'restoring', 'restored'):
        raise ValueError('Invalid spell test journal')
    return record


def test_active(work):
    return test_record(work).get('state') in ('applying', 'applied', 'restoring')


def require_no_test(work):
    if test_active(work):
        raise ValueError('Restore full spell files in Client before replacing the client')


def require_export_ready(work, client):
    record = test_record(work)
    if record and record['state'] != 'restored':
        if client is None: raise ValueError('Active spell compatibility mode requires its imported client')
        verify_installed_test(client, record)
    return record


def _spell_paths(client):
    def unique(parent, name):
        matches = [p for p in parent.iterdir() if p.name.casefold() == name.casefold()]
        if len(matches) != 1 or matches[0].is_symlink():
            raise ValueError('Missing, ambiguous or linked client path: ' + name)
        return matches[0]
    client = Path(client)
    if client.is_symlink(): raise ValueError('Client cannot be a symlink')
    resources = unique(client, 'Resources')
    if not resources.is_dir(): raise ValueError('Resources must be a directory')
    return [unique(client, 'spells_us.txt'), unique(resources, 'spells_us.txt')]


def _identity(client):
    marker = Path(client) / 'trasc-client.json'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 65536:
        raise ValueError('Invalid imported client identity')
    return hashlib.sha256(marker.read_bytes()).hexdigest()


def _test_targets(client, record):
    paths = _spell_paths(client)
    if _identity(client) != record['client_identity'] or [str(p.relative_to(client)) for p in paths] != record['paths']:
        raise ValueError('The imported client changed after the spell test; original backups are retained')
    return paths


def verify_installed_test(client, record):
    """Runs in the client runtime too; no server-only module imports here."""
    if not record or record.get('state') == 'restored': return {'state': 'inactive'}
    if record.get('state') != 'applied':
        raise ValueError('Spell test was interrupted. Use Restore full spell files before launching')
    reports = []
    for target in _test_targets(client, record):
        report = inspect_data(read_table(target))
        if report['source_sha256'] != record['filtered_sha256'] or report['removed_rows']:
            raise ValueError('Spell test files changed. Restore full spell files before launching')
        reports.append({'path': str(target.relative_to(client)), 'rows': report['rows'],
                        'max_id': report['max_id_before'], 'sha256': report['source_sha256']})
    return {'state': 'applied', 'excluded_ids': record['excluded_ids'],
            'excluded_count': record.get('excluded_count', len(record['excluded_ids'])), 'installed': reports}


def _save_test(work, record):
    from engine import atomic_json
    atomic_json(Path(work) / 'backups/client-spell-test/current.json', record)
    atomic_json(Path(work) / 'logs/client-spell-test.json', record)


def restore_test(work, client):
    from managed_content import replace_client_file
    record = test_record(work)
    if not record or record['state'] == 'restored':
        return {'message': 'No spell exclusion mode is active.'}
    if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9a-f]{12}', record.get('backup_id', '')):
        raise ValueError('Invalid spell test backup location')
    backup = Path(work) / 'backups/client-spell-test' / record['backup_id']
    if backup.is_symlink(): raise ValueError('Spell backup cannot be a symlink')
    targets = _test_targets(client, record)
    originals = [read_table(backup / name) for name in ('root.txt', 'resources.txt')]
    # Validate every original and destination before changing either copy.
    for target, data in zip(targets, originals):
        if hashlib.sha256(data).hexdigest() != record['original_sha256']:
            raise ValueError('Spell backup checksum failed; files were not restored')
        allowed = {record['original_sha256'], record['filtered_sha256']}
        if record['state'] in ('applying', 'restoring'):
            allowed.add(record.get('previous_filtered_sha256'))
        if hashlib.sha256(read_table(target)).hexdigest() not in allowed:
            raise ValueError('Spell files changed outside the test; backups retained, restore refused')
    record['state'] = 'restoring'; _save_test(work, record)
    # No cancellation once restoring: finish both originals or leave a journal
    # that blocks launch and permits a subsequent Restore to finish safely.
    for target, data in zip(targets, originals): replace_client_file(target, data)
    for target in targets:
        if hashlib.sha256(read_table(target)).hexdigest() != record['original_sha256']:
            raise ValueError('Spell restore verification failed')
    record.update(state='restored', restored_at=time.time())
    _save_test(work, record)
    return {'message': 'Full spell files restored and verified in root and Resources. Compatibility mode is off.', 'spell_test': record}


def _new_record(work, client, targets, original, report):
    """Retain each complete generation before publishing any replacement."""
    from managed_content import replace_client_file
    backup_id = time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(6)
    backup = Path(work) / 'backups/client-spell-test' / backup_id
    backup.mkdir(parents=True)
    for name in ('root.txt', 'resources.txt'):
        replace_client_file(backup / name, original)
        if read_table(backup / name) != original: raise ValueError('Spell backup verification failed')
    return {'format': 1, 'policy': 'rof2-limit-v1', 'limit_exclusive': ROF2_SPELL_LIMIT,
            'state': 'applying', 'created_at': time.time(), 'backup_id': backup_id,
            'client_identity': _identity(client), 'paths': [str(p.relative_to(client)) for p in targets],
            'original_sha256': report['source_sha256'], 'filtered_sha256': report['compatible_sha256'],
            'original_rows': report['rows'], 'filtered_rows': report['kept_rows'],
            'excluded_count': report['removed_rows'], 'excluded_ids': report['removed_ids'],
            'excluded_ids_truncated': report['removed_ids_truncated'],
            'excluded_spells': report['removed_spells'], 'reported_spells': report['reported_spells']}


def install_export(work, client, install):
    """Wrap the existing multi-file transaction with a recoverable spell journal.

    Restore always selects the latest full generation after a successful sync.
    A normal transaction failure returns to the previous journal; process death
    leaves an applying journal that accepts either old or new filtered bytes.
    """
    previous = require_export_ready(work, client)
    if not previous or previous['state'] == 'restored': return install()
    targets = _test_targets(client, previous)
    folder = Path(work) / 'server/export'
    original = read_table(folder / 'spells_us.unfiltered.txt')
    report = inspect_data(original, include_names=True)
    if hashlib.sha256(read_table(folder / 'spells_us.txt')).hexdigest() != report['compatible_sha256']:
        raise ValueError('Filtered export checksum failed; no client files changed')
    record = _new_record(work, client, targets, original, report)
    record['previous_filtered_sha256'] = previous['filtered_sha256']
    record['previous_backup_id'] = previous['backup_id']
    _save_test(work, record)
    try:
        result = install()
        record['state'] = 'applied'
        verify_installed_test(client, record)
        _save_test(work, record)
        return result
    except Exception:
        # The existing transaction rolls back its writes on cancellation/I/O
        # errors. Only reinstate the old journal if its installed bytes verify.
        try: verify_installed_test(client, previous)
        except (ValueError, OSError): pass
        else: _save_test(work, previous)
        raise


def apply_test(work, client, check_cancel=lambda: None):
    from managed_content import replace_client_file
    record = test_record(work)
    if record.get('state') == 'applied':
        verify_installed_test(client, record)
        return {'message': 'Spell compatibility mode is already active; complete backups are retained.', 'spell_test': record}
    require_no_test(work)
    targets = _spell_paths(client)
    data = [read_table(p) for p in targets]
    if data[0] != data[1]: raise ValueError('Root and Resources spell files differ. Export & sync client data before enabling compatibility')
    output = io.BytesIO(); report = inspect_data(data[0], output, include_names=True)
    filtered = output.getvalue()
    record = _new_record(work, client, targets, data[0], report)
    _save_test(work, record)  # Durable originals and journal precede replacement.
    try:
        for target in targets:
            check_cancel(); replace_client_file(target, filtered)
        record['state'] = 'applied'
        verify_installed_test(client, record)
        _save_test(work, record)
    except Exception:
        restore_test(work, client)
        raise
    return {'message': 'Spell compatibility mode enabled: ' + str(report['removed_rows']) +
            ' high-ID entries excluded from both folders; ' + str(report['kept_rows']) +
            ' rows retained. Future exports stay filtered. Restore full spell files turns the mode off.',
            'spell_test': record}
