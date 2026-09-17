"""Edit the installed game's INI without importing a sample over personal settings."""
import hashlib
from pathlib import Path
import re
from client_display import MAX_INI_BYTES, atomic_bytes

RACES = ('Human', 'Barbarian', 'Erudite', 'WoodElf', 'HighElf', 'DarkElf',
         'HalfElf', 'Dwarf', 'Troll', 'Ogre', 'Halfling', 'Gnome', 'Iksar', 'VahShir')
MODELS = ['AllLuclinPcModelsOff'] + ['UseLuclin'+race+gender for race in RACES for gender in ('Male','Female')] + ['UseLuclinElementals','LoadVeliousArmorsWithLuclin','LoadSocialAnimations']
MANAGED = {('defaults','windowedmode')} | {('videomode', k) for k in ('width','height','windowedwidth','windowedheight')}

def source(engine):
    root = engine.work/'client/current'
    if root.parent.is_symlink() or root.is_symlink() or not root.is_dir(): raise ValueError('Import the client first')
    matches = [p for p in root.iterdir() if p.name.casefold() == 'eqclient.ini']
    if len(matches) != 1: raise ValueError('Expected one eqclient.ini in the installed client. Launch the game once first.')
    path = matches[0]
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INI_BYTES:
        raise ValueError('eqclient.ini must be an ordinary file smaller than 2 MiB')
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')): raise ValueError('UTF-16 INI files are not supported')
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    return path, raw, bom, raw[len(bom):].decode('latin-1')

def records(text):
    section = ''
    for index, line in enumerate(text.splitlines(keepends=True)):
        s = line.strip()
        if s.startswith('[') and s.endswith(']'): section = s[1:-1].strip()
        elif section and '=' in s and not s.startswith((';','#')):
            key, value = s.split('=',1)
            yield index, section, key.strip(), value.strip()

def inspect(engine, args=None):
    _, raw, _, text = source(engine)
    entries, seen = [], set()
    for _, section, key, value in records(text):
        identity = (section.casefold(),key.casefold())
        if identity in seen: raise ValueError('Duplicate INI setting: '+section+'/'+key+'. Resolve it before using the editor.')
        seen.add(identity)
        entries.append({'section':section,'key':key,'value':value,'managed':identity in MANAGED})
    for key in MODELS:
        if ('defaults',key.casefold()) not in seen:
            entries.append({'section':'Defaults','key':key,'value':'','missing':True,'managed':False})
    return {'revision':hashlib.sha256(raw).hexdigest(),'entries':entries,'models':MODELS}

def save(engine, args):
    snapshot = inspect(engine)
    if args.get('revision') != snapshot['revision']: raise ValueError('eqclient.ini changed. Reload settings before saving.')
    changes = args.get('changes')
    if not isinstance(changes,list) or len(changes)>2048: raise ValueError('Invalid INI changes')
    known = {(e['section'].casefold(),e['key'].casefold()):e for e in snapshot['entries']}
    pending = {}
    for item in changes:
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in ('section','key','value')): raise ValueError('Invalid INI setting')
        identity = (item['section'].casefold(),item['key'].casefold()); value = item['value']
        if identity not in known or identity in MANAGED or identity in pending: raise ValueError('Unknown, repeated or launcher-managed setting')
        if len(value)>1024 or any(ord(c)<32 or ord(c)>255 for c in value): raise ValueError('Use a single-line Windows INI value')
        if identity[0]=='defaults' and known[identity]['key'] in MODELS and value.upper() not in ('TRUE','FALSE'): raise ValueError('Model settings must be TRUE or FALSE')
        if value != known[identity]['value']: pending[identity] = value
    if not pending: return {**snapshot,'message':'No settings changed.'}
    path, raw, bom, text = source(engine)
    if hashlib.sha256(raw).hexdigest() != snapshot['revision']: raise ValueError('eqclient.ini changed. Reload settings before saving.')
    lines = text.splitlines(keepends=True)
    for index, section, key, _ in records(text):
        identity = (section.casefold(),key.casefold())
        if identity not in pending: continue
        line = lines[index]; ending = '\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
        lines[index] = line.split('=',1)[0]+'='+pending.pop(identity)+ending
    text = ''.join(lines)
    # Only missing model keys may be added; insert into the existing Defaults section.
    if pending:
        ending = '\r\n' if '\r\n' in text else '\n'
        extra = ''.join(known[i]['key']+'='+v+ending for i,v in pending.items())
        match = re.search(r'^\[Defaults\][ \t]*\r?$', text, re.I|re.M)
        if match:
            at = text.find('\n',match.end())
            text = text+ending+extra if at<0 else text[:at+1]+extra+text[at+1:]
        else: text += ending+'[Defaults]'+ending+extra
    backup = engine.work/'backups/client-settings'
    if (engine.work/'backups').is_symlink() or backup.is_symlink(): raise ValueError('Unsafe INI backup directory')
    backup.mkdir(parents=True,exist_ok=True)
    for name in ('eqclient.original.ini','eqclient.previous.ini'):
        target = backup/name
        if target.is_symlink() or (target.exists() and not target.is_file()): raise ValueError('Unsafe INI backup file')
    if not (backup/'eqclient.original.ini').exists(): atomic_bytes(backup/'eqclient.original.ini',raw)
    atomic_bytes(backup/'eqclient.previous.ini',raw)
    atomic_bytes(path,bom+text.encode('latin-1'))
    return {**inspect(engine),'message':'Game settings saved. Restart the client to load model changes. Previous INI saved in backups/client-settings.'}
