"""One opt-in camera-only proxy, with an exact, crash-recoverable DLL restore.

The journal lives inside this profile's client so session backups retain it.
No executable, INI, prefix or runtime changes; imported DLL ownership is retained.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct

EXE_SHA256 = '4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3'
MARKER = b'TRASC_TRADITIONAL_CAMERA_ONLY_V1'
LIMIT = 64 * 1024 * 1024


def digest(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError('Camera adapter requires a bounded regular file: ' + path.name)
    with path.open('rb') as source:
        result = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024*1024), b''): result.update(chunk)
        return result.hexdigest()


def supported(request, client):
    name = request.get('executable', '')
    if not name or '/' in name or '\\' in name or name in ('.', '..'): return False
    path = client / name
    return (not path.is_symlink() and path.is_file() and path.stat().st_size == 8774656
            and digest(path) == EXE_SHA256)


def checked_bundle(asset):
    receipt = asset.with_name('traditional-camera-bundle.json')
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 32768:
        raise ValueError('Bundled camera receipt is missing or invalid')
    manifest = json.loads(receipt.read_text())
    raw = asset.read_bytes() if not asset.is_symlink() and asset.is_file() and asset.stat().st_size <= LIMIT else b''
    if (manifest.get('adapter') != 'traditional-camera-only-v1'
            or manifest.get('executable_sha256') != EXE_SHA256
            or manifest.get('file') != asset.name
            or manifest.get('sha256') != hashlib.sha256(raw).hexdigest()
            or MARKER not in raw or not raw.startswith(b'MZ') or len(raw) < 64):
        raise ValueError('Bundled camera adapter failed verification')
    offset = struct.unpack_from('<I', raw, 60)[0]
    if offset > len(raw) - 6 or raw[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', raw, offset+4)[0] != 0x14c:
        raise ValueError('Bundled camera adapter must be 32-bit x86')
    return raw, manifest['sha256']


class Adapter:
    def __init__(self, client):
        self.client = Path(client)
        if self.client.is_symlink() or not self.client.is_dir():
            raise ValueError('Unsafe client directory for camera adapter')
        self.folder = self.client / '.trasc-camera-adapter'
        if self.folder.is_symlink() or (self.folder.exists() and not self.folder.is_dir()):
            raise ValueError('Unsafe camera recovery directory')
        self.folder.mkdir(mode=0o700, exist_ok=True)
        self.journal = self.folder / 'current.json'
        self.backup = self.folder / 'original.dll'
        lock = self.folder / 'lock'
        if lock.is_symlink() or (lock.exists() and not lock.is_file()):
            raise ValueError('Unsafe camera adapter lock')
        self.lock = lock.open('a+b')
        try: fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise ValueError('Another client session owns camera settings')

    def _write(self, path, data):
        # Keep temporary adapter bytes inside our directory, never overwrite an
        # unrelated imported dinput8.dll.new beside the executable.
        temporary = (self.folder / 'install.new' if path.parent == self.client
                     else path.with_name(path.name + '.new'))
        if temporary.is_symlink() or (temporary.exists() and not temporary.is_file()):
            raise ValueError('Unsafe camera temporary file')
        with temporary.open('wb') as target:
            target.write(data); target.flush(); os.fsync(target.fileno())
        os.replace(temporary, path)

    def recover(self):
        if not self.journal.exists() and not self.journal.is_symlink():
            if self.backup.exists() or self.backup.is_symlink():
                raise ValueError('Camera recovery backup has no ownership journal; retain it and export logs')
            return False
        if self.journal.is_symlink() or not self.journal.is_file() or self.journal.stat().st_size > 32768:
            raise ValueError('Invalid camera recovery journal')
        record = json.loads(self.journal.read_text())
        name = record.get('name', '')
        if record.get('schema') != 1 or name.lower() != 'dinput8.dll' or '/' in name or '\\' in name:
            raise ValueError('Invalid camera recovery ownership')
        executable = record.get('executable', '')
        if (not executable or '/' in executable or '\\' in executable or executable in ('.', '..')
                or record.get('executable_sha256') != EXE_SHA256
                or not supported({'executable': executable}, self.client)):
            raise ValueError('Client executable changed; retain camera recovery files and export logs')
        current = self.client / name
        matches = [p for p in self.client.iterdir() if p.name.lower() == 'dinput8.dll']
        if any(p.name != name for p in matches): raise ValueError('Ambiguous camera recovery DLLs')
        old, proxy = record.get('original_sha256'), record.get('adapter_sha256')
        if not isinstance(proxy, str) or len(proxy) != 64 or (old is not None and (not isinstance(old, str) or len(old) != 64)):
            raise ValueError('Invalid camera recovery hashes')
        present = digest(current) if current.exists() or current.is_symlink() else None
        if old is not None:
            if self.backup.exists() or self.backup.is_symlink():
                if digest(self.backup) != old or present not in (None, proxy):
                    raise ValueError('Camera recovery files changed; retain both files and export logs')
                os.replace(self.backup, current)
            elif present != old:
                raise ValueError('Original DirectInput DLL is missing; retain camera recovery files')
        else:
            if self.backup.exists() or self.backup.is_symlink(): raise ValueError('Unexpected camera backup')
            if present == proxy: current.unlink()
            elif present is not None: raise ValueError('Camera DLL changed; retain it and export logs')
        temporary = self.folder / 'install.new'
        if temporary.exists() or temporary.is_symlink():
            if digest(temporary) != proxy:
                raise ValueError('Camera temporary adapter changed; retain recovery files')
            temporary.unlink()
        self.journal.unlink()
        return True

    def prepare(self, request, asset):
        recovered = self.recover()
        report = {'mode': 'off', 'previous_settings_restored': recovered}
        if request.get('profile') != 'traditional' or request.get('mode') != 'client' or not request.get('mouse_warp', False):
            return report
        if not supported(request, self.client):
            return dict(report, mode='unsupported_executable')
        raw, sha = checked_bundle(Path(asset))
        matches = [p for p in self.client.iterdir() if p.name.lower() == 'dinput8.dll']
        if len(matches) > 1: raise ValueError('More than one DirectInput DLL is present; retain them and export logs')
        original = matches[0] if matches else None
        old = digest(original) if original else None
        if old == sha:
            raise ValueError('Managed camera DLL has no journal; retain it and export logs')
        name = original.name if original else 'dinput8.dll'
        record = {'schema': 1, 'name': name, 'original_sha256': old, 'adapter_sha256': sha,
                  'executable': request['executable'], 'executable_sha256': EXE_SHA256}
        self._write(self.journal, (json.dumps(record, indent=2)+'\n').encode())
        try:
            if original: os.replace(original, self.backup)
            self._write(self.client / name, raw)
        except Exception:
            self.recover()
            raise
        return dict(report, mode='enabled', adapter_sha256=sha, imported_dll_preserved=old is not None)

    def close(self):
        if self.lock.closed: return
        try: self.recover()
        finally: self.lock.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != 'restore':
        raise SystemExit('Usage: traditional_camera.py restore CLIENT')
    manager = Adapter(Path(sys.argv[2]))
    try:
        restored = manager.recover()
        print('Traditional camera: original DirectInput restored' if restored else 'Traditional camera: no pending restore')
    finally:
        # A conflict must retain the journal/backup; closing releases ownership.
        manager.lock.close()
