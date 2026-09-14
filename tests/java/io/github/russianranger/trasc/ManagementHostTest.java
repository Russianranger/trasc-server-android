package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

public final class ManagementHostTest {
    static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    static void write(Path root,String path,String value)throws IOException {Path p=root.resolve(path);Files.createDirectories(p.getParent());Files.writeString(p,value);}
    static void rewriteZip(File src,File target,String change,String value)throws IOException {
        try(ZipFile in=new ZipFile(src);ZipOutputStream out=new ZipOutputStream(new FileOutputStream(target))) {
            Enumeration<? extends ZipEntry> entries=in.entries();
            while(entries.hasMoreElements()) {
                ZipEntry e=entries.nextElement();out.putNextEntry(new ZipEntry(e.getName()));
                if(e.getName().equals(change))out.write(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                else try(InputStream stream=in.getInputStream(e)){stream.transferTo(out);}
                out.closeEntry();
            }
        }
    }
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("trasc-session-test-");
        try {
            Path runtime=tmp.resolve("rootfs"),work=tmp.resolve("work");
            write(runtime,"etc/trasc-runtime.json","{\"format\":1,\"architecture\":\"arm64\"}");
            write(runtime,"usr/bin/test","runtime binary");SessionArchive.chmod(runtime.resolve("usr/bin/test"),0755);
            String multiarch="var/lib/dpkg/info/binutils-common:arm64.conffiles";
            write(runtime,multiarch,"/etc/test.conf\n");
            write(runtime,"var/lib/dpkg/info/libc6:arm64.list","/usr/lib/aarch64-linux-gnu/libc.so.6\n");
            write(work,"logs/2026-09-13T15:16:00.log","timestamp filename");
            Files.createSymbolicLink(runtime.resolve("bin"),Paths.get("usr/bin"));
            write(work,"settings.json","{\"test\":true}");SessionArchive.chmod(work.resolve("settings.json"),0600);
            write(work,"server/bin/world","binary");SessionArchive.chmod(work.resolve("server/bin/world"),0755);
            write(work,"database/triune/test.ibd","world data");write(work,"maps/base/nektulos.map","map data");
            write(work,"backups/database.sql.gz","snapshot");write(work,"logs/control.log","log");write(work,"server/logs/world.log","world log");
            write(work,"client/current/eqgame.exe","MZclient");write(work,"client/controller.json","bindings");
            write(work,"client/runtime/etc/trasc-client-runtime.json","client runtime");
            write(work,"client/prefix/drive_c/user.reg","Wine settings");
            Files.createDirectories(work.resolve("client/prefix/dosdevices"));Files.createSymbolicLink(work.resolve("client/prefix/dosdevices/d:"),Paths.get("/client"));
            write(work,"sources/current/file.cpp","source");write(work,"builds/current/cache","build cache");
            write(work,"run/api-token","do not archive");write(work,"incoming/source.zip","temporary");write(work,"exports/old.zip","do not recurse");
            Files.createSymbolicLink(work.resolve("server/maps"),Paths.get("/work/maps"));
            File archive=tmp.resolve("session.zip").toFile();SessionArchive.create(runtime.toFile(),work.toFile(),archive,"test",s->{});
            try(ZipFile z=new ZipFile(archive)) {
                check(z.getEntry("binaries/current/world")!=null,"Binaries must have a separate component");
                check(z.getEntry("database/triune/test.ibd")!=null,"Physical DB included");
                check(z.stream().noneMatch(e->e.getName().contains("api-token")||e.getName().contains("old.zip")||e.getName().contains("temporary")),"No temporary process/export data");
            }
            Path restored=tmp.resolve("restored");SessionArchive.restore(archive,restored.toFile(),s->{});
            check(Files.readString(restored.resolve("work/database/triune/test.ibd")).equals("world data"),"Database roundtrip");
            check(SessionArchive.mode(restored.resolve("work/server/bin/world"))==0755,"Executable permissions preserved");
            check(SessionArchive.mode(restored.resolve("work/settings.json"))==0600,"Credential permissions preserved");
            check(Files.readSymbolicLink(restored.resolve("rootfs/bin")).toString().equals("usr/bin"),"Runtime symlink preserved");
            check(Files.readSymbolicLink(restored.resolve("work/server/maps")).toString().equals("/work/maps"),"Guest absolute symlink preserved");
            check(Files.isDirectory(restored.resolve("work/run")),"Fresh process directory created");
            check(Files.readString(restored.resolve("work/client/runtime/etc/trasc-client-runtime.json")).equals("client runtime"),"Embedded client runtime included");
            check(Files.readSymbolicLink(restored.resolve("work/client/prefix/dosdevices/d:")).toString().equals("/client"),"Wine drive symlink roundtrip");
            check(Files.readString(restored.resolve("rootfs/"+multiarch)).equals("/etc/test.conf\n"),"Exact reported Debian multiarch filename must roundtrip");
            check(Files.readString(restored.resolve("work/logs/2026-09-13T15:16:00.log")).equals("timestamp filename"),"Linux colon filenames must roundtrip in other components too");
            for(String unsafe:new String[]{"/absolute","C:/Windows/file","c:relative","runtime/../escape","runtime//file","runtime/./file","runtime/back\\slash","runtime/nul\0file"}) {
                try{SessionArchive.confined(tmp,unsafe);throw new AssertionError("Unsafe path accepted: "+unsafe);}catch(IOException expected){}
            }
            File corrupt=tmp.resolve("corrupt.zip").toFile();rewriteZip(archive,corrupt,"maps/base/nektulos.map","bad data");
            try{SessionArchive.restore(corrupt,tmp.resolve("bad").toFile(),s->{});throw new AssertionError("Corrupt file accepted");}catch(IOException expected){check(expected.getMessage().contains("checksum"),"Corruption must be detected by hash");}
            String index;try(ZipFile z=new ZipFile(archive);InputStream in=z.getInputStream(z.getEntry(SessionArchive.INDEX))){index=new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);}
            File traversal=tmp.resolve("traversal.zip").toFile();rewriteZip(archive,traversal,SessionArchive.INDEX,index.replace(SessionArchive.encode("maps/base/nektulos.map"),SessionArchive.encode("../escaped")));
            try{SessionArchive.restore(traversal,tmp.resolve("attack").toFile(),s->{});throw new AssertionError("Traversal accepted");}catch(IOException expected){}
            check(!Files.exists(tmp.resolve("escaped")),"Traversal wrote outside staging");
            String conflicting=index+"F\t420\t0\t"+"0".repeat(64)+"\t"+SessionArchive.encode("server/maps/escape")+"\t\n";
            File links=tmp.resolve("link-attack.zip").toFile();rewriteZip(archive,links,SessionArchive.INDEX,conflicting);
            try{SessionArchive.restore(links,tmp.resolve("links").toFile(),s->{});throw new AssertionError("Link-child attack accepted");}catch(IOException expected){}
            // No Python server/process exists in this test: diagnostics must be fully native.
            LocalLogs.failure(work.toFile(),"session_backup",new IOException("simulated archive failure"));
            write(work,"logs/operation.log","x".repeat(100000)+"LATEST");
            write(work,"logs/runtime.log","runtime stopped");
            write(work,"server/logs/zones/cabeast.log","nested zone log");
            write(work,"client/current/DINPUT8.log","system DirectInput load failed");
            write(work,"client/current/Logs/dbg.txt","game initialization failed");
            write(work,"client/current/logs/UIErrors.txt","UI diagnostic");
            write(work,"client/current/eqclient.ini","saved client settings");
            write(work,"client/current/Logs/eqlog_character.txt","private chat");
            write(tmp,"outside/secret.log","do not export");
            Files.createSymbolicLink(work.resolve("logs/secret.log"),tmp.resolve("outside/secret.log"));
            Files.createSymbolicLink(work.resolve("logs/linked-directory"),tmp.resolve("outside"));
            Files.createSymbolicLink(work.resolve("client/current/Logs/crash.log"),tmp.resolve("outside/secret.log"));
            check(LocalLogs.tail(work.toFile(),"app.log").contains("simulated archive failure"),"Native backup error is readable after runtime failure");
            String tail=LocalLogs.tail(work.toFile(),"operation.log");
            check(tail.length()==LocalLogs.TAIL_BYTES&&tail.endsWith("LATEST"),"Log viewer returns bounded latest output");
            check(LocalLogs.tail(work.toFile(),"server/zones/cabeast.log").equals("nested zone log"),"Nested server logs readable");
            check(LocalLogs.tail(work.toFile(),"client/Logs/dbg.txt").equals("game initialization failed"),"Game startup log readable without runtime");
            check(LocalLogs.tail(work.toFile(),"client/DINPUT8.log").contains("DirectInput"),"Proxy log readable with original filename case");
            check(LocalLogs.tail(work.toFile(),"missing.log").equals("No log output yet."),"Missing log is not a connection failure");
            Map<String,Path> names=LocalLogs.inventory(work.toFile());
            check(names.containsKey("app.log")&&names.containsKey("server/zones/cabeast.log"),"Native inventory includes app and nested server logs");
            check(names.containsKey("client/DINPUT8.log")&&names.containsKey("client/Logs/dbg.txt")&&names.containsKey("client/logs/UIErrors.txt"),"Native inventory includes client startup logs with either directory case");
            check(!names.containsKey("client/eqclient.ini")&&!names.containsKey("client/eqgame.exe")&&!names.containsKey("client/Logs/eqlog_character.txt")&&!names.containsKey("client/Logs/crash.log"),"Client inventory excludes settings, binaries, chat and symlinks");
            check(!names.containsKey("secret.log")&&!names.containsKey("linked-directory/secret.log"),"Inventory never follows symlinks");
            for(String unsafe:new String[]{"../settings.json","server/../../settings.json","secret.log","linked-directory/secret.log","client/../settings.json","client/eqclient.ini","client/Logs/../../settings.json","client/Logs/crash.log","client/Logs/eqlog_character.txt"}) {
                try{LocalLogs.tail(work.toFile(),unsafe);throw new AssertionError("Unsafe log read accepted: "+unsafe);}catch(IOException expected){}
            }
            File bundle=LocalLogs.export(work.toFile(),"{\"native\":{\"alive\":false}}");
            try(ZipFile z=new ZipFile(bundle)) {
                check(z.getEntry("logs/operation.log").getSize()==100006,"Log bundle includes full output, not just the viewer tail");
                for(String needed:new String[]{"logs/app.log","logs/runtime.log","server/logs/zones/cabeast.log","client/current/DINPUT8.log","client/current/Logs/dbg.txt","status.json","export-notes.txt"})check(z.getEntry(needed)!=null,"Missing log bundle entry: "+needed);
                check(z.getEntry("client/current/eqclient.ini")==null&&z.getEntry("client/current/Logs/eqlog_character.txt")==null,"Client settings and chat are not diagnostic exports");
                check(z.stream().noneMatch(e->e.getName().contains("secret")||e.getName().contains("settings")||e.getName().contains("api-token")),"Bundle excludes linked data and credentials");
            }
            Path empty=tmp.resolve("fresh-app");Files.createDirectories(empty);
            try(ZipFile z=new ZipFile(LocalLogs.export(empty.toFile(),"{}"))){check(z.getEntry("status.json")!=null,"Fresh installation still exports diagnostics");}
            Files.createSymbolicLink(empty.resolve("logs"),tmp.resolve("outside"));
            try(ZipFile z=new ZipFile(LocalLogs.export(empty.toFile(),"{}"))){check(z.stream().noneMatch(e->e.getName().contains("secret")),"Symlinked log root cannot export outside data");}
            Files.delete(empty.resolve("logs"));Files.createDirectory(empty.resolve("logs"));
            Files.createSymbolicLink(empty.resolve("server"),tmp.resolve("outside"));
            check(LocalLogs.inventory(empty.toFile()).isEmpty(),"Symlinked server parent is ignored");
            Files.createSymbolicLink(empty.resolve("client"),work.resolve("client"));
            check(LocalLogs.inventory(empty.toFile()).isEmpty(),"Symlinked client parent is ignored");
            List<String> emitted=new ArrayList<>();
            ControllerInput input=new ControllerInput(new ControllerInput.Sink(){public void button(String a,boolean d){emitted.add(a+":"+d);}public void pointer(float x,float y){emitted.add("move");}public void wheel(int v){emitted.add("wheel:"+v);}});
            Map<String,String> bindings=ControllerInput.defaults();bindings.put("A","KeyW");bindings.put("B","KeyW");input.configure(bindings,.2f,700);
            input.value("A",1);check(emitted.isEmpty(),"Inactive controller must not emit");input.activate(true);
            input.value("A",1);input.value("A",1);input.value("B",1);input.value("A",0);
            check(emitted.equals(Arrays.asList("KeyW:true")),"Shared key must stay down until all sources release");input.value("B",0);
            check(emitted.equals(Arrays.asList("KeyW:true","KeyW:false")),"Exactly one key release");
            emitted.clear();input.axis("RightLeft","RightRight",.1f);input.tick(.016f);check(emitted.isEmpty(),"Deadzone suppresses drift");
            input.axis("RightLeft","RightRight",.8f);input.tick(.016f);check(emitted.contains("move"),"Analog pointer moves");
            input.value("L2",1);input.activate(false);check(emitted.contains("MouseRight:false"),"Focus loss releases mouse");
            emitted.clear();input.tick(.016f);check(emitted.isEmpty(),"No pointer motion after losing focus");
            System.out.println("PASS: Debian multiarch session roundtrip, checksums, traversal rejection, permissions, symlinks, native offline log reading/export, controller focus, held-key reference counts and analog pointer");
        } finally {TarExtractor.remove(tmp.toFile());}
    }
}
