"""Install owner-specific bot socials without rewriting personal INI settings.

The native TAKP and RoF2 clients use the same Socials keys, but TAKP has one
ten-button hotbar and a bare E<index> binding. RoF2 has ten twelve-button bars
and a comma-separated binding. Only an existing character file is edited.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import time

from managed_content import client_file

MAX_INI_BYTES = 2 * 1024**2
MAX_SCAN = 20000
MAX_CANDIDATES = 64
MAX_BACKUPS = 256
BACKUPS = 'backups/bot-socials'
SOCIAL_KEY = re.compile(r'Page(\d+)Button(\d+)(Name|Color|Line([1-5]))$', re.I)
BUTTON_KEY = re.compile(r'Page(\d+)Button(\d+)$', re.I)
SECTION = re.compile(r'\[([^\]\r\n]+)\][ \t]*(?:;[^\r\n]*)?$')
BOT_NAME = re.compile(r'[A-Za-z]{4,15}$')
SOCIAL_ID = re.compile(r'[a-z_]{1,32}\.[0-9a-f]{24}$')
SOCIAL_LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ]{0,14}$')
MAX_SELECTED = 20
MAX_SOCIALS = 120
# Verified against Servertakp 25bf70acb6bd24853cf09e447ddd62b96a4491a4,
# zone/player_bot.cpp HandlePlayerBotCommand. Each command names an explicitly
# selected owned bot. In particular, native `revive all` is NOT supported.
TAKP_ACTIONS = (
    ('spawn', 'Spawn party', 'spawn {name}', 'Party', 'Spawn and group the selected companions. Server party limits still apply.'),
    ('revive', 'Revive party', 'revive {name}', 'Party', 'Revive selected fallen companions after a 60-second wait, while the owner is out of combat. They return at 1 HP; use Spawn party afterward.'),
    ('follow', 'Follow', 'follow {name}', 'Party', 'Follow the owner.'),
    ('stay', 'Stay', 'stay {name}', 'Party', 'Stay in place.'),
    ('attack', 'Attack', 'attack {name}', 'Party', 'Attack the current attackable NPC target within 200 units.'),
    ('assist', 'Assist', 'assist {name}', 'Party', 'Enable the server assist behavior.'),
    ('passive', 'Passive', 'passive {name}', 'Party', 'Use passive behavior.'),
    ('summon', 'Gather party', 'summon {name}', 'Party', 'Move spawned companions to the owner and follow, out of combat.'),
    ('dismiss', 'Dismiss party', 'dismiss {name}', 'Party', 'Save and dismiss spawned companions, out of combat.'),
    ('sit_on', 'Sit', 'sit {name} on', 'Behavior', 'Sit and stay until Stand releases them.'),
    ('sit_off', 'Stand', 'sit {name} off', 'Behavior', 'Stand and restore the previous follow or stay mode.'),
    ('dps_on', 'DPS spells on', 'dps cast on {name}', 'Behavior', 'Enable direct-damage casting for spawned companions; saved per bot.'),
    ('dps_off', 'DPS spells off', 'dps cast off {name}', 'Behavior', 'Disable direct-damage casting. DoTs, buffs and heals remain allowed.'),
    ('taunt_on', 'Taunt on', 'taunt {name} 1', 'Behavior', 'Enable taunt; class and skill requirements still apply.'),
    ('taunt_off', 'Taunt off', 'taunt {name} 0', 'Behavior', 'Disable taunt.'),
    ('ranged_on', 'Ranged on', 'ranged {name} 1', 'Behavior', 'Enable ranged attacks when available.'),
    ('ranged_off', 'Ranged off', 'ranged {name} 0', 'Behavior', 'Disable ranged attacks.'),
    ('petenabled_on', 'Pets on', 'petenabled {name} 1', 'Behavior', 'Enable pets when the companion can summon one.'),
    ('petenabled_off', 'Pets off', 'petenabled {name} 0', 'Behavior', 'Disable pets.'),
    ('suspend', 'Suspend AI', 'suspend {name}', 'Behavior', 'Suspend the companion AI behavior.'),
    ('release', 'Resume AI', 'release {name}', 'Behavior', 'Release suspended AI behavior.'),
    ('pet', 'Summon pets', 'pet {name}', 'Magic', 'Ask eligible companions to cast their pet utility.'),
    ('petdismiss', 'Dismiss pets', 'petdismiss {name}', 'Magic', 'Dismiss pets and disable them, out of combat.'),
    ('cure', 'Cure', 'cure {name}', 'Magic', 'Use a cure on the current target, or owner if no target.'),
    ('resurrect', 'Resurrect', 'resurrect {name}', 'Magic', 'Cast resurrection on the targeted player corpse, out of combat; this is separate from reviving a fallen bot.'),
    ('mez', 'Mez', 'mez {name}', 'Magic', 'Use mesmerize on the current target.'),
    ('charm', 'Charm', 'charm {name}', 'Magic', 'Use charm on the current target.'),
    ('fear', 'Fear', 'fear {name}', 'Magic', 'Use fear on the current target.'),
    ('lull', 'Lull', 'lull {name}', 'Magic', 'Use lull on the current target.'),
    ('invisibility', 'Invisibility', 'invisibility {name}', 'Magic', 'Cast invisibility on the current target, or owner if no target.'),
    ('invisundead', 'Invis undead', 'invisundead {name}', 'Magic', 'Cast invisibility versus undead when available.'),
    ('levitate', 'Levitate', 'levitate {name}', 'Magic', 'Cast levitation on the current target, or owner if no target.'),
    ('waterbreathing', 'Water breathing', 'waterbreathing {name}', 'Magic', 'Cast water breathing when available.'),
    ('report', 'Report party', 'report {name}', 'Reports', 'Report HP, mana, pets, direct-damage casting and taunt.'),
    ('inventory', 'Inventory', 'inventory {name}', 'Reports', 'List the selected companions’ saved equipment.'),
    ('supplies', 'Supplies', 'supplies {name}', 'Reports', 'List saved supply quantities.'),
    ('spells', 'Spells', 'spells {name}', 'Reports', 'List spells for spawned companions.'),
    ('abilities', 'Abilities', 'abilities {name}', 'Reports', 'List available abilities for spawned companions.'),
    ('departures', 'Departures', 'departures {name}', 'Reports', 'List available departure spells.'),
)
# Both exact modern server pins have identical command handler bodies:
# Custom 8f6ca0795f424a7b4eab750ff38fc6473d48375c,
#   Release-NMS-Server/zone/bot_commands/{bot,attack,follow,guard,hold,
#                                      release,suspend,taunt}.cpp
# Traditional 4aceae18b94ffaafc08e2b17bc41cd72c77f795d,
#   zone/bot_commands/bot_{bot,attack,follow,guard,hold,release,suspend,taunt}.cpp
# `byname` is an owner-scoped spawned-bot selector, never a global fallback.
# Neither server registers a fallen-bot revive, sit or stand command.
MODERN_ACTIONS = (
    ('spawn_group', 'Spawn and group', None, 'Party', 'Keep one guarded spawn, target and invite button per companion. Party limits and timing still apply.'),
    ('spawn', 'Spawn only', 'botspawn {name}', 'Party', 'Spawn selected names in combined buttons. This does not invite them; use Spawn and group for invitations.'),
    ('follow', 'Follow owner', 'follow reset byname {name}', 'Party', 'Reset following to the owner and clear hate. The bot must be in the owner’s group or raid.'),
    ('follow_target', 'Follow target', 'follow byname {name}', 'Party', 'Follow your current friendly group or raid target and clear hate.'),
    ('stay', 'Guard position', 'guard byname {name}', 'Party', 'Guard the current position.'),
    ('guard_clear', 'Stop guarding', 'guard clear byname {name}', 'Party', 'Clear the guarded position.'),
    ('attack', 'Attack target', 'attack byname {name}', 'Party', 'Order the selected spawned companions to attack your current enemy target.'),
    ('summon', 'Gather party', 'botsummon byname {name}', 'Party', 'Summon selected spawned companions and their pets to your location.'),
    ('dismiss', 'Camp party', 'botcamp byname {name}', 'Party', 'Save and camp selected spawned companions.'),
    ('hold', 'Hold attacks', 'hold byname {name}', 'Behavior', 'Hold attacks until Resume attacks is used.'),
    ('hold_clear', 'Resume attacks', 'hold clear byname {name}', 'Behavior', 'Release held attacks; this is separate from resuming suspended AI.'),
    ('suspend', 'Suspend AI', 'suspend byname {name}', 'Behavior', 'Suspend the selected companions’ AI processing until Resume AI.'),
    ('release', 'Resume AI', 'release byname {name}', 'Behavior', 'Resume suspended AI processing and clear hate.'),
    ('taunt_on', 'Taunt on', 'taunt on byname {name}', 'Behavior', 'Enable taunt for eligible selected companions.'),
    ('taunt_off', 'Taunt off', 'taunt off byname {name}', 'Behavior', 'Disable taunt.'),
    ('pettaunt_on', 'Pet taunt on', 'taunt on pet byname {name}', 'Behavior', 'Enable taunt on eligible pets belonging to the selected companions.'),
    ('pettaunt_off', 'Pet taunt off', 'taunt off pet byname {name}', 'Behavior', 'Disable taunt on the selected companions’ pets.'),
    ('ranged_on', 'Ranged on', 'bottoggleranged 1 byname {name}', 'Behavior', 'Enable ranged attacks where the selected companion can use them.'),
    ('ranged_off', 'Ranged off', 'bottoggleranged 0 byname {name}', 'Behavior', 'Disable ranged attacks.'),
    ('helm_on', 'Show helm', 'bottogglehelm 1 byname {name}', 'Appearance', 'Show the selected companions’ helms.'),
    ('helm_off', 'Hide helm', 'bottogglehelm 0 byname {name}', 'Appearance', 'Hide the selected companions’ helms.'),
    ('report', 'Report party', 'botreport byname {name}', 'Reports', 'Report the selected spawned companions’ readiness.'),
    ('follow_current', 'Follow status', 'follow current byname {name}', 'Reports', 'Report whom each selected spawned companion is following.'),
)


def _action_specs(profile):
    return TAKP_ACTIONS if profile == 'takp' else MODERN_ACTIONS if profile in ('custom', 'traditional') else ()


def catalogue(profile):
    return [{'id': key, 'label': label, 'group': group, 'description': description}
            for key, label, _, group, description in _action_specs(profile)]


def _actions(profile, args):
    value = args.get('actions')
    if value is None:
        return None  # Original per-bot format and receipts remain compatible.
    specifications = _action_specs(profile)
    known = {entry[0] for entry in specifications}
    if (not specifications or not isinstance(value, list) or not value or
            any(not isinstance(key, str) or key not in known for key in value) or len(value) != len(set(value))):
        raise ValueError('Choose distinct supported commands for this world')
    return [entry for entry in specifications if entry[0] in value]


def _social_key(social):
    return social.get('social_id', social.get('bot_id'))


def _valid_social(social, profile='takp', owner_name=None):
    if not isinstance(social, dict):
        return False
    legacy = ('social_id' not in social and type(social.get('bot_id')) is int and social['bot_id'] > 0 and
              isinstance(social.get('name'), str) and BOT_NAME.fullmatch(social['name']) and
              isinstance(social.get('label'), str) and BOT_NAME.fullmatch(social['label']))
    grouped = ('bot_id' not in social and isinstance(social.get('social_id'), str) and SOCIAL_ID.fullmatch(social['social_id']) and
               isinstance(social.get('label'), str) and SOCIAL_LABEL.fullmatch(social['label']) and
               isinstance(social.get('bot_ids'), list) and 1 <= len(social['bot_ids']) <= 5 and
               all(type(value) is int and value > 0 for value in social['bot_ids']) and
               len(set(social['bot_ids'])) == len(social['bot_ids']) and
               isinstance(social.get('names'), list) and len(social['names']) == len(social['bot_ids']) and
               all(isinstance(value, str) and BOT_NAME.fullmatch(value) for value in social['names']) and
               social.get('action') in {entry[0] for entry in _action_specs(profile)})
    if grouped:
        chunk = [{'id': identity, 'name': name} for identity, name in zip(social['bot_ids'], social['names'])]
        if social['action'] == 'spawn_group':
            grouped = (len(chunk) == 1 and isinstance(owner_name, str) and
                       type(social.get('spawn_pause')) is int and 5 <= social['spawn_pause'] <= 100)
            commands = _commands(profile, chunk[0]['name'], {'spawn_pause': social.get('spawn_pause')}, owner_name) if grouped else None
        else:
            template = next(entry[2] for entry in _action_specs(profile) if entry[0] == social['action'])
            prefix = '/say #bot ' if profile == 'takp' else '/say ^'
            commands = [prefix + template.format(name=bot['name']) for bot in chunk]
        grouped = (social['social_id'] == social['action'] + '.' + _digest(chunk)[:24] and
                   grouped and social.get('lines') == commands)
    return bool((legacy or grouped) and
                type(social.get('page')) is int and 1 <= social['page'] <= 10 and
                type(social.get('button')) is int and 1 <= social['button'] <= 12 and
                isinstance(social.get('lines'), list) and 1 <= len(social['lines']) <= 5 and
                all(isinstance(line, str) and len(line) <= 255 and not any(c in line for c in '\r\n\0') for line in social['lines']))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return _sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode())


def _directory(path):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError('Bot social directories must be ordinary folders')
    return path


def _read(path, limit=MAX_INI_BYTES):
    """Read an ordinary file through a non-following descriptor with a bound."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Bot social file is unsafe or exceeds its size limit')
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Bot social file exceeds its size limit')
    return raw


class Ini:
    """Byte-preserving INI editor; a # or ; inside a value is literal text."""
    def __init__(self, raw):
        if not raw or len(raw) > MAX_INI_BYTES or b'\0' in raw:
            raise ValueError('Character INI must be a nonempty native Windows text file')
        self.bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
        # Latin-1 is a reversible byte mapping. New keys/commands are ASCII;
        # existing UTF-8 or Windows code-page text is never transcoded.
        self.lines = raw[len(self.bom):].decode('latin-1').splitlines(keepends=True)
        self.newline = '\r\n' if b'\r\n' in raw else '\n'
        self.entries, self.sections = {}, {}
        section = ''
        for index, line in enumerate(self.lines):
            body = line.rstrip('\r\n')
            trimmed = body.strip(' \t')
            match = SECTION.fullmatch(trimmed)
            if match:
                section = match[1].strip().casefold()
                if section in self.sections and self.relevant(section):
                    raise ValueError('Duplicate social or hotbar INI sections are ambiguous')
                self.sections[section] = index
            elif not trimmed or trimmed.startswith((';', '#')):
                continue
            elif '=' in body:
                key, value = body.split('=', 1)
                identity = (section, key.strip().casefold())
                if identity in self.entries and self.relevant(section):
                    raise ValueError('Duplicate social or hotbar INI keys are ambiguous')
                self.entries[identity] = (index, value)

    @staticmethod
    def relevant(section):
        return section == 'socials' or section.startswith('hotbuttons')

    def get(self, section, key):
        return self.entries.get((section.casefold(), key.casefold()), (None, ''))[1]

    def merge(self, changes):
        lines = self.lines[:]
        additions = {}
        for (section, key), value in changes.items():
            if not isinstance(value, str) or any(c in value for c in '\r\n\0'):
                raise ValueError('Social commands must fit one INI line')
            identity = (section.casefold(), key.casefold())
            if identity in self.entries:
                index = self.entries[identity][0]
                old = lines[index]
                ending = '\r\n' if old.endswith('\r\n') else '\n' if old.endswith('\n') else '\r' if old.endswith('\r') else ''
                lines[index] = old.split('=', 1)[0] + '=' + value + ending
            else:
                additions.setdefault(section.casefold(), (section, []))[1].append(key + '=' + value + self.newline)
        inserts, appended = {}, []
        for section, (spelling, values) in additions.items():
            if section in self.sections:
                start = self.sections[section]
                end = next((i for i in range(start + 1, len(lines)) if SECTION.fullmatch(lines[i].strip())), len(lines))
                inserts.setdefault(end, []).extend(values)
            else:
                appended.extend(['[' + spelling + ']' + self.newline, *values])
        output = []
        for i in range(len(lines) + 1):
            if i in inserts:
                if output and not output[-1].endswith(('\r', '\n')):
                    output[-1] += self.newline
                output.extend(inserts[i])
            if i < len(lines):
                output.append(lines[i])
        # Finish insertions into the existing last section before introducing
        # any new section at EOF; otherwise its new keys could land under the
        # appended Socials header rather than their own HotButtons section.
        if appended:
            if output and not output[-1].endswith(('\r', '\n')):
                output[-1] += self.newline
            output.extend(appended)
        updated = self.bom + ''.join(output).encode('latin-1')
        if len(updated) > MAX_INI_BYTES:
            raise ValueError('Updated character INI exceeds its size limit')
        return updated


def _owner_key(owner):
    if (not isinstance(owner, dict) or type(owner.get('id')) is not int or owner['id'] <= 0 or
            type(owner.get('account_id')) is not int or owner['account_id'] <= 0 or
            not isinstance(owner.get('name'), str) or not re.fullmatch(r'[A-Za-z]{1,64}', owner['name'])):
        raise ValueError('Choose a valid character owner')
    return {key: owner[key] for key in ('id', 'account_id', 'name')}


def _selected(bots, limit=5):
    if not isinstance(bots, list) or not 1 <= len(bots) <= limit:
        raise ValueError(f'Select one to {limit} owned bots for buttons')
    result, seen = [], set()
    for bot in bots:
        if (not isinstance(bot, dict) or type(bot.get('id')) is not int or bot['id'] <= 0 or
                bot['id'] in seen or not isinstance(bot.get('name'), str) or not BOT_NAME.fullmatch(bot['name'])):
            raise ValueError('Choose distinct, valid owned bots')
        seen.add(bot['id'])
        result.append({'id': bot['id'], 'name': bot['name']})
    return result


def _identity(engine, owner, args):
    identity = args.get('identity')
    if not isinstance(identity, str) or not identity or len(identity) > 256:
        raise ValueError('Refresh the bot deployment before installing socials')
    return {'profile': engine.profile, 'identity': identity, 'owner': _owner_key(owner)}


def _qualified(ini, profile):
    if not any(section in ini.sections for section in ('socials', 'hotbuttons', 'abilities', 'combatskills', 'friends')):
        raise ValueError('This is not a recognized character settings INI')
    for (section, key), (_, value) in ini.entries.items():
        if section == 'socials' and key.startswith('page'):
            match = SOCIAL_KEY.fullmatch(key)
            if not match or not 1 <= int(match[1]) <= 10 or not 1 <= int(match[2]) <= 12:
                raise ValueError('Unsupported social keys in this character INI')
        if section.startswith('hotbuttons'):
            match_section = re.fullmatch(r'hotbuttons([2-9]|10)?', section)
            if not match_section or (profile == 'takp' and section != 'hotbuttons'):
                raise ValueError('Unsupported hotbar sections in this character INI')
            if key.startswith('page'):
                match = BUTTON_KEY.fullmatch(key)
                if not match or not 1 <= int(match[1]) <= 10 or not 1 <= int(match[2]) <= (10 if profile == 'takp' else 12):
                    raise ValueError('Unsupported hotbar keys in this character INI')
                if value and profile == 'takp' and not re.fullmatch(r'[A-Z]?-?\d+', value.strip()):
                    raise ValueError('TAKP hotbar uses an unsupported binding format')


def _character_files(engine, owner):
    client = engine._local_client(False)
    if client is None:
        return None, []
    expression = re.compile(re.escape(owner['name']) + (r'(?:_[A-Za-z0-9][A-Za-z0-9_. -]{0,95})?\.ini' if engine.profile == 'takp' else r'_[A-Za-z0-9][A-Za-z0-9_. -]{0,95}\.ini'), re.I)
    candidates, seen = [], {}
    for count, path in enumerate(client.iterdir()):
        if count >= MAX_SCAN:
            raise ValueError('Character INI scan reached its file limit')
        if expression.fullmatch(path.name):
            seen.setdefault(path.name.casefold(), []).append(path)
            candidates.append(path)
            if len(candidates) > MAX_CANDIDATES:
                raise ValueError('Too many character INI candidates')
    result = []
    for path in sorted(candidates, key=lambda p: p.name.casefold()):
        entry = {'file': path.name}
        try:
            if len(seen[path.name.casefold()]) != 1 or path.is_symlink():
                raise ValueError('Ambiguous or linked character INI')
            raw = _read(path)
            _qualified(Ini(raw), engine.profile)
            entry.update(revision=_sha(raw), supported=True)
        except (ValueError, OSError) as exc:
            entry.update(supported=False, reason=str(exc))
        result.append(entry)
    return client, result


def _character(engine, owner, args):
    client, files = _character_files(engine, owner)
    chosen = args.get('character_file')
    available = [entry for entry in files if entry.get('supported')]
    if chosen is None and len(available) == 1:
        chosen = available[0]['file']
    selected = next((entry for entry in files if entry['file'] == chosen), None)
    if not selected or not selected.get('supported'):
        reason = selected.get('reason') if selected else ('Choose the actual character settings file' if available else 'Enter the world and camp this character once, then stop the client to create its settings file')
        return client, files, None, None, None, reason
    path = client_file(client, chosen)
    raw = _read(path)
    ini = Ini(raw)
    _qualified(ini, engine.profile)
    return client, files, path, raw, ini, None


def _backup_root(engine):
    _directory(engine.work / 'backups')
    return _directory(engine.work / BACKUPS)


def _records(engine, context, character_file):
    root = _backup_root(engine)
    if not root.exists():
        return []
    records, remaining = [], 32 * 1024**2
    for index, directory in enumerate(root.iterdir()):
        if index >= MAX_BACKUPS:
            raise ValueError('Bot social backup history reached its limit')
        if directory.is_symlink() or not directory.is_dir() or not re.fullmatch('[0-9a-f]{24}', directory.name):
            continue
        try:
            record = json.loads(_read(directory / 'record.json', 256 * 1024))
            if (not isinstance(record, dict) or record.get('format') != 1 or record.get('id') != directory.name or
                    record.get('context') != context or record.get('character_file') != character_file or
                    record.get('state') not in ('prepared', 'installed') or
                    not all(isinstance(record.get(key), str) and re.fullmatch('[0-9a-f]{64}', record[key]) for key in ('before_sha256', 'after_sha256')) or
                    type(record.get('created_at')) not in (int, float) or not math.isfinite(record['created_at'])):
                continue
            socials, placements = record.get('socials'), record.get('placements')
            if (record.get('operation') not in ('install', 'restore') or
                    not isinstance(socials, list) or len(socials) > MAX_SOCIALS or
                    not isinstance(placements, list) or len(placements) > len(socials)):
                continue
            valid_socials = all(_valid_social(social, engine.profile, context['owner']['name']) for social in socials)
            if not valid_socials:
                continue
            _placements(placements, socials, engine.profile)
            if record['operation'] == 'install' and (not isinstance(record.get('request_sha256'), str) or not re.fullmatch('[0-9a-f]{64}', record['request_sha256'])):
                continue
            if record['operation'] == 'restore' and (not isinstance(record.get('restored_from'), str) or not re.fullmatch('[0-9a-f]{24}', record['restored_from'])):
                continue
            size = (directory / character_file).lstat().st_size
            if size > remaining:
                raise ValueError('Bot social backup history reached its byte limit')
            saved = _read(directory / character_file)
            remaining -= len(saved)
            if _sha(saved) != record['before_sha256']:
                continue
            records.append(record)
        except (ValueError, OSError, TypeError):
            continue
    return sorted(records, key=lambda record: record['created_at'], reverse=True)


def _commands(profile, name, args, owner_name):
    if profile == 'takp':
        return ['/say #bot spawn ' + name]
    pause = args.get('spawn_pause', 20)
    if type(pause) is not int or not 5 <= pause <= 100:
        raise ValueError('Use a summon pause between 5 and 100 tenths of a second')
    # Always targeting is compatible with either value of the server's
    # GroupInvitesRequireTarget rule. Never change the player's server rule.
    # Select the owner before looking for the bot. If a refused/slow spawn
    # leaves /target Name unsuccessful, /invite acts on self instead of a
    # previously selected unrelated player. The two target changes still fit
    # inside a five-line native social and require no macro addon.
    return [f'/pause {pause}, /say ^botspawn {name}', '/target ' + owner_name,
            f'/pause 5, /target {name}', '/invite']


def _social_values(ini, page, button):
    key = f'Page{page}Button{button}'
    return [ini.get('Socials', key + 'Name'), ini.get('Socials', key + 'Color'),
            *[ini.get('Socials', key + 'Line' + str(line)) for line in range(1, 6)]]


def _binding(profile, social):
    index = (social['page'] - 1) * 12 + social['button'] - 1
    return 'E' + str(index) if profile == 'takp' else f'E{index},@-1,0000000000000000,0,{social["label"]}'


def _hotbar(section, key):
    match_section = re.fullmatch(r'hotbuttons([2-9]|10)?', section)
    match = BUTTON_KEY.fullmatch(key)
    if match_section and match:
        return {'bar': int(match_section[1] or 1), 'page': int(match[1]), 'button': int(match[2])}
    return None


def _plan(engine, owner, bots, args):
    context = _identity(engine, owner, args)
    actions = _actions(engine.profile, args)
    selected = _selected(bots, MAX_SELECTED if actions else 5)
    client, files, path, raw, ini, reason = _character(engine, owner, args)
    result = {'supported': reason is None, 'reason': reason, 'character_files': files,
              'character_file': path.name if path else None, 'file_revision': _sha(raw) if raw else None,
              'socials': [], 'empty_hotbar_slots': [], 'backups': [], 'preview_token': None,
              'spawn_pause': args.get('spawn_pause', 20)}
    if actions:
        result['actions'] = [entry[0] for entry in actions]
        result['message'] = ('Each button runs its displayed names. Commands with more than five names use numbered buttons. ' +
                             ('Revival requires a 60-second wait after falling and the owner out of combat; bots return at 1 HP; spawn afterward.'
                              if engine.profile == 'takp' else
                              'Spawn and group keeps one guarded button per companion. Spawn only does not invite. Follow requires group or raid membership.'))
    if reason:
        return result, None
    records = _records(engine, context, path.name)
    result['backups'] = [{'id': r['id'], 'file': r['character_file'], 'created_at': r['created_at'],
                          'restorable': r['after_sha256'] == _sha(raw)} for r in records[:20]]
    owned = {}
    for record in records:
        for social in record.get('socials', []) if record.get('operation') == 'install' else []:
            owned.setdefault(_social_key(social), social)
    reserved = set()
    for (section, key), (_, value) in ini.entries.items():
        if _hotbar(section, key):
            match = re.match(r'E(\d+)(?:,|$)', value.strip(), re.I)
            if match:
                reserved.add(int(match[1]))
    free = []
    for page in range(1, 11):
        for button in range(1, 13):
            values = _social_values(ini, page, button)
            if not values[0].strip() and not any(value.strip() for value in values[2:]) and (page - 1) * 12 + button - 1 not in reserved:
                free.append((page, button))
    requested = []
    if actions:
        for action, label, template, _, _ in actions:
            width = 1 if action == 'spawn_group' else 5
            chunks = [selected[start:start + width] for start in range(0, len(selected), width)]
            for index, chunk in enumerate(chunks, 1):
                # Stable identity includes the exact action and displayed names,
                # rather than one arbitrary bot ID shared by several buttons.
                identity = action + '.' + _digest(chunk)[:24]
                # Existing modern spawn/invite buttons retain their companion
                # labels and four-line guard; they cannot be combined into a
                # five-line native social without removing invitations.
                numbered = chunk[0]['name'] if action == 'spawn_group' else label if len(chunks) == 1 else label[:13] + ' ' + str(index)
                commands = (_commands(engine.profile, chunk[0]['name'], args, owner['name']) if action == 'spawn_group' else
                            [('/say #bot ' if engine.profile == 'takp' else '/say ^') + template.format(name=bot['name']) for bot in chunk])
                requested.append({'social_id': identity, 'action': action, 'bot_ids': [bot['id'] for bot in chunk],
                                  'names': [bot['name'] for bot in chunk], 'label': numbered,
                                  'lines': commands})
                if action == 'spawn_group':
                    requested[-1]['spawn_pause'] = args.get('spawn_pause', 20)
    else:
        requested = [{'bot_id': bot['id'], 'name': bot['name'], 'label': bot['name'],
                      'lines': _commands(engine.profile, bot['name'], args, owner['name'])} for bot in selected]
    if len(requested) > MAX_SOCIALS:
        raise ValueError('These commands need more than 120 social slots. Select fewer commands or companions')
    used = set()
    for social in requested:
        label, commands = social['label'], social['lines']
        previous = owned.get(_social_key(social))
        if previous is None and social.get('action') == 'spawn_group':
            # Only a prior launcher receipt may adopt a legacy per-bot button,
            # and only if the exact current label/commands still match below.
            previous = owned.get(social['bot_ids'][0])
        reuse = bool(previous and previous.get('label') == label and
                     previous.get('lines') == commands and type(previous.get('page')) is int and type(previous.get('button')) is int and
                     1 <= previous['page'] <= 10 and 1 <= previous['button'] <= 12 and
                     _social_values(ini, previous['page'], previous['button']) == [label, '0', *commands, *[''] * (5 - len(commands))])
        if reuse:
            page, button = previous['page'], previous['button']
        elif free:
            page, button = free.pop(0)
        else:
            raise ValueError('There are not enough empty social slots for these commands')
        if (page, button) in used:
            raise ValueError('Recorded bot social slots are ambiguous')
        used.add((page, button))
        result['socials'].append(dict(social, page=page, button=button, existing=reuse))
    bars, buttons = (1, 10) if engine.profile == 'takp' else (10, 12)
    for bar in range(1, bars + 1):
        section = 'HotButtons' + (str(bar) if bar > 1 else '')
        for page in range(1, 11):
            for button in range(1, buttons + 1):
                if not ini.get(section, f'Page{page}Button{button}').strip():
                    result['empty_hotbar_slots'].append({'bar': bar, 'page': page, 'button': button})
    result['preview_token'] = _digest({'context': context, 'file': path.name, 'revision': _sha(raw),
                                       'bots': selected, 'socials': result['socials']})
    return result, (client, path, raw, ini, context, records)


def preview(engine, owner, bots, args):
    return _plan(engine, owner, bots, args)[0]


def _require_stopped(engine):
    if any(getattr(process, 'poll', lambda: 0)() is None for name, process in getattr(engine, 'processes', {}).items() if name.startswith('client')):
        raise ValueError('Stop the embedded client before changing its socials')
    # Android also holds the native client lock when submitting writes. This
    # independent supervisor check protects direct daemon API calls.
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            if directory.stat().st_uid == os.getuid() and any(part.endswith(b'/client_runner.py') for part in (directory / 'cmdline').read_bytes().split(b'\0')):
                raise ValueError('Stop the embedded client before changing its socials')
        except (OSError, ProcessLookupError):
            continue


def _write_json(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=True, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())


def _replace(engine, owner, client, path, original, updated, context, record):
    engine.check_cancel()
    _require_stopped(engine)
    root = _backup_root(engine)
    root.mkdir(parents=True, exist_ok=True)
    if sum(1 for _ in root.iterdir()) >= MAX_BACKUPS:
        raise ValueError('Bot social backup history reached its limit; remove old backups in Files')
    identity = secrets.token_hex(12)
    backup = root / identity
    backup.mkdir()
    temporary = '.trasc-bot-socials-' + identity + '.tmp'
    descriptor, committed = None, False
    record = dict(record, format=1, id=identity, context=context, character_file=path.name,
                  created_at=time.time(), before_sha256=_sha(original), after_sha256=_sha(updated), state='prepared')
    try:
        with (backup / path.name).open('xb') as output:
            output.write(original)
            output.flush()
            os.fsync(output.fileno())
        _write_json(backup / 'record.json', record)
        descriptor = os.open(client, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        before_directory = os.fstat(descriptor)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
        with os.fdopen(fd, 'wb') as output:
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        engine.check_cancel()
        _require_stopped(engine)
        current = engine._local_client()
        if (current.stat().st_dev, current.stat().st_ino) != (before_directory.st_dev, before_directory.st_ino) or _read(client_file(current, path.name)) != original:
            raise ValueError('Character settings changed. Preview socials again before installing')
        # Revalidate the owner filename immediately before the anchored rename.
        _, files = _character_files(engine, owner)
        if not any(item['file'] == path.name and item.get('supported') for item in files):
            raise ValueError('Character settings identity changed. Preview again')
        os.replace(temporary, path.name, src_dir_fd=descriptor, dst_dir_fd=descriptor)
        committed = True
        os.fsync(descriptor)
        # A prepared receipt plus an exact after digest also recognizes the
        # rename after a process crash; no second social allocation is needed.
        updated_record = backup / 'record.installed.json'
        _write_json(updated_record, dict(record, state='installed'))
        os.replace(updated_record, backup / 'record.json')
        return record
    finally:
        if descriptor is not None:
            try:
                os.unlink(temporary, dir_fd=descriptor)
            except FileNotFoundError:
                pass
            os.close(descriptor)
        if not committed:
            shutil.rmtree(backup)


def _placements(value, socials, profile):
    if not isinstance(value, list) or len(value) > len(socials):
        raise ValueError('Choose at most one hotbar placement per social')
    known = {_social_key(social) for social in socials}
    result, bots, slots = [], set(), set()
    for placement in value:
        if not isinstance(placement, dict):
            raise ValueError('Choose a valid bot hotbar placement')
        key = 'social_id' if 'social_id' in placement else 'bot_id'
        if set(placement) != {key, 'bar', 'page', 'button'}:
            raise ValueError('Choose a valid bot hotbar placement')
        if any(type(placement[field]) is not int for field in ('bar', 'page', 'button')):
            raise ValueError('Hotbar positions must be ordinary integers')
        if (key == 'bot_id' and type(placement[key]) is not int) or (key == 'social_id' and
                (not isinstance(placement[key], str) or not SOCIAL_ID.fullmatch(placement[key]))):
            raise ValueError('Choose a valid social identity')
        bot, bar, page, button = (placement[field] for field in (key, 'bar', 'page', 'button'))
        if bot not in known or bot in bots or (bar, page, button) in slots or not 1 <= bar <= (1 if profile == 'takp' else 10) or not 1 <= page <= 10 or not 1 <= button <= (10 if profile == 'takp' else 12):
            raise ValueError('Choose distinct hotbar positions supported by this client')
        bots.add(bot)
        slots.add((bar, page, button))
        result.append(dict(placement))
    return sorted(result, key=lambda item: (1, item['social_id']) if 'social_id' in item else (0, item['bot_id']))


def install(engine, owner, bots, args):
    _require_stopped(engine)
    context = _identity(engine, owner, args)
    actions = _actions(engine.profile, args)
    selected = _selected(bots, MAX_SELECTED if actions else 5)
    client, _, path, raw, _, reason = _character(engine, owner, args)
    if reason:
        raise ValueError(reason)
    # Echoing an already-applied preview is a retry, not another allocation.
    request = {'context': context, 'bots': selected, 'file': path.name,
               'revision': args.get('file_revision'), 'token': args.get('preview_token'),
               'placements': args.get('placements', []), 'spawn_pause': args.get('spawn_pause', 20)}
    if actions:
        request['actions'] = [entry[0] for entry in actions]
    request_sha = _digest(request)
    records = _records(engine, context, path.name)
    for record in records:
        if record.get('request_sha256') == request_sha and record['after_sha256'] == _sha(raw):
            return {'message': 'These bot socials are already installed.', 'installed': True, 'reused': True,
                    'character_file': path.name, 'file_revision': _sha(raw), 'backup_id': record['id'],
                    'socials': record.get('socials', []), 'placements': record.get('placements', [])}
    result, details = _plan(engine, owner, bots, args)
    if args.get('file_revision') != result['file_revision'] or args.get('preview_token') != result['preview_token']:
        raise ValueError('Character settings or bot selection changed. Preview socials again before installing')
    client, path, raw, ini, context, records = details
    placements = _placements(args.get('placements', []), result['socials'], engine.profile)
    changes = {}
    for social in result['socials']:
        prefix = f'Page{social["page"]}Button{social["button"]}'
        changes[('Socials', prefix + 'Name')] = social['label']
        changes[('Socials', prefix + 'Color')] = '0'
        for line in range(1, 6):
            changes[('Socials', prefix + 'Line' + str(line))] = social['lines'][line - 1] if line <= len(social['lines']) else ''
    social_by_id = {_social_key(social): social for social in result['socials']}
    owned_bindings = {(p.get('bar'), p.get('page'), p.get('button'), _social_key(p)) for record in records for p in record.get('placements', []) if isinstance(p, dict)}
    for placement in placements:
        section = 'HotButtons' + (str(placement['bar']) if placement['bar'] > 1 else '')
        key = f'Page{placement["page"]}Button{placement["button"]}'
        binding = _binding(engine.profile, social_by_id[_social_key(placement)])
        existing = ini.get(section, key)
        slot = (placement['bar'], placement['page'], placement['button'], _social_key(placement))
        if existing.strip() and not (slot in owned_bindings and existing == binding):
            raise ValueError('That hotbar position is occupied. Choose a free position')
        changes[(section, key)] = binding
    updated = ini.merge(changes)
    if updated == raw:
        return {'message': 'These bot socials and hotbar positions are already installed.', 'installed': True,
                'reused': True, 'character_file': path.name, 'file_revision': _sha(raw),
                'socials': result['socials'], 'placements': placements}
    record = _replace(engine, owner, client, path, raw, updated, context,
                      {'operation': 'install', 'request_sha256': request_sha,
                       'socials': result['socials'], 'placements': placements})
    return {'message': 'Bot command socials installed. Start the client and use the chosen buttons.',
            'installed': True, 'reused': False, 'character_file': path.name, 'file_revision': _sha(updated),
            'backup_id': record['id'], 'backup': BACKUPS + '/' + record['id'] + '/' + path.name,
            'socials': result['socials'], 'placements': placements}


def restore(engine, args):
    """The caller supplies a freshly database-validated owner in _owner."""
    _require_stopped(engine)
    owner = args.get('_owner')
    context = _identity(engine, owner, args)
    client, _, path, raw, _, reason = _character(engine, owner, args)
    if reason:
        raise ValueError(reason)
    records = _records(engine, context, path.name)
    record = next((r for r in records if r['id'] == args.get('backup_id')), None)
    if record is None:
        raise ValueError('Choose a social backup belonging to this character and deployment')
    # If the first restore committed but its response was lost, recognize the
    # exact owner-scoped transition without requiring a second file write.
    for recovery in records:
        if (recovery['operation'] == 'restore' and recovery.get('restored_from') == record['id'] and
                recovery['before_sha256'] == args.get('file_revision') == record['after_sha256'] and
                recovery['after_sha256'] == _sha(raw) == record['before_sha256']):
            return {'message': 'These previous character settings are already restored.', 'restored': True,
                    'reused': True, 'character_file': path.name, 'file_revision': _sha(raw),
                    'backup_id': recovery['id']}
    if args.get('file_revision') != _sha(raw):
        raise ValueError('Character settings changed. Refresh before restoring socials')
    if record['after_sha256'] != _sha(raw):
        raise ValueError('Character settings changed since this backup. Restore would overwrite later changes')
    saved = _read(_backup_root(engine) / record['id'] / path.name)
    result = _replace(engine, owner, client, path, raw, saved, context,
                      {'operation': 'restore', 'restored_from': record['id'], 'socials': [], 'placements': []})
    return {'message': 'Previous character socials and hotbar settings restored.', 'restored': True,
            'character_file': path.name, 'file_revision': _sha(saved), 'backup_id': result['id']}
