"""Compare the imported source overlay with a case-insensitive Windows client."""
import hashlib
import json
from pathlib import Path, PurePosixPath
from managed_content import client_file, digest

PROTECTED = {'spells_us.txt', 'dbstr_us.txt', 'skillcaps.txt', 'basedata.txt', 'trasc-client.json', 'eqgame.exe'}


def relative_path(value):
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError('Invalid add-on path')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or any(':' in x or '\\' in x or not x or x.endswith((' ', '.')) for x in p.parts):
        raise ValueError('Add-on path must stay inside the client')
    return p.as_posix()


def target_path(client, name):
    target = client
    for part in PurePosixPath(relative_path(name)).parts:
        target = client_file(target, part)
        if target.exists() and not target.is_file() and not target.is_dir(): raise ValueError('Invalid client path')
    return target


def overlay(engine):
    source = engine.work/'sources/current'
    choices = [source/'Release-NMS-Client/ClientFiles', source/'ClientFiles', source/'client/ClientFiles']
    found = [p for p in choices if p.is_dir() and not p.is_symlink()]
    if len(found) != 1: raise ValueError('Import source containing Release-NMS-Client/ClientFiles first')
    root = found[0]
    if any(p.is_symlink() for p in [root, *root.parents] if p.is_relative_to(source)):
        raise ValueError('Linked source paths are not supported')
    return root


def policy(engine):
    path = engine.work/'client/addon-locks.json'
    if not path.exists(): return {'format':1, 'locked':[]}
    if path.is_symlink() or path.stat().st_size > 1024*1024: raise ValueError('Invalid add-on lock file')
    record = json.loads(path.read_text())
    if record.get('format') != 1 or not isinstance(record.get('locked'), list): raise ValueError('Invalid add-on lock file')
    record['locked'] = sorted({relative_path(p).casefold() for p in record['locked']})
    return record


def scan(engine, args=None):
    client = engine._local_client(); root = overlay(engine)
    locked = set(policy(engine)['locked']); entries = []; seen = set(); total = 0
    for path in sorted(root.rglob('*')):
        engine.check_cancel()
        if path.is_symlink(): raise ValueError('Linked overlay files are not supported')
        if path.is_dir(): continue
        name = relative_path(path.relative_to(root).as_posix()); key = name.casefold()
        if key in seen: raise ValueError('Duplicate Windows-case overlay path: '+name)
        seen.add(key); total += path.stat().st_size
        if len(seen) > 10000 or total > 2*1024**3: raise ValueError('Client overlay is too large')
        dest = target_path(client, name)
        if dest.exists() and not dest.is_file(): raise ValueError('Client file conflicts with a folder: '+name)
        source_hash = digest(path); installed_hash = digest(dest) if dest.exists() else None
        protected = path.name.casefold() in PROTECTED
        entries.append({'path':name, 'bytes':path.stat().st_size, 'source_sha256':source_hash,
                        'client_sha256':installed_hash, 'status':'missing' if installed_hash is None else 'same' if source_hash == installed_hash else 'different',
                        'locked':key in locked, 'protected':protected})
    signature = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    return {'entries':entries, 'snapshot':signature, 'source':str(root.relative_to(engine.work)),
            'counts':{s:sum(x['status']==s for x in entries) for s in ('missing','different','same')}}


def set_lock(engine, args):
    from engine import atomic_json
    name = relative_path(args.get('path')).casefold()
    if not isinstance(args.get('locked'), bool): raise ValueError('Choose lock or unlock')
    current = scan(engine)
    if name not in {x['path'].casefold() for x in current['entries']}: raise ValueError('Rescan the source overlay')
    record = policy(engine); locked = set(record['locked'])
    if args['locked']: locked.add(name)
    else: locked.discard(name)
    record['locked'] = sorted(locked); atomic_json(engine.work/'client/addon-locks.json', record)
    return scan(engine)


def copy_files(engine, args):
    from engine import atomic_json
    current = scan(engine)
    if args.get('snapshot') != current['snapshot']: raise ValueError('Source or client files changed. Compare again before copying')
    mode = args.get('mode', 'selected')
    if mode not in ('selected','missing','all'): raise ValueError('Invalid copy mode')
    selected = args.get('paths', [])
    if not isinstance(selected, list): raise ValueError('Invalid add-on selection')
    names = {relative_path(p).casefold() for p in selected}
    known = {x['path'].casefold() for x in current['entries']}
    if names - known: raise ValueError('Unknown add-on selection')
    root = overlay(engine); client = engine._local_client(); changes = {}
    for item in current['entries']:
        chosen = (mode == 'all' and item['status'] != 'same') or (mode == 'missing' and item['status'] == 'missing') or (mode == 'selected' and item['path'].casefold() in names)
        if not chosen: continue
        if item['locked'] or item['protected']:
            if mode == 'selected': raise ValueError('Unlock this file before copying; generated data and managed files cannot be copied here')
            continue
        changes[target_path(client,item['path'])] = root/item['path']
    if not changes: return {'message':'No unlocked files need copying.', 'comparison':current}
    backup = engine._apply_client_changes(client, changes)
    result = {'message':str(len(changes))+' add-on files copied. Previous files backed up in '+backup+'.', 'backup':backup,
              'copied':len(changes), 'comparison':scan(engine)}
    atomic_json(engine.work/'logs/client-addons.json', {'backup':backup,'copied':len(changes),'paths':[str(p.relative_to(client)) for p in changes]})
    return result
