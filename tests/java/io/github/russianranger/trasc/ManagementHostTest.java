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
            Files.createSymbolicLink(runtime.resolve("bin"),Paths.get("usr/bin"));
            write(work,"settings.json","{\"test\":true}");SessionArchive.chmod(work.resolve("settings.json"),0600);
            write(work,"server/bin/world","binary");SessionArchive.chmod(work.resolve("server/bin/world"),0755);
            write(work,"database/triune/test.ibd","world data");write(work,"maps/base/nektulos.map","map data");
            write(work,"backups/database.sql.gz","snapshot");write(work,"logs/control.log","log");write(work,"server/logs/world.log","world log");
            write(work,"client/current/eqgame.exe","MZclient");write(work,"client/controller.json","bindings");
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
            File corrupt=tmp.resolve("corrupt.zip").toFile();rewriteZip(archive,corrupt,"maps/base/nektulos.map","bad data");
            try{SessionArchive.restore(corrupt,tmp.resolve("bad").toFile(),s->{});throw new AssertionError("Corrupt file accepted");}catch(IOException expected){check(expected.getMessage().contains("checksum"),"Corruption must be detected by hash");}
            String index;try(ZipFile z=new ZipFile(archive);InputStream in=z.getInputStream(z.getEntry(SessionArchive.INDEX))){index=new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);}
            File traversal=tmp.resolve("traversal.zip").toFile();rewriteZip(archive,traversal,SessionArchive.INDEX,index.replace(SessionArchive.encode("maps/base/nektulos.map"),SessionArchive.encode("../escaped")));
            try{SessionArchive.restore(traversal,tmp.resolve("attack").toFile(),s->{});throw new AssertionError("Traversal accepted");}catch(IOException expected){}
            check(!Files.exists(tmp.resolve("escaped")),"Traversal wrote outside staging");
            String conflicting=index+"F\t420\t0\t"+"0".repeat(64)+"\t"+SessionArchive.encode("server/maps/escape")+"\t\n";
            File links=tmp.resolve("link-attack.zip").toFile();rewriteZip(archive,links,SessionArchive.INDEX,conflicting);
            try{SessionArchive.restore(links,tmp.resolve("links").toFile(),s->{});throw new AssertionError("Link-child attack accepted");}catch(IOException expected){}
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
            System.out.println("PASS: session components, checksums, traversal rejection, permissions, symlinks, controller focus, held-key reference counts and analog pointer");
        } finally {TarExtractor.remove(tmp.toFile());}
    }
}
