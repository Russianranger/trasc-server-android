"""ROF2 client spell-table compatibility; never changes server database rows."""
import hashlib
import io
import re
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


def inspect_data(data, output=None):
    """Validate every row before publication; preserve retained bytes exactly.

    Only IDs and numeric effect fields for the two reported spells enter the
    summary. No arbitrary spell descriptions or client settings are exported.
    """
    if not data or len(data) > MAX_TABLE_BYTES or b'\0' in data:
        raise ValueError('Invalid or oversized spell table')
    report = {'format': 1, 'limit_exclusive': ROF2_SPELL_LIMIT, 'rows': 0,
              'kept_rows': 0, 'removed_rows': 0, 'removed_ids': [],
              'max_id_before': None, 'max_id_after': None, 'reported_spells': {},
              'source_sha256': hashlib.sha256(data).hexdigest()}
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
            if len(report['removed_ids']) < 64: report['removed_ids'].append(spell_id)
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
    report = inspect_data(original, output)
    full = path.with_name('spells_us.unfiltered.txt')
    if full.is_symlink() or (full.exists() and not full.is_file()):
        raise ValueError('Unfiltered spell export must be a regular file')
    atomic_bytes(full, original)
    if report['removed_rows']: atomic_bytes(path, output.getvalue())
    return report
