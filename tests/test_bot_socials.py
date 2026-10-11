"""Literal-preserving bot social edits, stale previews and owner-scoped recovery.

Format excerpts are reduced fixtures from primary client tools:
TAKP: CoastalRedwood/Zeal 50dc9a41738034a56f3de3d34902e20000c34072
      Zeal/page10_binds.cpp, game_structures.h and game_functions.cpp;
      davehess/QuarmBossTracker c96db65aff3496cf3c4da18dfa6267d15f65311d
      test/buff-blocks.test.js (Aldenmar_pq.proj.ini, E18 binding).
RoF2: pronym-inc/eq-config-generator 5954f357bd9d92ad9b94cd571c1c95f54cfc6eef
      ini.py create_configs_for_class (E-index and comma fields).
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import bot_socials


OWNER = {'id': 12, 'account_id': 7, 'name': 'Aldenmar', 'account': 'local', 'level': 10}
BOTS = [{'id': 81, 'name': 'Ninnaflalzm', 'race': 1, 'class': 2, 'gender': 1},
        {'id': 82, 'name': 'Tormentedsoul', 'race': 3, 'class': 1, 'gender': 0}]
IDENTITY = 'a' * 64
# The actual native TAKP fixture uses Socials PageNButtonMName/Color/LineN,
# a single HotButtons section, bare E18 and a character + host-tag filename.
TAKP = (b'[Friends]\r\nFriend0=Bob\r\n[Socials]\r\n'
        b'Page1Button1Name=Assist\r\nPage1Button1Color=5\r\n'
        b'Page1Button1Line1=/say #existing ; literal\r\n'
        b'Page2Button1Name=Mine\r\nPage2Button1Color=5\r\n'
        b'Page2Button1Line1=/rs hello\r\n[HotButtons]\r\n'
        b'Page1Button1=E18\r\nPage1Button2=H2\r\n'
        b'[InspectText]\r\nText=Keep caf\xe9\r\n')
ROF2 = TAKP.replace(b'Page1Button1=E18', b'Page1Button1=E18,@-1,0000000000000000,0,')


class FakeEngine:
    def __init__(self, root, profile='takp'):
        self.work, self.profile = root, profile
        self.processes = {}
        self.client = root / 'client/current'
        self.client.mkdir(parents=True)
        self.cancel_hook = lambda: None

    def _local_client(self, required=True):
        return self.client

    def check_cancel(self):
        self.cancel_hook()


class BotSocialTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.engine = FakeEngine(self.root)
        self.path = self.engine.client / 'Aldenmar_takp.ini'
        self.path.write_bytes(TAKP)

    def args(self, **changes):
        return dict({'identity': IDENTITY, 'owner_id': OWNER['id']}, **changes)

    def preview(self, bots=None, **changes):
        return bot_socials.preview(self.engine, OWNER, BOTS if bots is None else bots, self.args(**changes))

    def install_args(self, preview, **changes):
        args = self.args(character_file=preview['character_file'], file_revision=preview['file_revision'],
                         preview_token=preview['preview_token'], placements=[])
        if 'actions' in preview:
            args['actions'] = preview['actions']
        args.update(changes)
        return args

    def install(self, preview=None, bots=None, **changes):
        preview = preview or self.preview(bots)
        return bot_socials.install(self.engine, OWNER, BOTS if bots is None else bots,
                                  self.install_args(preview, **changes))

    def test_native_takp_and_rof2_fixtures_select_actual_owner_file_and_format(self):
        for profile in ('takp', 'custom', 'traditional'):
            with self.subTest(profile=profile):
                self.engine.profile = profile
                self.path.write_bytes(TAKP if profile == 'takp' else ROF2)
                before = self.path.read_bytes()
                preview = self.preview()
                self.assertTrue(preview['supported'])
                self.assertEqual(preview['character_file'], self.path.name)
                self.assertEqual(len(preview['socials']), 2)
                self.assertEqual(len(preview['empty_hotbar_slots']), 98 if profile == 'takp' else 1198)
                placement = {'bot_id': 81, 'bar': 1, 'page': 1, 'button': 3}
                result = self.install(preview, placements=[placement])
                after = self.path.read_bytes()
                self.assertIn(b'Friend0=Bob\r\n', after)
                self.assertIn(b'Text=Keep caf\xe9\r\n', after)
                self.assertIn(b'Page1Button1Line1=/say #existing ; literal\r\n', after)
                self.assertIn(b'Page1Button2=H2\r\n', after)
                self.assertNotIn(b'\n', after.replace(b'\r\n', b''))
                if profile == 'takp':
                    self.assertIn(b'/say #bot spawn Ninnaflalzm', after)
                    self.assertIn(b'Page1Button3=E1\r\n', after)
                    self.assertNotIn(b'/invite', after)
                else:
                    self.assertIn(b'/pause 20, /say ^botspawn Ninnaflalzm', after)
                    self.assertIn(b'/pause 5, /target Ninnaflalzm', after)
                    self.assertIn(b'Line2=/target Aldenmar', after)
                    self.assertIn(b'Line4=/invite', after)
                    self.assertIn(b'Page1Button3=E1,@-1,0000000000000000,0,Ninnaflalzm\r\n', after)
                self.assertEqual((self.engine.work / result['backup']).read_bytes(), before)
                # Clear history between isolated profile examples.
                import shutil
                shutil.rmtree(self.root / 'backups')

    def test_latin1_utf8_bom_and_mixed_newline_bytes_are_preserved(self):
        original = b'\xef\xbb\xbf[Friends]\r\nFriend0=Ren\xc3\xa9\n[Socials]\r\n; note\nUnknown=literal # untouched\r\n[InspectText]\nText=tail'
        self.path.write_bytes(original)
        self.install()
        after = self.path.read_bytes()
        self.assertTrue(after.startswith(b'\xef\xbb\xbf[Friends]\r\nFriend0=Ren\xc3\xa9\n'))
        self.assertIn(b'; note\nUnknown=literal # untouched\r\n', after)
        self.assertTrue(after.endswith(b'[InspectText]\nText=tail'))

    def test_ini_merge_keeps_original_key_spelling_order_and_unrelated_bytes(self):
        raw = b'[Socials]\n page1button1name =\nPage1Button1Color=4\nPage1Button1Line1=\n[Other]\nSame=keep\n'
        ini = bot_socials.Ini(raw)
        updated = ini.merge({('Socials', 'Page1Button1Name'): 'Named', ('Socials', 'Page1Button1Line1'): '/say #bot spawn Named'})
        self.assertEqual(updated, raw.replace(b' page1button1name =\n', b' page1button1name =Named\n').replace(b'Page1Button1Line1=\n', b'Page1Button1Line1=/say #bot spawn Named\n'))

    def test_new_socials_section_does_not_capture_keys_for_existing_last_hotbar_section(self):
        self.path.write_bytes(b'[Friends]\nFriend0=Bob\n[HotButtons]\nPage1Button1=H2\n')
        preview = self.preview()
        self.install(preview, placements=[{'bot_id': 81, 'bar': 1, 'page': 1, 'button': 2}])
        ini = bot_socials.Ini(self.path.read_bytes())
        self.assertEqual(ini.get('HotButtons', 'Page1Button2'), 'E0')
        self.assertEqual(ini.get('Socials', 'Page1Button1Name'), 'Ninnaflalzm')
        self.assertEqual(ini.get('Socials', 'Page1Button2'), '')

    def test_duplicate_native_keys_or_sections_and_unsupported_keys_are_blocked(self):
        for addition in (b'[SOCIALS]\n', b'[Socials]\nPage1Button1Name=Again\nPage1Button1Name=Again\n',
                         b'[Socials]\nPage11Button1Name=Beyond\n', b'[HotButtons2]\nPage1Button1=E1\n'):
            with self.subTest(addition=addition):
                self.path.write_bytes(TAKP + addition)
                preview = self.preview()
                self.assertFalse(preview['supported'])
                self.assertFalse(preview['preview_token'])
                with self.assertRaises(ValueError):
                    self.install(preview)

    def test_missing_import_or_character_file_is_actionable_without_fabricating_ini(self):
        self.path.unlink()
        preview = self.preview()
        self.assertFalse(preview['supported'])
        self.assertIn('camp', preview['reason'])
        self.assertEqual(list(self.engine.client.iterdir()), [])
        self.engine._local_client = lambda required=True: None
        self.assertFalse(self.preview()['supported'])

    def test_owner_file_match_excludes_ui_settings_and_other_character_prefixes(self):
        (self.engine.client / 'UI_Aldenmar_takp.ini').write_bytes(TAKP)
        (self.engine.client / 'Aldenmarx_takp.ini').write_bytes(TAKP)
        (self.engine.client / 'eqclient.ini').write_bytes(TAKP)
        preview = self.preview()
        self.assertEqual([entry['file'] for entry in preview['character_files']], [self.path.name])
        self.assertFalse(self.preview(character_file='../eqclient.ini')['supported'])
        self.assertFalse(self.preview(character_file='UI_Aldenmar_takp.ini')['supported'])

    def test_ambiguous_server_suffix_needs_explicit_selection_and_windows_case_collisions_block(self):
        second = self.engine.client / 'Aldenmar_other.ini'
        second.write_bytes(TAKP)
        self.assertFalse(self.preview()['supported'])
        self.assertTrue(self.preview(character_file=second.name)['supported'])
        (self.engine.client / 'aldenmar_OTHER.INI').write_bytes(TAKP)
        self.assertFalse(self.preview(character_file=second.name)['supported'])

    def test_symlink_and_oversized_character_files_are_never_edited(self):
        outside = self.root / 'outside.ini'
        outside.write_bytes(TAKP)
        self.path.unlink()
        self.path.symlink_to(outside)
        self.assertFalse(self.preview()['supported'])
        self.assertEqual(outside.read_bytes(), TAKP)
        self.path.unlink()
        self.path.write_bytes(b'a' * (bot_socials.MAX_INI_BYTES + 1))
        self.assertFalse(self.preview()['supported'])

    def test_stale_preview_and_changed_bot_selection_preserve_file_without_backup(self):
        preview = self.preview()
        self.path.write_bytes(TAKP + b'; changed\r\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.install(preview)
        self.assertEqual(self.path.read_bytes(), TAKP + b'; changed\r\n')
        self.assertFalse((self.root / bot_socials.BACKUPS).exists())
        self.path.write_bytes(TAKP)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.install(preview, bots=BOTS[:1])

    def test_occupied_hotbars_and_duplicate_placements_are_rejected(self):
        preview = self.preview()
        for placements in ([{'bot_id': 81, 'bar': 1, 'page': 1, 'button': 2}],
                           [{'bot_id': 81, 'bar': 2, 'page': 1, 'button': 1}],
                           [{'bot_id': 81, 'bar': 1, 'page': 1, 'button': 11}],
                           [{'bot_id': 81, 'bar': 1, 'page': 1, 'button': 3}, {'bot_id': 82, 'bar': 1, 'page': 1, 'button': 3}],
                           [{'bot_id': 81, 'bar': True, 'page': 1, 'button': 3}]):
            with self.subTest(placements=placements), self.assertRaises(ValueError):
                self.install(preview, placements=placements)
            self.assertEqual(self.path.read_bytes(), TAKP)

    def test_empty_social_referenced_by_existing_hotbar_is_reserved(self):
        self.path.write_bytes(b'[HotButtons]\nPage1Button1=E0\n[Socials]\n')
        preview = self.preview()
        self.assertEqual((preview['socials'][0]['page'], preview['socials'][0]['button']), (1, 2))

    def test_blank_name_with_nonempty_fifth_line_is_occupied(self):
        self.path.write_bytes(b'[Socials]\nPage1Button1Name=\nPage1Button1Line5=/say keep\n')
        self.assertEqual(self.preview()['socials'][0]['button'], 2)

    def test_retry_and_new_preview_reuse_only_recorded_identical_socials(self):
        preview = self.preview()
        placements = [{'bot_id': 81, 'bar': 1, 'page': 1, 'button': 3}]
        installed = self.install(preview, placements=placements)
        after = self.path.read_bytes()
        retried = self.install(preview, placements=placements)
        self.assertTrue(retried['reused'])
        self.assertEqual(retried['backup_id'], installed['backup_id'])
        self.assertEqual(self.path.read_bytes(), after)
        self.assertEqual(len(list((self.root / bot_socials.BACKUPS).iterdir())), 1)
        newer = self.preview()
        self.assertTrue(all(social['existing'] for social in newer['socials']))
        self.assertEqual([(s['page'], s['button']) for s in newer['socials']], [(s['page'], s['button']) for s in preview['socials']])
        self.assertTrue(self.install(newer, placements=placements)['reused'])
        self.assertEqual(self.path.read_bytes(), after)

    def test_identical_unrecorded_personal_social_is_preserved_and_not_adopted(self):
        self.path.write_bytes(b'[Socials]\nPage1Button1Name=Ninnaflalzm\nPage1Button1Color=0\nPage1Button1Line1=/say #bot spawn Ninnaflalzm\n')
        self.assertEqual(self.preview()['socials'][0]['button'], 2)

    def test_restore_matches_owner_account_deployment_and_exact_after_revision(self):
        installed = self.install()
        args = self.args(_owner=OWNER, character_file=self.path.name,
                         file_revision=installed['file_revision'], backup_id=installed['backup_id'])
        for identity, owner in [('b' * 64, OWNER), (IDENTITY, dict(OWNER, id=13)), (IDENTITY, dict(OWNER, account_id=8))]:
            with self.subTest(identity=identity, owner=owner), self.assertRaises(ValueError):
                bot_socials.restore(self.engine, dict(args, identity=identity, _owner=owner))
        result = bot_socials.restore(self.engine, args)
        self.assertTrue(result['restored'])
        self.assertEqual(self.path.read_bytes(), TAKP)

    def test_restore_refuses_later_personal_changes_even_with_fresh_revision(self):
        installed = self.install()
        self.path.write_bytes(self.path.read_bytes() + b'; personal later change\r\n')
        with self.assertRaisesRegex(ValueError, 'later changes'):
            bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                file_revision=hashlib.sha256(self.path.read_bytes()).hexdigest(), backup_id=installed['backup_id']))

    def test_restore_retry_and_prepared_receipt_reuse_exact_owned_transition(self):
        installed = self.install()
        args = self.args(_owner=OWNER, character_file=self.path.name,
                         file_revision=installed['file_revision'], backup_id=installed['backup_id'])
        restored = bot_socials.restore(self.engine, args)
        receipt = self.root / bot_socials.BACKUPS / restored['backup_id'] / 'record.json'
        record = json.loads(receipt.read_text())
        record['state'] = 'prepared'
        receipt.write_text(json.dumps(record))
        retried = bot_socials.restore(self.engine, args)
        self.assertTrue(retried['reused'])
        self.assertEqual(retried['backup_id'], restored['backup_id'])
        self.assertEqual(self.path.read_bytes(), TAKP)
        self.assertEqual(len(list((self.root / bot_socials.BACKUPS).iterdir())), 2)
        with self.assertRaises(ValueError):
            bot_socials.restore(self.engine, dict(args, identity='b' * 64))
        self.path.write_bytes(TAKP + b'; personal afterwards\r\n')
        with self.assertRaises(ValueError):
            bot_socials.restore(self.engine, args)

    def test_restore_file_failure_is_atomic_and_retryable(self):
        installed = self.install()
        args = self.args(_owner=OWNER, character_file=self.path.name,
                         file_revision=installed['file_revision'], backup_id=installed['backup_id'])
        after = self.path.read_bytes()
        with patch('bot_socials.os.replace', side_effect=OSError('restore disk unavailable')):
            with self.assertRaisesRegex(OSError, 'restore disk unavailable'):
                bot_socials.restore(self.engine, args)
        self.assertEqual(self.path.read_bytes(), after)
        self.assertEqual(len(list((self.root / bot_socials.BACKUPS).iterdir())), 1)
        self.assertTrue(bot_socials.restore(self.engine, args)['restored'])
        self.assertEqual(self.path.read_bytes(), TAKP)

    def test_backup_tamper_and_linked_backup_root_are_rejected(self):
        installed = self.install()
        backup = self.root / installed['backup']
        backup.write_bytes(b'tampered')
        self.assertEqual(self.preview()['backups'], [])
        with self.assertRaises(ValueError):
            bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                file_revision=installed['file_revision'], backup_id=installed['backup_id']))

    def test_malformed_backup_receipt_is_ignored_and_fifo_candidate_cannot_block_scan(self):
        installed = self.install()
        record_path = self.root / bot_socials.BACKUPS / installed['backup_id'] / 'record.json'
        record = json.loads(record_path.read_text())
        record['socials'] = None
        record_path.write_text(json.dumps(record))
        self.assertEqual(self.preview()['backups'], [])
        for malformed in ([], None, 'not a receipt', 42):
            with self.subTest(malformed=malformed):
                record_path.write_text(json.dumps(malformed))
                self.assertEqual(self.preview()['backups'], [])
        fifo = self.engine.client / 'Aldenmar_fifo.ini'
        os.mkfifo(fifo)
        preview = self.preview(character_file=self.path.name)
        rejected = next(entry for entry in preview['character_files'] if entry['file'] == fifo.name)
        self.assertFalse(rejected['supported'])

    def test_atomic_replace_failure_keeps_original_and_cleans_staged_backup(self):
        with patch('bot_socials.os.replace', side_effect=OSError('disk unavailable')):
            with self.assertRaisesRegex(OSError, 'disk unavailable'):
                self.install()
        self.assertEqual(self.path.read_bytes(), TAKP)
        self.assertEqual(list((self.root / bot_socials.BACKUPS).iterdir()), [])
        self.assertFalse(any(path.name.startswith('.trasc-bot-socials') for path in self.engine.client.iterdir()))

    def test_change_between_stage_and_commit_is_detected(self):
        calls = []
        def hook():
            calls.append(1)
            if len(calls) == 2:
                self.path.write_bytes(TAKP + b'; concurrent\r\n')
        self.engine.cancel_hook = hook
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.install()
        self.assertEqual(self.path.read_bytes(), TAKP + b'; concurrent\r\n')
        self.assertEqual(list((self.root / bot_socials.BACKUPS).iterdir()), [])

    def test_running_client_is_independently_guarded(self):
        class Running:
            def poll(self):
                return None
        self.engine.processes['client'] = Running()
        with self.assertRaisesRegex(ValueError, 'Stop the embedded client'):
            self.install()
        self.assertEqual(self.path.read_bytes(), TAKP)

    def test_malformed_names_ids_limits_and_pause_are_rejected(self):
        for bots in ([], BOTS * 3, [{'id': True, 'name': 'Named'}], [{'id': 1, 'name': 'Bad\n/say injected'}], BOTS[:1] * 2):
            with self.subTest(bots=bots), self.assertRaises(ValueError):
                self.preview(bots)
        self.engine.profile = 'custom'
        self.path.write_bytes(ROF2)
        for pause in (True, 0, 101, '20'):
            with self.subTest(pause=pause), self.assertRaises(ValueError):
                self.preview(spawn_pause=pause)

    def test_prepared_crash_receipt_recognizes_committed_file_retry(self):
        preview = self.preview()
        installed = self.install(preview)
        record_path = self.root / bot_socials.BACKUPS / installed['backup_id'] / 'record.json'
        record = json.loads(record_path.read_text())
        record['state'] = 'prepared'
        record_path.write_text(json.dumps(record))
        self.assertTrue(self.install(preview)['reused'])
        self.assertEqual(len(list((self.root / bot_socials.BACKUPS).iterdir())), 1)

    def test_combined_spawn_and_separate_revive_use_selected_names_without_native_all(self):
        preview = self.preview(actions=['spawn', 'revive', 'follow'])
        self.assertEqual([s['label'] for s in preview['socials']], ['Spawn party', 'Revive party', 'Follow'])
        self.assertEqual(preview['socials'][0]['lines'], ['/say #bot spawn Ninnaflalzm', '/say #bot spawn Tormentedsoul'])
        self.assertEqual(preview['socials'][1]['lines'], ['/say #bot revive Ninnaflalzm', '/say #bot revive Tormentedsoul'])
        self.assertEqual(len({s['social_id'] for s in preview['socials']}), 3)
        self.assertTrue(all(' all' not in line for s in preview['socials'] for line in s['lines']))
        self.assertIn('60-second wait', preview['message'])
        self.assertIn('1 HP', preview['message'])
        placements = [{'social_id': s['social_id'], 'bar': 1, 'page': 1, 'button': i + 3}
                      for i, s in enumerate(preview['socials'])]
        installed = self.install(preview, placements=placements)
        ini = bot_socials.Ini(self.path.read_bytes())
        for i, s in enumerate(preview['socials']):
            self.assertEqual(ini.get('HotButtons', f'Page1Button{i + 3}'), bot_socials._binding('takp', s))
        self.assertEqual((self.root / installed['backup']).read_bytes(), TAKP)
        self.assertTrue(self.install(preview, placements=placements)['reused'])
        newer = self.preview(actions=['follow', 'revive', 'spawn'])
        self.assertEqual(newer['actions'], ['spawn', 'revive', 'follow'])
        self.assertTrue(all(s['existing'] for s in newer['socials']))
        self.assertEqual([s['social_id'] for s in preview['socials']], [s['social_id'] for s in newer['socials']])
        restored = bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                      file_revision=installed['file_revision'], backup_id=installed['backup_id']))
        self.assertTrue(restored['restored'])
        self.assertEqual(self.path.read_bytes(), TAKP)

    def test_twenty_selected_names_are_explicit_five_line_chunks_without_truncation(self):
        bots = [{'id': n + 1, 'name': 'Named' + chr(65 + n)} for n in range(20)]
        preview = self.preview(bots=bots, actions=['spawn', 'revive'])
        self.assertEqual(len(preview['socials']), 8)
        for action in ('spawn', 'revive'):
            socials = [s for s in preview['socials'] if s['action'] == action]
            self.assertEqual([name for s in socials for name in s['names']], [b['name'] for b in bots])
            self.assertEqual([len(s['lines']) for s in socials], [5] * 4)
            self.assertEqual([s['label'] for s in socials], [action.title() + ' party ' + str(i) for i in range(1, 5)])
            self.assertTrue(all(len(s['label'].encode('ascii')) <= 15 for s in socials))
        installed = self.install(preview, bots=bots)
        self.assertEqual(len(self.preview(bots=bots, actions=['spawn', 'revive'])['backups']), 1,
                         'More than five socials remain readable and restorable')
        self.assertTrue(all(s['existing'] for s in self.preview(bots=bots, actions=['spawn', 'revive'])['socials']))
        self.assertTrue(bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                             file_revision=installed['file_revision'], backup_id=installed['backup_id']))['restored'])

    def test_command_catalogue_orders_dps_arguments_and_distinguishes_resurrection(self):
        commands = bot_socials.catalogue('takp')
        self.assertIn('fallen', next(c['description'] for c in commands if c['id'] == 'revive'))
        self.assertIn('player corpse', next(c['description'] for c in commands if c['id'] == 'resurrect'))
        self.assertTrue(bot_socials.catalogue('traditional'))
        self.assertNotIn('revive', {c['id'] for c in bot_socials.catalogue('traditional')})
        preview = self.preview(actions=['dps_off', 'sit_on', 'taunt_on', 'resurrect'])
        expected = {'dps_off': '/say #bot dps cast off Ninnaflalzm', 'sit_on': '/say #bot sit Ninnaflalzm on',
                    'taunt_on': '/say #bot taunt Ninnaflalzm 1', 'resurrect': '/say #bot resurrect Ninnaflalzm'}
        self.assertEqual({s['action']: s['lines'][0] for s in preview['socials']}, expected)

    def test_unknown_duplicate_injected_commands_and_incompatible_profile_actions_are_refused(self):
        for actions in ([], ['spawn', 'spawn'], ['revive_all'], ['spawn\n/say injected'], 'spawn', [True]):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                self.preview(actions=actions)
        self.engine.profile = 'traditional'
        self.path.write_bytes(ROF2)
        with self.assertRaises(ValueError):
            self.preview(actions=['revive'])
        self.assertEqual(len(self.preview()['socials']), 2)
        self.assertEqual(self.path.read_bytes(), ROF2)

    def test_changed_command_selection_cannot_replay_a_preview(self):
        preview = self.preview(actions=['spawn'])
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.install(preview, actions=['revive'])
        self.assertEqual(self.path.read_bytes(), TAKP)
        self.assertFalse((self.root / bot_socials.BACKUPS).exists())

    def test_grouped_hotbar_slots_cannot_overwrite_or_alias_existing_buttons(self):
        preview = self.preview(actions=['spawn', 'revive'])
        keys = [s['social_id'] for s in preview['socials']]
        for placements in ([{'social_id': keys[0], 'bar': 1, 'page': 1, 'button': 2}],
                           [{'social_id': key, 'bar': 1, 'page': 1, 'button': 3} for key in keys],
                           [{'social_id': keys[0], 'bot_id': 81, 'bar': 1, 'page': 1, 'button': 3}],
                           [{'bot_id': 81, 'bar': 1, 'page': 1, 'button': 3}],
                           [{'social_id': 'spawn.' + '0' * 24, 'bar': 1, 'page': 1, 'button': 3}]):
            with self.subTest(placements=placements), self.assertRaises(ValueError):
                self.install(preview, placements=placements)
            self.assertEqual(self.path.read_bytes(), TAKP)

    def test_grouped_receipts_validate_exact_action_names_and_ids_and_keep_legacy_backups(self):
        legacy = self.install()
        self.assertTrue(self.preview(actions=['spawn', 'revive'])['backups'][0]['restorable'])
        bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                            file_revision=legacy['file_revision'], backup_id=legacy['backup_id']))
        preview = self.preview(actions=['spawn'])
        installed = self.install(preview)
        record_path = self.root / bot_socials.BACKUPS / installed['backup_id'] / 'record.json'
        record = json.loads(record_path.read_text())
        record['socials'][0]['action'] = 'revive'
        record_path.write_text(json.dumps(record))
        self.assertNotIn(installed['backup_id'], [b['id'] for b in self.preview(actions=['spawn'])['backups']])
        with self.assertRaises(ValueError):
            bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                file_revision=installed['file_revision'], backup_id=installed['backup_id']))

    def test_too_many_buttons_and_companions_are_refused_before_any_file_write(self):
        bots = [{'id': n + 1, 'name': 'Named' + chr(65 + n)} for n in range(21)]
        with self.assertRaises(ValueError):
            self.preview(bots=bots, actions=['spawn'])
        with self.assertRaisesRegex(ValueError, '120 social slots'):
            self.preview(bots=bots[:20], actions=[c['id'] for c in bot_socials.catalogue('takp')])
        self.assertEqual(self.path.read_bytes(), TAKP)
        self.assertFalse((self.root / bot_socials.BACKUPS).exists())

    def test_native_social_boundary_at_one_five_and_six_selected_names(self):
        bots = [{'id': n + 1, 'name': 'Named' + chr(65 + n)} for n in range(6)]
        for count, expected in [(1, [1]), (5, [5]), (6, [5, 1])]:
            with self.subTest(count=count):
                preview = self.preview(bots=bots[:count], actions=['spawn'])
                self.assertEqual([len(s['lines']) for s in preview['socials']], expected)
                self.assertEqual([identity for s in preview['socials'] for identity in s['bot_ids']],
                                 [b['id'] for b in bots[:count]])

    def test_personal_edit_of_grouped_social_is_preserved_and_allocates_a_free_slot(self):
        preview = self.preview(actions=['spawn', 'revive'])
        self.install(preview)
        first, second = preview['socials']
        before = self.path.read_bytes()
        changed = before.replace(b'Line1=/say #bot spawn Ninnaflalzm', b'Line1=/say Personal command')
        self.path.write_bytes(changed)
        newer = self.preview(actions=['spawn', 'revive'])
        self.assertFalse(newer['socials'][0]['existing'])
        self.assertNotEqual((first['page'], first['button']),
                            (newer['socials'][0]['page'], newer['socials'][0]['button']))
        self.assertTrue(newer['socials'][1]['existing'])
        self.install(newer)
        ini = bot_socials.Ini(self.path.read_bytes())
        self.assertEqual(ini.get('Socials', f'Page{first["page"]}Button{first["button"]}Line1'), '/say Personal command')
        self.assertIn(b'Text=Keep caf\xe9', self.path.read_bytes())

    def test_modern_catalogue_matches_verified_native_byname_handlers_and_excludes_takp_only_commands(self):
        expected = {
            'spawn': '/say ^botspawn Ninnaflalzm', 'dismiss': '/say ^botcamp byname Ninnaflalzm',
            'report': '/say ^botreport byname Ninnaflalzm', 'summon': '/say ^botsummon byname Ninnaflalzm',
            'attack': '/say ^attack byname Ninnaflalzm', 'follow': '/say ^follow reset byname Ninnaflalzm',
            'follow_target': '/say ^follow byname Ninnaflalzm', 'follow_current': '/say ^follow current byname Ninnaflalzm',
            'stay': '/say ^guard byname Ninnaflalzm', 'guard_clear': '/say ^guard clear byname Ninnaflalzm',
            'hold': '/say ^hold byname Ninnaflalzm', 'hold_clear': '/say ^hold clear byname Ninnaflalzm',
            'suspend': '/say ^suspend byname Ninnaflalzm', 'release': '/say ^release byname Ninnaflalzm',
            'taunt_on': '/say ^taunt on byname Ninnaflalzm', 'taunt_off': '/say ^taunt off byname Ninnaflalzm',
            'pettaunt_on': '/say ^taunt on pet byname Ninnaflalzm', 'pettaunt_off': '/say ^taunt off pet byname Ninnaflalzm',
            'ranged_on': '/say ^bottoggleranged 1 byname Ninnaflalzm', 'ranged_off': '/say ^bottoggleranged 0 byname Ninnaflalzm',
            'helm_on': '/say ^bottogglehelm 1 byname Ninnaflalzm', 'helm_off': '/say ^bottogglehelm 0 byname Ninnaflalzm',
        }
        for profile in ('custom', 'traditional'):
            with self.subTest(profile=profile):
                self.engine.profile = profile
                self.path.write_bytes(ROF2)
                catalogue = bot_socials.catalogue(profile)
                self.assertEqual(len(catalogue), 23)
                self.assertTrue({'revive', 'sit_on', 'sit_off', 'dps_on', 'resurrect'}.isdisjoint(c['id'] for c in catalogue))
                preview = self.preview(bots=BOTS[:1], actions=list(expected))
                self.assertEqual({s['action']: s['lines'][0] for s in preview['socials']}, expected)
                self.assertTrue(all(s['names'] == ['Ninnaflalzm'] for s in preview['socials']))
                self.assertEqual(self.path.read_bytes(), ROF2)
        self.assertEqual(len(bot_socials.catalogue('takp')), 39)

    def test_modern_guarded_spawn_keeps_invites_and_adopts_only_exact_recorded_legacy_buttons(self):
        for profile in ('custom', 'traditional'):
            with self.subTest(profile=profile):
                self.engine.profile = profile
                self.path.write_bytes(ROF2)
                legacy_preview = self.preview()
                self.install(legacy_preview)
                updated = self.preview(actions=['spawn_group'])
                self.assertTrue(all(s['existing'] for s in updated['socials']))
                self.assertEqual([(s['page'], s['button']) for s in updated['socials']],
                                 [(s['page'], s['button']) for s in legacy_preview['socials']])
                self.assertEqual([s['label'] for s in updated['socials']], [b['name'] for b in BOTS])
                for social, bot in zip(updated['socials'], BOTS):
                    self.assertEqual(social['lines'], [f'/pause 20, /say ^botspawn {bot["name"]}', '/target Aldenmar',
                                                     f'/pause 5, /target {bot["name"]}', '/invite'])
                    self.assertEqual(social['bot_ids'], [bot['id']])
                    self.assertEqual(social['spawn_pause'], 20)
                self.assertTrue(self.install(updated)['reused'])

    def test_modern_combined_spawn_is_explicitly_separate_from_grouping(self):
        self.engine.profile = 'custom'
        self.path.write_bytes(ROF2)
        preview = self.preview(actions=['spawn', 'spawn_group', 'follow'])
        self.assertEqual([s['action'] for s in preview['socials']], ['spawn_group', 'spawn_group', 'spawn', 'follow'])
        spawn = next(s for s in preview['socials'] if s['action'] == 'spawn')
        self.assertEqual(spawn['label'], 'Spawn only')
        self.assertEqual(spawn['lines'], ['/say ^botspawn Ninnaflalzm', '/say ^botspawn Tormentedsoul'])
        self.assertNotIn('/invite', spawn['lines'])
        self.assertIn('does not invite', preview['message'])
        self.assertEqual(len({s['social_id'] for s in preview['socials']}), 4)
        self.assertTrue(all(len(s['label'].encode('ascii')) <= 15 for s in preview['socials']))

    def test_modern_named_actions_keep_five_line_boundaries_and_twenty_names_without_truncation(self):
        bots = [{'id': n + 1, 'name': 'Named' + chr(65 + n)} for n in range(20)]
        for profile in ('custom', 'traditional'):
            self.engine.profile = profile
            self.path.write_bytes(ROF2)
            for count, widths in [(1, [1]), (5, [5]), (6, [5, 1]), (20, [5] * 4)]:
                with self.subTest(profile=profile, count=count):
                    preview = self.preview(bots=bots[:count], actions=['spawn_group', 'follow', 'report'])
                    self.assertEqual(len([s for s in preview['socials'] if s['action'] == 'spawn_group']), count)
                    for action in ('follow', 'report'):
                        socials = [s for s in preview['socials'] if s['action'] == action]
                        self.assertEqual([len(s['lines']) for s in socials], widths)
                        self.assertEqual([name for s in socials for name in s['names']], [b['name'] for b in bots[:count]])

    def test_modern_multi_action_install_retry_hotbar_format_and_restore_are_byte_exact(self):
        for profile in ('custom', 'traditional'):
            with self.subTest(profile=profile):
                self.engine.profile = profile
                self.path.write_bytes(ROF2)
                preview = self.preview(actions=['spawn_group', 'report', 'taunt_off'])
                placements = [{'social_id': s['social_id'], 'bar': 2, 'page': 3, 'button': n + 1}
                              for n, s in enumerate(preview['socials'])]
                installed = self.install(preview, placements=placements)
                after = self.path.read_bytes()
                ini = bot_socials.Ini(after)
                for placement, social in zip(placements, preview['socials']):
                    self.assertEqual(ini.get('HotButtons2', f'Page3Button{placement["button"]}'), bot_socials._binding(profile, social))
                retried = self.install(preview, placements=placements)
                self.assertTrue(retried['reused'])
                self.assertEqual(retried['backup_id'], installed['backup_id'])
                newer = self.preview(actions=['taunt_off', 'report', 'spawn_group'])
                self.assertTrue(all(s['existing'] for s in newer['socials']))
                self.assertEqual([s['social_id'] for s in newer['socials']], [s['social_id'] for s in preview['socials']])
                self.assertEqual(self.path.read_bytes(), after)
                restored = bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                              file_revision=installed['file_revision'], backup_id=installed['backup_id']))
                self.assertTrue(restored['restored'])
                self.assertEqual(self.path.read_bytes(), ROF2)

    def test_modern_record_tamper_pause_and_unsupported_actions_refuse_without_overwriting(self):
        self.engine.profile = 'traditional'
        self.path.write_bytes(ROF2)
        for actions in (['revive'], ['sit_on'], ['resurrect'], ['delete'], ['spawn', 'spawn'], ['follow\n/say injected']):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                self.preview(actions=actions)
        for pause in (True, 0, 101, '20'):
            with self.subTest(pause=pause), self.assertRaises(ValueError):
                self.preview(actions=['spawn_group'], spawn_pause=pause)
        preview = self.preview(actions=['spawn_group', 'follow'])
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.install(preview, actions=['spawn_group', 'stay'])
        self.assertEqual(self.path.read_bytes(), ROF2)
        installed = self.install(preview)
        record_path = self.root / bot_socials.BACKUPS / installed['backup_id'] / 'record.json'
        record = json.loads(record_path.read_text())
        record['socials'][0]['lines'][1] = '/target Someoneelse'
        record_path.write_text(json.dumps(record))
        self.assertNotIn(installed['backup_id'], [b['id'] for b in self.preview(actions=['spawn_group'])['backups']])

    def test_modern_multi_action_occupied_slots_and_later_personal_settings_remain_protected(self):
        self.engine.profile = 'custom'
        self.path.write_bytes(ROF2)
        preview = self.preview(actions=['follow', 'report'])
        for placements in ([{'social_id': preview['socials'][0]['social_id'], 'bar': 1, 'page': 1, 'button': 2}],
                           [{'social_id': s['social_id'], 'bar': 1, 'page': 1, 'button': 3} for s in preview['socials']]):
            with self.assertRaises(ValueError):
                self.install(preview, placements=placements)
            self.assertEqual(self.path.read_bytes(), ROF2)
        installed = self.install(preview)
        self.path.write_bytes(self.path.read_bytes() + b'; Personal settings after game exit\r\n')
        with self.assertRaisesRegex(ValueError, 'later changes'):
            bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                file_revision=hashlib.sha256(self.path.read_bytes()).hexdigest(), backup_id=installed['backup_id']))

    def test_modern_spawn_group_backups_validate_nondefault_pause_and_native_owner_guard(self):
        self.engine.profile = 'traditional'
        self.path.write_bytes(ROF2)
        preview = self.preview(actions=['spawn_group'], spawn_pause=35)
        installed = self.install(preview, spawn_pause=35)
        self.assertEqual(preview['socials'][0]['lines'][0], '/pause 35, /say ^botspawn Ninnaflalzm')
        newer = self.preview(actions=['spawn_group'], spawn_pause=35)
        self.assertTrue(all(s['existing'] for s in newer['socials']))
        self.assertTrue(newer['backups'][0]['restorable'])
        self.assertTrue(bot_socials.restore(self.engine, self.args(_owner=OWNER, character_file=self.path.name,
                                           file_revision=installed['file_revision'], backup_id=installed['backup_id']))['restored'])


if __name__ == '__main__':
    unittest.main()
