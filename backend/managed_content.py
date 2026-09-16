"""Reversible map maintenance and client import; shared by the local engine."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import time
import zipfile
from client_display import RESOLUTIONS, update_ini, display_ini

NEKTULOS = ('base/nektulos.map', 'nav/nektulos.nav')


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def client_file(parent, name):
    """Keep existing Windows-style casing, rejecting ambiguous or linked paths."""
    matches = [p for p in parent.iterdir() if p.name.casefold() == name.casefold()] if parent.exists() else []
    if len(matches) > 1: raise ValueError('Ambiguous client filename: ' + name)
    path = matches[0] if matches else parent / name
    if path.is_symlink(): raise ValueError('Client setup cannot replace symlinks: ' + name)
    return path


def replace_client_file(target, value):
    # Exclusive staging prevents a leftover or imported .trasc-new symlink from
    # redirecting writes. The destination changes only after the full copy.
    fd, name = tempfile.mkstemp(prefix='.trasc-', dir=target.parent)
    os.close(fd)
    temp = Path(name)
    try:
        if isinstance(value, Path): shutil.copy2(value, temp)
        elif isinstance(value, bytes): temp.write_bytes(value)
        else: temp.write_text(value, encoding='cp1252')
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


class ManagedContent:
    def nektulos_status(self, args=None):
        marker = self.work / 'backups/nektulos/current.json'
        data = json.loads(marker.read_text()) if marker.exists() else {}
        return {'applied': data.get('state') == 'applied',
                'backup': data.get('backup'),
                'legacy_ready': all((self.work / 'maps/legacy' / n).is_file() for n in NEKTULOS)}

    def _nektulos_backup(self, record):
        from engine import safe_path
        backup = safe_path(self.work / 'backups/nektulos', record['backup'], True)
        # Verify the entire original pair before touching either destination.
        for name, original in record['originals'].items():
            if name not in NEKTULOS: raise ValueError('Invalid Nektulos backup manifest')
            if original is not None and digest(safe_path(backup, name, True)) != original:
                raise ValueError('Nektulos backup checksum failed: ' + name)
        return backup

    def _nektulos_restore(self, record):
        from engine import safe_path
        backup = self._nektulos_backup(record)
        for name in NEKTULOS:
            dest = safe_path(self.work / 'maps', name)
            if record['originals'][name] is None:
                dest.unlink(missing_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                temp = dest.with_name(dest.name + '.restoring')
                shutil.copy2(backup / name, temp)
                os.replace(temp, dest)

    def recover_nektulos(self):
        from engine import atomic_json
        marker = self.work / 'backups/nektulos/current.json'
        if not marker.exists(): return
        record = json.loads(marker.read_text())
        if record['state'] in ('applying', 'reverting'):
            self._nektulos_restore(record)
            record['state'] = 'reverted'
            atomic_json(marker, record)
            self.log('Recovered interrupted Nektulos operation; original maps restored.')

    def fix_nektulos(self, args):
        from engine import atomic_json, safe_path
        if self.server_running(): raise ValueError('Stop the server before changing Nektulos maps')
        self.recover_nektulos()
        if self.nektulos_status()['applied']:
            for name in NEKTULOS:
                live = safe_path(self.work / 'maps', name)
                legacy = safe_path(self.work / 'maps', 'legacy/' + name)
                if not live.is_file() or not legacy.is_file() or digest(live) != digest(legacy):
                    raise ValueError('Nektulos files changed since Apply. Use Revert Nektulos before applying again; the intervening files will be backed up.')
            return {'message': 'Legacy Nektulos maps are already applied. The original backup is still retained.'}
        for name in NEKTULOS:
            src = safe_path(self.work / 'maps', 'legacy/' + name, True)
            if not src.is_file() or not src.stat().st_size:
                raise ValueError('Missing or empty legacy map: maps/legacy/' + name)
        identity = time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3)
        backup = self.work / 'backups/nektulos' / identity
        record = {'state': 'applying', 'backup': identity, 'originals': {}}
        marker = self.work / 'backups/nektulos/current.json'
        try:
            for name in NEKTULOS:
                dest = safe_path(self.work / 'maps', name)
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                record['originals'][name] = digest(dest) if dest.is_file() else None
                if dest.exists(): shutil.copy2(dest, saved)
                shutil.copy2(self.work / 'maps/legacy' / name, saved.with_suffix(saved.suffix + '.replacement'))
            atomic_json(marker, record)  # Recovery journal before the first replacement.
            for name in NEKTULOS:
                dest = safe_path(self.work / 'maps', name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                staged = backup / name
                shutil.copy2(staged.with_suffix(staged.suffix + '.replacement'), dest.with_name(dest.name + '.replacing'))
                os.replace(dest.with_name(dest.name + '.replacing'), dest)
            record['state'] = 'applied'
            atomic_json(marker, record)
        except Exception:
            if marker.exists() and json.loads(marker.read_text()).get('backup') == identity:
                self._nektulos_restore(record)
                record['state'] = 'reverted'
                atomic_json(marker, record)
            raise
        finally:
            for p in backup.rglob('*.replacement'): p.unlink(missing_ok=True)
        return {'message': 'Legacy Nektulos geometry and navigation applied. Start the server to load them.',
                'backup': str(backup.relative_to(self.work))}

    def revert_nektulos(self, args):
        from engine import atomic_json, safe_path
        if self.server_running(): raise ValueError('Stop the server before reverting Nektulos maps')
        self.recover_nektulos()
        if not self.nektulos_status()['applied']: raise ValueError('There is no applied Nektulos fix to revert')
        marker = self.work / 'backups/nektulos/current.json'
        record = json.loads(marker.read_text())
        self._nektulos_backup(record)
        # Preserve any edits made since Apply, in addition to the original pair.
        saved = self.work / 'backups/nektulos' / ('before-revert-' + secrets.token_hex(4))
        for name in NEKTULOS:
            src = safe_path(self.work / 'maps', name)
            if src.is_file():
                (saved / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, saved / name)
        record['state'] = 'reverting'
        atomic_json(marker, record)
        self._nektulos_restore(record)
        record['state'] = 'reverted'
        atomic_json(marker, record)
        return {'message': 'Original Nektulos map pair restored. Start the server to load it.'}

    def client_status(self, args=None):
        from client_spells import test_record
        marker = self.work / 'client/current/trasc-client.json'
        result = json.loads(marker.read_text()) if marker.exists() else {'imported': False}
        try: result['spell_test'] = test_record(self.work)
        except (ValueError, OSError) as e: result['spell_test'] = {'state': 'error', 'error': str(e)}
        return result

    def apply_spell_test(self, args):
        from client_spells import apply_test
        return apply_test(self.work, self._local_client(), self.check_cancel)

    def restore_spell_test(self, args):
        from client_spells import restore_test
        return restore_test(self.work, self._local_client())

    def _local_client(self, required=True):
        from engine import safe_path
        client = self.work / 'client/current'
        if client.parent.is_symlink() or client.is_symlink(): raise ValueError('Client setup cannot follow symlinks')
        safe_path(self.work, 'client/current')
        marker = client_file(client, 'trasc-client.json')
        if not marker.is_file():
            if required: raise ValueError('Import a client ZIP first')
            return None
        return client

    def _client_data_changes(self, client):
        from engine import CLIENT_FILES
        changes = {}
        resources = client_file(client, 'Resources')
        if resources.exists() and not resources.is_dir(): raise ValueError('Resources must be a directory')
        for name in CLIENT_FILES:
            for parent in (client, resources):
                target = client_file(parent, name)
                if target.exists() and not target.is_file(): raise ValueError('Expected a client file: ' + name)
                changes[target] = self.work / 'server/export' / name
        return changes

    def _apply_client_changes(self, client, changes):
        from engine import atomic_json, safe_path
        backup = self.work / 'backups/client-setup' / (time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
        backup.mkdir(parents=True)
        record = {'state':'prepared','files':{},'created':time.time()}
        for target in changes:
            relative = str(target.relative_to(client)); safe_path(client, relative)
            record['files'][relative] = target.exists()
            if target.exists():
                if not target.is_file(): raise ValueError('Expected a client file: ' + relative)
                saved = backup / relative; saved.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(target, saved)
        atomic_json(backup / 'manifest.json', record)
        applied = []
        created_dirs = set()
        try:
            for target, value in changes.items():
                self.check_cancel()
                if not target.parent.exists():
                    target.parent.mkdir(parents=True)
                    created_dirs.add(target.parent)
                replace_client_file(target, value)
                applied.append(target)
            record['state'] = 'applied';atomic_json(backup / 'manifest.json', record)
        except Exception:
            for target in reversed(applied):
                relative = str(target.relative_to(client))
                if record['files'][relative]: replace_client_file(target, backup / relative)
                else: target.unlink(missing_ok=True)
            for folder in created_dirs: folder.rmdir()
            record['state'] = 'rolled_back';atomic_json(backup / 'manifest.json', record)
            raise
        return str(backup.relative_to(self.work))

    def prepare_client(self, args):
        from engine import atomic_json
        from client_spells import require_no_test
        require_no_test(self.work)
        client = self._local_client()
        resolution = args.get('resolution', '800x600')
        if resolution not in RESOLUTIONS: raise ValueError('Unsupported client resolution')
        fullscreen = args.get('fullscreen', False)
        if not isinstance(fullscreen, bool): raise ValueError('Invalid fullscreen option')
        changes = self._client_data_changes(client)
        host = client_file(client, 'eqhost.txt')
        changes[host] = '[LoginServer]\r\nHost=' + self.config['ip'] + ':' + str(self.config['login_port']) + '\r\n'
        ini = client_file(client, 'eqclient.ini')
        text = ini.read_text(encoding='cp1252') if ini.exists() else ''
        changes[ini] = display_ini(text, resolution, fullscreen)
        result = self._export_client_data()
        backup = self._apply_client_changes(client, changes)
        result.update(local_client_synced=True, copied_files=8, backup=backup,
                      message='All four client data files overwritten in the local client root and Resources folder; login address and display settings prepared. Originals saved in ' + backup + '.')
        atomic_json(self.work / 'logs/client-data-sync.json', result)
        return result

    def import_client_zip(self, args):
        from engine import atomic_json, safe_path, extract_archive
        from client_spells import require_no_test
        require_no_test(self.work)
        archive = safe_path(self.work / 'incoming', args['file'], True)
        if not archive.is_file() or archive.parent != self.work / 'incoming':
            raise ValueError('Choose a client ZIP through the Android file picker')
        stage = self.work / 'client' / ('import-' + secrets.token_hex(4))
        try:
            if not zipfile.is_zipfile(archive): raise ValueError('Select a ZIP containing your ROF2 client')
            stats = extract_archive(archive, stage)
            candidates = [p.parent for p in stage.rglob('*') if p.is_file() and p.name.lower() == 'eqgame.exe']
            if len(candidates) != 1: raise ValueError('The ZIP must contain exactly one client directory with eqgame.exe')
            root = candidates[0]
            executable = next(p for p in root.iterdir() if p.name.lower() == 'eqgame.exe')
            with executable.open('rb') as f:
                if f.read(2) != b'MZ': raise ValueError('eqgame.exe is not a Windows executable')
            dll = next((p for p in root.iterdir() if p.name.lower() == 'dinput8.dll' and p.is_file()), None)
            record = {'imported': True, 'imported_at': time.time(), 'files': stats['files'], 'bytes': stats['bytes'],
                      'executable': executable.name, 'dinput8_present': dll is not None,
                      'dinput8_sha256': digest(dll) if dll else None, 'launch_available': False}
            atomic_json(root / 'trasc-client.json', record)
            self.check_cancel()
            current, previous = self.work / 'client/current', self.work / 'client/previous'
            if previous.exists(): shutil.rmtree(previous)
            if current.exists(): os.replace(current, previous)
            try: os.replace(root, current)
            except Exception:
                if previous.exists(): os.replace(previous, current)
                raise
            return {'message': 'Client extracted. The temporary ZIP inside this app was deleted; your original ZIP is unchanged. Install the client runtime to launch it.', 'client': record}
        finally:
            if stage.exists(): shutil.rmtree(stage)
            archive.unlink(missing_ok=True)
