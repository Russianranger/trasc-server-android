package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.*;

/** The production format, not a raised legacy heap/entry limit. */
public final class StreamSessionHostTest {
    static void check(boolean b,String message){if(!b)throw new AssertionError(message);}
    interface Action {void run()throws Exception;}
    static void rejected(Action a,String message)throws Exception {try{a.run();throw new AssertionError("Accepted "+message);}catch(IOException expected){}}
    static File export(Path base,Path tmp)throws Exception {
        Path prefs=tmp.resolve("prefs.properties");Files.writeString(prefs,"client_controls=[]\nlauncher_preferences={\"theme\":\"necromancer\"}\n");
        File out=tmp.resolve("stream.zip").toFile();SessionArchive.createAll(base.toFile(),out,"test","traditional",prefs.toFile(),s->{});return out;
    }
    static void basic(Path tmp)throws Exception {
        Path base=tmp.resolve("base");AllSessionHostTest.fixture(base,"before ");
        AllSessionHostTest.write(base,"work/client/readonly/keep","readonly");SessionArchive.chmod(base.resolve("work/client/readonly"),0555);
        Files.createSymbolicLink(base.resolve("work/client/absolute"),Paths.get("/etc/passwd"));
        Files.createSymbolicLink(base.resolve("work/client/broken"),Paths.get("missing"));
        File archive=export(base,tmp);Properties info=SessionArchive.readManifest(archive);
        check(StreamSessionArchive.FORMAT.equals(info.getProperty("format"))&&SessionArchive.allProfiles(info),"Production emits recognized format 3");
        check(SessionArchive.includedComponents(info).size()==6,"Both components of all three worlds retained");
        try(ZipFile zip=SessionArchive.openArchive(archive)){check(zip.size()==2&&zip.getEntry(StreamSessionArchive.PAYLOAD)!=null,"ZIP central directory stays at two members");}
        rejected(()->SessionArchive.requireProfile(archive,"traditional"),"single-profile import of new backup");
        Path stage=tmp.resolve("restore");SessionArchive.restore(archive,stage.toFile(),s->{});
        for(String id:SessionArchive.WORLDS){Path home=stage.resolve("worlds/"+id);check(Files.readString(home.resolve("work/database/world.ibd")).equals("before "+id+" database"),"DB restored for "+id);}
        check(Files.readSymbolicLink(stage.resolve("worlds/custom/work/client/absolute")).toString().equals("/etc/passwd"),"Guest absolute symlink retained");
        check(Files.readSymbolicLink(stage.resolve("worlds/custom/work/client/broken")).toString().equals("missing"),"Broken guest link retained");
        check(SessionArchive.mode(stage.resolve("worlds/custom/work/client/readonly"))==0555,"Directory permissions applied after children");
        check(Files.readString(stage.resolve("global/preferences.properties")).contains("necromancer"),"Global settings retained");
        AllProfileSwap.activate(base.toFile(),stage.toFile(),"traditional",true);AllSessionHostTest.verify(base,"before ");
        // Corrupt a real file byte while leaving its per-file hash intact.
        byte[] payload;try(ZipFile zip=new ZipFile(archive)){payload=zip.getInputStream(zip.getEntry(StreamSessionArchive.PAYLOAD)).readAllBytes();}
        byte[] needle="before custom database".getBytes(java.nio.charset.StandardCharsets.UTF_8);int at=-1;
        for(int i=0;i<=payload.length-needle.length;i++)if(Arrays.equals(Arrays.copyOfRange(payload,i,i+needle.length),needle)){at=i;break;}
        check(at>=0,"Corruption fixture found DB bytes");payload[at]^=1;File corrupt=tmp.resolve("corrupt.zip").toFile();writeZip(corrupt,payload,info);
        rejected(()->SessionArchive.restore(corrupt,tmp.resolve("bad-data").toFile(),s->{}),"corrupted DB before activation");AllSessionHostTest.verify(base,"before ");
        // Both single-profile and v2 archives remain readable through the new dispatch.
        File old=tmp.resolve("legacy.zip").toFile();SessionArchive.createAllLegacy(base.toFile(),old,"old","traditional",tmp.resolve("prefs.properties").toFile(),s->{});
        SessionArchive.restore(old,tmp.resolve("legacy-restore").toFile(),s->{});
        Path busy=tmp.resolve("busy");Files.createDirectory(busy);Files.writeString(busy.resolve("keep"),"untouched");
        rejected(()->SessionArchive.restore(archive,busy.toFile(),s->{}),"preexisting staging data");check(Files.readString(busy.resolve("keep")).equals("untouched"),"Staging conflict retained");
        Path linked=tmp.resolve("linked");Files.createSymbolicLink(linked,busy);rejected(()->SessionArchive.restore(archive,linked.toFile(),s->{}),"symlink staging");
        boolean[] copying={false};int[] calls={0};SessionArchive.Progress cancel=new SessionArchive.Progress(){public void update(String s){}public void bytes(long n,long total){copying[0]=true;}public void check()throws IOException {if(copying[0]&&++calls[0]>20)throw new InterruptedIOException("cancelled");}};
        File cancelled=tmp.resolve("cancelled.zip").toFile();rejected(()->SessionArchive.createAll(base.toFile(),cancelled,"test","traditional",null,cancel),"cancelled production export");check(!cancelled.exists(),"Partial local export removed");
        OutputStream broken=new OutputStream(){int count;public void write(int b)throws IOException{if(++count>32)throw new IOException("provider full");}};
        File spool=tmp.resolve("not-created.zip").toFile();rejected(()->SessionArchive.createAll(base.toFile(),spool,"test","traditional",null,s->{},broken),"provider write failure");check(!spool.exists(),"No duplicate private ZIP in direct-destination export");
        AllSessionHostTest.verify(base,"before ");
        int[] checks={0};SessionArchive.Progress cancelRestore=new SessionArchive.Progress(){public void update(String s){}public void check()throws IOException{if(++checks[0]>12)throw new InterruptedIOException("cancelled restore");}};
        rejected(()->SessionArchive.restore(archive,tmp.resolve("restore-cancelled").toFile(),cancelRestore),"cancelled staged restore");AllSessionHostTest.verify(base,"before ");
        try(java.util.stream.Stream<Path> files=Files.list(tmp)){check(files.noneMatch(p->p.getFileName().toString().startsWith("session-finalize-")),"Finalization journals removed after success, corruption and cancellation");}
        Path partial=tmp.resolve("partial");AllSessionHostTest.write(partial,"profiles/traditional/work/client/current/only.dat","partial");
        File partialZip=tmp.resolve("partial.zip").toFile();SessionArchive.createAll(partial.toFile(),partialZip,"test","traditional",tmp.resolve("prefs.properties").toFile(),t->{});
        Path partialStage=tmp.resolve("partial-stage");Properties partialManifest=SessionArchive.restore(partialZip,partialStage.toFile(),t->{});
        check(SessionArchive.includedComponents(partialManifest).equals(Collections.singletonList("traditional/work")),"Partial archive marks only present work");
        AllProfileSwap.activate(base.toFile(),partialStage.toFile(),"traditional",true,SessionArchive.includedComponents(partialManifest));
        check(Files.readString(base.resolve("work/database/world.ibd")).equals("before custom database"),"Absent Custom preserved");
        check(Files.readString(base.resolve("profiles/takp/work/database/world.ibd")).equals("before takp database"),"Absent TAKP preserved");
        check(Files.readString(base.resolve("profiles/traditional/work/client/current/only.dat")).equals("partial"),"Present partial work restored");
        check(Files.isRegularFile(base.resolve("profiles/traditional/rootfs/etc/trasc-runtime.json")),"Omitted Traditional runtime preserved");
    }
    static StreamSessionArchive.Record record(char type,String path,String link){return new StreamSessionArchive.Record(type,type=='L'?0:0755,0,"worlds/custom/"+path,link);}
    static void writeZip(File file,byte[] payload,Properties info)throws Exception {
        try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(file))){zip.putNextEntry(new ZipEntry(StreamSessionArchive.PAYLOAD));zip.write(payload);zip.closeEntry();zip.putNextEntry(new ZipEntry(SessionArchive.MANIFEST));info.store(zip,"");zip.closeEntry();}
    }
    static File crafted(Path tmp,String name,List<StreamSessionArchive.Record> records)throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);out.writeInt(StreamSessionArchive.MAGIC);StreamSessionArchive.Totals totals=new StreamSessionArchive.Totals();
        for(StreamSessionArchive.Record r:records){totals.add(r);StreamSessionArchive.header(out,r);if(r.type=='F')out.write(SessionArchive.sha().digest());}out.writeByte(0);out.flush();byte[] data=bytes.toByteArray();
        Properties m=new Properties();m.setProperty("format",StreamSessionArchive.FORMAT);m.setProperty("profiles","custom,traditional,takp");m.setProperty("selected_profile","custom");m.setProperty("architecture","arm64");m.setProperty("database_state","clean_shutdown");m.setProperty("entries",""+totals.count);m.setProperty("uncompressed_bytes","0");m.setProperty("metadata_bytes",""+totals.metadata);m.setProperty("payload_sha256",SessionArchive.hex(SessionArchive.sha().digest(data)));
        for(String id:SessionArchive.WORLDS)for(String flag:new String[]{"present","work","runtime","settings"})m.setProperty(id+"."+flag,Boolean.toString(id.equals("custom")&&(flag.equals("present")||flag.equals("work"))));
        File f=tmp.resolve(name+".zip").toFile();writeZip(f,data,m);return f;
    }
    static void attacks(Path tmp)throws Exception {
        List<List<StreamSessionArchive.Record>> cases=Arrays.asList(
            Arrays.asList(record('D',"client",""),record('F',"client/a",""),record('F',"client/a","")),
            Arrays.asList(record('D',"client",""),record('D',"client","")),
            Arrays.asList(record('L',"client","/tmp"),record('F',"client/escape","")),
            Arrays.asList(record('D',"client",""),record('F',"client/../../escape","")),
            Arrays.asList(record('D',"server",""),record('F',"server/bin/alias","")),
            Arrays.asList(record('D',"client",""),record('F',"client/file/child","")),
            Arrays.asList(record('F',"runtime","")),
            Arrays.asList(record('L',"configuration/settings.json","/etc/passwd"))
        );
        for(int i=0;i<cases.size();i++){File f=crafted(tmp,"attack-"+i,cases.get(i));Path stage=tmp.resolve("attack-stage-"+i);rejected(()->SessionArchive.restore(f,stage.toFile(),s->{}),"structural attack "+i);}
        // Length/totals bounds are checked before allocation or any data write.
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);out.writeInt(Integer.MAX_VALUE);
        rejected(()->StreamSessionArchive.text(new DataInputStream(new ByteArrayInputStream(bytes.toByteArray()))),"oversized string");
    }
    static void large(Path tmp)throws Exception {
        Path base=tmp.resolve("many");AllSessionHostTest.fixture(base,"large ");int perWorld=200001;
        for(String id:SessionArchive.WORLDS){Path home=id.equals("custom")?base:base.resolve("profiles/"+id);Path files=home.resolve("work/client/current/files");
            for(int i=0;i<perWorld;i++){Path dir=files.resolve(""+(i/1000));Files.createDirectories(dir);Files.createFile(dir.resolve(""+i));}
        }
        File legacy=tmp.resolve("legacy-limit.zip").toFile();rejected(()->SessionArchive.createAllLegacy(base.toFile(),legacy,"test","custom",null,s->{}),"same installation on legacy entry ceiling");
        File archive=export(base,tmp);Properties m=SessionArchive.readManifest(archive);check(Integer.parseInt(m.getProperty("entries"))>600000,"Real fixture exceeds old combined AND per-profile limit");
        Path stage=tmp.resolve("many-restored");SessionArchive.restore(archive,stage.toFile(),s->{});
        for(String id:SessionArchive.WORLDS){Path home=stage.resolve("worlds/"+id);for(int n:new int[]{0,100000,200000})check(Files.isRegularFile(home.resolve("work/client/current/files/"+(n/1000)+"/"+n)),"Boundary file retained in "+id);
            try(java.util.stream.Stream<Path> all=Files.walk(home.resolve("work/client/current/files"))){check(all.filter(p->Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)).count()==perWorld,"Every file retained for "+id);}
            check(Files.readString(home.resolve("work/database/world.ibd")).equals("large "+id+" database"),"World database intact for "+id);
        }
        try(ZipFile zip=new ZipFile(archive)){check(zip.size()==2,"600k source records still have only two ZIP members");}
        System.out.println("PASS: production streaming export/restore of "+m.getProperty("entries")+" records across three worlds; 200001 real client files per world; 48MiB heap; two ZIP members");
    }
    static void zip64(Path tmp)throws Exception {
        Path base=tmp.resolve("big");AllSessionHostTest.fixture(base,"big ");Path file=base.resolve("work/client/over4gb.dat");long size=0x100000000L+17;
        try(RandomAccessFile f=new RandomAccessFile(file.toFile(),"rw")){f.setLength(size);f.write(17);f.seek(size-1);f.write(32);}
        File archive=export(base,tmp);Path stage=tmp.resolve("big-restored");SessionArchive.restore(archive,stage.toFile(),s->{});Path restored=stage.resolve("worlds/custom/work/client/over4gb.dat");
        check(Files.size(restored)==size&&MessageDigest.isEqual(AllSessionHostTest.fileDigest(file),AllSessionHostTest.fileDigest(restored)),"Streaming ZIP64 payload hash and length preserved");
        System.out.println("PASS: production streaming ZIP64 export/restore of "+size+" bytes with independent SHA256 at 48MiB heap");
    }
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("trasc-stream-");try{basic(tmp);attacks(tmp);if(args.length>0&&args[0].equals("--large"))large(tmp);if(args.length>0&&args[0].equals("--zip64"))zip64(tmp);System.out.println("PASS: streaming v3 roundtrip, legacy read, staged atomic activation, checksums, permissions, inert links, structural refusals, cancellation and provider failure");}finally{SessionArchive.removeTree(tmp.toFile());}
    }
}
