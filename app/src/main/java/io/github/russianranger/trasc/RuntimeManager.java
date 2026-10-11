package io.github.russianranger.trasc;

import android.content.Context;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.*;

/** Owns the app-private runtime. No Termux paths, shell commands or root access. */
public final class RuntimeManager {
    private static RuntimeManager instance;
    public static synchronized RuntimeManager get(Context c) {
        if (instance == null) instance = new RuntimeManager(c.getApplicationContext());
        return instance;
    }
    final Context context;
    final WorldProfiles profiles;
    File home, work, rootfs;
    private String boundProfile;
    volatile boolean sessionCancelled,sessionCancellable;
    volatile long sessionBytes,sessionTotal=-1;
    volatile String sessionPhase="idle";
    volatile String status = "Install the runtime to begin.";
    volatile boolean installing;
    volatile boolean sessionBusy;
    private volatile Process process;
    private String token;
    private volatile String recoveryError;
    private volatile String sessionRecoveryError;
    void requireRecovered()throws IOException {if(sessionRecoveryError!=null)throw new IOException(sessionRecoveryError);if(recoveryError!=null)throw new IOException(recoveryError);}
    private final Timer logMaintenance=new Timer("log-retention",true);

    private RuntimeManager(Context c) {
        context=c;profiles=new WorldProfiles(c.getFilesDir());
        home=c.getFilesDir();work=new File(home,"work");rootfs=new File(home,"rootfs");
        try {AllProfileSwap.recover(c.getFilesDir());profiles.reload();applyAllPreferences();bindProfile(profiles.current());} catch(IOException e){recoveryError="Profile recovery failed: "+e.getMessage();status=recoveryError;}
        logMaintenance.schedule(new TimerTask(){@Override public void run(){
            synchronized(RuntimeManager.this){
                if(sessionBusy)return;
                try{LogRetention.prune(work);}catch(IOException e){android.util.Log.w("TRASC","Log cleanup deferred",e);}
            }
        }},1000,60000);
    }
    private void bindProfile(String id)throws IOException {
        boundProfile=id;home=profiles.home(id);work=new File(home,"work");rootfs=new File(home,"rootfs");
        if(sessionRecoveryError==null)recoveryError=null;token=null;process=null;
        recoverSessionSwap();
        for(String folder:new String[]{"incoming","logs","run"}) {
            File dir=new File(work,folder);if(!dir.isDirectory()&&!dir.mkdirs())throw new IOException("Cannot prepare the selected profile");
        }
        status=WorldProfiles.label(id)+" · "+(installed()?"Runtime stopped":"Install the runtime to begin.");
    }
    JSONObject switchProfile(String expected,String id)throws Exception {
        requireRecovered();WorldProfiles.valid(id);profiles.beginSwitch(expected);
        try {
            ClientRuntime client=ClientRuntime.get(context);
            synchronized(client){synchronized(this){
                if(alive()||installing||sessionBusy||client.alive()||client.busy)
                    throw new IOException("Stop the client and server runtime, and finish transfers before switching worlds");
                String previous=profiles.current();
                if(!previous.equals(id)){
                    client.releaseIdleResources();
                    try {
                        bindProfile(id);client.bindProfile(id);profiles.select(id);
                    } catch(Exception e){
                        try{bindProfile(previous);client.bindProfile(previous);}catch(Exception restore){recoveryError="Profile recovery requires reopening the app";e.addSuppressed(restore);}
                        throw e;
                    }
                }
                return nativeState();
            }}
        } finally {profiles.endSwitch();}
    }
    boolean installed() { return new File(rootfs,"etc/trasc-runtime.json").isFile(); }
    private JSONObject runtimeMarker(File root)throws IOException {
        File marker=new File(root,"etc/trasc-runtime.json");
        if(!Files.isRegularFile(marker.toPath(),java.nio.file.LinkOption.NOFOLLOW_LINKS)||marker.length()>8192)
            throw new IOException("Missing or invalid server runtime identity");
        try{return new JSONObject(new String(Files.readAllBytes(marker.toPath()),StandardCharsets.UTF_8));}
        catch(Exception e){throw new IOException("Invalid server runtime identity",e);}
    }
    private static boolean buildReady(String profile,JSONObject marker) {
        return ServerRuntimeIdentity.buildReady(profile,marker.optInt("format"),marker.optString("architecture"),
            marker.optString("profile"),marker.optString("runtime"),marker.optInt("build_adapter"));
    }
    boolean alive() { return process!=null && process.isAlive(); }
    synchronized void start() throws Exception {
        if(recoveryError!=null)throw new IOException(recoveryError);
        if (alive()) return;
        if (installing) throw new IOException("Runtime installation is in progress");
        if (!installed()) {status="Install the runtime to begin."; return;}
        JSONObject marker=runtimeMarker(rootfs);
        ServerRuntimeIdentity.validateSession(boundProfile,marker.optInt("format"),marker.optString("architecture"),
            marker.optString("profile"),marker.optString("runtime"),marker.optInt("build_adapter"));
        File nativeDir=new File(context.getApplicationInfo().nativeLibraryDir);
        File proot=new File(nativeDir,"libproot.so"), loader=new File(nativeDir,"libproot-loader.so");
        if (!proot.canExecute() || !loader.exists()) throw new IOException("This APK is missing its ARM64 runtime launcher");
        File backend=new File(home,"backend"); backend.mkdirs();
        for(String name:new String[]{"engine.py","bots.py","bot_socials.py","modern_bot_bridge.py","modern_bot_bridge.h","era_rules.py","era_presets.json","peq_database.py","client_ui.py","traditional_content.py","traditional_build.py","traditional_verify.py","traditional_runtime.py","takp_build.py","takp_runtime.py","takp_client.py","takp-client/bundle.json","takp-client/eqw-camera-build.json","takp-client/eqw-cursor-verification.json","takp-client/d3d8.dll","takp-client/eqgame.dll","takp-client/eqw.dll","boat_trial.py","ferry_service.py","ferry_service.lua","ferry_route.py","server_ferry.py","eq_server_ferry.h","spire.py","spire_catalog.py","log_retention.py","rule_catalog.py","managed_content.py","client_display.py","client_xauthority.py","client_settings.py","client_spells.py","client_addons.py","client_dll.py","client_toolchain.py","pack-client-sdk.py","client_mouse.py","eq_camera_mouse.h","eq_client_loading.h","eq_fast_decimal.h","eq_spell_checksum.h","eq_display_loading.h","eq_first_person_particles.h","eq_boat_diagnostics.h","player_data.py","player_tables.py","client_compile_runner.py"})
            try(InputStream in=context.getAssets().open(name)) { copy(in,new File(backend,name)); }
        for(String name:new String[]{"takp-client/eqw-LICENSE.txt","takp-client/d3d8to9-LICENSE.txt"})
            try(InputStream in=context.getAssets().open(name)) { copy(in,new File(backend,name)); }
        byte[] secret=new byte[32]; new SecureRandom().nextBytes(secret); token=hex(secret);
        write(new File(work,"run/api-token"),token);
        ClientTransientPaths temporary=new ClientTransientPaths(context.getFilesDir(),boundProfile,true);
        temporary.prepare();
        File tmp=temporary.tmp;
        new File(rootfs,"tmp").mkdirs(); new File(rootfs,"work").mkdirs(); new File(rootfs,"opt/trasc").mkdirs();
        // Docker's generated hosts file is absent from exported runtime archives.
        // Repair existing installations too, before any Linux process starts.
        write(new File(rootfs,"etc/hosts"),"127.0.0.1 localhost\n::1 localhost ip6-localhost ip6-loopback\n");
        write(new File(rootfs,"etc/resolv.conf"),"nameserver 1.1.1.1\nnameserver 8.8.8.8\n");
        List<String> command=new ArrayList<>(Arrays.asList(proot.getPath(),"--kill-on-exit","-0","-r",rootfs.getPath(),
            "-b","/dev","-b","/proc","-b",work.getPath()+":/work","-b",backend.getPath()+":/opt/trasc",
            "-b",tmp.getPath()+":/tmp","-w","/work","/usr/bin/env","-i","HOME=/root","USER=root",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","LANG=C.UTF-8","TMPDIR=/tmp",
            "PYTHONUNBUFFERED=1","/usr/bin/python3","/opt/trasc/engine.py","--token-file","/work/run/api-token","--profile",boundProfile));
        ProcessBuilder pb=new ProcessBuilder(command);
        pb.environment().put("PROOT_LOADER",loader.getPath());
        pb.environment().put("PROOT_TMP_DIR",tmp.getPath());
        pb.environment().put("PROOT_NO_SECCOMP","1");
        LogRetention.rotate(new File(work,"logs/runtime.log"));
        pb.redirectErrorStream(true); pb.redirectOutput(ProcessBuilder.Redirect.appendTo(new File(work,"logs/runtime.log")));
        process=pb.start(); status="Starting local control service…";
        for(int i=0;i<60;i++) {
            if(!alive()) throw new IOException("Runtime exited. Open Runtime log for the cause.");
            try { request("state",new JSONObject()); status="Runtime ready"; return; }
            catch(IOException e) {Thread.sleep(500);}
        }
        throw new IOException("Runtime did not become ready. Open Runtime log.");
    }
    JSONObject request(String op, JSONObject args) throws Exception {
        return request(op,args,120000);
    }
    JSONObject request(String op, JSONObject args,int timeout) throws Exception {
        if(token==null) throw new IOException("Open the runtime first");
        HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:18775/").openConnection();
        c.setConnectTimeout(2500); c.setReadTimeout(timeout); c.setRequestMethod("POST"); c.setDoOutput(true);
        c.setRequestProperty("Authorization","Bearer "+token); c.setRequestProperty("Content-Type","application/json");
        byte[] body=new JSONObject().put("operation",op).put("args",args).toString().getBytes(StandardCharsets.UTF_8);
        c.setFixedLengthStreamingMode(body.length);
        try {
            try(OutputStream out=c.getOutputStream()){out.write(body);}
            if(c.getResponseCode()!=200) throw new IOException("Local control service returned "+c.getResponseCode());
            try(InputStream in=c.getInputStream()){return new JSONObject(readText(in,4*1024*1024));}
        } finally {c.disconnect();}
    }
    synchronized void stop() throws Exception {
        if(!alive()) {status="Runtime stopped"; return;}
        captureFerryDiagnostics();
        status="Saving server state and stopping database…";
        try {request("exit",new JSONObject());} catch(Exception ignored) {}
        Process p=process;
        if(!p.waitFor(180,java.util.concurrent.TimeUnit.SECONDS)) {
            p.destroy(); status="Runtime forced to stop after shutdown timeout. Check logs before restarting.";
            throw new IOException(status);
        } else status="Runtime stopped";
        process=null;
    }
    JSONObject nativeState() throws Exception {
        android.content.SharedPreferences restoration=context.getSharedPreferences("session-restoration",Context.MODE_PRIVATE);
        JSONObject launcher=new JSONObject(restoration.getString("launcher_preferences","{}"));
        JSONObject marker;
        try{marker=runtimeMarker(rootfs);}catch(IOException e){marker=new JSONObject();}
        return new JSONObject().put("installed",installed()).put("alive",alive()).put("installing",installing)
            .put("session_busy",sessionBusy).put("session_cancellable",sessionBusy&&sessionCancellable)
            .put("session_phase",sessionPhase).put("session_bytes",sessionBytes).put("session_total",sessionTotal)
            .put("restored_activation",restoration.getString("activation",null)).put("launcher_preferences",launcher)
            .put("status",status).put("free_bytes",home.getUsableSpace()).put("abi",android.os.Build.SUPPORTED_ABIS[0])
            .put("profile",profiles.current()).put("profile_label",WorldProfiles.label(profiles.current()))
            .put("runtime_build_ready",buildReady(profiles.current(),marker))
            .put("runtime_version",marker.optString("runtime"))
            .put("runtime_profile",marker.optString("profile","legacy"));
    }
    JSONObject browseFiles(JSONObject args)throws Exception {
        if(recoveryError!=null)throw new IOException(recoveryError);
        Object offset=args.opt("offset"),limit=args.opt("limit"),query=args.opt("query"),path=args.opt("path");
        if(offset!=null&&!(offset instanceof Integer)||limit!=null&&!(limit instanceof Integer)
                ||query!=null&&!(query instanceof String)||path!=null&&!(path instanceof String))throw new IOException("Invalid file browser request");
        StorageFiles.Page page=StorageFiles.browse(work,args.optString("path",""),args.optString("query",""),args.optInt("offset",0),args.optInt("limit",200));
        org.json.JSONArray items=new org.json.JSONArray();
        for(StorageFiles.Entry e:page.items)items.put(new JSONObject().put("name",e.name).put("path",e.path)
            .put("directory",e.directory).put("size",e.size).put("deletable",e.deletable).put("protection",e.protection));
        return new JSONObject().put("path",page.path).put("items",items).put("total",page.total)
            .put("offset",page.offset).put("limit",page.limit).put("next_offset",page.nextOffset==null?JSONObject.NULL:page.nextOffset);
    }
    /** MainActivity owns client/runtime monitors and the exclusive profile reservation. */
    JSONObject cleanupFiles(String operation,JSONObject args)throws Exception {
        if(recoveryError!=null)throw new IOException(recoveryError);
        if(new File(home,"session-swap.properties").exists())throw new IOException("Session recovery must finish before deleting files");
        org.json.JSONArray requested=args.getJSONArray("paths");
        if(requested.length()==0||requested.length()>500)throw new IOException("Select between 1 and 500 files or folders");
        List<String> paths=new ArrayList<>();
        for(int i=0;i<requested.length();i++){Object p=requested.get(i);if(!(p instanceof String))throw new IOException("Invalid file selection");paths.add((String)p);}
        if(operation.equals("file_delete_preview")) {
            StorageFiles.Preview preview=StorageFiles.preview(work,paths);
            return new JSONObject().put("token",preview.token).put("paths",new org.json.JSONArray(preview.paths))
                .put("bytes",preview.bytes).put("files",preview.files);
        }
        StorageFiles.Result removed=StorageFiles.delete(work,paths,args.getString("token"));
        return new JSONObject().put("bytes",removed.bytes).put("files",removed.files).put("paths",new org.json.JSONArray(removed.paths))
            .put("free_bytes",home.getUsableSpace()).put("message","Deleted "+removed.paths.size()+" selected files or folders.");
    }
    synchronized JSONObject logRetention(JSONObject args)throws Exception {
        if(sessionBusy)throw new IOException("Wait for the complete session transfer");
        if(args.has("count")) {
            Object value=args.get("count");
            if(!(value instanceof Integer)||((Integer)value)<2||((Integer)value)>5)
                throw new IOException("Choose 2, 3, 4 or 5 older logs");
            LogRetention.save(work,(Integer)value);
        }
        long[] removed=args.has("count")?LogRetention.prune(work):new long[]{0,0};
        return new JSONObject().put("count",LogRetention.count(work)).put("removed_files",removed[0])
            .put("removed_bytes",removed[1]).put("message","Log retention saved. Removed "+removed[0]+" older logs; current logs are kept.");
    }
    JSONObject logs(String name)throws Exception {
        return new JSONObject().put("text",LocalLogs.tail(work,name))
            .put("names",new org.json.JSONArray(LocalLogs.inventory(work).keySet()));
    }
    synchronized JSONObject clearLogs(JSONObject args,boolean clientActive)throws Exception {
        long[] cleared=LogCleanup.clear(work,args.optString("mode"),System.currentTimeMillis(),
            alive()||installing||sessionBusy||clientActive);
        return new JSONObject().put("cleared_files",cleared[0]).put("cleared_bytes",cleared[1])
            .put("message","Reset "+cleared[0]+" diagnostic log files to 0 bytes.");
    }
    private void captureFerryDiagnostics() {
        if(!alive()||!boundProfile.equals("custom"))return;
        try {
            JSONObject snapshot=request("ferry_diagnostics",new JSONObject(),5000);
            if(!snapshot.optBoolean("ok"))throw new IOException(snapshot.optString("error"));
        }catch(Exception e){recordFailure("ferry_diagnostics",e);}
    }
    synchronized JSONObject exportLogs()throws Exception {
        if(sessionBusy)throw new IOException("Wait for the complete session transfer before exporting logs");
        try{AndroidExitDiagnostics.collect(context,work);}catch(Exception e){recordFailure("android_exit_diagnostics",e);}
        // Export still works offline. When available, refresh only the bounded
        // ferry diagnostic snapshot; no settings, credentials or API token.
        captureFerryDiagnostics();
        JSONObject metadata=new JSONObject().put("version",BuildConfig.VERSION_NAME)
            .put("created_utc",java.time.Instant.now().toString()).put("native",nativeState())
            .put("client",ClientRuntime.get(context).state())
            .put("android_sdk",android.os.Build.VERSION.SDK_INT).put("device",android.os.Build.MODEL);
        metadata.put("log_retention",LogRetention.count(work));
        File archive=LocalLogs.export(work,metadata.toString(2));
        return new JSONObject().put("file","exports/"+archive.getName());
    }
    void recordFailure(String operation,Exception error) {recordFailure(work,operation,error);}
    static void recordFailure(File work,String operation,Exception error) {
        try{LocalLogs.failure(work,operation,error);}catch(IOException ignored){android.util.Log.e("TRASC",operation+" failed",error);}
    }
    void installOnline() throws Exception {
        beginInstall();
        File cache=new File(context.getCacheDir(),profiles.current()+"/server-runtime");
        File manifest=new File(cache,"runtime-manifest.json"), archive=new File(cache,"runtime.tar.gz");
        try {
            Files.createDirectories(cache.toPath());
            String release=ServerRuntimeIdentity.release(profiles.current());
            download(release+"runtime-manifest.json",manifest);
            JSONObject m=new JSONObject(new String(Files.readAllBytes(manifest.toPath()),StandardCharsets.UTF_8));
            ServerRuntimeIdentity.validateInstall(profiles.current(),m.optInt("format"),m.optString("architecture"),
                m.optString("profile"),m.optString("runtime"),m.optInt("build_adapter"));
            String name=m.getString("file");
            if(!name.equals("runtime-arm64.tar.gz")) throw new IOException("Unexpected runtime filename");
            download(release+name,archive);
            status="Verifying runtime download…";
            if(!sha256(archive).equalsIgnoreCase(m.getString("sha256"))) throw new IOException("Runtime checksum does not match; download again");
            installArchive(archive);
        } finally {installing=false; archive.delete(); manifest.delete();}
    }
    void beginInstall() throws IOException {
        synchronized(this) {
            requireRecovered();
            if(alive() || installing || sessionBusy) throw new IOException("Stop the runtime and finish any session transfer before installing it");
            if(!Arrays.asList(android.os.Build.SUPPORTED_ABIS).contains("arm64-v8a")) throw new IOException("An ARM64 Android device is required");
            installing=true;
        }
    }
    private void awaitJob(String operation) throws Exception {
        JSONObject response=request(operation,new JSONObject());
        if(!response.getBoolean("ok"))throw new IOException(response.optString("error"));
        String id=response.getJSONObject("result").getString("id");
        for(;;) {
            if(!alive())throw new IOException("Runtime stopped while preparing the session backup");
            JSONObject state=request("state",new JSONObject());
            if(!state.getBoolean("ok"))throw new IOException(state.optString("error"));
            org.json.JSONArray jobs=state.getJSONObject("result").getJSONArray("jobs");
            for(int i=0;i<jobs.length();i++) {
                JSONObject job=jobs.getJSONObject(i);
                if(!id.equals(job.getString("id")))continue;
                if("done".equals(job.getString("status")))return;
                if("error".equals(job.getString("status")))throw new IOException(job.optString("error"));
            }
            Thread.sleep(500);
        }
    }
    synchronized JSONObject cancelSession()throws Exception {
        if(!sessionBusy||!sessionCancellable)throw new IOException("No cancellable session transfer is active");
        sessionCancelled=true;status="Cancelling session transfer…";return new JSONObject().put("cancelled",true).put("message",status);
    }
    SessionArchive.Progress sessionProgress(String phase) {
        sessionPhase=phase;return new SessionArchive.Progress(){
            public void update(String text){status=text;}
            public void bytes(long done,long total){sessionBytes=done;sessionTotal=total;}
            public void check()throws IOException {if(sessionCancelled||Thread.currentThread().isInterrupted())throw new InterruptedIOException("Session transfer cancelled; existing worlds are unchanged");}
        };
    }
    synchronized void beginSessionTransport(String phase)throws IOException {beginSession();sessionPhase=phase;}
    void endSessionTransport(){sessionCancellable=false;sessionPhase="idle";sessionBusy=false;profiles.endMaintenance();}
    private synchronized void beginSession()throws IOException {
        if(recoveryError!=null)throw new IOException(recoveryError);
        if(sessionBusy||installing||ClientRuntime.get(context).busy)throw new IOException("Wait for the current runtime, client or session operation");
        profiles.beginMaintenance();sessionBusy=true;sessionCancelled=false;sessionCancellable=true;sessionBytes=0;sessionTotal=-1;sessionPhase="preparing";
    }
    JSONObject backupSession()throws Exception {
        beginSession();
        File target=new File(work,"exports/session-"+System.currentTimeMillis()+".zip");
        try {
            ClientRuntime.get(context).stop();
            start();
            status="Stopping the server and making a database snapshot…";
            awaitJob("prepare_session_backup");
            stop();
            if(alive())throw new IOException("Runtime must be stopped before copying session files");
            target.getParentFile().mkdirs();
            SessionArchive.create(rootfs,work,target,BuildConfig.VERSION_NAME,profiles.current(),sessionProgress("archive"));
            status="Complete session ZIP ready. Runtime stopped; open runtime to continue.";
            return new JSONObject().put("file","exports/"+target.getName()).put("message","Complete session created. Save it outside the app. The runtime is stopped.");
        } catch(Exception e) {
            status="Session backup failed: "+e.getMessage()+(alive()?". See Logs for details.":". Runtime is stopped. Logs are still available; open runtime to continue.");
            recordFailure("session_backup",e);
            throw new IOException(status,e);
        } finally {sessionBusy=false;profiles.endMaintenance();}
    }
    /** This backend does not keep inactive world processes alive. Start only complete installed runtimes to checkpoint MariaDB. */
    private void quiesceAllProfiles()throws Exception {
        ClientRuntime.get(context).stop();String selected=profiles.current();boolean selectedPrepared=false;
        try {
            if(alive()) {assertNoJobs();awaitJob("prepare_session_backup");stop();selectedPrepared=true;}
            for(String id:SessionArchive.WORLDS) {
                sessionProgress("checkpoint").check();if(id.equals(selected)&&selectedPrepared)continue;
                File candidate=profiles.home(id),candidateRoot=new File(candidate,"rootfs"),candidateWork=new File(candidate,"work");
                if(!new File(candidateRoot,"etc/trasc-runtime.json").isFile()||!new File(candidateWork,"settings.json").isFile()) {
                    File database=new File(candidateWork,"database");File[] data=database.listFiles();
                    if(data!=null&&data.length>0)throw new IOException("Cannot verify the stopped database in incomplete world: "+id);
                    continue; // Partial/offline imports need no unavailable runtime launch.
                }
                bindProfile(id);status="Preparing "+WorldProfiles.label(id)+" for backup…";start();assertNoJobs();awaitJob("prepare_session_backup");stop();
                if(alive())throw new IOException("A world runtime did not stop cleanly: "+id);
            }
        } finally {
            try {if(alive())stop();}finally {
                if(!alive())bindProfile(selected);
                else {recoveryError="A world runtime failed to stop during backup. Reopen the app after checking shutdown logs.";status=recoveryError;}
            }
        }
    }
    private void assertNoJobs()throws Exception {
        if(!alive())return;
        org.json.JSONArray jobs=request("state",new JSONObject()).getJSONObject("result").getJSONArray("jobs");
        for(int i=0;i<jobs.length();i++)if(Arrays.asList("queued","running").contains(jobs.getJSONObject(i).getString("status")))throw new IOException("Finish the active operation before transferring all worlds");
    }
    private File preferencesSnapshot(JSONObject launcher)throws Exception {
        Properties props=new Properties();org.json.JSONArray controls=new org.json.JSONArray();
        for(Map.Entry<String,?> e:context.getSharedPreferences("client-controls",Context.MODE_PRIVATE).getAll().entrySet()) {
            controls.put(controlPreference(e.getKey(),e.getValue()));
        }
        props.setProperty("client_controls",controls.toString());
        String theme=launcher==null?"default":launcher.optString("theme","default");
        if(!Arrays.asList("default","necromancer","monk").contains(theme))throw new IOException("Unknown launcher appearance");
        props.setProperty("launcher_preferences",new JSONObject().put("theme",theme).toString());
        File file=File.createTempFile("session-preferences-",".properties",context.getCacheDir());
        try(FileOutputStream out=new FileOutputStream(file)){props.store(out,"Saved client controls and launcher appearance");out.getFD().sync();}
        try{checkedPreferences(file);return file;}catch(Exception e){file.delete();throw e;}
    }
    private JSONObject controlPreference(String key,Object value)throws Exception {
        String type=value instanceof Boolean?"boolean":value instanceof Float?"float":value instanceof Integer?"int":value instanceof Long?"long":value instanceof String?"string":"unsupported";
        if(type.equals("unsupported"))throw new IOException("Unsupported saved client control preference");return new JSONObject().put("key",key).put("type",type).put("value",value);
    }
    private void preserveOmittedControls(Properties preferences,Properties manifest)throws Exception {
        List<String> preserved=new ArrayList<>();for(String id:SessionArchive.WORLDS)if(!"true".equals(manifest.getProperty(id+".work")))preserved.add(id);
        Map<String,JSONObject> archived=new LinkedHashMap<>(),current=new LinkedHashMap<>();org.json.JSONArray values=new org.json.JSONArray(preferences.getProperty("client_controls"));
        for(int i=0;i<values.length();i++){JSONObject item=values.getJSONObject(i);archived.put(item.getString("key"),item);}
        for(Map.Entry<String,?> e:context.getSharedPreferences("client-controls",Context.MODE_PRIVATE).getAll().entrySet())current.put(e.getKey(),controlPreference(e.getKey(),e.getValue()));
        org.json.JSONArray merged=new org.json.JSONArray();for(JSONObject item:SessionPreferences.merge(archived,current,preserved).values())merged.put(item);preferences.setProperty("client_controls",merged.toString());
    }
    private Properties checkedPreferences(File file)throws Exception {
        if(!Files.isRegularFile(file.toPath(),java.nio.file.LinkOption.NOFOLLOW_LINKS)||file.length()>131072)throw new IOException("Invalid all-world device settings");
        Properties p=new Properties();try(InputStream in=new FileInputStream(file)){p.load(in);}
        org.json.JSONArray values=new org.json.JSONArray(p.getProperty("client_controls","[]"));if(values.length()>1000)throw new IOException("Too many control preferences");
        Set<String> keys=new HashSet<>();
        for(int i=0;i<values.length();i++) {
            JSONObject item=values.getJSONObject(i);String key=item.getString("key"),type=item.getString("type");
            if(key.length()>200||!keys.add(key)||!Arrays.asList("boolean","float","int","long","string").contains(type))throw new IOException("Invalid control preference");
            if(type.equals("boolean"))item.getBoolean("value");else if(type.equals("float")){if(!Double.isFinite(item.getDouble("value"))||!Float.isFinite((float)item.getDouble("value")))throw new IOException("Invalid control coordinate");}
            else if(type.equals("int"))item.getInt("value");else if(type.equals("long"))item.getLong("value");else if(item.getString("value").length()>8192)throw new IOException("Invalid control preference value");
        }
        JSONObject launcher=new JSONObject(p.getProperty("launcher_preferences","{}"));
        if(!Arrays.asList("default","necromancer","monk").contains(launcher.getString("theme")))throw new IOException("Invalid launcher appearance");return p;
    }
    private JSONObject applyAllPreferences()throws IOException {
        File file=new File(context.getFilesDir(),"session-preferences.properties");if(!file.isFile())return null;
        try {
            Properties p=checkedPreferences(file);String activation=p.getProperty("activation","");
            android.content.SharedPreferences receipts=context.getSharedPreferences("session-restoration",Context.MODE_PRIVATE);
            if(!activation.equals(receipts.getString("activation",null))) {
                android.content.SharedPreferences.Editor edit=context.getSharedPreferences("client-controls",Context.MODE_PRIVATE).edit().clear();
                org.json.JSONArray values=new org.json.JSONArray(p.getProperty("client_controls"));
                for(int i=0;i<values.length();i++){JSONObject v=values.getJSONObject(i);String key=v.getString("key");switch(v.getString("type")) {
                    case "boolean":edit.putBoolean(key,v.getBoolean("value"));break;case "float":edit.putFloat(key,(float)v.getDouble("value"));break;
                    case "int":edit.putInt(key,v.getInt("value"));break;case "long":edit.putLong(key,v.getLong("value"));break;case "string":edit.putString(key,v.getString("value"));break;
                }}
                if(!edit.commit()||!receipts.edit().putString("activation",activation).putString("launcher_preferences",p.getProperty("launcher_preferences")).commit())throw new IOException("Could not apply restored device settings");
            }
            return new JSONObject(p.getProperty("launcher_preferences"));
        } catch(Exception e){throw new IOException("Cannot recover restored device settings",e);}
    }
    JSONObject backupAllSessions(JSONObject launcher,OutputStream output)throws Exception {
        boolean own=!sessionBusy;if(own)beginSession();String selected=profiles.current();File prefs=null;
        File target=output==null?new File(work,"exports/all-worlds-"+System.currentTimeMillis()+".zip"):new File(context.getCacheDir(),"all-world-stream.zip");
        try {
            quiesceAllProfiles();prefs=preferencesSnapshot(launcher);SessionArchive.Progress progress=sessionProgress("archive");
            SessionArchive.createAll(context.getFilesDir(),target,BuildConfig.VERSION_NAME,selected,prefs,progress,output);
            status="All three worlds backed up. Client and server runtimes are stopped.";
            JSONObject result=new JSONObject().put("message",status).put("profiles",new org.json.JSONArray(SessionArchive.WORLDS));
            if(output==null)result.put("file","exports/"+target.getName());return result;
        } catch(Exception e){if(output==null)target.delete();recordFailure("session_backup_all",e);throw e;}
        finally {if(prefs!=null)prefs.delete();if(own)endSessionTransport();}
    }
    private boolean stagedConfiguration(File world,String relative)throws IOException {
        java.nio.file.Path root=world.toPath(),target=SessionArchive.confined(root,relative),current=root;
        for(java.nio.file.Path part:root.relativize(target)) {
            current=current.resolve(part);if(Files.isSymbolicLink(current))throw new IOException("Restored configuration cannot contain symbolic links: "+relative);
            if(!current.equals(target)&&Files.exists(current,java.nio.file.LinkOption.NOFOLLOW_LINKS)&&!Files.isDirectory(current,java.nio.file.LinkOption.NOFOLLOW_LINKS))throw new IOException("Invalid configuration directory: "+relative);
        }
        if(!Files.exists(target,java.nio.file.LinkOption.NOFOLLOW_LINKS))return false;
        if(!Files.isRegularFile(target,java.nio.file.LinkOption.NOFOLLOW_LINKS))throw new IOException("Configuration must be a regular file: "+relative);return true;
    }
    private void validateStagedWorld(File world,String id)throws Exception {
        File settingsFile=new File(world,"work/settings.json");
        if(stagedConfiguration(world,"rootfs/etc/trasc-runtime.json")) {
            JSONObject marker=runtimeMarker(new File(world,"rootfs"));
            ServerRuntimeIdentity.validateSession(id,marker.optInt("format"),marker.optString("architecture"),marker.optString("profile"),marker.optString("runtime"),marker.optInt("build_adapter"));
        }
        if(stagedConfiguration(world,"work/settings.json")) {
            if(!Files.isRegularFile(settingsFile.toPath(),java.nio.file.LinkOption.NOFOLLOW_LINKS)||settingsFile.length()>131072)throw new IOException("Invalid "+id+" settings");
            JSONObject settings=new JSONObject(new String(Files.readAllBytes(settingsFile.toPath()),StandardCharsets.UTF_8));
            if(!id.equals(settings.optString("profile","custom"))||!settings.getString("database").matches("[A-Za-z0-9_]+"))throw new IOException("World settings do not match "+id);
            for(String key:new String[]{"db_password","root_password"})if(!settings.getString(key).matches("[0-9a-f]{40}"))throw new IOException("Invalid database credentials in "+id);
            settings.put("bot_database_epoch",java.util.UUID.randomUUID().toString().replace("-",""));
            int settingsMode=SessionArchive.mode(settingsFile.toPath());File temp=new File(settingsFile.getParentFile(),"settings.session-new");
            try{try(FileOutputStream out=new FileOutputStream(temp)){out.write(settings.toString(2).getBytes(StandardCharsets.UTF_8));out.getFD().sync();}
                SessionArchive.chmod(temp.toPath(),settingsMode);Files.move(temp.toPath(),settingsFile.toPath(),java.nio.file.StandardCopyOption.ATOMIC_MOVE,java.nio.file.StandardCopyOption.REPLACE_EXISTING);AllProfileSwap.syncDirectory(settingsFile.getParentFile());
            }finally{Files.deleteIfExists(temp.toPath());}
        }
    }
    JSONObject restoreAllSessions(File archive,boolean replace)throws Exception {
        boolean own=!sessionBusy;if(own)beginSession();File staging=new File(context.getFilesDir(),"all-session-stage");
        String previous=profiles.current();boolean activated=false;
        try {
            Properties header=SessionArchive.readManifest(archive);if(!SessionArchive.allProfiles(header))throw new IOException("Choose an all-world backup, or use selected-world restore for older backups");
            SessionArchive.archiveProfiles(header);ClientRuntime.get(context).stop();assertNoJobs();
            if(alive()){awaitJob("prepare_session_backup");stop();}
            SessionArchive.removeTree(staging);Files.createDirectories(staging.toPath());
            Properties manifest=SessionArchive.restore(archive,staging,sessionProgress("verify"));
            for(String id:SessionArchive.WORLDS)validateStagedWorld(new File(staging,"worlds/"+id),id);
            File preferences=new File(staging,"global/preferences.properties");Properties prefs=checkedPreferences(preferences);preserveOmittedControls(prefs,manifest);prefs.setProperty("activation",java.util.UUID.randomUUID().toString());
            try(FileOutputStream out=new FileOutputStream(preferences)){prefs.store(out,"Restored device settings");out.getFD().sync();}
            checkedPreferences(preferences);
            SessionArchive.syncDirectories(staging,sessionProgress("verify"));sessionProgress("verify").check();sessionCancellable=false;sessionPhase="activate";status="Activating verified worlds…";
            String recoveryCopy=AllProfileSwap.activate(context.getFilesDir(),staging,manifest.getProperty("selected_profile"),replace,SessionArchive.includedComponents(manifest));activated=true;
            profiles.reload();bindProfile(profiles.current());ClientRuntime.get(context).bindProfile(profiles.current());JSONObject launcher=applyAllPreferences();
            status="All worlds restored. Open the runtime, review login IP, then start the server.";
            return new JSONObject().put("message",status).put("source_version",manifest.getProperty("app_version")).put("active_profile",profiles.current()).put("launcher_preferences",launcher)
                .put("restored_activation",context.getSharedPreferences("session-restoration",Context.MODE_PRIVATE).getString("activation",null)).put("recovery_copy",recoveryCopy);
        } catch(Exception e) {
            if(activated){recoveryError="All worlds are restored; device settings recovery is pending. Force-stop and reopen the app to retry before starting a runtime.";sessionRecoveryError=recoveryError;status=recoveryError;throw new IOException(recoveryError,e);}
            if(AllProfileSwap.pending(context.getFilesDir())){sessionRecoveryError="Interrupted all-world restore requires force-stopping and reopening the app for recovery.";recoveryError=sessionRecoveryError;status=sessionRecoveryError;}
            throw e;
        } finally {
            if(!activated){profiles.reload();if(!alive())bindProfile(previous);}
            try{SessionArchive.removeTree(staging);}finally{if(own)endSessionTransport();}
        }
    }
    private File sessionJournal(){return new File(home,"session-swap.properties");}
    private void recoverSessionSwap()throws IOException {
        File journal=sessionJournal();if(!journal.isFile())return;
        Properties info=new Properties();try(InputStream in=new FileInputStream(journal)){info.load(in);}
        for(String name:new String[]{"rootfs","work"}) {
            File live=new File(home,name),previous=new File(home,name+"-session-previous");
            if(previous.exists()) {
                TarExtractor.remove(live);
                if(!previous.renameTo(live))throw new IOException("Could not recover previous "+name);
            } else if(!Boolean.parseBoolean(info.getProperty(name)))TarExtractor.remove(live);
        }
        if(!journal.delete())throw new IOException("Could not finish session recovery");
        status="Recovered the previous session after an interrupted restore.";
    }
    JSONObject restoreSession(File archive,boolean replace)throws Exception {
        beginSession();
        File staging=new File(home,"session-stage");
        try {
            SessionArchive.requireProfile(archive,profiles.current());
            if((installed()||new File(work,"settings.json").isFile())&&!replace)
                throw new IOException("Select Replace this app's current session before restoring");
            ClientRuntime.get(context).stop();
            if(alive()) {
                JSONObject s=request("state",new JSONObject()).getJSONObject("result");
                org.json.JSONArray jobs=s.getJSONArray("jobs");
                for(int i=0;i<jobs.length();i++)if(Arrays.asList("running","queued").contains(jobs.getJSONObject(i).getString("status")))
                    throw new IOException("Finish the active operation before restoring a session");
                status="Stopping the current session cleanly…";
                awaitJob("prepare_session_backup");
                stop();
            }
            TarExtractor.remove(staging);staging.mkdirs();
            status="Checking complete session ZIP…";
            Properties manifest=SessionArchive.restore(archive,staging,sessionProgress("verify"));
            for(String path:new String[]{"rootfs/etc/trasc-runtime.json","work/settings.json"})
                if(new File(staging,path).length()>131072)throw new IOException("Session configuration exceeds supported size");
            JSONObject marker=new JSONObject(new String(Files.readAllBytes(new File(staging,"rootfs/etc/trasc-runtime.json").toPath()),StandardCharsets.UTF_8));
            ServerRuntimeIdentity.validateSession(profiles.current(),marker.optInt("format"),marker.optString("architecture"),
                marker.optString("profile"),marker.optString("runtime"),marker.optInt("build_adapter"));
            JSONObject settings=new JSONObject(new String(Files.readAllBytes(new File(staging,"work/settings.json").toPath()),StandardCharsets.UTF_8));
            if(!settings.optString("profile","custom").equals(profiles.current()))throw new IOException("Session settings belong to a different world profile");
            if(!settings.getString("database").matches("[A-Za-z0-9_]+"))throw new IOException("Invalid database name in session");
            for(String key:new String[]{"db_password","root_password"})if(!settings.getString(key).matches("[0-9a-f]{40}"))throw new IOException("Invalid database credentials in session");
            // A restored database is a new owner/roster snapshot. Old previews
            // and idempotency tokens must not target it even when IDs repeat.
            settings.put("bot_database_epoch",java.util.UUID.randomUUID().toString().replace("-",""));
            write(new File(staging,"work/settings.json"),settings.toString(2));
            sessionProgress("verify").check();sessionCancellable=false;sessionPhase="activate";
            Properties journal=new Properties();
            for(String name:new String[]{"rootfs","work"}) {
                journal.setProperty(name,String.valueOf(new File(home,name).exists()));
                TarExtractor.remove(new File(home,name+"-session-previous"));
            }
            try(FileOutputStream out=new FileOutputStream(sessionJournal())){journal.store(out,"Rollback an interrupted session activation");out.getFD().sync();}
            try {
                for(String name:new String[]{"rootfs","work"}) {
                    File live=new File(home,name),previous=new File(home,name+"-session-previous"),next=new File(staging,name);
                    if(live.exists()&&!live.renameTo(previous))throw new IOException("Cannot preserve previous "+name);
                    if(!next.renameTo(live))throw new IOException("Cannot activate restored "+name);
                }
                if(!sessionJournal().delete())throw new IOException("Cannot finish session activation");
            } catch(Exception e){recoverSessionSwap();throw e;}
            token=null;
            status="Complete session restored. Open runtime, review the login IP, then start the server.";
            return new JSONObject().put("message",status).put("source_version",manifest.getProperty("app_version"));
        } finally {try{TarExtractor.remove(staging);}finally{sessionBusy=false;profiles.endMaintenance();}}
    }
    void installArchive(File archive) throws Exception {
        File staging=new File(home,"rootfs-install"), previous=new File(home,"rootfs-previous");
        TarExtractor.remove(staging); staging.mkdirs();
        try {
            status="Unpacking runtime…";
            TarExtractor.extract(archive,staging,(n)->status="Unpacking runtime · "+n+" files");
            JSONObject marker=runtimeMarker(staging);
            ServerRuntimeIdentity.validateInstall(profiles.current(),marker.optInt("format"),marker.optString("architecture"),
                marker.optString("profile"),marker.optString("runtime"),marker.optInt("build_adapter"));
            for(String needed:new String[]{"usr/bin/python3.11","usr/sbin/mariadbd","usr/bin/cmake","usr/bin/git","usr/bin/g++"})
                if(!new File(staging,needed).exists()) throw new IOException("Runtime is incomplete: "+needed);
            if(!"custom".equals(profiles.current()))
                for(String needed:new String[]{"usr/bin/ninja","usr/bin/pkg-config","usr/bin/openssl","usr/bin/luajit","usr/bin/readelf","usr/lib/aarch64-linux-gnu/ossl-modules/legacy.so"})
                    if(!new File(staging,needed).isFile())throw new IOException(WorldProfiles.label(profiles.current())+" runtime is incomplete: "+needed);
            if(ServerRuntimeIdentity.reusableTakpImage(profiles.current(),marker.optInt("format"),marker.optString("architecture"),
                    marker.optString("profile"),marker.optString("runtime"),marker.optInt("build_adapter"))) {
                marker.put("source_profile",marker.getString("profile")).put("source_runtime",marker.getString("runtime"))
                    .put("profile","takp").put("runtime",ServerRuntimeIdentity.TAKP_VERSION);
                write(new File(staging,"etc/trasc-runtime.json"),marker.toString(2)+"\n");
            }
            TarExtractor.remove(previous);
            if(rootfs.exists() && !rootfs.renameTo(previous)) throw new IOException("Could not preserve previous runtime");
            if(!staging.renameTo(rootfs)) {previous.renameTo(rootfs); throw new IOException("Could not activate runtime");}
            TarExtractor.remove(previous); status="Runtime installed. Open runtime to continue.";
        } finally {TarExtractor.remove(staging);}
    }
    void download(String url,File target) throws Exception {
        download(url,target,text->status=text);
    }
    void download(String url,File target,SessionArchive.Progress progress) throws Exception {
        URL u=new URL(url); HttpURLConnection c=null;
        for(int redirect=0;redirect<6;redirect++) {
            if(!u.getProtocol().equals("https")) throw new IOException("HTTPS is required");
            c=(HttpURLConnection)u.openConnection(); c.setConnectTimeout(30000); c.setReadTimeout(60000);
            c.setInstanceFollowRedirects(false); c.setRequestProperty("User-Agent","TRASC-Server/0.1");
            int code=c.getResponseCode();
            if(code>=300 && code<400) {String location=c.getHeaderField("Location"); c.disconnect(); u=new URL(u,location); continue;}
            if(code!=200) {c.disconnect(); throw new IOException("Download returned HTTP "+code+". Use the matching offline runtime archive if unavailable.");}
            long size=c.getContentLengthLong(), done=0;
            if(size>home.getUsableSpace()-512L*1024*1024) {c.disconnect(); throw new IOException("Not enough storage for download");}
            try(InputStream in=c.getInputStream(); OutputStream out=new FileOutputStream(target)) {
                byte[] b=new byte[1024*1024]; int n;
                while((n=in.read(b))!=-1) {done+=n; if(done>4L*1024*1024*1024) throw new IOException("Runtime archive is too large"); out.write(b,0,n); progress.update("Downloading runtime · "+(done/1048576)+" MB");}
            } finally {c.disconnect();}
            return;
        }
        throw new IOException("Too many download redirects");
    }
    static String sha256(File file) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=new FileInputStream(file)){byte[] b=new byte[1024*1024]; int n; while((n=in.read(b))!=-1)digest.update(b,0,n);}
        return hex(digest.digest());
    }
    static String hex(byte[] bytes) {StringBuilder b=new StringBuilder(); for(byte x:bytes)b.append(String.format(Locale.ROOT,"%02x",x&255)); return b.toString();}
    static void write(File file,String text) throws IOException {file.getParentFile().mkdirs(); try(OutputStream out=new FileOutputStream(file)){out.write(text.getBytes(StandardCharsets.UTF_8));}}
    static void copy(InputStream in,File file) throws IOException {
        file.getParentFile().mkdirs();
        try(OutputStream out=new FileOutputStream(file)){byte[] b=new byte[1024*1024]; int n; while((n=in.read(b))!=-1){if(file.getParentFile().getUsableSpace()<n+67108864L)throw new IOException("Storage is full"); out.write(b,0,n);}}
    }
    static String readText(InputStream in,int limit) throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream(); byte[] b=new byte[8192]; int n;
        while((n=in.read(b))!=-1){if(out.size()+n>limit)throw new IOException("Response is too large");out.write(b,0,n);}
        return out.toString("UTF-8");
    }
}
