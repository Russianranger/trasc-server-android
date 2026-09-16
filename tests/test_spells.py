import hashlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_spells
import client_audio
from engine import Engine, CLIENT_FILES


def row(spell_id, ending=b'\r\n'):
    fields = [b'0'] * 237
    fields[0] = str(spell_id).encode()
    fields[1] = b'Fixture name \xe9'
    fields[120], fields[123], fields[145] = b'43', b'1', b'278'
    return b'^'.join(fields) + ending


class SpellCompatibilityTests(unittest.TestCase):
    def test_android_copied_backends_execute_export_and_packed_inventory_in_isolation(self):
        # APK presence alone is insufficient: Android copies explicit subsets
        # into two separate runtimes. Execute from those actual copy lists,
        # with neither the repository nor its other modules on sys.path.
        repo = Path(__file__).resolve().parents[1]
        for java, entry in (('RuntimeManager.java', 'engine.py'), ('ClientRuntime.java', 'client_runner.py')):
            source = (repo/'app/src/main/java/io/github/russianranger/trasc'/java).read_text()
            arrays = re.findall(r'new String\[\]\{([^}]+)\}', source)
            names = next(re.findall(r'"([^"\n]+)"', a) for a in arrays if '"'+entry+'"' in a)
            with tempfile.TemporaryDirectory() as temp:
                stage = Path(temp)
                for name in names:
                    if name.endswith('.py'): shutil.copy2(repo/'backend'/name, stage/name)
                script = '''import sys, pathlib, tempfile
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
root = pathlib.Path(sys.argv[1])/'work'; root.mkdir()
fields = [b'0']*237
def row(i):
    fields[0] = str(i).encode()
    return b'^'.join(fields)+b'\\n'
data = row(26)+row(50000)
if sys.argv[2] == 'engine.py':
    from engine import Engine, CLIENT_FILES
    engine = Engine(root)
    def exporter(*args, **kwargs):
        folder = root/'server/export'; folder.mkdir(parents=True)
        for name in CLIENT_FILES: (folder/name).write_bytes(data if name=='spells_us.txt' else b'fixture')
    with patch.object(engine,'ensure_db'), patch.object(engine,'write_config'), patch.object(engine,'run',side_effect=exporter):
        result=engine.export_client({})
    assert result['spell_compatibility']['removed_ids']==[50000]
else:
    import client_runner, client_audio
    client=root/'client';client.mkdir();logs=root/'logs';logs.mkdir()
    (client/'spells_us.txt').write_bytes(data)
    client_audio.inspect_client(client,logs,packed=True)
    import json
    assert json.loads((logs/'client-sound-assets.json').read_text())['spell_tables']['root']['removed_ids']==[50000]
'''
                result = subprocess.run([sys.executable, '-I', '-c', script, str(stage), entry],
                                        cwd=stage, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, java+'\n'+result.stdout+result.stderr)

    def test_filter_preserves_supported_rows_and_boundary_bytes(self):
        keep = b'\xef\xbb\xbf' + row(26) + b'\n' + row(200, b'\n') + row(44999, b'')
        data = b'\xef\xbb\xbf' + row(26) + row(50000) + b'\n' + row(200, b'\n') + row(45000) + row(44999, b'')
        output = io.BytesIO()
        report = client_spells.inspect_data(data, output)
        self.assertEqual(output.getvalue(), keep)
        self.assertEqual(report['removed_ids'], [50000, 45000])
        self.assertEqual(report['kept_rows'], 3)
        self.assertEqual(report['max_id_before'], 50000)
        self.assertEqual(report['max_id_after'], 44999)
        self.assertEqual(report['reported_spells']['200']['spell_animation'], 278)
        self.assertEqual(report['compatible_sha256'], hashlib.sha256(keep).hexdigest())
        self.assertEqual(client_spells.inspect_data(data), report)
        self.assertNotIn('Fixture name', json.dumps(report))

    def test_rejects_invalid_tables_before_replacing_export_or_backup(self):
        invalid = [b'', b'\xff\xfe\x00', row(26)+row(26), b'bad^row\n',
                   row(-1), row(4294967296), row(50000), row(26)+b'200^short\n',
                   row(26)+b'1^'+b'x'*client_spells.MAX_ROW_BYTES]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'spells_us.txt'
            full = Path(temp)/'spells_us.unfiltered.txt'
            for data in invalid:
                path.write_bytes(data); full.write_bytes(b'previous complete export')
                with self.assertRaises(ValueError): client_spells.prepare_export(path)
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(full.read_bytes(), b'previous complete export')
            path.write_bytes(row(26))
            with patch.object(client_spells, 'MAX_TABLE_BYTES', 10):
                with self.assertRaises(ValueError): client_spells.prepare_export(path)

    def test_report_is_bounded_and_compatible_export_is_idempotent(self):
        data = row(26) + b''.join(row(50000+i) for i in range(80))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'spells_us.txt'; path.write_bytes(data)
            report = client_spells.prepare_export(path)
            self.assertEqual(report['removed_rows'], 80)
            self.assertEqual(len(report['removed_ids']), 64)
            self.assertTrue(report['removed_ids_truncated'])
            self.assertEqual(path.read_bytes(), row(26))
            self.assertEqual(path.with_name('spells_us.unfiltered.txt').read_bytes(), data)
            second = client_spells.prepare_export(path)
            self.assertEqual(second['removed_rows'], 0)
            self.assertEqual(path.read_bytes(), row(26))

    def test_symlinks_are_rejected_without_changing_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); real = root/'original'; real.write_bytes(row(26)+row(50000))
            path = root/'spells_us.txt'; path.symlink_to(real)
            with self.assertRaises(ValueError): client_spells.prepare_export(path)
            path.unlink(); path.write_bytes(row(26))
            (root/'spells_us.unfiltered.txt').symlink_to(real)
            with self.assertRaises(ValueError): client_spells.prepare_export(path)
            self.assertEqual(real.read_bytes(), row(26)+row(50000))

    def test_real_export_and_prepare_paths_use_filtered_data_and_keep_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); engine = Engine(root)
            client = root/'client/current'; client.mkdir()
            (client/'trasc-client.json').write_text('{"imported":true}')
            (client/'Resources').mkdir()
            (client/'spells_us.txt').write_bytes(b'old root spells')
            (client/'Resources/spells_us.txt').write_bytes(b'old resource spells')
            source = row(26) + row(200) + row(50000) + row(50007)
            def exporter(*args, **kwargs):
                folder = root/'server/export'; folder.mkdir(parents=True, exist_ok=True)
                for name in CLIENT_FILES:
                    (folder/name).write_bytes(source if name == 'spells_us.txt' else b'other generated data')
            with patch.object(engine, 'ensure_db'), patch.object(engine, 'write_config'), \
                 patch.object(engine, 'run', side_effect=exporter), patch.object(engine, 'mysql') as mysql:
                result = engine.prepare_client({'resolution':'1280x720', 'fullscreen':True})
                mysql.assert_not_called()
            expected = row(26)+row(200)
            for relative in ('spells_us.txt', 'Resources/spells_us.txt'):
                self.assertEqual((client/relative).read_bytes(), expected)
            self.assertEqual((root/result['backup']/'spells_us.txt').read_bytes(), b'old root spells')
            self.assertEqual((root/result['backup']/'Resources/spells_us.txt').read_bytes(), b'old resource spells')
            self.assertEqual((root/'server/export/spells_us.unfiltered.txt').read_bytes(), source)
            report = json.loads((root/'logs/client-spell-export.json').read_text())
            self.assertEqual(report['removed_ids'], [50000, 50007])
            self.assertEqual(result['spell_compatibility'], report)
            with zipfile.ZipFile(next((root/'exports').glob('client-data-*.zip'))) as archive:
                self.assertEqual(archive.read('spells_us.txt'), expected)
                self.assertEqual(archive.read('Resources/spells_us.txt'), expected)
                self.assertEqual(json.loads(archive.read('rof2-spell-compatibility.json')), report)
                self.assertNotIn('spells_us.unfiltered.txt', archive.namelist())

    def test_installed_inventory_reports_both_tables_and_particle_settings_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); client = root/'client'; client.mkdir()
            logs = root/'logs'; logs.mkdir(); (client/'RESOURCES').mkdir()
            (client/'SPELLS_US.TXT').write_bytes(row(26)+row(50000))
            (client/'RESOURCES/spells_us.txt').write_bytes(row(26)+row(200))
            ini = b'[Defaults]\nShowSpellEffects=1\nSpellParticleOpacity=0.5\nSpellParticleDensity=1\nPassword=private\n'
            (client/'eqclient.ini').write_bytes(ini)
            client_audio.inspect_client(client, logs, packed=True)
            report = json.loads((logs/'client-sound-assets.json').read_text())
            self.assertEqual(report['spell_tables']['root']['removed_rows'], 1)
            self.assertEqual(report['spell_tables']['resources']['removed_rows'], 0)
            self.assertEqual(report['settings']['showspelleffects'], '1')
            self.assertEqual(report['settings']['spellparticledensity'], '1')
            self.assertNotIn('private', json.dumps(report))
            self.assertEqual((client/'SPELLS_US.TXT').read_bytes(), row(26)+row(50000))
            self.assertEqual((client/'eqclient.ini').read_bytes(), ini)


if __name__ == '__main__': unittest.main()
