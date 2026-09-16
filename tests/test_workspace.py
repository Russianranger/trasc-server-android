"""Guard destructive boundaries of add-on sync, SDK builds and player snapshots."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from engine import Engine
import client_addons
import client_dll
import managed_content
import player_data


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name);self.engine=Engine(self.work)
        self.client=self.work/'client/current';self.client.mkdir();(self.client/'trasc-client.json').write_text('{"imported":true}')
        self.source=self.work/'sources/current/Release-NMS-Client/ClientFiles';self.source.mkdir(parents=True)
        (self.source/'uifiles/default').mkdir(parents=True);(self.client/'UIFILES/Default').mkdir(parents=True)
        (self.source/'uifiles/default/existing.xml').write_bytes(b'new XML')
        (self.source/'uifiles/default/missing.xml').write_bytes(b'missing XML')
        (self.client/'UIFILES/Default/EXISTING.XML').write_bytes(b'old XML')
        (self.source/'spells_us.txt').write_bytes(b'never install')

    def test_overlay_lock_casefold_bulk_missing_and_all_with_backups(self):
        scan=client_addons.scan(self.engine)
        self.assertEqual(scan['counts'],{'missing':2,'different':1,'same':0})
        client_addons.set_lock(self.engine,{'path':'UIFILES/DEFAULT/MISSING.XML','locked':True})
        scan=client_addons.scan(self.engine)
        self.assertIn('No unlocked',client_addons.copy_files(self.engine,{'mode':'missing','snapshot':scan['snapshot']})['message'])
        result=client_addons.copy_files(self.engine,{'mode':'all','snapshot':scan['snapshot']})
        self.assertEqual(result['copied'],1)
        self.assertEqual((self.client/'UIFILES/Default/EXISTING.XML').read_bytes(),b'new XML')
        self.assertEqual((self.work/result['backup']/'UIFILES/Default/EXISTING.XML').read_bytes(),b'old XML')
        self.assertFalse((self.client/'spells_us.txt').exists())
        self.assertFalse((self.client/'UIFILES/Default/missing.xml').exists())
        self.engine=Engine(self.work)
        self.assertEqual(client_addons.policy(self.engine)['locked'],['uifiles/default/missing.xml'])
        scan=client_addons.set_lock(self.engine,{'path':'uifiles/default/missing.xml','locked':False})
        result=client_addons.copy_files(self.engine,{'mode':'selected','paths':['uifiles/default/missing.xml'],'snapshot':scan['snapshot']})
        self.assertEqual(result['copied'],1)

    def test_changed_files_stale_snapshots_and_symlinks_cannot_be_overwritten(self):
        scan=client_addons.scan(self.engine)
        (self.client/'UIFILES/Default/EXISTING.XML').write_bytes(b'edited after preview')
        with self.assertRaisesRegex(ValueError,'Compare again'): client_addons.copy_files(self.engine,{'mode':'all','snapshot':scan['snapshot']})
        with self.assertRaises(ValueError): client_addons.set_lock(self.engine,{'path':'../../server/file','locked':True})
        (self.client/'UIFILES/Default/missing.xml').symlink_to(self.work/'settings.json')
        with self.assertRaisesRegex(ValueError,'symlink'): client_addons.scan(self.engine)

    def test_addon_transaction_cancellation_restores_existing_and_removes_new(self):
        scan=client_addons.scan(self.engine);calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==2: raise ValueError('cancelled')
        # Run the transaction separately from read-only scan cancellation checks.
        with patch.object(client_addons,'scan',return_value=scan),patch.object(self.engine,'check_cancel',side_effect=cancel):
            with self.assertRaisesRegex(ValueError,'cancelled'): client_addons.copy_files(self.engine,{'mode':'all','snapshot':scan['snapshot']})
        self.assertEqual((self.client/'UIFILES/Default/EXISTING.XML').read_bytes(),b'old XML')
        self.assertFalse((self.client/'UIFILES/Default/missing.xml').exists())

    def test_dll_build_requires_sdk_and_lock_protects_deployment(self):
        with patch.object(client_dll,'compiler_status',return_value={'compiler':True,'sdk':False}):
            with self.assertRaisesRegex(ValueError,'SDK first'): client_dll.build_dll(self.engine,{})
        path=self.work/'bad.dll';path.write_bytes(b'not a DLL')
        with self.assertRaisesRegex(ValueError,'Windows DLL'): client_dll.validate_dll(path)
        project=self.work/'test.vcxproj'
        project.write_text('''<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'"><ClCompile><StructMemberAlignment>1Byte</StructMemberAlignment><RuntimeLibrary>MultiThreaded</RuntimeLibrary><Optimization>Disabled</Optimization><BufferSecurityCheck>false</BufferSecurityCheck><PreprocessorDefinitions>WIN32;NDEBUG;%(PreprocessorDefinitions)</PreprocessorDefinitions><AdditionalIncludeDirectories>..\\Detours\\inc</AdditionalIncludeDirectories></ClCompile></ItemDefinitionGroup><ItemGroup><ClCompile Include="main.cpp"/></ItemGroup></Project>''')
        recipe=client_dll.project_recipe(project)
        self.assertEqual(recipe['sources'],['main.cpp']);self.assertEqual(recipe['definitions'],['WIN32','NDEBUG'])
        project.write_text(project.read_text().replace('1Byte','8Bytes'))
        with self.assertRaisesRegex(ValueError,'ABI settings'): client_dll.project_recipe(project)

    def snapshot(self, extra=None):
        manifest={'format':'trasc-players-1','tables':{}}
        path=self.work/'incoming/players.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name in ['account','character_data']:
                data=b'H31\tH54657374\n'
                manifest['tables'][name]={'columns':[{'name':'id','type':'int(11)'},{'name':'name','type':'varchar(64)'}],
                   'member':'tables/'+name+'.tsv','rows':1,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
                z.writestr('tables/'+name+'.tsv',data)
            if extra: extra(manifest,z)
            z.writestr('manifest.json',json.dumps(manifest))
        return path

    def test_player_snapshot_does_not_accept_sql_or_world_tables(self):
        path=self.snapshot()
        _,manifest,_=player_data.read_snapshot(self.engine,str(path.relative_to(self.work)))
        self.assertEqual(len(manifest['tables']),2)
        self.snapshot(lambda m,z:z.writestr('inject.sql','DROP DATABASE peq;'))
        with self.assertRaisesRegex(ValueError,'Unexpected'): player_data.read_snapshot(self.engine,'incoming/players.zip')
        def world(m,z):
            m['tables']['items']=m['tables']['account'].copy();m['tables']['items']['member']='tables/items.tsv';z.writestr('tables/items.tsv',b'H31\tH54657374\n')
        self.snapshot(world)
        with self.assertRaisesRegex(ValueError,'Unknown player table'): player_data.read_snapshot(self.engine,'incoming/players.zip')

    def test_player_schema_review_blocks_removed_data_columns_before_backup(self):
        self.snapshot()
        columns={name:[{'name':'id','type':'int(11)','nullable':'NO','default':'<NULL>','extra':'auto_increment'}] for name in ['account','character_data']}
        with patch.object(player_data,'stopped'),patch.object(player_data,'schema',return_value=({'account':'InnoDB','character_data':'InnoDB'},columns)),patch.object(player_data,'rows',return_value=[]),patch.object(self.engine,'backup_database') as backup:
            preview=player_data.preview_players(self.engine,{'file':'incoming/players.zip'})
            self.assertFalse(preview['compatible']);self.assertIn('removed columns name',' '.join(preview['problems']))
            with self.assertRaisesRegex(ValueError,'removed columns'): player_data.restore_players(self.engine,{'file':'incoming/players.zip','replace':True,'sha256':preview['sha256']})
            backup.assert_not_called()


if __name__=='__main__': unittest.main()
