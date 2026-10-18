"""Reviewed deployment of the installed Triptych quest and plugin tree.

This module never fetches source, changes a database, runs an executable patch,
removes a runtime-only file, or touches another world profile. The shared
transaction service owns byte comparison, durable backups and recovery.
"""
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

import custom_deployment as deployment

KIND = 'quest_sync'
SOURCE_LIMIT = 1024 * 1024

# These witnesses are checked individually against the selected checkout, rather
# than treating an existing directory as proof that an update was installed.
FEATURES = (
    {'name': 'Cake Defense baking and shroud mission', 'update': 'October 9',
     'files': ('Release-NMS-Quests/bazaar/Wendel_Sweetcrumb.lua',
               'Release-NMS-Quests/rivervale/#Cake_Defense_Baker.lua',
               'Release-NMS-Quests/rivervale/player.lua',
               'Release-NMS-Quests/global/global_player.pl'),
     'note': 'Quest deployment does not install its database content or rebuild the shroud engine.'},
    {'name': 'Deity rank 2 quests', 'update': 'October 9',
     'files': ('Release-NMS-Plugins/deity_blessings.pl',
               'Release-NMS-Quests/bazaar/Blessing_of_the_Gods.pl',
               'Release-NMS-Quests/potranquility/Blessing_of_the_Gods.pl',
               'Release-NMS-Quests/eastkarana/Avatar_of_Bertoxxulous.pl',
               'Release-NMS-Quests/butcher/Roderik_High_Priest_of_Brell.pl',
               'Release-NMS-Quests/feerrott/Avatar_of_Cazic-Thule.pl',
               'Release-NMS-Quests/southro/an_Aspect_of_Erollisi_Marr.pl',
               'Release-NMS-Quests/poknowledge/Fizzlethorpe_Bristlebanes_Image.pl',
               'Release-NMS-Quests/innothule/an_evil_little_imp.pl',
               'Release-NMS-Quests/southkarana/Avatar_of_Karana.pl',
               'Release-NMS-Quests/potranquility/Avatar_of_Mithaniel_Marr.pl',
               'Release-NMS-Quests/erudsxing/Primate_of_Prexus.pl',
               'Release-NMS-Quests/potranquility/Avatar_of_Quellious_the_Tranquil.pl',
               'Release-NMS-Quests/potranquility/Avatar_of_Rallos_Zek.pl',
               'Release-NMS-Quests/qeynos2/Helera_Garet.pl',
               'Release-NMS-Quests/northro/Avatar_of_Solusek_Ro.pl',
               'Release-NMS-Quests/potranquility/Herald_of_Justice_Due.pl',
               'Release-NMS-Quests/gfaydark/Avatar_of_Tunare.pl',
               'Release-NMS-Quests/poknowledge/a_crystalline_avatar.pl'),
     'note': 'The corresponding deity and NPC database content must already be installed.'},
    {'name': 'Halloween and Nights of the Dead quests', 'update': 'October 9',
     'files': ('Release-NMS-Quests/lua_modules/halloween.lua',
               'Release-NMS-Quests/poknowledge/Edmund_Strangeways.pl',
               'Release-NMS-Quests/poknowledge/Illis_Taberish.pl',
               'Release-NMS-Quests/poknowledge/Rhaeda_Evel.pl',
               'Release-NMS-Quests/crescent/Jilian_Florantine.pl',
               'Release-NMS-Quests/gfaydark/Elder_Ritualist_Longshadow.pl',
               'Release-NMS-Quests/gfaydark/Skinwalker.pl',
               'Release-NMS-Quests/gfaydark/a_revealed_skinwalker1.pl',
               'Release-NMS-Quests/gfaydark/a_revealed_skinwalker2.pl',
               'Release-NMS-Quests/gfaydark/a_revealed_skinwalker3.pl'),
     'note': 'Seasonal event activation and associated NPC database setup are separate.'},
    {'name': 'Shroud quest support', 'update': 'October 9',
     'files': ('Release-NMS-Quests/bazaar/Wendel_Sweetcrumb.lua',
               'Release-NMS-Quests/rivervale/#Cake_Defense_Baker.lua',
               'Release-NMS-Quests/rivervale/player.lua',
               'Release-NMS-Quests/global/global_player.pl',
               'Release-NMS-Server/zone/shroud.cpp'),
     'note': 'Shroud support also needs the matching built server and database migration; this scan only deploys scripts.'},
    {'name': 'Legends of Norrath support', 'update': 'October 16',
     'files': ('Release-NMS-Quests/global/items/script_8884.pl',
               'Release-NMS-Server/world/lon_service.cpp',
               'Release-NMS-Server/zone/nms_lon_session.cpp'),
     'note': 'The item script is the Fang of Chalandria click handler. Import client card data separately; LoN also requires matching server binaries, client DLL and database. Service initialization must be checked after restart.'},
    {'name': 'Native achievements', 'update': 'October 16',
     'files': ('Release-NMS-Server/zone/achievement_manager.cpp',
               'Release-NMS-Server/zone/client_achievements.cpp',
               'Release-NMS-Server/common/achievements.cpp',
               'Release-NMS-Server/common/database/database_update_manifest.cpp'),
     'note': 'The native achievement feature is server code and database content, not proof supplied by the older Aurelian Stoneward reward quest. No migration or rebuild is performed.'},
    {'name': 'Mercenary support', 'update': 'October 16',
     'files': ('Release-NMS-Plugins/NMS_sod_utils.pl',
               'Release-NMS-Server/zone/merc.cpp'),
     'note': 'The plugin supplies tier and task support. Mercenary engine changes and database setup require the corresponding server build and existing migrations.'},
)


def _check(engine):
    checker = getattr(engine, 'check_cancel', None)
    if checker:
        checker()


def _source(engine):
    deployment.require_custom(engine)
    work = Path(engine.work).absolute()
    root = work / 'sources/current'
    for candidate in (work, work / 'sources', root):
        if candidate.is_symlink():
            raise ValueError('Quest source cannot be a symbolic link')
    if not root.is_dir():
        raise ValueError('Import the Triptych source for this Custom profile first')
    for name in ('Release-NMS-Quests', 'Release-NMS-Plugins'):
        candidate = root / name
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError('The selected source is missing an ordinary ' + name + ' directory; refresh or import the complete Triptych source')
    return root


def _source_identity(engine, root=None):
    root = root or _source(engine)
    marker = root / 'trasc-source.json'
    metadata = {}
    marker_sha = None
    if marker.exists() or marker.is_symlink():
        if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > SOURCE_LIMIT:
            raise ValueError('Invalid source provenance; import the source again')
        raw = marker.read_bytes()
        marker_sha = hashlib.sha256(raw).hexdigest()
        try:
            metadata = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise ValueError('Invalid source provenance; import the source again') from error
        if not isinstance(metadata, dict):
            raise ValueError('Invalid source provenance; import the source again')
    revision = metadata.get('commit')
    if revision is not None and not re.fullmatch(r'[0-9a-fA-F]{40}', str(revision)):
        raise ValueError('The selected source has an invalid commit identity')
    return {'revision': revision.lower() if revision else None,
            'commit': revision.lower() if revision else None,
            'source_marker_sha256': marker_sha,
            'source_path': str(root),
            'repository': metadata.get('repo') if isinstance(metadata.get('repo'), str) else None,
            'ref': metadata.get('ref') if isinstance(metadata.get('ref'), str) else None,
            'provenance': metadata.get('type', 'unrecorded'),
            'revision_label': revision.lower() if revision else 'Archive import: commit not recorded'}


def _lua_destinations(layout):
    values = list(layout.get('lua_module_paths', [layout['lua_modules']]))
    values.append(str(Path(layout['quests']) / 'lua_modules'))
    return list(dict.fromkeys(str(Path(value)) for value in values))


def _groups(engine, root=None):
    root = root or _source(engine)
    layout = deployment.destinations(engine)
    quests = root / 'Release-NMS-Quests'
    lua = quests / 'lua_modules'
    if lua.is_symlink():
        raise ValueError('Quest Lua module source cannot be a symbolic link')
    quest_destination = Path(layout['quests'])
    exclusions = {'plugins', 'lua_modules'}
    lua_destinations = _lua_destinations(layout)
    for destination in [layout['plugins'], *lua_destinations]:
        path = Path(destination)
        if path != quest_destination and path.is_relative_to(quest_destination):
            relative = path.relative_to(quest_destination).as_posix()
            if relative not in ('plugins', 'lua_modules') and (quests / relative).exists():
                raise ValueError('Configured helper directory overlaps quest source content: ' + relative)
            exclusions.add(relative)
    groups = [
        {'name': 'quests', 'source': quests, 'destination': quest_destination,
         'exclude': sorted(exclusions)},
        {'name': 'plugins', 'source': root / 'Release-NMS-Plugins',
         'destination': Path(layout['plugins']), 'exclude': []},
    ]
    default = str(quest_destination / 'lua_modules')
    for index, destination in enumerate(lua_destinations):
        group_name = ('lua_modules' if index == 0 else 'lua_modules_default'
                      if destination == default else 'lua_modules_' + str(index + 1))
        groups.append({'name': group_name, 'source': lua,
                       'destination': Path(destination), 'exclude': []})
    return groups


def _hash(path, engine):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            _check(engine)
            block = stream.read(1024 * 1024)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def _witness(root, relative):
    """Validate a fixed repository witness without following linked ancestors."""
    if root.is_symlink():
        raise ValueError('Update witness root is a symbolic link')
    path = root / relative
    current = root
    for part in Path(relative).parts:
        if part in ('.', '..') or '\\' in part:
            raise ValueError('Invalid update witness')
        current = current / part
        if current.is_symlink():
            raise ValueError('Update witness is a symbolic link')
    return path


def feature_report(engine):
    """Check the real update witnesses; do not claim SQL/code deployment."""
    root = _source(engine)
    layout = deployment.destinations(engine)
    result = []
    for feature in FEATURES:
        evidence = []
        for relative in feature.get('files', ()):
            _check(engine)
            item = {'source': relative, 'state': 'missing_or_additional_setup'}
            try:
                source = _witness(root, relative)
                if relative.startswith('Release-NMS-Quests/lua_modules/'):
                    name = relative.removeprefix('Release-NMS-Quests/lua_modules/')
                    placements = [(Path(path), name) for path in _lua_destinations(layout)]
                elif relative.startswith('Release-NMS-Quests/'):
                    placements = [(Path(layout['quests']), relative.removeprefix('Release-NMS-Quests/'))]
                elif relative.startswith('Release-NMS-Plugins/'):
                    placements = [(Path(layout['plugins']), relative.removeprefix('Release-NMS-Plugins/'))]
                else:
                    if source.is_file():
                        item['state'] = 'database_or_server_code'
                    evidence.append(item)
                    continue
                item['destination'] = str(placements[0][0] / placements[0][1])
                item['destinations'] = []
                if source.is_file():
                    item['source_sha256'] = _hash(source, engine)
                    item['state'] = 'source_present_deployed'
                    for dest_root, name in placements:
                        placement = {'path': str(dest_root / name), 'state': 'source_present_not_deployed'}
                        try:
                            # Fixed witnesses and configured roots receive the
                            # same link refusal as the full transfer inventory.
                            checked = _witness(dest_root, name)
                            if checked.is_file():
                                placement['sha256'] = _hash(checked, engine)
                                if placement['sha256'] == item['source_sha256']:
                                    placement['state'] = 'source_present_deployed'
                        except (OSError, ValueError) as error:
                            placement['error'] = str(error)
                            item['error'] = str(error)
                        if placement['state'] != 'source_present_deployed':
                            item['state'] = 'source_present_not_deployed'
                        item['destinations'].append(placement)
                    item['destination_sha256'] = item['destinations'][0].get('sha256')
            except (OSError, ValueError) as error:
                item['error'] = str(error)
            evidence.append(item)
        states = {entry['state'] for entry in evidence}
        if not states or 'missing_or_additional_setup' in states:
            state = 'missing_or_additional_setup'
        elif 'source_present_not_deployed' in states:
            state = 'source_present_not_deployed'
        elif 'source_present_deployed' in states:
            state = 'source_present_deployed'
        else:
            state = 'database_or_server_code'
        result.append({'name': feature['name'], 'update': feature['update'],
                       'state': state, 'files': evidence, 'note': feature.get('note', '')})
    return {'features': result,
            'scope': 'Filesystem verification only. No database migration, player data change, server rebuild, or client executable patch is performed.',
            'restart_required': True}


def _source_fingerprint(engine, root=None, read_only=False):
    # Fingerprint unique source content, independent of the number of runtime
    # mirrors. A changed directory configuration is not a source file edit.
    reader = (SimpleNamespace(work=engine.work, profile=engine.profile, check_cancel=lambda: None)
              if read_only else engine)
    root = root or _source(engine)
    content = {}
    for name, path, exclusions in (
            ('quests', root / 'Release-NMS-Quests', ('plugins', 'lua_modules')),
            ('plugins', root / 'Release-NMS-Plugins', ()),
            ('lua_modules', root / 'Release-NMS-Quests/lua_modules', ())):
        entries = deployment.inventory(reader, path, exclusions)
        content[name] = deployment.identity({
            key: {field: value.get(field) for field in ('bytes', 'sha256', 'error')}
            for key, value in entries.items()})
    return deployment.identity(content)


def _directory_report(engine):
    layout = deployment.destinations(engine)
    return {key: value for key, value in layout.items()
            if key in ('runtime', 'quests', 'plugins', 'lua_modules',
                       'quest_paths', 'plugin_paths', 'lua_module_paths')}


def _freshness(engine, report):
    source = dict(report.get('source', {}))
    source['last_commit'] = report.get('last_commit')
    source['last_sync'] = report.get('last_sync')
    source['dirty'] = None
    previous = (report.get('last_source_identity') or {}).get('tree_sha256')
    if previous:
        fingerprint = _source_fingerprint(engine, read_only=True)
        source['tree_sha256'] = fingerprint
        source['dirty'] = (fingerprint != previous or source.get('commit') != report.get('last_commit'))
    report['source'] = source
    report['source_changed_since_last_sync'] = source['dirty']
    return report


def status(engine, args=None):
    deployment.require_custom(engine)
    result = dict(deployment.status(engine, KIND))
    try:
        root = _source(engine)
        result['source'] = _source_identity(engine, root)
        result['destinations'] = _directory_report(engine)
        result['source_available'] = True
        _freshness(engine, result)
    except (ValueError, OSError) as error:
        result['source_available'] = False
        result['source_error'] = str(error)
    result['database_untouched'] = True
    return result


def scan(engine, args=None):
    root = _source(engine)
    groups = _groups(engine, root)
    features = feature_report(engine)
    source = _source_identity(engine, root)
    source['tree_sha256'] = _source_fingerprint(engine, root)
    report = deployment.preview(engine, KIND, groups, source, extra={'features': features})
    if report.get('source_fingerprint'):
        saved = deployment.load_preview(engine, KIND, report['token'])
        canonical = {}
        for group in saved['groups']:
            if group['name'] in ('quests', 'plugins', 'lua_modules'):
                canonical[group['name']] = deployment.identity({
                    key: {field: value.get(field) for field in ('bytes', 'sha256', 'error')}
                    for key, value in group['source_inventory'].items()})
        if deployment.identity(canonical) != source['tree_sha256']:
            raise ValueError('Quest source changed during inspection; scan again')
    # Keep source/UI field names consistent between preflight and status.
    report.setdefault('source', source)
    report.setdefault('features', features)
    history = deployment.status(engine, KIND)
    report['source'].update(last_commit=history.get('last_commit'), last_sync=history.get('last_sync'),
                            dirty=(source['tree_sha256'] != (history.get('last_source_identity') or {}).get('tree_sha256') or
                                   source.get('commit') != history.get('last_commit'))
                            if (history.get('last_source_identity') or {}).get('tree_sha256') else None)
    report['directory_policy'] = 'Quests and Perl plugins deploy to the first configured search directory; additional quest and plugin directories are preserved. Lua modules deploy to every configured Lua directory and quests/lua_modules. Counts include every placement.'
    report['group_labels'] = {group['name']: ('Lua modules' if group['name'].startswith('lua_modules') else group['name'].capitalize()) + ' → ' + str(group['destination']) for group in groups}
    report['lua_destinations'] = _lua_destinations(deployment.destinations(engine))
    report['configured_directories'] = _directory_report(engine)
    report['database_untouched'] = True
    return report


def files(engine, args):
    deployment.require_custom(engine)
    return deployment.details(engine, args, KIND)


def diff(engine, args):
    deployment.require_custom(engine)
    return deployment.diff(engine, KIND, args)


def apply(engine, args):
    _source(engine)
    result = deployment.apply(engine, KIND, args)
    # The transaction is durably committed. A late Cancel or a diagnostic error
    # must not misreport a successful deployment as a failed unrolled-back job.
    reader = SimpleNamespace(work=engine.work, profile=engine.profile, check_cancel=lambda: None)
    try:
        result['features'] = feature_report(reader)
    except (ValueError, OSError) as error:
        result['post_check_error'] = str(error)
        result['features'] = {'features': [], 'scope': 'Post-deployment verification needs attention; the file transaction committed successfully.'}
    result['database_untouched'] = True
    result['restart_required'] = True
    return result
