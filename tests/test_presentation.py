import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import client_presentation

class PresentationTest(unittest.TestCase):
    def test_defaults_and_choices(self):
        self.assertEqual(client_presentation.options({}),('rfb',30))
        for mode in ('rfb','native_surface'):
            for fps in (30,60): self.assertEqual(client_presentation.options({'presentation_mode':mode,'display_fps':fps}),(mode,fps))
        for invalid in (0,120,True,'60'):
            with self.assertRaises(ValueError): client_presentation.options({'display_fps':invalid})
    def test_current_path_has_no_helper_process(self):
        class Host:
            request={}
            def spawn(self,*args): raise AssertionError('Current display must not start prototype')
        self.assertEqual(client_presentation.start(Host())['presentation_active'],'rfb')
    def test_broken_bundle_falls_back_without_starting(self):
        class Host:
            request={'presentation_mode':'native_surface','display_fps':60}
            def spawn(self,*args): raise AssertionError('Unverified helper must not run')
        with patch.object(client_presentation.Path,'read_text',return_value='not-json'):
            result=client_presentation.start(Host())
        self.assertEqual(result['presentation_active'],'rfb')
        self.assertTrue(result['presentation_fallback'])
