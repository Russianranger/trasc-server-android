"""Exercise the native DLL worker's current-session identity without Wine."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import client_compile_runner as runner
import client_dll
import client_mouse


class CompilerSessionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.work=self.root/'work';self.work.mkdir()
        self.session=self.root/'session';self.session.mkdir()
        for name in ('client','logs','run','builds'):(self.work/name).mkdir()
        for name,value in (('WORK',self.work),('SESSION',self.session),('LOG',self.work/'logs/client-compiler.log')):
            change=patch.object(runner,name,value);change.start();self.addCleanup(change.stop)

    def request(self,**changes):
        request={'profile':'custom','mode':'compiler',**changes}
        (self.session/'request.json').write_text(json.dumps(request))

    def test_initializes_profile_from_current_request_instead_of_saved_game_options(self):
        self.request()
        saved=self.work/'client/launch-options.json'
        saved.write_text('{"profile":"takp","mode":"client"}')
        compiler=runner.Compiler()
        self.assertEqual(compiler.profile,'custom')
        self.assertEqual(compiler.work,self.work)
        self.assertFalse(compiler.server_running())
        self.assertEqual(json.loads(saved.read_text()),{'profile':'takp','mode':'client'})

    def test_rejects_other_profiles_modes_and_missing_identity(self):
        for request in ({'profile':'traditional','mode':'compiler'}, {'profile':'takp','mode':'compiler'},
                        {'profile':'unknown','mode':'compiler'}, {'profile':'CUSTOM','mode':'compiler'},
                        {'profile':'custom','mode':'client'}, {'profile':'custom','mode':'desktop'},
                        {'profile':'custom'}, {'mode':'compiler'}, {}, [], None):
            with self.subTest(request=request):
                (self.session/'request.json').write_text(json.dumps(request))
                with self.assertRaisesRegex(ValueError,'Custom compiler request'): runner.Compiler()

    def test_missing_invalid_and_oversized_current_requests_do_not_use_saved_options(self):
        (self.work/'client/launch-options.json').write_text('{"profile":"custom","mode":"compiler"}')
        with self.assertRaisesRegex(ValueError,'Cannot read the compiler launch request'):runner.Compiler()
        for contents in (b'{broken',b'\xff'):
            (self.session/'request.json').write_bytes(contents)
            with self.assertRaisesRegex(ValueError,'Cannot read the compiler launch request'):runner.Compiler()
        (self.session/'request.json').write_bytes(b' '*65537)
        with self.assertRaisesRegex(ValueError,'too large'):runner.Compiler()

    def test_rejected_main_reports_error_without_starting_or_cleaning_up_wine(self):
        self.request(profile='traditional')
        lease=self.work/'run/client-dll-building.json';lease.write_bytes(b'launcher lease')
        display=self.session/'display.sock';display.write_bytes(b'existing display')
        with patch.object(runner.signal,'signal'),patch.object(runner,'update') as update, \
             patch.object(runner,'rotate') as rotate,patch.object(runner,'write_xauthority') as auth, \
             patch.object(runner.subprocess,'Popen') as start,patch.object(runner.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'Custom compiler request'):runner.main()
        update.assert_called_once()
        self.assertEqual(update.call_args.args,('error',))
        for operation in (rotate,auth,start,run):operation.assert_not_called()
        self.assertEqual(lease.read_bytes(),b'launcher lease')
        self.assertEqual(display.read_bytes(),b'existing display')

    def test_validated_worker_reaches_real_build_sdk_check(self):
        self.request();compiler=runner.Compiler()
        with patch.object(compiler,'run') as run:
            with self.assertRaisesRegex(ValueError,'Microsoft x86 toolchain and SDK first'):
                client_dll.build_dll(compiler,{})
        run.assert_not_called()

    def test_real_build_recipe_stages_mocked_toolchain_output_and_preserves_client(self):
        self.request();compiler=runner.Compiler()
        client=self.work/'client/current';client.mkdir()
        installed=client/'dinput8.dll';installed.write_bytes(b'installed DLL remains')
        prefix=self.work/'client/prefix';prefix.mkdir();(prefix/'user.reg').write_bytes(b'game prefix remains')
        project=self.work/'sources/current/Release-NMS-Client/eqgame_dll/eqgame_dll.vcxproj'
        project.parent.mkdir(parents=True)
        project.write_text('''<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'"><ClCompile><StructMemberAlignment>1Byte</StructMemberAlignment><RuntimeLibrary>MultiThreaded</RuntimeLibrary><Optimization>Disabled</Optimization><BufferSecurityCheck>false</BufferSecurityCheck><PreprocessorDefinitions>WIN32;NDEBUG</PreprocessorDefinitions></ClCompile></ItemDefinitionGroup><ItemGroup><ClCompile Include="main.cpp"/></ItemGroup></Project>''')
        (project.parent/'main.cpp').write_text('int fixture;')
        sdk=self.work/'client/toolchain'
        for name in ('include/msvc','include/ucrt','include/shared','include/um','include/winrt','lib/msvc','lib/ucrt','lib/um','bin'):
            (sdk/name).mkdir(parents=True,exist_ok=True)
        for name in ('include/msvc/vector','include/um/Windows.h','lib/msvc/libcmt.lib','lib/ucrt/libucrt.lib','lib/um/kernel32.lib','bin/cl.exe','bin/link.exe','bin/c1xx.dll','bin/c2.dll','bin/vcruntime140.dll','bin/msvcp140.dll','sdk.json'):
            (sdk/name).write_bytes(b'fixture')
        dll=bytearray(512);dll[:2]=b'MZ';struct.pack_into('<I',dll,0x3c,128)
        dll[128:132]=b'PE\0\0';struct.pack_into('<H',dll,132,0x14c)
        struct.pack_into('<H',dll,150,0x2000);struct.pack_into('<H',dll,152,0x10b)
        dll+=b'\0'.join(marker.encode() for marker in (client_mouse.MARKER,client_mouse.LOADING_MARKER,client_mouse.DISPLAY_MARKER,client_mouse.PARTICLE_MARKER,client_mouse.BOAT_MARKER))
        def toolchain(args,**kwargs):
            self.assertEqual(kwargs['cwd'],project.parent)
            if Path(args[0]).name=='link.exe':
                build=next((self.work/'builds').glob('client-dll-*'))
                (build/'dinput8.dll').write_bytes(dll)
        with patch.object(compiler,'run',side_effect=toolchain) as run,patch.object(compiler,'log'), \
             patch.object(client_mouse,'prepare_sources',return_value={}):
            result=client_dll.build_dll(compiler,{})
        self.assertEqual(run.call_count,2)
        self.assertEqual([Path(call.args[0][0]).name for call in run.call_args_list],['cl.exe','link.exe'])
        staged=self.work/'builds/client-dll-staged'
        self.assertEqual((staged/'dinput8.dll').read_bytes(),dll)
        self.assertEqual(json.loads((staged/'build.json').read_text()),result['build'])
        self.assertEqual(installed.read_bytes(),b'installed DLL remains')
        self.assertEqual((prefix/'user.reg').read_bytes(),b'game prefix remains')


if __name__=='__main__':unittest.main()
