package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

/** Round-trip, bounded transport, adversarial archives and cross-world crash recovery. */
public final class AllSessionHostTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    interface Action {void run()throws Exception;}
    static void rejected(Action action,String message)throws Exception {try{action.run();throw new AssertionError(message);}catch(IOException expected){}}
    static void write(Path root,String relative,String data)throws IOException {ManagementHostTest.write(root,relative,data);}
    static void fixture(Path base,String prefix)throws IOException {
        for(String id:SessionArchive.WORLDS) {
            String home=id.equals("custom")?"":"profiles/"+id+"/";
            write(base,home+"rootfs/etc/trasc-runtime.json","{\"profile\":\""+id+"\"}");
            write(base,home+"work/settings.json",prefix+id+" settings");write(base,home+"work/database/world.ibd",prefix+id+" database");
            write(base,home+"work/client/prefix/user.reg",prefix+id+" Wine");write(base,home+"work/client/controller.json",prefix+id+" controller");
            write(base,home+"work/client/runtime/etc/receipt.json",prefix+id+" runtime");write(base,home+"work/server/bin/build-info.json",prefix+id+" receipt");
            write(base,home+"work/run/api-token","excluded");write(base,home+"work/exports/recursive.zip","excluded");
        }
        write(base,"world-profile.properties","active=traditional\n");
    }
    static void verify(Path base,String prefix)throws IOException {
        for(String id:SessionArchive.WORLDS) {
            Path home=id.equals("custom")?base:base.resolve("profiles/"+id);
            check(Files.readString(home.resolve("work/database/world.ibd")).equals(prefix+id+" database"),"Retained DB for "+id);
            check(Files.readString(home.resolve("work/client/prefix/user.reg")).equals(prefix+id+" Wine"),"Retained Wine prefix for "+id);
            check(Files.readString(home.resolve("work/server/bin/build-info.json")).equals(prefix+id+" receipt"),"Retained server receipt for "+id);
        }
    }
    static File backup(Path base,Path tmp)throws Exception {
        File prefs=tmp.resolve("preferences.properties").toFile();Files.writeString(prefs.toPath(),"client_controls=[]\nlauncher_preferences={\"theme\":\"monk\"}\n");
        File zip=tmp.resolve("all.zip").toFile();SessionArchive.createAll(base.toFile(),zip,"test","traditional",prefs,s->{});return zip;
    }
    static String index(File archive)throws IOException {
        try(ZipFile z=new ZipFile(archive);InputStream in=z.getInputStream(z.getEntry(SessionArchive.INDEX))){return new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);}
    }
    static void roundtripAndFailures(Path tmp)throws Exception {
        Path base=tmp.resolve("base");fixture(base,"before ");File archive=backup(base,tmp);
        try(ZipFile zip=new ZipFile(archive)) {
            for(String id:SessionArchive.WORLDS)check(zip.getEntry("worlds/"+id+"/database/world.ibd")!=null,"Archive contains "+id);
            check(zip.stream().noneMatch(e->e.getName().contains("api-token")||e.getName().contains("recursive.zip")),"No process credentials or recursion");
        }
        Properties manifest=SessionArchive.readManifest(archive);check(SessionArchive.allProfiles(manifest),"New versioned format");
        Path stage=tmp.resolve("stage");SessionArchive.restore(archive,stage.toFile(),s->{});
        for(String id:SessionArchive.WORLDS)check(Files.readString(stage.resolve("worlds/"+id+"/work/database/world.ibd")).equals("before "+id+" database"),"Independent database staged");
        fixture(base,"old ");AllProfileSwap.activate(base.toFile(),stage.toFile(),"traditional",true);verify(base,"before ");check(WorldProfiles.read(base.toFile()).equals("traditional"),"Selected world restored");
        for(int failure:new int[]{0,2,4,6,7}) {
            fixture(base,"old ");stage=tmp.resolve("stage-"+failure);SessionArchive.restore(archive,stage.toFile(),s->{});Path selectedStage=stage;
            rejected(()->AllProfileSwap.activate(base.toFile(),selectedStage.toFile(),"takp",true,i->{if(i==failure)throw new IOException("simulated world activation failure");}),"Failure must reject activation");
            verify(base,"old ");check(WorldProfiles.read(base.toFile()).equals("traditional"),"Failed transaction retains prior selection");check(!AllProfileSwap.pending(base.toFile()),"Completed rollback clears journal");
        }
        // Simulated process death bypasses the normal IOException rollback.
        fixture(base,"old ");stage=tmp.resolve("crash-stage");SessionArchive.restore(archive,stage.toFile(),s->{});
        try{AllProfileSwap.activate(base.toFile(),stage.toFile(),"takp",true,i->{if(i==4)throw new IllegalStateException("simulated process death");});throw new AssertionError("Crash hook missed");}catch(IllegalStateException expected){}
        check(AllProfileSwap.pending(base.toFile()),"Crash keeps recovery journal");AllProfileSwap.recover(base.toFile());AllProfileSwap.recover(base.toFile());verify(base,"old ");
        Path rejectedStage=tmp.resolve("no-replace");SessionArchive.restore(archive,rejectedStage.toFile(),s->{});
        rejected(()->AllProfileSwap.activate(base.toFile(),rejectedStage.toFile(),"takp",false),"Existing worlds require explicit replacement");verify(base,"old ");
        String inventory=index(archive);File malicious=tmp.resolve("namespace.zip").toFile();
        ManagementHostTest.rewriteZip(archive,malicious,SessionArchive.INDEX,inventory.replace(SessionArchive.encode("worlds/traditional/database/world.ibd"),SessionArchive.encode("worlds/unknown/database/world.ibd")));
        rejected(()->SessionArchive.restore(malicious,tmp.resolve("bad-namespace").toFile(),s->{}),"Unknown world must reject");
        File duplicate=tmp.resolve("duplicate.zip").toFile();ManagementHostTest.rewriteZip(archive,duplicate,SessionArchive.INDEX,inventory+inventory.lines().filter(l->l.contains(SessionArchive.encode("worlds/custom/database/world.ibd"))).findFirst().get()+"\n");
        rejected(()->SessionArchive.restore(duplicate,tmp.resolve("bad-duplicate").toFile(),s->{}),"Duplicate world destination must reject");
        String alias=inventory.lines().filter(l->l.contains(SessionArchive.encode("worlds/custom/binaries/current/build-info.json"))).findFirst().get().replace(SessionArchive.encode("worlds/custom/binaries/current/build-info.json"),SessionArchive.encode("worlds/custom/server/bin/build-info.json"));
        File overlap=tmp.resolve("overlap.zip").toFile();ManagementHostTest.rewriteZip(archive,overlap,SessionArchive.INDEX,inventory+alias+"\n");
        rejected(()->SessionArchive.restore(overlap,tmp.resolve("bad-overlap").toFile(),s->{}),"Component aliases cannot overlap live destinations");
        File nested=tmp.resolve("nested.zip").toFile();ManagementHostTest.rewriteZip(archive,nested,SessionArchive.INDEX,inventory.replace(SessionArchive.encode("worlds/custom/database/world.ibd"),SessionArchive.encode("worlds/custom/worlds/traditional/database/world.ibd")));
        rejected(()->SessionArchive.restore(nested,tmp.resolve("bad-nested").toFile(),s->{}),"Nested namespaces must reject");
        File corrupt=tmp.resolve("corrupt.zip").toFile();ManagementHostTest.rewriteZip(archive,corrupt,"worlds/takp/database/world.ibd","corrupt");
        rejected(()->SessionArchive.restore(corrupt,tmp.resolve("bad-last-world").toFile(),s->{}),"Last-world corruption must reject before activation");verify(base,"old ");
        rejected(()->SessionArchive.limitedLine(new StringReader("x".repeat(40000))),"Oversized metadata line must reject before unbounded allocation");
        File cancelled=tmp.resolve("cancelled.zip").toFile();SessionArchive.Progress cancellation=new SessionArchive.Progress(){int checks;public void update(String s){}public void check()throws IOException{if(++checks>20)throw new InterruptedIOException("cancelled");}};
        rejected(()->SessionArchive.createAll(base.toFile(),cancelled,"test","custom",tmp.resolve("preferences.properties").toFile(),cancellation),"Cancelled archive must fail");check(!cancelled.exists(),"Cancelled partial local archive removed");verify(base,"old ");
        // Partial worlds, without any server runtime, are still represented and restored.
        // A corrupt recovery journal must reject before any live-world mutation.
        Properties badJournal=new Properties();badJournal.setProperty("format","2");badJournal.setProperty("phase","activating");badJournal.setProperty("components",String.join(",",AllProfileSwap.worldComponents()));badJournal.setProperty("recovery",java.util.UUID.randomUUID().toString());
        for(int i=0;i<8;i++)badJournal.setProperty("had."+i,i==7?"invalid":"false");
        AllProfileSwap.store(base.toFile(),badJournal);rejected(()->AllProfileSwap.recover(base.toFile()),"Corrupt last journal field cannot partly remove worlds");verify(base,"old ");Files.delete(base.resolve(AllProfileSwap.JOURNAL));
        // Valid read-only modes cannot strand rollback/staging deletion; live originals keep their modes.
        for(String id:SessionArchive.WORLDS){Path home=id.equals("custom")?base:base.resolve("profiles/"+id);write(home,"work/client/readonly/file.dat","readonly");SessionArchive.chmod(home.resolve("work/client/readonly"),0555);}
        Path readOnlyStage=tmp.resolve("readonly-stage");SessionArchive.restore(archive,readOnlyStage.toFile(),s->{});
        rejected(()->AllProfileSwap.activate(base.toFile(),readOnlyStage.toFile(),"custom",true,i->{if(i==4)throw new IOException("readonly rollback");}),"Rollback must handle read-only old directories");verify(base,"old ");
        check(SessionArchive.mode(base.resolve("work/client/readonly"))==0555,"Recovered old directory permissions stay intact");
        Path cleanupTree=tmp.resolve("readonly-cleanup");write(cleanupTree,"nested/file","data");SessionArchive.chmod(cleanupTree.resolve("nested"),0555);SessionArchive.chmod(cleanupTree,0555);SessionArchive.removeTree(cleanupTree.toFile());check(!Files.exists(cleanupTree),"Read-only staged tree is removable");
        Properties changedManifest=SessionArchive.readManifest(archive);changedManifest.setProperty("takp.runtime","false");StringWriter changed=new StringWriter();changedManifest.store(changed,"inconsistent runtime presence");
        File inconsistent=tmp.resolve("bad-runtime-flag.zip").toFile();ManagementHostTest.rewriteZip(archive,inconsistent,SessionArchive.MANIFEST,changed.toString());
        rejected(()->SessionArchive.restore(inconsistent,tmp.resolve("bad-runtime-flag").toFile(),s->{}),"Presence metadata must match actual runtime root");
        Path partial=tmp.resolve("partial");write(partial,"profiles/takp/work/client/current/eqgame.exe","partial client");
        File partialArchive=tmp.resolve("partial.zip").toFile();SessionArchive.createAll(partial.toFile(),partialArchive,"test","custom",tmp.resolve("preferences.properties").toFile(),s->{});
        Path partialStage=tmp.resolve("partial-stage");SessionArchive.restore(partialArchive,partialStage.toFile(),s->{});
        check(Files.readString(partialStage.resolve("worlds/takp/work/client/current/eqgame.exe")).equals("partial client"),"Partial import survives");
        Properties partialInfo=SessionArchive.readManifest(partialArchive);check(SessionArchive.presentProfiles(partialInfo).equals(Collections.singletonList("takp")),"Absent profiles have no archive namespace");
        String priorCustom=Files.readString(base.resolve("work/database/world.ibd")),priorTraditional=Files.readString(base.resolve("profiles/traditional/work/database/world.ibd")),priorTakpRuntime=Files.readString(base.resolve("profiles/takp/rootfs/etc/trasc-runtime.json"));
        String retained=AllProfileSwap.activate(base.toFile(),partialStage.toFile(),"custom",true,SessionArchive.includedComponents(partialInfo));
        check(Files.readString(base.resolve("work/database/world.ibd")).equals(priorCustom)&&Files.readString(base.resolve("profiles/traditional/work/database/world.ibd")).equals(priorTraditional),"Absent worlds preserve both prior destination trees");
        check(Files.readString(base.resolve("profiles/takp/rootfs/etc/trasc-runtime.json")).equals(priorTakpRuntime),"Client-only partial backup preserves destination runtime");
        check(Files.readString(base.resolve("profiles/takp/work/client/current/eqgame.exe")).equals("partial client"),"Included work replaces its snapshot");
        check(Files.readString(base.resolve(retained+"/0/database/world.ibd")).equals("old takp database"),"Prior included world tree retained in recovery copy");
    }
    static void boundedTransport()throws Exception {
        long length=48L*1024*1024;int[] maxRead={0};long[] remaining={length},written={0};
        InputStream in=new InputStream(){public int read(){throw new AssertionError("Byte-by-byte large transport");}public int read(byte[] b,int off,int n){maxRead[0]=Math.max(maxRead[0],n);if(remaining[0]==0)return -1;int count=(int)Math.min(n,remaining[0]);Arrays.fill(b,off,off+count,(byte)7);remaining[0]-=count;return count;}};
        OutputStream out=new OutputStream(){public void write(int b){throw new AssertionError("Byte-by-byte transport");}public void write(byte[] b,int off,int n){written[0]+=n;}};
        check(SessionTransfer.copy(in,out,length,null,s->{})==length&&written[0]==length,"Large stream copied completely");check(maxRead[0]<=SessionTransfer.BUFFER_BYTES,"Read buffer bounded to 1MiB");
        SessionArchive.Progress cancel=new SessionArchive.Progress(){public void update(String s){}public void check()throws IOException{throw new InterruptedIOException("cancelled SAF stream");}};
        rejected(()->SessionTransfer.copy(new ByteArrayInputStream(new byte[4096]),out,4096,null,cancel),"Cancelled SAF stream must stop");
        rejected(()->SessionTransfer.copy(new ByteArrayInputStream(new byte[4]),out,8,null,s->{}),"Truncated transfer must reject");
        rejected(()->SessionTransfer.copy(new ByteArrayInputStream(new byte[4]),out,SessionArchive.MAX_ARCHIVE_BYTES+1,null,s->{}),"Oversize transfer preflight must reject");
    }
    static void zip64(Path tmp)throws Exception {
        Path base=tmp.resolve("zip64-base");write(base,"work/client/current/marker.txt","large client");
        long size=0x1_0000_0000L+17;
        File sparse=base.resolve("work/client/current/large.dat").toFile();try(RandomAccessFile out=new RandomAccessFile(sparse,"rw")){out.setLength(size);out.seek(0);out.write(0x54);out.seek(0x1_0000_0000L);out.write(0x52);out.seek(size-1);out.write(0x43);}
        File prefs=tmp.resolve("preferences.properties").toFile();File archive=tmp.resolve("zip64.zip").toFile();
        // Direct stream avoids reserving a second 4GiB private archive; compression retains a small ZIP.
        try(OutputStream out=new FileOutputStream(archive)){SessionArchive.createAll(base.toFile(),tmp.resolve("spool.zip").toFile(),"test","custom",prefs,s->{},out);}
        try(ZipFile zip=new ZipFile(archive)){check(zip.getEntry("worlds/custom/client/current/large.dat").getSize()==size,"ZIP64 preserves greater-than-4GiB file size");}
        check(archive.length()<64L*1024*1024,"Sparse logical file written as bounded compressed stream");
        Path stage=tmp.resolve("zip64-restored");SessionArchive.restore(archive,stage.toFile(),s->{});
        Path restored=stage.resolve("worlds/custom/work/client/current/large.dat");check(Files.size(restored)==size,"ZIP64 import preserves greater-than-4GiB size");
        check(java.security.MessageDigest.isEqual(fileDigest(sparse.toPath()),fileDigest(restored)),"Independent restored large-file SHA256 matches source");
        try(RandomAccessFile in=new RandomAccessFile(restored.toFile(),"r")){check(in.read()==0x54,"Large-file first marker restored");in.seek(0x1_0000_0000L);check(in.read()==0x52,"Marker beyond4GiB restored");in.seek(size-1);check(in.read()==0x43,"Large-file final marker restored");}
        check(Files.readString(stage.resolve("worlds/custom/work/client/current/marker.txt")).equals("large client"),"Large archive companion marker restored");
        System.out.println("ZIP64 export/import passed: "+size+" bytes, source/restored SHA256 and markers match, archive "+archive.length()+" bytes");
    }
    static byte[] fileDigest(Path path)throws Exception {
        java.security.MessageDigest digest=SessionArchive.sha();byte[] buffer=new byte[1024*1024];try(InputStream in=Files.newInputStream(path)){int count;while((count=in.read(buffer))!=-1)digest.update(buffer,0,count);}return digest.digest();
    }
    static void centralBounds(Path tmp)throws Exception {
        File attack=tmp.resolve("directory-count.zip").toFile();byte[] record=new byte[98];
        java.nio.ByteBuffer b=java.nio.ByteBuffer.wrap(record).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        b.putInt(0,0x06064b50);b.putLong(4,44);b.putLong(24,300000);b.putLong(32,300000);
        b.putInt(56,0x07064b50);b.putLong(64,0);b.putInt(72,1);b.putInt(76,0x06054b50);b.putShort(84,(short)65535);b.putShort(86,(short)65535);b.putInt(88,-1);b.putInt(92,-1);
        Files.write(attack.toPath(),record);rejected(()->{try(ZipFile zip=SessionArchive.openArchive(attack)){}},"Hostile ZIP64 entry count must reject before eager allocation");
        File large=tmp.resolve("large-directory.zip").toFile();long center=SessionArchive.centralBudget()+1;
        byte[] end=new byte[22];java.nio.ByteBuffer last=java.nio.ByteBuffer.wrap(end).order(java.nio.ByteOrder.LITTLE_ENDIAN);last.putInt(0,0x06054b50);last.putShort(8,(short)1);last.putShort(10,(short)1);last.putInt(12,(int)center);
        try(RandomAccessFile out=new RandomAccessFile(large,"rw")){out.setLength(center+22);out.seek(center);out.write(end);}
        rejected(()->{try(ZipFile zip=SessionArchive.openArchive(large)){}},"Oversized central directory must reject before ZipFile allocation");
    }
    static void partialPreferences()throws Exception {
        Map<String,String> archived=new LinkedHashMap<>(),current=new LinkedHashMap<>();
        archived.put("custom.gear_x","source-custom");archived.put("traditional.look_hidden","source-traditional");archived.put("takp.gear_x","source-takp");archived.put("global","source-global");
        current.put("custom.gear_x","target-custom");current.put("traditional.look_hidden","target-traditional");current.put("takp.gear_x","target-takp");current.put("custom.look_y","target-only");
        Map<String,String> merged=SessionPreferences.merge(archived,current,Arrays.asList("custom","traditional"));
        check(merged.get("custom.gear_x").equals("target-custom")&&merged.get("custom.look_y").equals("target-only")&&merged.get("traditional.look_hidden").equals("target-traditional"),"Omitted work trees retain native overlay preferences");
        check(merged.get("takp.gear_x").equals("source-takp")&&merged.get("global").equals("source-global"),"Included work and global preferences restore archive values");
        current.remove("traditional.look_hidden");check(!SessionPreferences.merge(archived,current,Arrays.asList("traditional")).containsKey("traditional.look_hidden"),"Omitted profile cannot inherit stale archive-only native preferences");
        current.clear();for(int i=0;i<1000;i++)current.put("custom.key"+i,"x");rejected(()->SessionPreferences.merge(archived,current,Arrays.asList("custom")),"Merged native preferences remain bounded");
    }
    static void largeMetadata(Path tmp)throws Exception {
        Path base=tmp.resolve("metadata-base"),links=base.resolve("work/client/prefix/dosdevices");Files.createDirectories(links);
        String target="x".repeat(350),padding="n".repeat(96);
        for(int i=0;i<87000;i++){Path folder=links.resolve(String.valueOf(i/1000));Files.createDirectories(folder);Files.createSymbolicLink(folder.resolve(padding+i),Paths.get(target));}
        File archive=tmp.resolve("metadata.zip").toFile();SessionArchive.createAll(base.toFile(),archive,"test","custom",tmp.resolve("preferences.properties").toFile(),s->{});
        long inventory;try(ZipFile zip=SessionArchive.openArchive(archive)){inventory=zip.getEntry(SessionArchive.INDEX).getSize();}
        check(inventory>50L*1024*1024&&inventory<=SessionArchive.MAX_INDEX_BYTES,"Fixture approaches supported index byte budget");
        Path stage=tmp.resolve("metadata-stage");SessionArchive.restore(archive,stage.toFile(),s->{});
        check(Files.readSymbolicLink(stage.resolve("worlds/custom/work/client/prefix/dosdevices/86/"+padding+"86999")).toString().equals(target),"Long-name/link metadata roundtrip");
        System.out.println("87000 long-name/link records, "+inventory+" index bytes, passed under the supplied heap limit");
    }
    static void highEntries(Path tmp)throws Exception {
        Path base=tmp.resolve("entry-base"),files=base.resolve("work/client/current/files");Files.createDirectories(files);
        int count=190000;for(int i=0;i<count;i++){Path folder=files.resolve(String.valueOf(i/1000));Files.createDirectories(folder);Files.createFile(folder.resolve(String.valueOf(i)));}
        File archive=tmp.resolve("entries.zip").toFile();SessionArchive.createAll(base.toFile(),archive,"test","custom",tmp.resolve("preferences.properties").toFile(),s->{});
        Path stage=tmp.resolve("entries-stage");SessionArchive.restore(archive,stage.toFile(),s->{});
        check(Files.isRegularFile(stage.resolve("worlds/custom/work/client/current/files/189/189999")),"High entry-count ZIP64 archive restored at bounded heap");
        System.out.println("190000-file archive export/import passed under the supplied heap limit");
    }
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("trasc-all-session-");
        try{roundtripAndFailures(tmp);boundedTransport();centralBounds(tmp);partialPreferences();if(args.length>0&&args[0].equals("--zip64"))zip64(tmp);if(args.length>0&&args[0].equals("--entries"))highEntries(tmp);if(args.length>0&&args[0].equals("--metadata"))largeMetadata(tmp);System.out.println("All-world archive, rollback/crash recovery, namespace, cancellation and bounded transport tests passed");}
        finally{SessionArchive.removeTree(tmp.toFile());}
    }
}
