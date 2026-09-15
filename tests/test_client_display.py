import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from client_display import apply_display, display_ini, RESOLUTIONS


class ClientDisplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.client=self.root/'client';self.client.mkdir();self.prefix=self.root/'prefix'

    def tearDown(self):self.temp.cleanup()

    def test_fullscreen_and_windowed_switch_preserves_settings_and_exact_original(self):
        original=b'; comment\r\n[Defaults]\r\nWindowedMode=TRUE\r\nCPUAffinity0=0\r\n[VideoMode]\r\nWidth=800\r\nHeight=600\r\n[Other]\r\nName=caf\xe9\r\n'
        ini=self.client/'EQCLIENT.INI';ini.write_bytes(original)
        report=apply_display(self.client,self.prefix,'1280x720',True)
        self.assertTrue(report['fullscreen']);self.assertTrue(report['changed'])
        text=ini.read_bytes();self.assertIn(b'WindowedMode=FALSE',text)
        for line in (b'Width=1280',b'Height=720',b'WindowedWidth=1280',b'WindowedHeight=720',b'CPUAffinity0=0',b'Name=caf\xe9',b'; comment'):self.assertIn(line,text)
        self.assertFalse((self.client/'eqclient.ini').exists())
        backup=self.prefix/'trasc-display-originals'
        self.assertEqual((backup/'eqclient.ini').read_bytes(),original)
        self.assertFalse(apply_display(self.client,self.prefix,'1280x720',True)['changed'])
        apply_display(self.client,self.prefix,'800x600',False)
        self.assertIn(b'WindowedMode=TRUE',ini.read_bytes())
        self.assertIn(b'Width=800',ini.read_bytes())
        self.assertEqual((backup/'eqclient.ini').read_bytes(),original)
        self.assertEqual((backup/'eqclient.previous.ini').read_bytes(),text)

    def test_invalid_or_ambiguous_input_does_not_change_client_files(self):
        ini=self.client/'eqclient.ini';ini.write_bytes(b'[Defaults]\n')
        for resolution,fullscreen in [('1920x1080',True),('1280x720','false')]:
            with self.assertRaises(ValueError):apply_display(self.client,self.prefix,resolution,fullscreen)
        (self.client/'EQCLIENT.INI').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError,'Ambiguous'):apply_display(self.client,self.prefix,'1280x720',True)
        self.assertEqual(ini.read_bytes(),b'[Defaults]\n');self.assertFalse(self.prefix.exists())

    def test_symlinks_and_failed_backup_leave_original_untouched(self):
        outside=self.root/'outside';outside.write_bytes(b'untouched')
        ini=self.client/'eqclient.ini';ini.symlink_to(outside)
        with self.assertRaises(ValueError):apply_display(self.client,self.prefix,'1280x720',True)
        ini.unlink();ini.write_bytes(b'[Defaults]\nWindowedMode=TRUE\n')
        original=ini.read_bytes()
        with patch('client_display.atomic_bytes',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):apply_display(self.client,self.prefix,'1280x720',True)
        self.assertEqual(ini.read_bytes(),original);self.assertEqual(outside.read_bytes(),b'untouched')

    def test_bom_and_supported_sizes(self):
        ini=self.client/'eqclient.ini';ini.write_bytes(b'\xef\xbb\xbf[Defaults]\r\nWindowedMode=TRUE\r\n')
        apply_display(self.client,self.prefix,'1280x720',True)
        self.assertTrue(ini.read_bytes().startswith(b'\xef\xbb\xbf[Defaults]\r\nWindowedMode=FALSE'))
        self.assertEqual(ini.read_bytes().count(b'[Defaults]'),1)
        for size in RESOLUTIONS:self.assertIn('WindowedMode=TRUE',display_ini('',size,False))
