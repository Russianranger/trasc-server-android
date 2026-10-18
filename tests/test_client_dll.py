"""Current Triptych project languages and exact-source DLL provenance.

The project fixture is the MIT-licensed Release-NMS-Client project at
Triptych commit 38a4f2ad03203cb2f12dbff26fd613cc47efba0a. Toolchain execution
is mocked here; these tests do not claim an MSVC or physical-device build.
"""
import hashlib
import json
from pathlib import Path
import os
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import client_dll
import client_mouse
import client_launch_compatibility as launch


PROJECT = '''<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'"><ClCompile><StructMemberAlignment>1Byte</StructMemberAlignment><RuntimeLibrary>MultiThreaded</RuntimeLibrary><Optimization>Disabled</Optimization><BufferSecurityCheck>false</BufferSecurityCheck><CompileAs>CompileAsCpp</CompileAs><PreprocessorDefinitions>WIN32;NDEBUG</PreprocessorDefinitions></ClCompile></ItemDefinitionGroup><ItemGroup>{}</ItemGroup></Project>'''
FIXTURE = Path(__file__).with_name('fixtures')/'eqgame_dll-38a4f2.vcxproj'
COMMIT = '38a4f2ad03203cb2f12dbff26fd613cc47efba0a'


def dll_bytes():
    value=bytearray(512);value[:2]=b'MZ';struct.pack_into('<I',value,0x3c,128)
    value[128:132]=b'PE\0\0';struct.pack_into('<H',value,132,0x14c)
    struct.pack_into('<H',value,150,0x2000);struct.pack_into('<H',value,152,0x10b)
    value+=b'\0'.join(m.encode() for m in (client_mouse.MARKER,client_mouse.LOADING_MARKER,
        client_mouse.DISPLAY_MARKER,client_mouse.PARTICLE_MARKER,client_mouse.BOAT_MARKER))
    return value


class ClientDllTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.work=Path(temp.name)
        for name in ('client/current','logs','builds'):(self.work/name).mkdir(parents=True)
        self.root=self.work/'sources/current/Release-NMS-Client'
        self.project=self.root/'eqgame_dll/eqgame_dll.vcxproj'
        self.project.parent.mkdir(parents=True)
        self.engine=SimpleNamespace(work=self.work,profile='custom',check_cancel=lambda:None,
            server_running=lambda:False,log=lambda message:None)
        self.project.write_text(PROJECT.format('<ClCompile Include="main.cpp"/>'))
        (self.project.parent/'main.cpp').write_text('int fixture;')
        (self.project.parent/'header.h').write_text('#define FIXTURE 1')
        (self.work/'sources/current/trasc-source.json').write_text(json.dumps({'commit':COMMIT}))

    def sdk(self):
        sdk=self.work/'client/toolchain'
        for name in ('include/msvc','include/ucrt','include/shared','include/um','include/winrt','lib/msvc','lib/ucrt','lib/um','bin'):
            (sdk/name).mkdir(parents=True,exist_ok=True)
        for name in ('include/msvc/vector','include/um/Windows.h','lib/msvc/libcmt.lib','lib/ucrt/libucrt.lib','lib/um/kernel32.lib','bin/cl.exe','bin/link.exe','bin/c1xx.dll','bin/c2.dll','bin/vcruntime140.dll','bin/msvcp140.dll','sdk.json'):
            (sdk/name).write_bytes(b'fixture')

    def build(self, mutate=None):
        calls=[]
        def run(args,**kwargs):
            calls.append(args)
            if Path(args[0]).name=='link.exe':
                output=next(v for v in args if str(v).startswith('/out:'))
                path=Path(str(output)[5:].removeprefix('Z:').replace('\\','/'))
                path.write_bytes(dll_bytes())
                if mutate:mutate()
        self.engine.run=run
        with patch.object(client_mouse,'prepare_sources',return_value={}):
            result=client_dll.build_dll(self.engine,{})
        return result,calls

    def test_real_selected_project_has_one_explicit_c_translation_unit(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                         '321125c4fde8d57a9981f6708682c2886c5e3b3dff15151beb1fb5abda2c8506')
        recipe=client_dll.project_recipe(FIXTURE)
        self.assertEqual(len(recipe['sources']),53)
        self.assertEqual([name for name,mode in recipe['languages'].items() if mode=='c'],['nms_vorbis.c'])

    def test_real_project_emits_tc_for_vorbis_and_tp_for_cpp(self):
        self.project.write_bytes(FIXTURE.read_bytes());recipe=client_dll.project_recipe(self.project)
        for name in recipe['sources']:(self.project.parent/name).write_text('/* fixture */')
        for name in ('Detours/inc','dependencies/dx9/Include'):
            (self.root/name).mkdir(parents=True)
        self.sdk();result,calls=self.build()
        compile_calls=calls[:-1];self.assertEqual(len(compile_calls),53)
        for name,command in zip(recipe['sources'],compile_calls):
            c=name=='nms_vorbis.c'
            self.assertEqual('/TC' in command,c);self.assertEqual('/TP' in command,not c)
            self.assertEqual('/std:c++14' in command,not c)
        self.assertEqual(result['build']['source_identity']['commit'],COMMIT)
        inventory=json.loads((self.work/'builds/client-dll-staged/source-inputs.json').read_text())
        self.assertIn('eqgame_dll/nms_vorbis.c',inventory['inputs'])
        self.assertIn('eqgame_dll/header.h',inventory['inputs'])
        self.assertIn('@launcher/eq_client_loading.h',inventory['inputs'])
        self.assertIn('@sdk/sdk.json',inventory['inputs'])
        self.assertFalse((self.work/'client/current/dinput8.dll').exists())

    def test_conditional_debug_override_does_not_override_release_c(self):
        self.project.write_text(PROJECT.format('''<ClCompile Include="main.cpp"><CompileAs Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">CompileAsCpp</CompileAs><CompileAs Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">CompileAsC</CompileAs></ClCompile>'''))
        self.assertEqual(client_dll.project_recipe(self.project)['languages']['main.cpp'],'c')

    def test_unsupported_or_ambiguous_compile_as_fails_closed(self):
        for tag in ('<CompileAs>Unexpected</CompileAs>','<CompileAs>CompileAsC</CompileAs><CompileAs>CompileAsCpp</CompileAs>',
                    '<CompileAs Condition="SomethingElse">CompileAsC</CompileAs>'):
            self.project.write_text(PROJECT.format('<ClCompile Include="main.cpp">'+tag+'</ClCompile>'))
            with self.subTest(tag=tag),self.assertRaisesRegex(ValueError,'CompileAs'):
                client_dll.project_recipe(self.project)

    def test_default_compile_as_honors_c_extension(self):
        self.project.write_text(PROJECT.format('<ClCompile Include="main.c"><CompileAs>Default</CompileAs></ClCompile>'))
        self.assertEqual(client_dll.project_recipe(self.project)['languages']['main.c'],'c')

    def test_content_change_with_identical_size_mtime_invalidates_cached_identity(self):
        first=client_dll.source_identity(self.engine)
        path=self.project.parent/'header.h';before=path.stat()
        path.write_text('#define FIXTURE 2');os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        second=client_dll.source_identity(self.engine)
        self.assertNotEqual(first['sha256'],second['sha256'])

    def test_add_remove_files_and_revision_changes_affect_identity(self):
        first=client_dll.source_identity(self.engine)['sha256'];extra=self.project.parent/'extra.h'
        extra.write_text('new header');self.assertNotEqual(first,client_dll.source_identity(self.engine)['sha256'])
        extra.unlink();self.assertEqual(first,client_dll.source_identity(self.engine)['sha256'])
        (self.work/'sources/current/trasc-source.json').write_text(json.dumps({'commit':'a'*40}))
        self.assertNotEqual(first,client_dll.source_identity(self.engine)['sha256'])

    def test_client_assets_and_whole_sdk_are_not_hashed(self):
        first=client_dll.source_identity(self.engine)['sha256']
        assets=self.root/'ClientFiles';assets.mkdir();(assets/'client.bin').write_bytes(b'large unrelated assets')
        sdk=self.work/'client/toolchain/include';sdk.mkdir(parents=True);(sdk/'library.h').write_text('SDK content')
        self.assertEqual(first,client_dll.source_identity(self.engine)['sha256'])

    def test_relative_bundled_headers_and_sdk_manifest_are_bound(self):
        dependency=self.root/'Blech/Blech.h';dependency.parent.mkdir();dependency.write_text('header')
        self.sdk();first=client_dll.source_identity(self.engine)
        self.assertIn('Blech/Blech.h',first['inputs'])
        dependency.write_text('edited header')
        second=client_dll.source_identity(self.engine)['sha256'];self.assertNotEqual(first['sha256'],second)
        (self.work/'client/toolchain/sdk.json').write_bytes(b'changed SDK manifest')
        self.assertNotEqual(second,client_dll.source_identity(self.engine)['sha256'])

    def test_missing_declared_include_is_not_created_and_later_headers_are_hashed(self):
        self.project.write_text(self.project.read_text().replace('<CompileAs>',
            '<AdditionalIncludeDirectories>../dependencies/boost</AdditionalIncludeDirectories><CompileAs>',1))
        missing=self.root/'dependencies/boost'
        first=client_dll.source_identity(self.engine)
        self.assertFalse(missing.exists())
        self.assertEqual(client_dll._include_path(self.root,self.project.parent,'../dependencies/boost'),missing)
        missing.mkdir(parents=True);(missing/'example.hpp').write_text('new actual dependency')
        second=client_dll.source_identity(self.engine)
        self.assertNotEqual(first['sha256'],second['sha256'])
        self.assertIn('dependencies/boost/example.hpp',second['inputs'])

    def test_missing_declared_include_is_passed_unchanged_to_compiler(self):
        self.project.write_text(self.project.read_text().replace('<CompileAs>',
            '<AdditionalIncludeDirectories>../dependencies/boost</AdditionalIncludeDirectories><CompileAs>',1))
        self.sdk();_,calls=self.build();missing=self.root/'dependencies/boost'
        argument='/I'+('Z:'+str(missing).replace('/','\\') if os.name!='nt' else str(missing))
        self.assertIn(argument,calls[0]);self.assertFalse(missing.exists())

    def test_missing_include_cannot_escape_source_or_hide_a_link(self):
        outside=self.work/'outside';outside.mkdir()
        (self.root/'linked').symlink_to(outside,target_is_directory=True)
        for entry in ('../../outside/missing','../missing/../../outside','../missing/../linked/child'):
            with self.subTest(entry=entry),self.assertRaisesRegex(ValueError,'escapes|Linked'):
                client_dll._include_path(self.root,self.project.parent,entry)

    def test_unchanged_inputs_reuse_hashes_but_rescan_paths(self):
        client_dll.source_identity(self.engine)
        # No source-file reads after the stat-based cache is primed; metadata is
        # still read and every directory is enumerated to detect new inputs.
        original=Path.open
        def guarded(path,*args,**kwargs):
            if path.suffix in ('.cpp','.h'):raise AssertionError('Rehashed an unchanged input')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',guarded):client_dll.source_identity(self.engine)

    def test_linked_input_and_parent_normalization_escape_rejected(self):
        outside=self.work/'outside';outside.mkdir();(outside/'secret.h').write_text('outside')
        (self.project.parent/'linked').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Linked'):client_dll.source_identity(self.engine)
        with self.assertRaisesRegex(ValueError,'Linked'):
            client_dll._source_path(self.root,self.project.parent/'linked/../main.cpp')

    def test_input_inspection_is_bounded(self):
        with patch.object(client_dll,'SOURCE_SINGLE_LIMIT',4):
            with self.assertRaisesRegex(ValueError,'oversized'):client_dll.source_identity(self.engine)

    def test_legacy_deployed_and_staged_receipts_remain_unknown_without_rewrite(self):
        staged=self.work/'builds/client-dll-staged';staged.mkdir();data=dll_bytes()
        (staged/'dinput8.dll').write_bytes(data);(self.work/'client/current/DINPUT8.dll').write_bytes(data)
        legacy={'sha256':hashlib.sha256(data).hexdigest(),'built_at':1790429966.9277978}
        paths=[staged/'build.json',self.work/'logs/client-dll-deploy.json']
        for path in paths:path.write_text(json.dumps(legacy))
        before=[p.read_bytes() for p in paths];status=client_dll.compiler_status(self.engine)
        self.assertEqual([status['freshness'][k]['state'] for k in ('installed','staged')],['unknown','unknown'])
        self.assertEqual(before,[p.read_bytes() for p in paths])
        with self.assertRaisesRegex(ValueError,'Rebuild dinput8'):
            client_dll.deploy_dll(self.engine,{})

    def test_current_stale_and_modified_freshness(self):
        self.sdk();result,_=self.build();data=dll_bytes()
        (self.work/'client/current/dinput8.dll').write_bytes(data)
        deployed=self.work/'logs/client-dll-deploy.json';deployed.write_text(json.dumps(result['build']))
        self.assertEqual(client_dll.compiler_status(self.engine)['freshness']['installed']['state'],'current')
        (self.project.parent/'header.h').write_text('edited')
        self.assertEqual(client_dll.compiler_status(self.engine)['freshness']['staged']['state'],'stale')
        with self.assertRaisesRegex(ValueError,'Rebuild dinput8'):client_dll.deploy_dll(self.engine,{})
        (self.work/'client/current/dinput8.dll').write_bytes(b'locally replaced')
        self.assertEqual(client_dll.compiler_status(self.engine)['freshness']['installed']['state'],'modified')

    def test_selected_source_refresh_preserves_verified_deployed_pair_for_launch_only(self):
        self.sdk();result,_=self.build();installed=self.work/'client/current/dinput8.dll'
        installed.write_bytes(dll_bytes())
        receipt=self.work/'logs/client-dll-deploy.json';receipt.write_text(json.dumps(result['build']))
        (self.work/'sources/current/trasc-source.json').write_text(json.dumps({'commit':'a'*40}))
        before={p:p.read_bytes() for p in (installed,receipt,self.work/'sources/current/trasc-source.json')}
        requirements={'known_deployed':True,'required_spellbook_slots':1440,'deployed_source_commit':COMMIT}
        with patch.object(launch.client_compatibility,'requirements',return_value=requirements), \
                patch.object(launch.client_connection,'status',return_value={'host':{'host':'127.0.0.1'}}), \
                patch.object(launch.client_spellbook,'status',return_value={'patched':True}):
            checked=launch.preflight(self.engine,{})
        self.assertTrue(checked['allowed']);self.assertEqual(checked['dll_state'],'stale')
        self.assertEqual(checked['dll_evidence'],'verified_deployed_source_receipt')
        self.assertEqual(checked['dll_source_commit'],COMMIT);self.assertTrue(checked['warnings'])
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        with self.assertRaisesRegex(ValueError,'Rebuild dinput8'):client_dll.deploy_dll(self.engine,{})

    def test_deployed_pair_fallback_rejects_modified_legacy_and_invalid_source_receipts(self):
        self.sdk();result,_=self.build();installed=self.work/'client/current/dinput8.dll'
        receipt=self.work/'logs/client-dll-deploy.json'
        (self.work/'sources/current/trasc-source.json').write_text(json.dumps({'commit':'a'*40}))
        requirements={'known_deployed':True,'required_spellbook_slots':1440,'deployed_source_commit':COMMIT}
        records=[]
        legacy=dict(result['build']);legacy.pop('source_identity');records.append(('legacy',legacy,dll_bytes()))
        records.append(('modified',result['build'],b'changed DLL'))
        invalid=dict(result['build'],source_identity={'format':1,'commit':COMMIT});records.append(('invalid',invalid,dll_bytes()))
        other=dict(result['build'],source_identity={**result['build']['source_identity'],'commit':'b'*40})
        records.append(('different revision',other,dll_bytes()))
        for name,record,contents in records:
            installed.write_bytes(contents);receipt.write_text(json.dumps(record))
            with self.subTest(name=name), \
                    patch.object(launch.client_compatibility,'requirements',return_value=requirements), \
                    patch.object(launch.client_connection,'status',return_value={'host':{'host':'127.0.0.1'}}), \
                    patch.object(launch.client_spellbook,'status',return_value={'patched':True}):
                checked=launch.preflight(self.engine,{})
                self.assertFalse(checked['allowed']);self.assertNotIn('dll_evidence',checked)

    def test_verified_current_build_deploys_only_on_explicit_action(self):
        self.sdk();self.build();installed=self.work/'client/current/dinput8.dll'
        installed.write_bytes(b'original')
        self.engine._local_client=lambda:self.work/'client/current'
        replacements=[]
        def apply(client,changes):
            replacements.append(changes)
            self.assertEqual(installed.read_bytes(),b'original')
            installed.write_bytes(next(iter(changes.values())).read_bytes())
            return 'backups/client-setup/fixture'
        self.engine._apply_client_changes=apply
        self.assertEqual(replacements,[])
        result=client_dll.deploy_dll(self.engine,{})
        self.assertEqual(len(replacements),1)
        self.assertEqual(result['backup'],'backups/client-setup/fixture')
        self.assertEqual(client_dll.compiler_status(self.engine)['freshness']['installed']['state'],'current')

    def test_changed_source_during_compile_does_not_replace_existing_stage(self):
        self.sdk();self.build();stage=self.work/'builds/client-dll-staged'
        before={p.name:p.read_bytes() for p in stage.iterdir()}
        with self.assertRaisesRegex(ValueError,'changed during compilation'):
            self.build(lambda:(self.project.parent/'header.h').write_text('changed during build'))
        self.assertEqual(before,{p.name:p.read_bytes() for p in stage.iterdir()})

    def test_missing_source_is_reported_without_assuming_current(self):
        self.project.unlink();status=client_dll.compiler_status(self.engine)
        self.assertFalse(status['source']['available'])
        self.assertEqual(status['freshness']['staged']['state'],'missing')


if __name__=='__main__':unittest.main()
