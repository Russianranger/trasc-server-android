"""Explicit profile-local skin selection and reversible, surgical layout merging."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
import client_ui

FILE = 'UI_Rusuty_Traditional.ini'
XML = b'<XML><Screen item="PlayerWindow"/><Screen item="GroupWindow"/><Screen item="ChatWindow"/><Screen item="EQMainWnd"/><Screen item="CastSpellWnd"/><Screen item="PetInfoWindow"/></XML>'
ORIGINAL = (b'\xef\xbb\xbf; personal \x85 preference\r\n[Main]\r\n  UISkin = Default  ; keep this comment\r\nAtlasSkin=Classic\r\n'
            b'[PlayerWindow]\r\nShow=0\r\nXPos1280x720=50\r\nAlpha=192\r\nBGTint.red=13\r\n'
            b'[ChatManager]\r\nNumWindows=1\r\nChannelMap=private preference\r\n'
            b'[MainChat]\r\nFont=7\r\n[Unknown]\r\nCustom=private value\r\n')
PRESET = (b'[Main]\r\nUISkin=WrongFolder\r\nAtlasSkin=DoNotCopy\r\n'
          b'[PlayerWindow]\r\nShow=1\r\nXPos1280x720=1099\r\nYPos1280x720=0\r\nWidth1280x720=181\r\nHeight1280x720=185\r\n'
          b'RestoreWidth1280x720=181\r\nMinimized1280x720=0\r\nLocked=false\r\nINIVersion=1\r\nAlpha=255\r\nBGTint.red=255\r\n'
          b'[CastSpellWnd]\r\nShow=1\r\nXPos1280x720=128\r\nYPos1280x720=0\r\nWidth1280x720=51\r\nHeight1280x720=464\r\nINIVersion=1\r\n'
          b'[MainChat]\r\nXPos1280x720=179\r\nYPos1280x720=480\r\nWidth1280x720=460\r\nHeight1280x720=240\r\nFont=3\r\n'
          b'[Chat 1]\r\nShow=1\r\nXPos1280x720=639\r\n'
          b'[ChatManager]\r\nNumWindows=2\r\nChannelMap=do not copy\r\n'
          b'[Unknown]\r\nShow=1\r\nXPos1280x720=1\r\nCustom=do not copy\r\n'
          b'[ViewPort1280x720]\r\nX=179\r\nY=0\r\nW=920\r\nH=480\r\nXScale=0\r\nYScale=0.0\r\nWScale=0\r\nHScale=0\r\n')


class ClientUiActivation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.engines = {profile: Engine(self.root / profile, profile) for profile in ('custom', 'traditional')}
        for engine in self.engines.values():
            client = engine.work / 'client/current'
            client.mkdir()
            (client / 'trasc-client.json').write_text('{"imported":true}')
            (client / FILE).write_bytes(ORIGINAL)
            (client / 'eqclient.ini').write_bytes(b'[Defaults]\r\nKeep=TRUE\r\n')
            for skin in ('Default', 'Stone'):
                folder = client / 'UIFILES' / skin
                folder.mkdir(parents=True)
                (folder / 'EQUI.xml').write_bytes(XML)
            (client / 'UIFILES/Stone' / (FILE + '.txt')).write_bytes(PRESET)
        self.engine = self.engines['traditional']
        self.client = self.engine.work / 'client/current'

    def revision(self, engine=None):
        engine = engine or self.engine
        return hashlib.sha256((engine.work / 'client/current' / FILE).read_bytes()).hexdigest()

    def activate(self, engine=None, **overrides):
        engine = engine or self.engine
        arguments = dict(skin='Stone', character_file=FILE, revision=self.revision(engine), apply_layout=False)
        arguments.update(overrides)
        return engine.dispatch('activate_client_ui', arguments)

    def restore(self, identity, **overrides):
        arguments = dict(activation_id=identity, character_file=FILE, revision=self.revision())
        arguments.update(overrides)
        return self.engine.dispatch('restore_client_ui', arguments)

    def test_selection_is_byte_surgical_in_both_profiles_and_default_is_selectable(self):
        for profile, engine in self.engines.items():
            with self.subTest(profile=profile):
                before = {str(p.relative_to(engine.work / 'client/current')): p.read_bytes()
                          for p in (engine.work / 'client/current').rglob('*') if p.is_file()}
                result = self.activate(engine)
                target = engine.work / 'client/current' / FILE
                self.assertEqual(target.read_bytes(), ORIGINAL.replace(b'UISkin = Default', b'UISkin = Stone'))
                self.assertEqual((engine.work / result['backup']).read_bytes(), ORIGINAL)
                self.assertFalse(result['layout_applied'])
                self.assertEqual(result['ui']['characters'][0]['skin'], 'Stone')
                self.assertEqual(result['ui']['characters'][0]['revision'], self.revision(engine))
                for name, value in before.items():
                    if name != FILE:
                        self.assertEqual((engine.work / 'client/current' / name).read_bytes(), value)
                default = self.activate(engine, skin='default')
                self.assertEqual(default['skin'], 'Default')
                self.assertEqual(target.read_bytes(), ORIGINAL)

    def test_explicit_layout_changes_only_valid_window_geometry_and_visibility(self):
        result = self.activate(apply_layout=True)
        raw = (self.client / FILE).read_bytes()
        entries = client_ui._parse_ini(raw)['entries']
        value = lambda section, key: entries[(section.casefold(), key.casefold())]['value']
        self.assertTrue(result['layout_applied'])
        self.assertEqual(value('Main', 'UISkin'), 'Stone')
        self.assertEqual(value('Main', 'AtlasSkin'), 'Classic')
        self.assertEqual(value('PlayerWindow', 'XPos1280x720'), '1099')
        self.assertEqual(value('PlayerWindow', 'Alpha'), '192')
        self.assertEqual(value('PlayerWindow', 'BGTint.red'), '13')
        self.assertEqual(value('PlayerWindow', 'Minimized1280x720'), '0')
        self.assertEqual(value('CastSpellWnd', 'Width1280x720'), '51')
        self.assertEqual(value('CastSpellWnd', 'INIVersion'), '1')
        self.assertEqual(value('MainChat', 'Width1280x720'), '460')
        self.assertEqual(value('MainChat', 'Font'), '7')
        self.assertEqual(value('ChatManager', 'NumWindows'), '1')
        self.assertEqual(value('ChatManager', 'ChannelMap'), 'private preference')
        self.assertEqual(value('Unknown', 'Custom'), 'private value')
        self.assertNotIn(('unknown', 'show'), entries)
        self.assertNotIn(('chat 1', 'show'), entries)
        self.assertEqual(value('ViewPort1280x720', 'W'), '920')
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf; personal \x85 preference\r\n'))
        self.assertEqual((self.engine.work / result['backup']).read_bytes(), ORIGINAL)

    def test_existing_dynamic_chat_pane_is_positioned_without_filter_changes(self):
        (self.client / FILE).write_bytes(ORIGINAL + b'[Chat 1]\r\nXPos1280x720=5\r\nFont=8\r\n')
        self.activate(apply_layout=True)
        entries = client_ui._parse_ini((self.client / FILE).read_bytes())['entries']
        self.assertEqual(entries[('chat 1', 'xpos1280x720')]['value'], '639')
        self.assertEqual(entries[('chat 1', 'font')]['value'], '8')

    def test_status_exposes_only_selection_revision_and_valid_matching_layout(self):
        result = client_ui.status(self.engine)
        self.assertEqual(result['characters'][0], dict(file=FILE, skin='Default', revision=self.revision(), layout_skins=['Stone']))
        self.assertNotIn('private preference', json.dumps(result))
        (self.client / 'UIFILES/Stone' / (FILE + '.txt')).write_bytes(b'[PlayerWindow]\nXPos1280x720=notnumeric\n')
        self.assertEqual(client_ui.status(self.engine)['characters'][0]['layout_skins'], [])

    def test_stale_revision_and_bad_argument_types_leave_original(self):
        for arguments in (dict(revision='0' * 64), dict(revision=None), dict(apply_layout='true'),
                          dict(character_file='../' + FILE), dict(skin='../Stone'), dict(skin='Missing')):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.activate(**arguments)
        self.assertEqual((self.client / FILE).read_bytes(), ORIGINAL)

    def test_utf16_and_duplicate_sections_keys_are_rejected_without_echoing_values(self):
        for raw in (b'\xff\xfe[\x00M\x00a\x00i\x00n\x00]\x00',
                    b'[Main]\nUISkin=Default\n[main]\nUISkin=secret value\n',
                    b'[Main]\nUISkin=Default\nuiskin=secret value\n', b'[Main]\nprivate line without equals\n'):
            with self.subTest(raw=raw):
                (self.client / FILE).write_bytes(raw)
                with self.assertRaises(ValueError) as error:
                    self.activate()
                self.assertNotIn('secret value', str(error.exception))
                self.assertEqual((self.client / FILE).read_bytes(), raw)
                self.assertEqual(client_ui.status(self.engine)['characters'], [])

    def test_case_safe_character_skin_and_preset_names_use_installed_spelling(self):
        self.activate(character_file=FILE.lower(), skin='sToNe')
        self.assertEqual(client_ui.status(self.engine)['characters'][0]['file'], FILE)
        preset = self.client / 'UIFILES/Stone' / (FILE + '.txt')
        preset.rename(preset.with_name((FILE + '.txt').lower()))
        self.activate(apply_layout=True)
        for path, payload in ((self.client / FILE.lower(), ORIGINAL),
                              (self.client / 'UIFILES/stone/EQUI.xml', XML)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            with self.assertRaisesRegex(ValueError, 'Ambiguous'):
                self.activate()
            if path.name.endswith('.ini'):
                path.unlink()

    def test_duplicate_or_linked_preset_and_invalid_geometry_preserve_original(self):
        preset = self.client / 'UIFILES/Stone' / (FILE + '.txt')
        for raw in (b'[PlayerWindow]\nXPos1280x720=999999\n',
                    b'[PlayerWindow]\nShow=execute\n', b'[PlayerWindow]\nWidth1280x720=-1\n',
                    b'[ViewPort1280x720]\nXScale=NaN\n', b'[PlayerWindow]\nXPos1280x720=3\nxpos1280x720=4\n'):
            with self.subTest(raw=raw):
                preset.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.activate(apply_layout=True)
                self.assertEqual((self.client / FILE).read_bytes(), ORIGINAL)
        preset.unlink()
        preset.symlink_to(self.client / FILE)
        with self.assertRaisesRegex(ValueError, 'symlinks|linked'):
            self.activate(apply_layout=True)

    def test_missing_layout_and_no_equi_skin_are_rejected(self):
        (self.client / 'UIFILES/Stone' / (FILE + '.txt')).unlink()
        with self.assertRaisesRegex(ValueError, 'no included layout'):
            self.activate(apply_layout=True)
        (self.client / 'UIFILES/Stone/EQUI.xml').unlink()
        with self.assertRaisesRegex(ValueError, 'EQUI XML'):
            self.activate()

    def test_cancel_or_atomic_replacement_failure_retains_original_and_removes_temporary(self):
        self.engine.cancel.set()
        with self.assertRaisesRegex(ValueError, 'cancel'):
            self.activate()
        self.engine.cancel.clear()
        original_replace = os.replace
        def fail(source, destination, **kwargs):
            if kwargs.get('dst_dir_fd') is not None:
                raise OSError('Storage failed')
            return original_replace(source, destination, **kwargs)
        with patch('client_ui.os.replace', side_effect=fail), self.assertRaisesRegex(OSError, 'Storage failed'):
            self.activate()
        self.assertEqual((self.client / FILE).read_bytes(), ORIGINAL)
        self.assertFalse(list(self.client.glob('.trasc-ui-activation-*')))
        self.assertFalse(list((self.engine.work / client_ui.ACTIVATION_BACKUPS).iterdir()))

    def test_snapshot_changed_before_commit_is_preserved(self):
        changed = ORIGINAL.replace(b'AtlasSkin=Classic', b'AtlasSkin=NewChoice')
        calls = 0
        def edit_on_recheck():
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.client / FILE).write_bytes(changed)
        with patch.object(self.engine, 'check_cancel', side_effect=edit_on_recheck):
            with self.assertRaisesRegex(ValueError, 'settings changed'):
                self.activate()
        self.assertEqual((self.client / FILE).read_bytes(), changed)

    def test_linked_character_skin_backup_root_and_client_cannot_escape(self):
        outside = self.root / 'outside.ini'
        outside.write_bytes(ORIGINAL)
        (self.client / FILE).unlink()
        (self.client / FILE).symlink_to(outside)
        with self.assertRaises(ValueError):
            self.activate()
        (self.client / FILE).unlink()
        (self.client / FILE).write_bytes(ORIGINAL)
        backup = self.engine.work / client_ui.ACTIVATION_BACKUPS
        backup.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.activate()
        self.assertEqual(outside.read_bytes(), ORIGINAL)
        self.assertEqual((self.client / FILE).read_bytes(), ORIGINAL)

    def test_restore_is_exact_reversible_and_available_after_game_rewrites_ini(self):
        result = self.activate(apply_layout=True)
        previous = result['ui']['characters'][0]['previous_settings']
        changed = (self.client / FILE).read_bytes().replace(b'UISkin = Stone', b'UISkin = Default')
        (self.client / FILE).write_bytes(changed)
        self.assertEqual(client_ui.status(self.engine)['characters'][0]['previous_settings']['id'], previous['id'])
        restored = self.restore(previous['id'])
        self.assertEqual((self.client / FILE).read_bytes(), ORIGINAL)
        self.assertEqual((self.engine.work / restored['backup']).read_bytes(), changed)
        second = self.restore(restored['ui']['characters'][0]['previous_settings']['id'])
        self.assertEqual((self.client / FILE).read_bytes(), changed)
        self.assertEqual(second['revision'], self.revision())

    def test_restore_rejects_stale_revision_tampered_backup_and_other_profile(self):
        result = self.activate()
        previous = result['ui']['characters'][0]['previous_settings']
        current = (self.client / FILE).read_bytes()
        with self.assertRaises(ValueError):
            self.restore(previous['id'], revision='0' * 64)
        saved = self.engine.work / previous['backup']
        saved.write_bytes(b'[Main]\nUISkin=Bad\n')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.restore(previous['id'])
        self.assertEqual((self.client / FILE).read_bytes(), current)
        saved.write_bytes(ORIGINAL)
        other = self.engines['custom']
        destination = other.work / client_ui.ACTIVATION_BACKUPS / previous['id']
        shutil.copytree(saved.parent, destination)
        with self.assertRaisesRegex(ValueError, 'record'):
            other.dispatch('restore_client_ui', dict(activation_id=previous['id'], character_file=FILE,
                                                    revision=self.revision(other)))

    def test_restore_rejects_record_and_backup_links_or_path_traversal(self):
        result = self.activate()
        previous = result['ui']['characters'][0]['previous_settings']
        for identity in ('../outside', '', 'x' * 24):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                self.restore(identity)
        folder = (self.engine.work / previous['backup']).parent
        record = folder / 'record.json'
        value = record.read_bytes()
        record.unlink()
        outside = self.root / 'record.json'
        outside.write_bytes(value)
        record.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.restore(previous['id'])

    def test_history_overflow_never_exposes_an_arbitrarily_older_backup(self):
        self.activate()
        self.activate(skin='Default')
        self.activate()
        with patch.object(client_ui, 'MAX_ACTIVATION_BACKUPS', 2):
            character = client_ui.status(self.engine)['characters'][0]
            self.assertNotIn('previous_settings', character)
            self.assertIn('previous_settings_error', character)
            self.assertEqual(character['skin'], 'Stone')

    def test_skin_names_ambiguous_with_inline_comments_are_rejected(self):
        folder = self.client / 'UIFILES/Skin #note'
        folder.mkdir()
        (folder / 'EQUI.xml').write_bytes(XML)
        with self.assertRaisesRegex(ValueError, 'INI comment'):
            self.activate(skin=folder.name)
        self.assertEqual((self.client / FILE).read_bytes(), ORIGINAL)

    def test_character_status_stops_reading_at_aggregate_byte_budget(self):
        for number in range(3):
            (self.client / f'UI_{number}_Traditional.ini').write_bytes(ORIGINAL)
        original_read = client_ui._ordinary_bytes
        reads = []
        def counted_read(path, maximum=client_ui.MAX_INI_BYTES):
            reads.append(path.name)
            return original_read(path, maximum)
        with patch.object(client_ui, 'MAX_CHARACTER_TOTAL_BYTES', len(ORIGINAL) * 2), \
                patch('client_ui._ordinary_bytes', side_effect=counted_read):
            result = client_ui.status(self.engine)
        self.assertEqual(len(result['characters']), 2)
        self.assertEqual(len([name for name in reads if name.startswith('UI_') and name.endswith('.ini')]), 2)
        self.assertIn('character_errors', result)

    def test_non_ascii_selection_never_writes_latin1_under_a_utf8_bom(self):
        folder = self.client / 'UIFILES/Café'
        folder.mkdir()
        (folder / 'EQUI.xml').write_bytes(XML)
        with self.assertRaisesRegex(ValueError, 'ASCII skin name'):
            self.activate(skin=folder.name)
        self.assertEqual((self.client / FILE).read_bytes(), ORIGINAL)
        (self.client / FILE).write_bytes(ORIGINAL[3:])
        self.activate(skin=folder.name)
        self.assertIn('UISkin = Café'.encode('latin-1'), (self.client / FILE).read_bytes())


if __name__ == '__main__':
    unittest.main()
