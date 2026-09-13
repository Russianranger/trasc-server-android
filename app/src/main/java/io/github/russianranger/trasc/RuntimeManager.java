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
    final File home, work, rootfs;
    volatile String status = "Install the runtime to begin.";
    volatile boolean installing;
    private volatile Process process;
    private String token;
    static final String RELEASE = "https://github.com/Russianranger/trasc-server-android/releases/download/runtime-v1/";

    private RuntimeManager(Context c) {
        context=c; home=c.getFilesDir(); work=new File(home,"work"); rootfs=new File(home,"rootfs");
        new File(work,"incoming").mkdirs(); new File(work,"logs").mkdirs(); new File(work,"run").mkdirs();
    }
    boolean installed() { return new File(rootfs,"etc/trasc-runtime.json").isFile(); }
    boolean alive() { return process!=null && process.isAlive(); }
    synchronized void start() throws Exception {
        if (alive()) return;
        if (installing) throw new IOException("Runtime installation is in progress");
        if (!installed()) {status="Install the runtime to begin."; return;}
        File nativeDir=new File(context.getApplicationInfo().nativeLibraryDir);
        File proot=new File(nativeDir,"libproot.so"), loader=new File(nativeDir,"libproot-loader.so");
        if (!proot.canExecute() || !loader.exists()) throw new IOException("This APK is missing its ARM64 runtime launcher");
        File backend=new File(home,"backend"); backend.mkdirs();
        try(InputStream in=context.getAssets().open("engine.py")) { copy(in,new File(backend,"engine.py")); }
        byte[] secret=new byte[32]; new SecureRandom().nextBytes(secret); token=hex(secret);
        write(new File(work,"run/api-token"),token);
        File tmp=new File(home,"tmp"); tmp.mkdirs();
        new File(rootfs,"tmp").mkdirs(); new File(rootfs,"work").mkdirs(); new File(rootfs,"opt/trasc").mkdirs();
        // Docker's generated hosts file is absent from exported runtime archives.
        // Repair existing installations too, before any Linux process starts.
        write(new File(rootfs,"etc/hosts"),"127.0.0.1 localhost\n::1 localhost ip6-localhost ip6-loopback\n");
        write(new File(rootfs,"etc/resolv.conf"),"nameserver 1.1.1.1\nnameserver 8.8.8.8\n");
        List<String> command=new ArrayList<>(Arrays.asList(proot.getPath(),"--kill-on-exit","-0","-r",rootfs.getPath(),
            "-b","/dev","-b","/proc","-b",work.getPath()+":/work","-b",backend.getPath()+":/opt/trasc",
            "-b",tmp.getPath()+":/tmp","-w","/work","/usr/bin/env","-i","HOME=/root","USER=root",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","LANG=C.UTF-8","TMPDIR=/tmp",
            "PYTHONUNBUFFERED=1","/usr/bin/python3","/opt/trasc/engine.py","--token-file","/work/run/api-token"));
        ProcessBuilder pb=new ProcessBuilder(command);
        pb.environment().put("PROOT_LOADER",loader.getPath());
        pb.environment().put("PROOT_TMP_DIR",tmp.getPath());
        pb.environment().put("PROOT_NO_SECCOMP","1");
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
        if(token==null) throw new IOException("Open the runtime first");
        HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:18775/").openConnection();
        c.setConnectTimeout(2500); c.setReadTimeout(120000); c.setRequestMethod("POST"); c.setDoOutput(true);
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
        status="Saving server state and stopping database…";
        try {request("exit",new JSONObject());} catch(Exception ignored) {}
        Process p=process;
        if(!p.waitFor(180,java.util.concurrent.TimeUnit.SECONDS)) {
            p.destroy(); status="Runtime forced to stop after shutdown timeout. Check logs before restarting.";
        } else status="Runtime stopped";
        process=null;
    }
    JSONObject nativeState() throws Exception {
        return new JSONObject().put("installed",installed()).put("alive",alive()).put("installing",installing)
            .put("status",status).put("free_bytes",home.getUsableSpace()).put("abi",android.os.Build.SUPPORTED_ABIS[0]);
    }
    void installOnline() throws Exception {
        File manifest=new File(context.getCacheDir(),"runtime-manifest.json"), archive=new File(context.getCacheDir(),"runtime.tar.gz");
        beginInstall();
        try {
            download(RELEASE+"runtime-manifest.json",manifest);
            JSONObject m=new JSONObject(new String(Files.readAllBytes(manifest.toPath()),StandardCharsets.UTF_8));
            if(!m.getString("architecture").equals("arm64") || m.getInt("format")!=1) throw new IOException("Unsupported runtime manifest");
            String name=m.getString("file");
            if(!name.equals("runtime-arm64.tar.gz")) throw new IOException("Unexpected runtime filename");
            download(RELEASE+name,archive);
            status="Verifying runtime download…";
            if(!sha256(archive).equalsIgnoreCase(m.getString("sha256"))) throw new IOException("Runtime checksum does not match; download again");
            installArchive(archive);
        } finally {installing=false; archive.delete(); manifest.delete();}
    }
    void beginInstall() throws IOException {
        synchronized(this) {
            if(alive() || installing) throw new IOException("Stop the runtime before installing it");
            if(!Arrays.asList(android.os.Build.SUPPORTED_ABIS).contains("arm64-v8a")) throw new IOException("An ARM64 Android device is required");
            installing=true;
        }
    }
    void installArchive(File archive) throws Exception {
        File staging=new File(home,"rootfs-install"), previous=new File(home,"rootfs-previous");
        TarExtractor.remove(staging); staging.mkdirs();
        try {
            status="Unpacking runtime…";
            TarExtractor.extract(archive,staging,(n)->status="Unpacking runtime · "+n+" files");
            JSONObject marker=new JSONObject(new String(Files.readAllBytes(new File(staging,"etc/trasc-runtime.json").toPath()),StandardCharsets.UTF_8));
            if(marker.getInt("format")!=1 || !marker.getString("architecture").equals("arm64")) throw new IOException("This is not a TRASC ARM64 runtime archive");
            for(String needed:new String[]{"usr/bin/python3.11","usr/sbin/mariadbd","usr/bin/cmake","usr/bin/git","usr/bin/g++"})
                if(!new File(staging,needed).exists()) throw new IOException("Runtime is incomplete: "+needed);
            TarExtractor.remove(previous);
            if(rootfs.exists() && !rootfs.renameTo(previous)) throw new IOException("Could not preserve previous runtime");
            if(!staging.renameTo(rootfs)) {previous.renameTo(rootfs); throw new IOException("Could not activate runtime");}
            TarExtractor.remove(previous); status="Runtime installed. Open runtime to continue.";
        } finally {TarExtractor.remove(staging);}
    }
    void download(String url,File target) throws Exception {
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
                while((n=in.read(b))!=-1) {done+=n; if(done>4L*1024*1024*1024) throw new IOException("Runtime archive is too large"); out.write(b,0,n); status="Downloading runtime · "+(done/1048576)+" MB";}
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
