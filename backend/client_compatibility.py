"""Read-only Custom server/client ABI evidence, separate from source selection.

Refreshing source does not change the deployed server. Only a hash-verified
deployed zone receipt can establish an enforced client requirement.
"""
import hashlib
import json
from pathlib import Path
import re
import stat

HEADER = 'Release-NMS-Server/common/patches/rof2_limits.h'
LIMIT = 1024 * 1024
ZONE_LIMIT = 512 * 1024**2
# These exact repository revisions were inspected against the upstream
# spellbook-1440 contract. Never treat arbitrary descendants as equivalent.
KNOWN_REVISIONS = {
    '38a4f2ad03203cb2f12dbff26fd613cc47efba0a': 1440,
    '9e62980552d6ef484a974df87e8342a673319c73': 1440,
    'ff14f1aa1fd135246263e8315c65624235586483': 1440,
    'd118ec7a2fe4fe388fa2191afc9cf154512467eb': 720,
    '8f6ca0795f424a7b4eab750ff38fc6473d48375c': 720,
}


def _commit(value):
    return value.lower() if isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{40}', value) else None


def _ordinary(engine, relative, limit):
    root = Path(engine.work).absolute()
    path = root
    if root.is_symlink():
        raise ValueError('Compatibility evidence cannot use a symbolic link')
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Compatibility evidence cannot use a symbolic link')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError('Compatibility evidence is not an ordinary bounded file')
    return path, info


def _json(engine, relative):
    path, _ = _ordinary(engine, relative, LIMIT)
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError('Invalid compatibility provenance')
    return value


def source_record(engine):
    """Snapshot the selected header for inclusion in a new build-info receipt."""
    if getattr(engine, 'profile', 'custom') != 'custom':
        return None
    path, _ = _ordinary(engine, 'sources/current/' + HEADER, LIMIT)
    raw = path.read_bytes()
    # Ignore comments so a retired/example definition cannot supply evidence.
    text = re.sub(rb'/\*.*?\*/|//[^\r\n]*', b'', raw, flags=re.S)
    matches = re.findall(rb'\bconst\s+int\s+SPELLBOOK_SIZE\s*=\s*(\d+)\s*;', text)
    if len(matches) != 1 or int(matches[0]) not in (720, 1440):
        raise ValueError('Selected RoF2 spellbook constant is missing or unsupported')
    info = _json(engine, 'sources/current/trasc-source.json')
    if info.get('commit') is not None and _commit(info['commit']) is None:
        raise ValueError('Invalid selected source commit')
    return {'format': 1, 'source_commit': _commit(info.get('commit')),
            'spellbook_slots': int(matches[0]), 'source_header': HEADER,
            'source_header_sha256': hashlib.sha256(raw).hexdigest()}


def _verified_zone(engine, expected):
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
        return False
    path, info = _ordinary(engine, 'server/bin/zone', ZONE_LIMIT)
    identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    previous = getattr(engine, '_client_compatibility_zone_cache', None)
    if previous and previous[0] == identity:
        return previous[1] == expected
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        header = stream.read(20)
        if len(header) != 20 or header[:4] != b'\x7fELF' or header[4] != 2 or int.from_bytes(header[18:20], 'little') != 183:
            return False
        digest.update(header)
        total = len(header)
        while True:
            checker = getattr(engine, 'check_cancel', None)
            if checker:
                checker()
            data = stream.read(256 * 1024)
            if not data:
                break
            total += len(data)
            if total > ZONE_LIMIT:
                raise ValueError('Deployed zone exceeds the compatibility inspection limit')
            digest.update(data)
    after = path.stat()
    if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('Deployed zone changed while checking compatibility')
    actual = digest.hexdigest()
    engine._client_compatibility_zone_cache = (identity, actual)
    return actual == expected


def requirements(engine):
    """Return facts about deployed binaries and indications from selected source.

    Missing/legacy/unverifiable receipts stay unknown. They must not block a
    working old server merely because newer source was downloaded.
    """
    result = {'profile': getattr(engine, 'profile', 'custom'),
              'selected_source_commit': None, 'deployed_source_commit': None,
              'selected_spellbook_slots': None, 'required_spellbook_slots': None,
              'known_deployed': False, 'deployed_binary_verified': False,
              'evidence': 'unknown', 'warnings': []}
    if result['profile'] != 'custom':
        return dict(result, evidence='not_custom', message='Triptych spellbook compatibility applies only to the Custom profile')
    try:
        selected = _json(engine, 'sources/current/trasc-source.json')
        result['selected_source_commit'] = _commit(selected.get('commit'))
        result['selected_spellbook_slots'] = source_record(engine)['spellbook_slots']
    except (OSError, ValueError, TypeError) as error:
        result['warnings'].append('Selected source could not be inspected: ' + str(error))
    try:
        info = _json(engine, 'server/bin/build-info.json')
        source = info.get('source')
        if not isinstance(source, dict):
            raise ValueError('Deployed build has no source provenance')
        revision = _commit(source.get('commit'))
        if source.get('commit') is not None and revision is None:
            raise ValueError('Invalid deployed source commit')
        result['deployed_source_commit'] = revision
        hashes = info.get('binaries', {})
        if not isinstance(hashes, dict):
            raise ValueError('Invalid deployed binary hashes')
        expected = info.get('zone_sha256') or hashes.get('zone')
        if info.get('zone_sha256') and hashes.get('zone') and info['zone_sha256'] != hashes['zone']:
            raise ValueError('Deployed zone hash receipts disagree')
        result['deployed_binary_verified'] = _verified_zone(engine, expected)
        if not result['deployed_binary_verified']:
            raise ValueError('Deployed zone does not match a recorded ARM64 binary hash')
        receipt = info.get('client_compatibility')
        slots = None
        if receipt is not None:
            if (not isinstance(receipt, dict) or receipt.get('format') != 1
                    or receipt.get('spellbook_slots') not in (720, 1440)
                    or isinstance(receipt.get('spellbook_slots'), bool)
                    or receipt.get('source_header') != HEADER
                    or not isinstance(receipt.get('source_header_sha256'), str)
                    or not re.fullmatch(r'[0-9a-f]{64}', receipt['source_header_sha256'])
                    or _commit(receipt.get('source_commit')) != revision):
                raise ValueError('Invalid deployed client compatibility receipt')
            slots = receipt['spellbook_slots']
            result['evidence'] = 'verified_build_header'
        elif revision in KNOWN_REVISIONS:
            slots = KNOWN_REVISIONS[revision]
            result['evidence'] = 'verified_binary_known_revision'
        if slots is not None:
            result.update(required_spellbook_slots=slots, known_deployed=True)
    except (OSError, ValueError, TypeError) as error:
        result['warnings'].append('Deployed compatibility could not be established: ' + str(error))
    if result['known_deployed']:
        result['message'] = 'The verified deployed Custom server requires a ' + str(result['required_spellbook_slots']) + '-slot RoF2 client spellbook'
    elif result['selected_spellbook_slots']:
        result['evidence'] = 'selected_source_only'
        result['message'] = ('Selected source indicates ' + str(result['selected_spellbook_slots']) +
                             ' spellbook slots. Deployed server compatibility is unverified; refreshing source alone does not change its binaries')
    else:
        result['message'] = 'Deployed Custom server spellbook compatibility is unknown; no client requirement is inferred'
    return result
