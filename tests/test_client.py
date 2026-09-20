import json
import hashlib
import io
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_runner
import runtime_probe
import client_metrics
from engine import Engine, CLIENT_FILES
from managed_content import update_ini


def pe(path, machine=0x14c):
    data=bytearray(256);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,128);data[128:132]=b'PE\0\0';struct.pack_into('<H',data,132,machine);path.write_bytes(data)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.engine=Engine(self.root)
        self.client=self.root/'client/current';self.client.mkdir();pe(self.client/'eqgame.exe');pe(self.client/'dinput8.dll')
        (self.client/'trasc-client.json').write_text(json.dumps({'executable':'eqgame.exe','imported':True}))

    def tearDown(self): self.temp.cleanup()

    def test_mouse_warp_is_reversible_and_scoped_to_game(self):
        request={'mode':'client','executable':'eqgame.exe','resolution':'800x600'}
        for enabled,value in ((True,'default'),(False,'default')):
            supervisor=client_runner.Supervisor(dict(request,mouse_warp=enabled))
            with patch.object(supervisor,'run') as run,patch.object(supervisor,'update') as update,patch('client_mouse.launch_mode',return_value='off'):
                supervisor.configure_mouse()
                args=run.call_args.args[0]
                self.assertEqual(args[4],r'HKCU\Software\Wine\AppDefaults\eqgame.exe\DirectInput')
                self.assertEqual(args[-2],value)
                update.assert_called_once_with(mouse_warp=value,camera_mouse='off')
                self.assertEqual(supervisor.env['TRASC_EQ_CAMERA_MOUSE_V1'],'0')
        with self.assertRaisesRegex(ValueError,'mouse recentering'):
            client_runner.validate_request(dict(request,mouse_warp='force'))

    def test_loading_experiment_is_independent_and_clears_inherited_mode(self):
        for mode, expected in [('fast','fast'),('profile','profile'),('needs_dll','off'),('off','off')]:
            supervisor=client_runner.Supervisor({'mode':'client','resolution':'800x600'})
            with patch('client_mouse.loading_mode',return_value=mode),patch('client_mouse.display_mode',return_value='profile'),patch.object(supervisor,'update') as update:
                supervisor.configure_loading()
                self.assertEqual(supervisor.env['TRASC_EQ_LOAD_V2'],expected)
                self.assertEqual(supervisor.env['TRASC_EQ_LOAD_V1'],'off')
                update.assert_called_once_with(spell_loading=mode,display_loading='profile',particle_mode='off',boat_mode='off')
                self.assertEqual(supervisor.env['TRASC_EQ_DISPLAY_V1'],'profile')
        with self.assertRaisesRegex(ValueError,'spell loading'):
            client_runner.validate_request({'fast_spell_parse':'yes'})

    def test_model_loading_mode_is_scoped_validated_and_clears_inherited_settings(self):
        with self.assertRaisesRegex(ValueError,'model loading'):
            client_runner.validate_request({'reduce_load_pauses':'yes'})
        for mode in ('yield','profile','off','needs_dll','unsupported_executable'):
            with patch.dict(os.environ,{'TRASC_EQ_DISPLAY_V1':'yield'}):
                supervisor=client_runner.Supervisor({'mode':'desktop','resolution':'800x600'})
                self.assertEqual(supervisor.env['TRASC_EQ_DISPLAY_V1'],'off')
            with patch('client_mouse.loading_mode',return_value='fast'),patch('client_mouse.display_mode',return_value=mode),patch.object(supervisor,'update'):
                supervisor.configure_loading()
                self.assertEqual(supervisor.env['TRASC_EQ_DISPLAY_V1'],mode if mode in ('yield','profile') else 'off')
                self.assertEqual(supervisor.env['TRASC_EQ_LOAD_V2'],'fast')

    def test_particle_mode_is_validated_and_clears_inherited_repair(self):
        with self.assertRaisesRegex(ValueError,'particle option'):
            client_runner.validate_request({'particle_mode':'force'})
        for mode in ('off','profile','repair','needs_dll','unsupported_graphics','unsupported_executable'):
            with patch.dict(os.environ,{'TRASC_EQ_PARTICLES_V1':'repair'}):
                supervisor=client_runner.Supervisor({'mode':'desktop','resolution':'800x600'})
                self.assertEqual(supervisor.env['TRASC_EQ_PARTICLES_V1'],'off')
            with patch('client_mouse.loading_mode',return_value='fast'),patch('client_mouse.display_mode',return_value='yield'),patch('client_mouse.particle_mode',return_value=mode),patch.object(supervisor,'update') as update:
                supervisor.configure_loading()
                self.assertEqual(supervisor.env['TRASC_EQ_PARTICLES_V1'],mode if mode in ('profile','repair') else 'off')
                self.assertEqual(supervisor.env['TRASC_EQ_LOAD_V2'],'fast')
                self.assertEqual(supervisor.env['TRASC_EQ_DISPLAY_V1'],'yield')
                self.assertEqual(update.call_args.kwargs['particle_mode'],mode)

    def test_boat_mode_is_validated_and_never_inherits_enablement(self):
        with self.assertRaisesRegex(ValueError,'boat option'):
            client_runner.validate_request({'boat_mode':'repair'})
        for mode in ('off','profile','needs_dll','unsupported_executable'):
            with patch.dict(os.environ,{'TRASC_EQ_BOATS_V1':'profile','TRASC_EQ_BOATS_V2':'profile'}):
                supervisor=client_runner.Supervisor({'mode':'desktop','resolution':'800x600'})
                self.assertEqual(supervisor.env['TRASC_EQ_BOATS_V1'],'off')
                self.assertEqual(supervisor.env['TRASC_EQ_BOATS_V2'],'off')
            with patch('client_mouse.boat_mode',return_value=mode),patch.object(supervisor,'update') as update:
                supervisor.configure_loading()
                self.assertEqual(supervisor.env['TRASC_EQ_BOATS_V1'],'off')
                self.assertEqual(supervisor.env['TRASC_EQ_BOATS_V2'],'profile' if mode=='profile' else 'off')
                self.assertEqual(update.call_args.kwargs['boat_mode'],mode)

    def test_runtime_preflight_uses_only_temporary_files_and_verifies_io(self):
        session=self.root/'runtime-preflight';session.mkdir()
        report=runtime_probe.probe(session)
        self.assertTrue(report['ok'])
        self.assertEqual([p.name for p in session.iterdir()],['runtime-probe.json'])
        self.assertGreaterEqual(report['timings_seconds']['seek_read_1024'],0)
        request={'mode':'desktop','resolution':'800x600','runtime_mode':'unknown'}
        with self.assertRaisesRegex(ValueError,'runtime mode'):client_runner.validate_request(request)

    def test_prefix_reuse_invalidates_on_changes_missing_files_or_failed_check(self):
        for folder in ('prefix', 'session', 'logs'): (self.root/folder).mkdir(exist_ok=True)
        with patch.object(client_runner, 'PREFIX', self.root/'prefix'), patch.object(client_runner, 'SESSION', self.root/'session'), patch.object(client_runner, 'LOGS', self.root/'logs'):
            supervisor=client_runner.Supervisor({'mode':'desktop','resolution':'800x600'})
            marker=self.root/'prefix/.trasc-prefix-ready.json'
            with patch.object(supervisor, 'prefix_signature', return_value={'version':1}) as signature, patch.object(client_runner, 'prefix_diagnostics', return_value={'prefix_ready':True}) as diagnostics, patch.object(supervisor,'run') as run, patch.object(supervisor,'check_prefix') as check:
                supervisor.prepare_prefix();self.assertEqual(run.call_args.args[0][-1],'-u')
                supervisor.prepare_prefix();self.assertEqual(run.call_args.args[0][-1],'-i')
                signature.return_value={'version':2}
                supervisor.prepare_prefix();self.assertEqual(run.call_args.args[0][-1],'-u')
                diagnostics.return_value={'prefix_ready':False}
                supervisor.prepare_prefix();self.assertEqual(run.call_args.args[0][-1],'-u')
                check.side_effect=RuntimeError('failed check')
                with self.assertRaisesRegex(RuntimeError,'failed check'):supervisor.prepare_prefix()
                self.assertFalse(marker.exists())
                self.assertIn('wine_prefix',supervisor.status['timings_seconds'])

    def test_cpu_profiles_retain_memory_ordering_and_validate_selection(self):
        request={'mode':'desktop','resolution':'800x600','cpu_profile':'balanced'}
        client_runner.validate_request(request)
        balanced=client_runner.Supervisor(request).env
        compatible=client_runner.Supervisor(dict(request,cpu_profile='compatibility')).env
        self.assertEqual(balanced['BOX64_DYNAREC_STRONGMEM'],compatible['BOX64_DYNAREC_STRONGMEM'])
        self.assertEqual(balanced['BOX64_DYNAREC_SAFEFLAGS'],'1')
        self.assertEqual(compatible['BOX64_DYNAREC_SAFEFLAGS'],'2')
        self.assertEqual(compatible['BOX64_DYNAREC_BIGBLOCK'],'0')
        accurate=client_runner.Supervisor(dict(request,cpu_profile='accurate')).env
        client_runner.validate_request(dict(request,cpu_profile='accurate'))
        self.assertEqual(accurate['BOX64_DYNAREC_X87DOUBLE'],'1')
        self.assertEqual(accurate['BOX64_DYNAREC_FASTROUND'],'0')
        self.assertEqual(accurate['BOX64_DYNAREC_FASTNAN'],'0')
        self.assertEqual(accurate['BOX64_SYNC_ROUNDING'],'1')
        self.assertEqual(accurate['BOX64_DYNAREC_BIGBLOCK'],balanced['BOX64_DYNAREC_BIGBLOCK'])
        self.assertNotIn('BOX64_DYNAREC_X87DOUBLE',balanced)
        with self.assertRaisesRegex(ValueError,'CPU profile'):client_runner.validate_request(dict(request,cpu_profile='unknown'))

    def test_graphics_identity_requires_actual_virgl_and_host_driver(self):
        guest='OpenGL renderer string: virgl (Adreno (TM) 740)\n'
        status=client_runner.graphics_status('virgl',guest,'TRASC GPU renderer: Adreno (TM) 740\n')
        self.assertEqual(status['graphics_acceleration'],'host_gpu')
        self.assertEqual(status['host_gl_renderer'],'Adreno (TM) 740')
        self.assertEqual(client_runner.graphics_status('virgl',guest)['graphics_acceleration'],'unknown')
        status=client_runner.graphics_status('virgl','OpenGL renderer string: virgl (llvmpipe)\n','TRASC GPU renderer: llvmpipe\n')
        self.assertEqual(status['graphics_acceleration'],'software')
        with self.assertRaisesRegex(RuntimeError,'did not load VirGL'):
            client_runner.graphics_status('virgl','OpenGL renderer string: llvmpipe\n')
        with self.assertRaisesRegex(RuntimeError,'driver check failed'):client_runner.graphics_status('virgl','')
        # A prior GPU log cannot label a subsequent software launch accelerated.
        status=client_runner.graphics_status('software','OpenGL renderer string: llvmpipe\n','TRASC GPU renderer: Adreno (TM) 740\n')
        self.assertEqual(status['graphics_acceleration'],'software');self.assertEqual(status['host_gl_renderer'],'')

    def test_graphics_options_and_native_process_failure(self):
        request={'mode':'desktop','resolution':'800x600','renderer':'virgl'}
        client_runner.validate_request(request)
        with self.assertRaisesRegex(ValueError,'graphics option'):client_runner.validate_request(dict(request,renderer='invalid'))
        gpu=client_runner.Supervisor(request)
        self.assertEqual(gpu.env['GALLIUM_DRIVER'],'virpipe')
        self.assertEqual(gpu.env['VTEST_SOCKET_NAME'],'/tmp/.virgl_test')
        self.assertEqual(client_runner.Supervisor(dict(request,renderer='software')).env['GALLIUM_DRIVER'],'llvmpipe')
        with patch.object(client_runner,'SESSION',self.root):
            (self.root/'gpu-failed').touch()
            with self.assertRaisesRegex(RuntimeError,'GPU bridge exited'):gpu.stopping()

    def test_normal_launch_disables_hot_traces_but_keeps_errors_and_dll_proof(self):
        normal=client_runner.Supervisor({'mode':'client','resolution':'800x600'}).env['WINEDEBUG']
        self.assertEqual(normal,'-all,+timestamp,+pid,err+all,trace+loaddll,trace+fps,warn+dsound,warn+wave,warn+mmdevapi')
        self.assertNotIn('trace+frametime',normal)
        self.assertNotIn('trace+seh',normal)
        self.assertIn('trace+seh',client_runner.wine_debug(True))

    def test_frame_rates_require_a_complete_interval_and_survive_rotation(self):
        capture=client_runner.WineLog(self.root/'fps.log',512)
        first=b'10.1:0120:0124:trace:fps:wined3d_cs_exec_present 08ab @ approx 0.01fps\n'
        capture.observe(first)
        self.assertNotIn('wine_present',capture.snapshot()[0])
        line=b'12.0:0120:0124:trace:fps:wined3d_cs_exec_present 08ab @ approx 4.25fps\n'
        capture.observe(line[:25]);self.assertNotIn('wine_present',capture.snapshot()[0])
        capture.observe(line[25:])
        self.assertEqual(capture.snapshot()[0]['wine_present']['per_second'],4.25)
        # Another process/swapchain gets its own initial-interval exclusion.
        capture.observe(first.replace(b'0120',b'0150'))
        self.assertEqual(capture.snapshot()[0]['wine_present']['stream'],'0120:08ab')
        capture.pump(io.BytesIO(b'unrelated output\n'*1000))
        self.assertEqual(capture.snapshot()[0]['wine_present']['per_second'],4.25)
        capture.observe(b'err:winediag:wined3d_init Setting multithreaded command stream to 0x1.\n')
        self.assertEqual(capture.snapshot()[0]['graphics_threading_observed'],'multi')
        capture.observe(b'err:winediag:wined3d_init Setting multithreaded command stream to 0.\n')
        self.assertEqual(capture.snapshot()[0]['graphics_threading_observed'],'single')

    def test_graphics_threading_is_explicit_and_does_not_change_cpu_or_prefix(self):
        request={'mode':'desktop','resolution':'800x600'}
        multi=client_runner.Supervisor(request);single=client_runner.Supervisor(dict(request,graphics_threading='single'))
        self.assertEqual(multi.env['WINE_D3D_CONFIG'],'csmt=1')
        self.assertEqual(single.env['WINE_D3D_CONFIG'],'csmt=0')
        worker=client_runner.Supervisor(dict(request,graphics_threading='opengl_worker'))
        client_runner.validate_request(dict(request,graphics_threading='opengl_worker'))
        self.assertEqual(worker.env['WINE_D3D_CONFIG'],'csmt=0')
        self.assertEqual(worker.env['mesa_glthread'],'true')
        self.assertEqual(single.env['mesa_glthread'],'false')
        self.assertEqual({k:v for k,v in worker.env.items() if k not in ('mesa_glthread','TRASC_CLIENT_LAUNCH')},
                         {k:v for k,v in single.env.items() if k not in ('mesa_glthread','TRASC_CLIENT_LAUNCH')})
        self.assertEqual({k:v for k,v in multi.env.items() if k not in ('WINE_D3D_CONFIG','TRASC_CLIENT_LAUNCH')},
                         {k:v for k,v in single.env.items() if k not in ('WINE_D3D_CONFIG','TRASC_CLIENT_LAUNCH')})
        with self.assertRaisesRegex(ValueError,'graphics threading'):
            client_runner.validate_request(dict(request,graphics_threading='unknown'))

    def test_previous_game_log_is_bounded_and_does_not_modify_imported_files(self):
        logs=self.root/'logs';logs.mkdir(exist_ok=True)
        source=self.client/'Logs';source.mkdir()
        game=source/'dbg.txt';data=b'begin\n'+b'x'*4096+b'\nend';game.write_bytes(data)
        (self.client/'eqclient.ini').write_text('private settings')
        client_runner.preserve_game_log(self.client,logs,1024)
        saved=(logs/'client-game.previous.log').read_bytes()
        self.assertEqual(len(saved),1024);self.assertTrue(saved.startswith(b'begin'));self.assertTrue(saved.endswith(b'end'))
        self.assertEqual(game.read_bytes(),data)
        game.unlink();game.symlink_to(self.client/'eqclient.ini')
        client_runner.preserve_game_log(self.client,logs,1024)
        self.assertFalse((logs/'client-game.previous.log').exists())
        game.unlink();source.rmdir();source.symlink_to(self.root/'logs',target_is_directory=True)
        (logs/'dbg.txt').write_text('outside')
        client_runner.preserve_game_log(self.client,logs,1024)
        self.assertFalse((logs/'client-game.previous.log').exists())

    def test_thread_observation_follows_owned_children_and_handles_exits(self):
        proc=self.root/'proc'
        def task(pid,tid,name,children='',cpu=3):
            p=proc/str(pid)/'task'/str(tid);p.mkdir(parents=True,exist_ok=True)
            fields=['0']*40;fields[0]='R';fields[11]='11';fields[12]='7';fields[36]=str(cpu)
            (p/'stat').write_text(str(tid)+' ('+name+') '+' '.join(fields))
            (p/'status').write_text('Cpus_allowed_list:\t0-5\n');(p/'children').write_text(children)
        task(10,10,'wine main (x)','20 30');task(20,20,'eqgame.exe');task(20,21,'wine:gl0')
        task(40,40,'unrelated:gl0')
        sample=client_metrics.process_threads(10,proc)
        self.assertTrue(sample['incomplete']) # Child 30 exited / is inaccessible.
        self.assertTrue(sample['game_running'])
        task(20,20,'unrelated.exe')
        self.assertFalse(client_metrics.process_threads(10,proc)['game_running'])
        task(20,20,'eqgame.exe')
        game_stat=proc/'20/task/20/stat'
        game_stat.write_text(game_stat.read_text().replace(') R ', ') Z '))
        self.assertFalse(client_metrics.process_threads(10,proc)['game_running'])
        self.assertEqual([w['tid'] for w in sample['mesa_gl_workers']],[21])
        self.assertEqual(sample['threads'][0]['cpu_ticks'],18)
        self.assertEqual(sample['mesa_gl_workers'][0]['allowed_cpus'],'0-5')
        self.assertEqual(sample['mesa_gl_workers'][0]['last_cpu'],3)
        self.assertNotIn(40,[t['pid'] for t in sample['threads']])

    def test_launch_marker_finds_detached_wine_without_collecting_other_environments(self):
        proc=self.root/'proc';proc.mkdir();(proc/'self').symlink_to(proc/'10')
        for pid,marker in [(10,'session-a'),(20,'session-a'),(30,'session-a-old')]:
            p=proc/str(pid);task=p/'task'/str(pid);task.mkdir(parents=True)
            (p/'environ').write_bytes(('PRIVATE=not-for-logs\0TRASC_CLIENT_LAUNCH='+marker+'\0').encode())
            fields=['0']*40;fields[0]='R'
            (task/'stat').write_text(str(pid)+' (wine:gl0) '+' '.join(fields))
            (task/'status').write_text('Cpus_allowed_list:\t0-3\n')
            # No children file: all processes have reparented independently.
        sample=client_metrics.process_threads(10,proc,launch_token='session-a')
        self.assertEqual({w['pid'] for w in sample['mesa_gl_workers']},{10,20})
        self.assertFalse(sample['incomplete'])
        self.assertNotIn('PRIVATE',json.dumps(sample));self.assertNotIn('session-a',json.dumps(sample))

    def test_stream_rotation_keeps_load_evidence_and_split_fatal_error(self):
        path=self.root/'client-wine.log'
        proxy=b'trace:loaddll:build_module Loaded L"D:\\dinput8.dll" at 00100000: native\n'
        system=b'trace:loaddll:build_module Loaded L"C:\\windows\\syswow64\\dinput8.dll" at 70000000: builtin\n'
        payload=proxy+system+b'ordinary output\n'*900+b'wine: could not load kernel32.dll, status c0000135'
        capture=client_runner.WineLog(path,1024)
        capture.pump(io.BufferedReader(io.BytesIO(payload),buffer_size=37))
        fields,error=capture.snapshot()
        self.assertEqual(fields['wine_log_bytes'],len(payload))
        self.assertTrue(fields['native_loaded']);self.assertTrue(fields['system_dinput8_loaded'])
        self.assertIn('c0000135',error)
        self.assertGreater(fields['wine_log_rotations'],1)
        self.assertLessEqual(path.stat().st_size,1024)
        self.assertLessEqual(path.with_suffix('.overflow.log').stat().st_size,1024)
        self.assertEqual(len(fields['dll_evidence']),2)
        self.assertIn(b'c0000135',path.read_bytes())

    def test_upgrade_archives_large_old_trace_without_copying_a_gigabyte(self):
        path=self.root/'client-wine.log';previous=path.with_suffix('.previous.log')
        path.write_bytes(b'FIRST\n'+b'a'*10000+b'\nLAST\n')
        client_runner.archive_log(path,1024)
        data=previous.read_bytes()
        self.assertFalse(path.exists());self.assertEqual(len(data),1024)
        self.assertTrue(data.startswith(b'FIRST'));self.assertTrue(data.endswith(b'LAST\n'))
        self.assertIn(b'previous log shortened',data)
        path.write_bytes(b'next small session')
        client_runner.archive_log(path,1024)
        self.assertEqual(previous.read_bytes(),b'next small session')

    def test_pe32_and_native_dll_architecture_validation(self):
        request={'mode':'client','resolution':'800x600','executable':'eqgame.exe','native_dinput8':True}
        with patch.object(client_runner,'CLIENT',self.client):
            client_runner.validate_request(request)
            pe(self.client/'dinput8.dll',0x8664)
            with self.assertRaisesRegex(ValueError,'32-bit'): client_runner.validate_request(request)
            client_runner.validate_request(dict(request,native_dinput8=False))
            with self.assertRaisesRegex(ValueError,'executable name'): client_runner.validate_request(dict(request,executable='../eqgame.exe'))
            with self.assertRaisesRegex(ValueError,'resolution'): client_runner.validate_request(dict(request,resolution='800x600; bad'))

    def test_presence_and_override_are_not_native_load_confirmation(self):
        self.assertFalse(client_runner.dll_status('dinput8.dll present; WINEDLLOVERRIDES=dinput8=n')['native_loaded'])
        self.assertFalse(client_runner.dll_status('trace:loaddll:build_module Loaded L"C:\\windows\\system32\\dinput8.dll": builtin')['native_loaded'])
        self.assertTrue(client_runner.dll_status('trace:loaddll:build_module Loaded L"D:\\dinput8.dll" at 00100000: native')['native_loaded'])

    def test_proxy_and_system_directinput_loads_are_distinguished(self):
        proxy=r'146718.383:0194:0198:trace:loaddll:build_module Loaded L"D:\\DINPUT8.dll" at 7AE60000: native'
        system=r'146720.142:0194:0198:trace:loaddll:build_module Loaded L"C:\\windows\\system32\\dinput8.dll" at 70000000: builtin'
        status=client_runner.dll_status(proxy+'\n'+system)
        self.assertTrue(status['native_loaded']);self.assertTrue(status['system_dinput8_loaded'])
        self.assertEqual(status['evidence'],[proxy,system])
        self.assertFalse(client_runner.dll_status(system)['native_loaded'])
        self.assertFalse(client_runner.dll_status(proxy)['system_dinput8_loaded'])
        self.assertFalse(client_runner.dll_status(system.replace('builtin','native'))['native_loaded'])

    def test_stop_reason_separates_requested_stop_from_error(self):
        supervisor=client_runner.Supervisor({'mode':'desktop','resolution':'800x600'})
        with patch.object(client_runner,'SESSION',self.root),patch.object(client_runner,'stop_requested',False),patch.object(client_runner,'stop_reason',None):
            self.assertFalse(supervisor.stopping())
            (self.root/'stop').touch();self.assertTrue(supervisor.stopping())
            self.assertEqual(supervisor.status['stop_reason'],'stop_request')
        with patch.object(client_runner,'stop_requested',True),patch.object(client_runner,'stop_reason','SIGTERM'):
            self.assertTrue(supervisor.stopping())
            self.assertEqual(supervisor.status['stop_reason'],'SIGTERM')

    def test_reported_loader_failure_is_fatal_but_optional_driver_warnings_are_not(self):
        error=client_runner.fatal_launch_error('wine: could not load kernel32.dll, status c0000135')
        self.assertIn('c0000135',error)
        self.assertIn('kernel32.dll',error)
        self.assertIsNone(client_runner.fatal_launch_error('err:ntoskrnl:ZwLoadDriver winebth failed\nError loading needed lib libXcomposite.so.1'))
        dependency='err:module:import_dll Library VCRUNTIME140.dll (which is needed by L"D:\\dinput8.dll") not found'
        self.assertIsNone(client_runner.fatal_launch_error(dependency))
        self.assertIn('VCRUNTIME140.dll',client_runner.fatal_launch_error(dependency+'\nerr:module:loader_init Importing dlls for L"D:\\eqgame.exe" failed, status c0000135'))

    def test_prefix_check_distinguishes_incomplete_prefix_from_missing_runtime(self):
        prefix=self.root/'prefix';wine=self.root/'wine'
        for parent in (prefix/'drive_c/windows/syswow64',wine/'lib/wine/i386-windows'):
            parent.mkdir(parents=True)
            for name in ('ntdll.dll','kernel32.dll','kernelbase.dll','cmd.exe'):pe(parent/name)
        self.assertTrue(client_runner.prefix_diagnostics(prefix,wine)['prefix_ready'])
        (prefix/'drive_c/windows/syswow64/kernel32.dll').unlink()
        report=client_runner.prefix_diagnostics(prefix,wine)
        self.assertFalse(report['prefix_ready']);self.assertTrue(report['runtime_ready'])
        pe(wine/'lib/wine/i386-windows/kernel32.dll',0x8664)
        self.assertFalse(client_runner.prefix_diagnostics(prefix,wine)['runtime_ready'])


    def model_fixture(self):
        source=self.root/'directx';source.mkdir()
        destination=self.root/'prefix/drive_c/windows/syswow64';destination.mkdir(parents=True)
        manifest={'format':1,'source_sha256':client_runner.DIRECTX_SOURCE_SHA256,'files':{}}
        for name in client_runner.MODEL_DLLS:
            pe(source/name)
            manifest['files'][name]={'bytes':(source/name).stat().st_size,'sha256':hashlib.sha256((source/name).read_bytes()).hexdigest()}
            (destination/name).write_bytes(b'original builtin '+name.encode())
        (source/'directx.json').write_text(json.dumps(manifest))
        return source,destination

    def test_models_validate_complete_pair_and_preserve_original_system_files(self):
        source,destination=self.model_fixture()
        original={n:(destination/n).read_bytes() for n in client_runner.MODEL_DLLS}
        client_runner.prepare_model_libraries(source,self.root/'prefix')
        for name in client_runner.MODEL_DLLS:
            self.assertEqual((destination/name).read_bytes(),(source/name).read_bytes())
            self.assertEqual((self.root/'prefix/trasc-directx-originals'/name).read_bytes(),original[name])
        client_runner.prepare_model_libraries(source,self.root/'prefix')
        (source/'d3dx9_35.dll').write_bytes(b'bad'+b'x'*253)
        with self.assertRaisesRegex(ValueError,'verification'):client_runner.prepare_model_libraries(source,self.root/'prefix')
        self.assertEqual((destination/'d3dx9_30.dll').read_bytes(),(source/'d3dx9_30.dll').read_bytes())

    def test_bad_model_pair_and_failed_install_do_not_leave_partial_replacement(self):
        source,destination=self.model_fixture()
        original={n:(destination/n).read_bytes() for n in client_runner.MODEL_DLLS}
        real_replace=client_runner.os.replace
        def fail_second(src,dest):
            if Path(src).name=='d3dx9_35.dll':raise OSError('simulated install failure')
            return real_replace(src,dest)
        with patch.object(client_runner.os,'replace',side_effect=fail_second):
            with self.assertRaisesRegex(OSError,'simulated'):client_runner.prepare_model_libraries(source,self.root/'prefix')
        for name in client_runner.MODEL_DLLS:self.assertEqual((destination/name).read_bytes(),original[name])
        (source/'d3dx9_35.dll').write_bytes(b'bad'+b'x'*253)
        with self.assertRaisesRegex(ValueError,'verification'):client_runner.prepare_model_libraries(source,self.root/'prefix')
        for name in client_runner.MODEL_DLLS:self.assertEqual((destination/name).read_bytes(),original[name])

    def test_model_load_evidence_distinguishes_native_and_builtin(self):
        trace=r'0194:trace:loaddll:build_module Loaded L"C:\\windows\\system32\\D3DX9_35.dll" at 1000: native'
        self.assertEqual(client_runner.model_dll_status(trace)[0],{'d3dx9_35.dll':'native'})
        self.assertEqual(client_runner.model_dll_status(trace.replace('native','builtin'))[0],{'d3dx9_35.dll':'builtin'})
        self.assertEqual(client_runner.model_dll_status('Installed d3dx9_35.dll; d3dx9_35=n,b')[0],{})

    def export_fixture(self):
        folder=self.root/'server/export';folder.mkdir(parents=True,exist_ok=True)
        for name in CLIENT_FILES:(folder/name).write_text('generated '+name)
        return {'filter_applied':False}

    def test_prepare_keeps_other_settings_and_dll_and_backs_up_handshake_files(self):
        (self.client/'eqclient.ini').write_text('; keep comment\n[Defaults]\nWindowedMode=FALSE\nFoo=untouched\n[Other]\nMusic=1\n')
        (self.client/'EQHOST.TXT').write_text('old endpoint');(self.client/'resources').mkdir()
        (self.client/'resources/spells_us.txt').write_text('old spells')
        dll=(self.client/'dinput8.dll').read_bytes()
        with patch.object(self.engine,'_export_client_data',side_effect=self.export_fixture): result=self.engine.prepare_client({'resolution':'960x540'})
        self.assertIn('Host=127.0.0.1:5999',(self.client/'EQHOST.TXT').read_text())
        self.assertFalse((self.client/'eqhost.txt').exists())
        ini=(self.client/'eqclient.ini').read_text();self.assertIn('Foo=untouched',ini);self.assertIn('Music=1',ini);self.assertIn('; keep comment',ini);self.assertIn('WindowedWidth=960',ini)
        self.assertEqual((self.client/'dinput8.dll').read_bytes(),dll)
        self.assertEqual((self.root/result['backup']/'resources/spells_us.txt').read_text(),'old spells')
        for name in CLIENT_FILES:
            self.assertEqual((self.client/name).read_bytes(),(self.client/'resources'/name).read_bytes())

    def test_failed_prepare_restores_already_replaced_files(self):
        first=CLIENT_FILES[0];(self.client/first).write_text('original')
        calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==3: raise RuntimeError('test interruption')
        with patch.object(self.engine,'_export_client_data',side_effect=self.export_fixture),patch.object(self.engine,'check_cancel',side_effect=cancel):
            with self.assertRaisesRegex(RuntimeError,'interruption'):self.engine.prepare_client({})
        self.assertEqual((self.client/first).read_text(),'original')
        self.assertFalse((self.client/'Resources'/first).exists())

    def test_ini_sections_are_preserved_and_values_replace_case_insensitively(self):
        text='[defaults]\nwindowedmode=FALSE\n[Unrelated]\nWidth=7\n'
        updated=update_ini(text,'Defaults',{'WindowedMode':'TRUE'})
        self.assertIn('windowedmode=TRUE\r\n[Unrelated]\r\nWidth=7',updated)
        self.assertEqual(updated.count('[defaults]'),1)


if __name__=='__main__':unittest.main()
