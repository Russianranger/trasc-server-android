package io.github.russianranger.trasc;

import android.content.Context;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Independent client rootfs and Wine prefix; server packages/database are never changed. */
final class ClientRuntime {
    private static ClientRuntime instance;
    static synchronized ClientRuntime get(Context context){if(instance==null)instance=new ClientRuntime(context.getApplicationContext());return instance;}
    static final String RELEASE="https://github.com/Russianranger/trasc-server-android/releases/download/client-runtime-v1/";
    final Context context;
    final RuntimeManager server;
    final File root,client,prefix,run,tmp,directx;
    volatile boolean busy;
    volatile String status="Install the client runtime to try Wine and ROF2.";
    private volatile Process process;
    private volatile GraphicsBridge graphics;
    private volatile AudioBridge audio;
    ClientRuntime(Context context) {
        this.context=context;server=RuntimeManager.get(context);
        root=new File(server.work,"client/runtime");client=new File(server.work,"client/current");prefix=new File(server.work,"client/prefix");
        directx=new File(server.work,"client/directx");
        run=new File(server.home,"tmp/client/session");tmp=new File(server.home,"tmp/client/tmp");
    }
    boolean installed(){return new File(root,"etc/trasc-client-runtime.json").isFile();}
    boolean alive(){return (process!=null&&process.isAlive())||(graphics!=null&&graphics.alive());}
    File displaySocket(){return new File(run,"display.sock");}
    static JSONObject json(File file)throws Exception {
        if(file.length()>131072)throw new IOException("Client metadata exceeds limits");
        return new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
    }
    JSONObject state()throws Exception {
        JSONObject result=new JSONObject().put("installed",installed()).put("alive",alive()).put("busy",busy).put("status",status);
        File report=new File(run,"status.json");
        if(report.isFile())try{JSONObject info=json(report);result.put("launch",info);if(info.optBoolean("compiler"))result.put("status",info.optString("message",status));}catch(Exception ignored){}
        File options=new File(server.work,"client/launch-options.json");
        if(options.isFile())try{result.put("launch_options",json(options));}catch(Exception ignored){}
        result.put("directx_installed",DirectXInstaller.installed(directx));
        result.put("display_ready",alive()&&displaySocket().exists());
        return result;
    }
    private void begin()throws IOException {
        synchronized(server) {
            if(busy||server.sessionBusy||server.installing)throw new IOException("Finish the current runtime/session operation first");
            busy=true;
        }
    }
    synchronized JSONObject installOnline()throws Exception {
        begin();File archive=new File(context.getCacheDir(),"client-runtime.tar.gz"),manifest=new File(context.getCacheDir(),"client-runtime-manifest.json");
        try {
            if(alive())throw new IOException("Stop the client before changing its runtime");
            server.download(RELEASE+"client-runtime-manifest.json",manifest,text->status=text);
            JSONObject info=json(manifest);
            if(info.getInt("format")!=1||!info.getString("architecture").equals("arm64")||!info.getString("file").equals("client-runtime-arm64.tar.gz")||!info.getString("runtime").equals("client-1.0"))throw new IOException("Unsupported client runtime manifest");
            server.download(RELEASE+"client-runtime-arm64.tar.gz",archive,text->status=text);
            status="Verifying client runtime…";
            if(!RuntimeManager.sha256(archive).equalsIgnoreCase(info.getString("sha256")))throw new IOException("Client runtime checksum failed; download again");
            activate(archive);return state();
        } catch(Exception e){status=e.getMessage();server.recordFailure("client_runtime_install",e);throw e;}
        finally {busy=false;archive.delete();manifest.delete();}
    }
    synchronized JSONObject installOffline(File archive)throws Exception {
        begin();try{if(alive())throw new IOException("Stop the client before changing its runtime");activate(archive);return state();}
        catch(Exception e){status=e.getMessage();server.recordFailure("client_runtime_install",e);throw e;}
        finally{busy=false;}
    }
    private void activate(File archive)throws Exception {
        File staging=new File(server.home,"client-runtime-install"),previous=new File(server.work,"client/runtime-previous");
        // Recover an interrupted swap before removing any prior installation.
        if(!root.exists()&&previous.exists()&&!previous.renameTo(root))throw new IOException("Could not recover the previous client runtime");
        TarExtractor.remove(staging);staging.mkdirs();
        try {
            TarExtractor.extract(archive,staging,n->status="Unpacking client runtime · "+n+" files");
            JSONObject marker=json(new File(staging,"etc/trasc-client-runtime.json"));
            if(marker.getInt("format")!=1||!marker.getString("architecture").equals("arm64")||!marker.getString("runtime").equals("client-1.0"))throw new IOException("Choose the TRASC client runtime archive");
            for(String file:new String[]{"usr/bin/python3.11","usr/bin/Xtigervnc","usr/local/bin/box64","opt/wine/bin/wine","opt/wine/bin/wineserver"})
                if(!new File(staging,file).isFile())throw new IOException("Client runtime is incomplete: "+file);
            root.getParentFile().mkdirs();TarExtractor.remove(previous);
            if(root.exists()&&!root.renameTo(previous))throw new IOException("Could not preserve the previous client runtime");
            if(!staging.renameTo(root)){if(previous.exists())previous.renameTo(root);throw new IOException("Could not activate the client runtime");}
            TarExtractor.remove(previous);status="Client runtime installed. Try Wine desktop, then Launch ROF2.";
        } finally {TarExtractor.remove(staging);}
    }
    synchronized JSONObject installDirectX(File offline)throws Exception {
        begin();File archive=offline==null?new File(context.getCacheDir(),"directx_Jun2010_redist.exe"):offline;
        try {
            if(alive())throw new IOException("Stop the client before installing DirectX model helpers");
            if(offline==null)server.download(DirectXInstaller.URL,archive,text->status="DirectX helpers: "+text);
            status="Verifying and extracting DirectX model helpers…";
            File extractor=new File(context.getApplicationInfo().nativeLibraryDir,"libcabextract.so");
            DirectXInstaller.install(archive,directx,extractor,new File(server.work,"logs/client-directx.log"));
            status="DirectX model helpers installed. Launch ROF2 with model helpers enabled.";
            return state();
        } catch(Exception e){status=e.getMessage();server.recordFailure("client_directx_install",e);throw e;}
        finally {busy=false;if(offline==null)archive.delete();}
    }
    synchronized JSONObject start(JSONObject options)throws Exception {
        begin();boolean started=false,compilerLease=false;
        try {
            if(alive())throw new IOException("Client is already open. View it or stop it before another launch.");
            if(graphics!=null){graphics.stop();graphics=null;}
            if(audio!=null){audio.close();audio=null;}
            if(!installed())throw new IOException("Install the separate client runtime first");
            DirectXInstaller.recover(directx);
            if(server.alive()) {
                JSONObject response=server.request("state",new JSONObject());
                if(!response.getBoolean("ok"))throw new IOException(response.optString("error"));
                org.json.JSONArray jobs=response.getJSONObject("result").getJSONArray("jobs");
                for(int i=0;i<jobs.length();i++) {
                    JSONObject job=jobs.getJSONObject(i);
                    if(Arrays.asList("import_client_zip","prepare_client","export_client","apply_spell_test","restore_spell_test","client_addons_copy","client_dll_deploy").contains(job.optString("operation"))&&Arrays.asList("queued","running").contains(job.optString("status")))
                        throw new IOException("Wait for client file changes to finish before launching");
                }
            }
            String mode=options.optString("mode","client"),resolution=options.optString("resolution","800x600"),renderer=options.optString("renderer","software");
            String cpuProfile=options.optString("cpu_profile","balanced");
            String npcRendering=options.optString("npc_rendering","compatibility");
            String turnipDriver=options.optString("turnip_driver","24.3.4");
            if(!Arrays.asList("24.3.4","26.0.0").contains(turnipDriver))throw new IOException("Unsupported Turnip driver");
            if(!Arrays.asList("standard","compatibility","compatibility_042","direct_043").contains(npcRendering))throw new IOException("Unsupported NPC rendering mode");
            if(!Arrays.asList("balanced","compatibility","accurate").contains(cpuProfile))throw new IOException("Unsupported CPU profile");
            String runtimeMode=options.optString("runtime_mode","auto");
            if(!Arrays.asList("auto","compatibility").contains(runtimeMode))throw new IOException("Unsupported runtime mode");
            String graphicsThreading=options.optString("graphics_threading","multi");
            if(!Arrays.asList("multi","single","opengl_worker").contains(graphicsThreading))throw new IOException("Unsupported graphics threading");
            String cpuAffinity=options.optString("cpu_affinity","available");
            if(!Arrays.asList("available","game").contains(cpuAffinity))throw new IOException("Unsupported CPU affinity");
            if(!Arrays.asList("software","virgl","turnip").contains(renderer))throw new IOException("Unsupported graphics option");
            if(!Arrays.asList("desktop","client","compiler").contains(mode)||!Arrays.asList("640x480","800x600","960x540","1024x768","1280x720").contains(resolution))throw new IOException("Unsupported client launch option");
            if(mode.equals("compiler")) {
                if(!server.alive())throw new IOException("Open the server runtime before compiling");
                JSONObject state=server.request("state",new JSONObject()).getJSONObject("result");
                if(state.optBoolean("running"))throw new IOException("Stop the server before compiling the DLL");
                org.json.JSONArray jobs=state.getJSONArray("jobs");
                for(int i=0;i<jobs.length();i++)if(Arrays.asList("queued","running").contains(jobs.getJSONObject(i).optString("status")))
                    throw new IOException("Finish the current server operation before compiling");
                if(!new File(server.work,"client/toolchain/bin/cl.exe").isFile())throw new IOException("Import the Microsoft compiler/SDK ZIP first");
                RuntimeManager.write(new File(server.work,"run/client-dll-building.json"),new JSONObject().put("pid",android.os.Process.myPid()).toString());compilerLease=true;
            }
            File sessionPrefix=mode.equals("compiler")?new File(server.work,"client/compiler-prefix"):prefix;
            if(mode.equals("client")&&options.optBoolean("native_d3dx",true)&&!DirectXInstaller.installed(directx))throw new IOException("Install DirectX model helpers in the Client tab first, or disable model helpers for a Wine comparison");
            if(mode.equals("client")&&!new File(client,"trasc-client.json").isFile())throw new IOException("Import your ROF2 client ZIP first");
            String executable=mode.equals("client")?json(new File(client,"trasc-client.json")).getString("executable"):"";
            if(executable.contains("/")||executable.contains("\\"))throw new IOException("Invalid client executable path");
            if(options.optBoolean("repair_prefix",false)) {
                if(!mode.equals("desktop"))throw new IOException("Repair the Wine prefix in desktop mode first");
                File saved=ClientPrefix.preserve(prefix);
                RuntimeManager.write(new File(server.work,"logs/client-prefix-repair.json"),new JSONObject().put("created_utc",java.time.Instant.now().toString()).put("previous_prefix",saved==null?"none":server.work.toPath().relativize(saved.toPath()).toString()).toString(2));
            }
            TarExtractor.remove(run);TarExtractor.remove(tmp);run.mkdirs();tmp.mkdirs();sessionPrefix.mkdirs();client.mkdirs();
            File presentationLog=new File(server.work,"logs/client-presentation.log");
            if(presentationLog.exists())Files.move(presentationLog.toPath(),new File(server.work,"logs/client-presentation.previous.log").toPath(),StandardCopyOption.REPLACE_EXISTING);
            JSONObject request=new JSONObject().put("mode",mode).put("resolution",resolution).put("executable",executable).put("native_dinput8",options.optBoolean("native_dinput8",true))
                .put("diagnostic_logging",options.optBoolean("diagnostic_logging",false)).put("native_d3dx",mode.equals("client")&&options.optBoolean("native_d3dx",true)).put("renderer",renderer).put("cpu_profile",cpuProfile);
            request.put("runtime_mode",runtimeMode).put("storage",new JSONObject().put("kind","app_private_internal")
                .put("android_directory",client.getCanonicalPath()).put("windows_drive","D:").put("shared_storage",false));
            request.put("graphics_threading",graphicsThreading).put("cpu_affinity",cpuAffinity).put("fullscreen",mode.equals("client")&&options.optBoolean("fullscreen",true));
            request.put("npc_rendering",npcRendering).put("audio",options.optBoolean("audio",true)).put("sound_diagnostics",options.optBoolean("sound_diagnostics",false));
            request.put("turnip_driver",turnipDriver);
            File spellJournal=new File(server.work,"backups/client-spell-test/current.json");
            if(spellJournal.exists())request.put("spell_test",json(spellJournal));
            RuntimeManager.write(new File(run,"request.json"),request.toString());
            File backend=new File(server.home,"client-backend");backend.mkdirs();
            for(String name:new String[]{"client_runner.py","client_display.py","client_metrics.py","client_spells.py","client_vulkan.py","client_audio.py","libasound_module_pcm_trasc.so","audio-bundle.json","graphics_probe.py","runtime_probe.py","wined3d.dll","wined3d-patch.json","wineserver","wineserver-patch.json"})
                try(InputStream in=context.getAssets().open(name)){RuntimeManager.copy(in,new File(backend,name));}
            if(!new File(backend,"wineserver").setExecutable(true,true))throw new IOException("Could not prepare bundled Wine server");
            if(renderer.equals("turnip")) {
                status="Preparing Turnip "+turnipDriver+" and DXVK…";
                for(String name:new String[]{"turnip.so","turnip-26.0.0.so","vulkan-probe","dxvk-d3d9.dll","vulkan-bundle.json"})
                    try(InputStream in=context.getAssets().open(name)){RuntimeManager.copy(in,new File(backend,name));}
                if(!new File(backend,"vulkan-probe").setExecutable(true,true))throw new IOException("Could not prepare Vulkan preflight executable");
            }
            RuntimeManager.write(new File(root,"etc/hosts"),"127.0.0.1 localhost\n::1 localhost\n");
            RuntimeManager.write(new File(root,"etc/resolv.conf"),"nameserver 1.1.1.1\nnameserver 8.8.8.8\n");
            directx.mkdirs();new File(root,"directx").mkdirs();
            File nativeDir=new File(context.getApplicationInfo().nativeLibraryDir);
            List<String> command=new ArrayList<>(Arrays.asList(new File(nativeDir,"libproot.so").getPath(),"--kill-on-exit","-0","-r",root.getPath(),
                "-b",new File(backend,"wineserver").getPath()+":/opt/wine/bin/wineserver",
                "-b",new File(backend,"wined3d.dll").getPath()+":/opt/wine/lib/wine/i386-windows/wined3d.dll","-b","/dev","-b","/proc","-b","/sys","-b",directx.getPath()+":/directx","-b",client.getPath()+":/client","-b",sessionPrefix.getPath()+":/prefix","-b",run.getPath()+":/session",
                "-b",new File(server.work,"logs").getPath()+":/logs","-b",backend.getPath()+":/opt/trasc-client","-b",tmp.getPath()+":/tmp",
                "-w","/client","/usr/bin/env","-i","HOME=/root","USER=root","PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "LANG=C.UTF-8","TMPDIR=/tmp","PYTHONUNBUFFERED=1","/usr/bin/python3",mode.equals("compiler")?"/opt/trasc/client_compile_runner.py":"/opt/trasc-client/client_runner.py"));
            if(mode.equals("compiler"))command.addAll(1,Arrays.asList("-b",server.work.getPath()+":/work","-b",new File(server.home,"backend").getPath()+":/opt/trasc"));
            ProcessBuilder builder=new ProcessBuilder(command);builder.environment().put("PROOT_LOADER",new File(nativeDir,"libproot-loader.so").getPath());
            builder.environment().put("PROOT_TMP_DIR",tmp.getPath());
            boolean accelerated=false;
            File probeLog=new File(server.work,"logs/client-runtime-probe.log");
            if(runtimeMode.equals("auto")) {
                status="Checking faster runtime file access…";
                List<String> probeCommand=new ArrayList<>(command);probeCommand.set(probeCommand.size()-1,"/opt/trasc-client/runtime_probe.py");
                accelerated=ProotAcceleration.preflight(probeCommand,builder.environment(),probeLog,20000);
            } else RuntimeManager.write(probeLog,"Compatibility runtime selected; accelerator preflight skipped.\n");
            ProotAcceleration.configure(builder.environment(),accelerated);
            request.put("runtime_acceleration",accelerated?"seccomp":"compatibility").put("runtime_probe_verified",accelerated);
            RuntimeManager.write(new File(run,"request.json"),request.toString());
            if(renderer.equals("virgl")) {
                status="Opening Android GPU driver…";
                graphics=GraphicsBridge.start(new File(nativeDir,"libvirgl-server.so"),new File(tmp,".virgl_test"),new File(server.work,"logs/client-gpu.log"));
            }
            if(request.getBoolean("audio"))audio=AudioBridge.start(context,new File(run,"audio.sock"),new File(server.work,"logs/client-audio.log"));
            File prootLog=new File(server.work,"logs/client-proot.log");
            if(prootLog.exists())Files.move(prootLog.toPath(),new File(server.work,"logs/client-proot.previous.log").toPath(),StandardCopyOption.REPLACE_EXISTING);
            builder.redirectErrorStream(true);builder.redirectOutput(prootLog);
            process=builder.start();started=true;status="Starting client display and Wine…";
            if(mode.equals("client"))RuntimeManager.write(new File(server.work,"client/launch-options.json"),request.toString());
            final Process active=process;final GraphicsBridge bridge=graphics;final AudioBridge playback=audio;
            Thread monitor=new Thread(()->{
                try {
                    while(active.isAlive()) {
                        if(bridge!=null&&!bridge.alive()) {
                            RuntimeManager.write(new File(run,"gpu-failed"),"GPU bridge exited\n");
                            server.recordFailure("client_gpu",new IOException("GPU bridge exited; see client-gpu.log. Choose Software graphics to compare."));
                            break;
                        }
                        if(active.waitFor(1,TimeUnit.SECONDS))break;
                    }
                    active.waitFor();
                    synchronized(ClientRuntime.this){if(bridge!=null&&graphics==bridge){bridge.stop();graphics=null;}if(playback!=null&&audio==playback){playback.close();audio=null;}}
                } catch(Exception e){server.recordFailure("client_gpu_cleanup",e);}
            },"client-graphics-lifecycle");monitor.setDaemon(true);monitor.start();
            for(int i=0;i<200;i++) {
                File report=new File(run,"status.json");
                if(report.isFile()){JSONObject info=json(report);if(info.optString("phase").equals("error"))throw new IOException(info.optString("error"));}
                if(!process.isAlive())throw new IOException("Client runtime exited. See client-runtime.log and client-wine.log.");
                if(displaySocket().exists()){status=mode.equals("compiler")?"Microsoft DLL compilation running. See client-compiler.log; Stop client cancels.":"Client display open. Wine may take a minute to prepare its first prefix.";return state();}
                Thread.sleep(100);
            }
            throw new IOException("Client display startup timed out; export Logs");
        } catch(Exception e){server.recordFailure("client_start",e);if(started&&alive())stop();else if(graphics!=null){graphics.stop();graphics=null;}if(audio!=null){audio.close();audio=null;}status=e.getMessage();if(compilerLease)new File(server.work,"run/client-dll-building.json").delete();throw e;}
        finally {busy=false;}
    }
    synchronized void stop()throws Exception {
        Process active=process;
        if(active!=null&&active.isAlive()) {
            status="Stopping Wine and the client display…";run.mkdirs();RuntimeManager.write(new File(run,"stop"),"stop\n");
            if(!active.waitFor(25,TimeUnit.SECONDS)){active.destroy();if(!active.waitFor(5,TimeUnit.SECONDS)){active.destroyForcibly();if(!active.waitFor(5,TimeUnit.SECONDS))throw new IOException("Client runtime did not stop; wait before backing up");}}
        }
        if(graphics!=null){graphics.stop();graphics=null;}
        if(audio!=null){audio.close();audio=null;}
        new File(server.work,"run/client-dll-building.json").delete();
        process=null;status="Client stopped. Server runtime is managed separately.";
    }
}
