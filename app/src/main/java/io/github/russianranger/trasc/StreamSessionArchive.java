package io.github.russianranger.trasc;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.*;
import java.util.*;
import java.util.zip.*;

/** Format 3: two ZIP members, a forward-only record stream and a small manifest.
 * No per-file ZIP directory or heap inventory. Exclusive staged creation detects
 * duplicates; links remain inert placeholders until the entire stream verifies.
 * A bounded-record disk journal applies links and directory modes in reverse.
 */
final class StreamSessionArchive {
    static final String FORMAT="trasc-all-sessions-3", PAYLOAD="session-stream.bin";
    static final int MAGIC=0x54534333, MAX_RECORDS=2000000, MAX_TEXT=16384, MAX_DEPTH=256;
    static final long MAX_METADATA=512L*1024*1024;
    static final int BUFFER=1024*1024;
    static final class Record {
        int type,mode;long size;String name,link;
        Record(int type,int mode,long size,String name,String link){this.type=type;this.mode=mode;this.size=size;this.name=name;this.link=link;}
    }
    static final class Totals {
        int count;long bytes,metadata;
        void add(Record r)throws IOException {
            if(++count>MAX_RECORDS)throw new IOException("Backup exceeds the streaming limit of "+MAX_RECORDS+" entries");
            if(r.size<0||r.size>SessionArchive.MAX_BYTES-bytes)throw new IOException("Backup exceeds the supported total size");
            bytes+=r.size;metadata+=21L+textBytes(r.name).length+textBytes(r.link).length+(r.type=='F'?32:0);
            if(metadata>MAX_METADATA)throw new IOException("Backup path/link metadata exceeds the supported streaming size");
        }
    }
    static byte[] textBytes(String s)throws IOException {
        byte[] b=s.getBytes(StandardCharsets.UTF_8);
        if(b.length>MAX_TEXT||s.indexOf('\0')>=0)throw new IOException("Backup path or link is too long or invalid");return b;
    }
    static void text(DataOutput out,String s)throws IOException {byte[] b=textBytes(s);out.writeInt(b.length);out.write(b);}
    static String text(DataInput in)throws IOException {
        int n=in.readInt();if(n<0||n>MAX_TEXT)throw new IOException("Invalid streaming path length");
        byte[] b=new byte[n];in.readFully(b);String s=new String(b,StandardCharsets.UTF_8);
        if(s.indexOf('\0')>=0||!Arrays.equals(b,s.getBytes(StandardCharsets.UTF_8)))throw new IOException("Invalid UTF-8 streaming path");return s;
    }
    static void header(DataOutput out,Record r)throws IOException {out.writeByte(r.type);out.writeInt(r.mode);out.writeLong(r.size);text(out,r.name);text(out,r.link);}
    static Record header(DataInput in,int type)throws IOException {return new Record(type,in.readInt(),in.readLong(),text(in),text(in));}
    static Path validate(Path stage,Record r)throws IOException {
        if(r.type!='F'&&r.type!='D'&&r.type!='L'||r.mode<0||r.mode>0777||r.size<0||r.size>SessionArchive.MAX_BYTES)throw new IOException("Invalid streaming record type, mode or size");
        if(r.type!='F'&&r.size!=0||r.type!='L'&&!r.link.isEmpty()||r.type=='L'&&(r.link.isEmpty()||r.mode!=0))throw new IOException("Invalid streaming link/directory record");
        if(!r.name.startsWith("worlds/")&&!r.name.equals("global/preferences.properties"))throw new IOException("Invalid streaming world namespace");
        SessionArchive.confined(stage,r.name);Path target=SessionArchive.destination(stage,r.name);
        if(stage.relativize(target).getNameCount()>MAX_DEPTH)throw new IOException("Backup directory nesting exceeds the safe limit");
        if(r.name.matches("worlds/(custom|traditional|takp)/runtime")&&r.type!='D')throw new IOException("Runtime root must be a directory");
        if((r.name.equals("global/preferences.properties")||r.name.matches("worlds/(custom|traditional|takp)/configuration/settings.json"))&&r.type!='F')throw new IOException("Saved settings must be a regular file");
        return target;
    }
    static List<SessionArchive.Source> sources(File base,String selected,File preferences,Properties manifest)throws IOException {
        WorldProfiles.valid(selected);WorldProfiles profiles=new WorldProfiles(base.getCanonicalFile());List<SessionArchive.Source> result=new ArrayList<>();
        manifest.setProperty("format",FORMAT);manifest.setProperty("profiles","custom,traditional,takp");manifest.setProperty("selected_profile",selected);
        for(String id:SessionArchive.WORLDS){
            File home=profiles.home(id),root=new File(home,"rootfs"),work=new File(home,"work");
            List<SessionArchive.Source> all=SessionArchive.sources(root,work,"worlds/"+id+"/"),workSources=new ArrayList<>(all.subList(1,all.size()));
            boolean runtime=Files.exists(root.toPath(),LinkOption.NOFOLLOW_LINKS),data=SessionArchive.hasData(workSources);
            manifest.setProperty(id+".present",String.valueOf(runtime||data));manifest.setProperty(id+".runtime",String.valueOf(runtime));manifest.setProperty(id+".work",String.valueOf(data));
            manifest.setProperty(id+".settings",String.valueOf(data&&Files.isRegularFile(work.toPath().resolve("settings.json"),LinkOption.NOFOLLOW_LINKS)));
            if(runtime)result.add(all.get(0));
            if(data){
                // The server parent must precede the separately archived bin/log children.
                for(SessionArchive.Source s:workSources)if(s.server)result.add(s);
                for(SessionArchive.Source s:workSources)if(!s.server)result.add(s);
            }
        }
        if(preferences!=null)result.add(new SessionArchive.Source("global/preferences.properties",preferences.toPath(),false));return result;
    }
    interface Visitor {void accept(Path path,Record record)throws IOException;}
    static void walk(List<SessionArchive.Source> sources,Path base,SessionArchive.Progress progress,Visitor visitor)throws IOException {
        Path virtual=Paths.get("/");
        for(SessionArchive.Source source:sources){
            progress.check();if(!Files.exists(source.path,LinkOption.NOFOLLOW_LINKS))continue;
            // A component may itself be a guest link, but component ancestors may
            // not redirect an otherwise independent component outside its home.
            for(Path p=source.path.getParent();p!=null&&p.startsWith(base)&&!p.equals(base);p=p.getParent())if(Files.isSymbolicLink(p))throw new IOException("Linked backup component ancestor: "+source.name);
            progress.update("Scanning / backing up "+source.name);
            Files.walkFileTree(source.path,EnumSet.noneOf(FileVisitOption.class),MAX_DEPTH,new SimpleFileVisitor<Path>(){
                void add(Path p,BasicFileAttributes a)throws IOException {
                    progress.check();String relative=source.path.relativize(p).toString(),name=source.name+(relative.isEmpty()?"":"/"+relative);
                    int type=a.isSymbolicLink()?'L':a.isDirectory()?'D':a.isRegularFile()?'F':0;
                    if(type==0)throw new IOException("Stop all processes before backing up: "+name);
                    Record r=new Record(type,type=='L'?0:SessionArchive.mode(p),type=='F'?a.size():0,name,type=='L'?Files.readSymbolicLink(p).toString():"");validate(virtual,r);visitor.accept(p,r);
                }
                @Override public FileVisitResult preVisitDirectory(Path p,BasicFileAttributes a)throws IOException {
                    if(source.server&&SessionArchive.excludedServerChild(source.path.relativize(p)))return FileVisitResult.SKIP_SUBTREE;
                    add(p,a);return FileVisitResult.CONTINUE;
                }
                @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a)throws IOException {
                    if(a.isDirectory())throw new IOException("Backup directory nesting exceeds the safe limit");
                    if(!source.server||!SessionArchive.excludedServerChild(source.path.relativize(p)))add(p,a);return FileVisitResult.CONTINUE;
                }
            });
        }
    }
    static void create(File base,File archive,String version,String selected,File preferences,SessionArchive.Progress progress,OutputStream external)throws IOException {
        Files.createDirectories(archive.getParentFile().toPath());new SessionArchive.MemoryBudget().check();
        Properties manifest=new Properties();List<SessionArchive.Source> sources=sources(base,selected,preferences,manifest);Totals expected=new Totals();
        walk(sources,base.getCanonicalFile().toPath(),progress,(p,r)->{expected.add(r);if(expected.count%2000==0)progress.update("Checking backup size · "+expected.count+" entries · "+expected.bytes+" bytes");});
        long overhead=expected.metadata+expected.bytes/500+16L*1024*1024;
        SessionArchive.checkSpace(archive.getParentFile(),external==null?expected.bytes+overhead:16L*1024*1024);
        progress.bytes(0,expected.bytes);Totals actual=new Totals();byte[] buffer=new byte[BUFFER];long[] done={0};
        MessageDigest fileHash=SessionArchive.sha(); // Reuse native-backed Android digest contexts.
        try(ZipOutputStream zip=new ZipOutputStream(new BufferedOutputStream(external==null?new FileOutputStream(archive):external,BUFFER))){
            zip.setLevel(1);zip.putNextEntry(new ZipEntry(PAYLOAD));MessageDigest payload=SessionArchive.sha();DataOutputStream out=new DataOutputStream(new BufferedOutputStream(new DigestOutputStream(zip,payload),65536));out.writeInt(MAGIC);
            walk(sources,base.getCanonicalFile().toPath(),progress,(path,r)->{
                actual.add(r);header(out,r);
                if(r.type=='F'){
                    fileHash.reset();MessageDigest hash=fileHash;long left=r.size;
                    try(InputStream input=Files.newInputStream(path,LinkOption.NOFOLLOW_LINKS)){
                        while(left>0){progress.check();int n=input.read(buffer,0,(int)Math.min(left,buffer.length));if(n<0)throw new EOFException("File changed during backup: "+r.name);if(n==0)continue;
                            if(external==null)SessionArchive.checkSpace(archive.getParentFile(),n);out.write(buffer,0,n);hash.update(buffer,0,n);left-=n;done[0]+=n;progress.bytes(done[0],expected.bytes);
                        }
                        if(input.read()!=-1)throw new IOException("File changed during backup: "+r.name);
                    }
                    out.write(hash.digest());
                }
                if(actual.count%1000==0)progress.update("Backing up · "+actual.count+" entries");
            });
            if(actual.count!=expected.count||actual.bytes!=expected.bytes||actual.metadata!=expected.metadata)throw new IOException("Backup inventory changed; retry after stopping all operations");
            out.writeByte(0);out.flush();zip.closeEntry();manifest.setProperty("payload_sha256",SessionArchive.hex(payload.digest()));
            manifest.setProperty("architecture","arm64");manifest.setProperty("database_state","clean_shutdown");manifest.setProperty("app_version",version);manifest.setProperty("created_utc",java.time.Instant.now().toString());
            manifest.setProperty("entries",Integer.toString(actual.count));manifest.setProperty("uncompressed_bytes",Long.toString(actual.bytes));manifest.setProperty("metadata_bytes",Long.toString(actual.metadata));
            zip.putNextEntry(new ZipEntry(SessionArchive.MANIFEST));manifest.store(zip,"TRASC streaming backup — keep private");zip.closeEntry();progress.check();
        }catch(IOException e){if(external==null)archive.delete();throw e;}
        if(external==null)try(FileOutputStream f=new FileOutputStream(archive,true)){f.getFD().sync();}
        progress.update("Complete streaming session ZIP ready · "+actual.count+" entries");
    }
    static long number(Properties m,String key,long max)throws IOException {
        try{long n=Long.parseLong(m.getProperty(key));if(n<0||n>max)throw new NumberFormatException();return n;}catch(Exception e){throw new IOException("Invalid streaming backup totals: "+key,e);}
    }
    static void journal(RandomAccessFile f,Record r)throws IOException {
        long at=f.getFilePointer();header(f,r);f.writeInt((int)(f.getFilePointer()-at));
    }
    static Properties restore(File archive,File staging,SessionArchive.Progress progress)throws IOException {
        Path stage=staging.toPath().toAbsolutePath().normalize();
        if(Files.isSymbolicLink(stage))throw new IOException("Staging must not be a symbolic link");Files.createDirectories(stage);
        try(DirectoryStream<Path> items=Files.newDirectoryStream(stage)){if(items.iterator().hasNext())throw new IOException("Streaming restore requires empty staging");}
        File journal=File.createTempFile("session-finalize-",".bin",staging.getParentFile());
        try(ZipFile zip=SessionArchive.openArchive(archive);RandomAccessFile deferred=new RandomAccessFile(journal,"rw")){
            Properties m=SessionArchive.readManifest(archive);SessionArchive.archiveProfiles(m);SessionArchive.presentProfiles(m);
            if(!FORMAT.equals(m.getProperty("format"))||!"arm64".equals(m.getProperty("architecture"))||!"clean_shutdown".equals(m.getProperty("database_state")))throw new IOException("Unsupported streaming backup");
            long count=number(m,"entries",MAX_RECORDS),bytes=number(m,"uncompressed_bytes",SessionArchive.MAX_BYTES),metadata=number(m,"metadata_bytes",MAX_METADATA);
            if(!m.getProperty("payload_sha256","").matches("[0-9a-f]{64}"))throw new IOException("Invalid streaming checksum");
            Set<String> names=new HashSet<>();Enumeration<? extends ZipEntry> members=zip.entries();
            while(members.hasMoreElements()){String n=members.nextElement().getName();if(!Arrays.asList(PAYLOAD,SessionArchive.MANIFEST).contains(n)||!names.add(n))throw new IOException("Unexpected or duplicate streaming ZIP member");}
            if(names.size()!=2)throw new IOException("Incomplete streaming backup");
            ZipEntry member=zip.getEntry(PAYLOAD);if(member.getSize()!=bytes+metadata+5)throw new IOException("Streaming payload size does not match its manifest");
            SessionArchive.checkSpace(staging,bytes+count*8192L+metadata+16L*1024*1024);
            for(String id:SessionArchive.WORLDS)Files.createDirectories(stage.resolve("worlds/"+id+"/work"));Files.createDirectory(stage.resolve("global"));
            boolean[][] presence=new boolean[3][4];Totals actual=new Totals();byte[] buffer=new byte[BUFFER];long completed=0;MessageDigest digest=SessionArchive.sha(),fileHash=SessionArchive.sha();progress.bytes(0,bytes);
            try(DataInputStream in=new DataInputStream(new BufferedInputStream(new DigestInputStream(zip.getInputStream(member),digest),BUFFER))){
                if(in.readInt()!=MAGIC)throw new IOException("Invalid streaming backup header");int type;
                while((type=in.readUnsignedByte())!=0){
                    progress.check();Record r=header(in,type);Path target=validate(stage,r);actual.add(r);
                    if(actual.count>count||actual.bytes>bytes||actual.metadata>metadata)throw new IOException("Streaming payload exceeds its manifest");
                    if(!Files.isDirectory(target.getParent(),LinkOption.NOFOLLOW_LINKS))throw new IOException("Streaming parent directory is missing or not a real directory: "+r.name);
                    if(r.name.startsWith("worlds/")){
                        String[] parts=r.name.split("/",3);int i=SessionArchive.WORLDS.indexOf(parts[1]);presence[i][0]=true;
                        boolean runtime=parts[2].equals("runtime")||parts[2].startsWith("runtime/");if(!runtime)presence[i][1]=true;
                        if(parts[2].equals("runtime")&&r.type=='D')presence[i][2]=true;if(parts[2].equals("configuration/settings.json")&&r.type=='F')presence[i][3]=true;
                    }
                    SessionArchive.checkSpace(staging,8192);
                    if(type=='D'){Files.createDirectory(target);journal(deferred,r);}
                    else if(type=='L'){Files.createFile(target);journal(deferred,r);}
                    else{
                        fileHash.reset();MessageDigest hash=fileHash;long left=r.size;
                        try(OutputStream raw=Files.newOutputStream(target,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);BufferedOutputStream out=new BufferedOutputStream(raw,65536)){
                            while(left>0){progress.check();int n=in.read(buffer,0,(int)Math.min(left,buffer.length));if(n<0)throw new EOFException("Truncated streaming file");if(n==0)continue;
                                SessionArchive.checkSpace(staging,n);out.write(buffer,0,n);hash.update(buffer,0,n);left-=n;completed+=n;progress.bytes(completed,bytes);
                            }
                            out.flush();
                        }
                        try(java.nio.channels.FileChannel f=java.nio.channels.FileChannel.open(target,StandardOpenOption.WRITE)){f.force(true);}
                        byte[] expected=new byte[32];in.readFully(expected);if(!MessageDigest.isEqual(expected,hash.digest()))throw new IOException("Streaming file checksum failed: "+r.name);SessionArchive.chmod(target,r.mode);
                    }
                    if(actual.count%1000==0)progress.update("Restoring and verifying · "+actual.count+" / "+count+" entries");
                }
                if(in.read()!=-1)throw new IOException("Unexpected trailing streaming payload");
            }
            if(actual.count!=count||actual.bytes!=bytes||actual.metadata!=metadata||!SessionArchive.hex(digest.digest()).equals(m.getProperty("payload_sha256")))throw new IOException("Streaming backup inventory or checksum mismatch");
            String[] flags={"present","work","runtime","settings"};
            for(int i=0;i<3;i++)for(int k=0;k<4;k++)if(!Boolean.toString(presence[i][k]).equals(m.getProperty(SessionArchive.WORLDS.get(i)+"."+flags[k])))throw new IOException("Streaming world presence mismatch");
            for(long end=deferred.length();end>0;){
                progress.check();deferred.seek(end-4);int size=deferred.readInt();if(size<21||size>MAX_TEXT*2+21||size>end-4)throw new IOException("Invalid finalization journal");
                end-=size+4;deferred.seek(end);Record r=header(deferred,deferred.readUnsignedByte());Path target=validate(stage,r);
                if(r.type=='L'){Files.delete(target);Files.createSymbolicLink(target,Paths.get(r.link));}else if(r.type=='D')SessionArchive.chmod(target,r.mode);else throw new IOException("Invalid deferred record");
            }
            for(String id:SessionArchive.WORLDS){Path world=stage.resolve("worlds/"+id);Files.createDirectories(world.resolve("rootfs"));for(String dir:new String[]{"run","incoming","exports"})Files.createDirectories(world.resolve("work/"+dir));}
            progress.update("Streaming session verified; ready to activate");return m;
        }finally{Files.deleteIfExists(journal.toPath());}
    }
    private StreamSessionArchive(){}
}
