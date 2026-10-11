package io.github.russianranger.trasc;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.*;
import java.security.*;
import java.util.*;
import java.util.zip.*;

/** Offline ZIP64 session transport. No running guest or Android API is needed.
 * Regular files are hashed, permissions recorded, and symlinks restored last.
 * All restoration happens in a separate staging tree before RuntimeManager swaps it.
 */
final class SessionArchive {
    interface Progress { void update(String text); default void bytes(long done,long total) {} default void check()throws IOException {if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Session transfer cancelled");} }
    static final long RESERVE=128L*1024*1024, MAX_BYTES=256L*1024*1024*1024;
    static final int MAX_FILES=200000;
    static final long MAX_INDEX_BYTES=64L*1024*1024,MAX_ARCHIVE_BYTES=MAX_BYTES+MAX_BYTES/500+MAX_FILES*1024L+16L*1024*1024;
    static final String INDEX="session-index.tsv", MANIFEST="session.properties", ALL_FORMAT="trasc-all-sessions-2";
    static final List<String> WORLDS=Collections.unmodifiableList(Arrays.asList("custom","traditional","takp"));
    static final LinkedHashMap<String,String> COMPONENTS=new LinkedHashMap<>();
    static {
        COMPONENTS.put("runtime", "@runtime");
        COMPONENTS.put("database", "database");
        COMPONENTS.put("binaries/current", "server/bin");
        COMPONENTS.put("binaries/staged", "server/bin.staged");
        COMPONENTS.put("binaries/previous", "server/bin.previous");
        COMPONENTS.put("maps", "maps");
        COMPONENTS.put("logs/app", "logs");
        COMPONENTS.put("logs/server", "server/logs");
        COMPONENTS.put("server", "server");
        COMPONENTS.put("sources", "sources");
        COMPONENTS.put("builds", "builds");
        COMPONENTS.put("backups", "backups");
        COMPONENTS.put("client", "client");
        COMPONENTS.put("configuration/settings.json", "settings.json");
    }
    static final class Entry {
        String name, type, hash, link; byte[] digest;boolean zipped;int mode; long size;
        String line() {return type+"\t"+mode+"\t"+size+"\t"+hash+"\t"+encode(name)+"\t"+encode(link)+"\n";}
    }
    static String encode(String s) {return Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8));}
    static String decode(String s)throws IOException {
        try{return new String(Base64.getDecoder().decode(s),StandardCharsets.UTF_8);}
        catch(IllegalArgumentException e){throw new IOException("Invalid session index",e);}
    }
    static String hex(byte[] data){StringBuilder b=new StringBuilder();for(byte v:data)b.append(String.format(Locale.ROOT,"%02x",v&255));return b.toString();}
    static MessageDigest sha()throws IOException {try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new IOException(e);}}
    static Path confined(Path root,String name)throws IOException {
        // Debian multiarch files use colons (e.g. binutils-common:arm64.conffiles).
        // Reject drive-prefixed paths, not ordinary Linux filename characters.
        if(name.isEmpty()||name.startsWith("/")||name.contains("\\")||name.indexOf('\0')>=0||name.matches("(?s)^[A-Za-z]:.*"))throw new IOException("Unsafe session path: "+name);
        for(String p:name.split("/",-1))if(p.isEmpty()||p.equals(".")||p.equals(".."))throw new IOException("Unsafe session path: "+name);
        Path out=root.resolve(name).normalize();
        if(!out.startsWith(root))throw new IOException("Session path escapes staging");
        return out;
    }
    static int mode(Path path)throws IOException {
        int result=0;
        PosixFilePermission[] bits={PosixFilePermission.OTHERS_EXECUTE,PosixFilePermission.OTHERS_WRITE,PosixFilePermission.OTHERS_READ,
            PosixFilePermission.GROUP_EXECUTE,PosixFilePermission.GROUP_WRITE,PosixFilePermission.GROUP_READ,
            PosixFilePermission.OWNER_EXECUTE,PosixFilePermission.OWNER_WRITE,PosixFilePermission.OWNER_READ};
        Set<PosixFilePermission> actual=Files.getPosixFilePermissions(path,LinkOption.NOFOLLOW_LINKS);
        for(int i=0;i<bits.length;i++)if(actual.contains(bits[i]))result|=1<<i;
        return result;
    }
    static void chmod(Path path,int value)throws IOException {
        PosixFilePermission[] bits={PosixFilePermission.OTHERS_EXECUTE,PosixFilePermission.OTHERS_WRITE,PosixFilePermission.OTHERS_READ,
            PosixFilePermission.GROUP_EXECUTE,PosixFilePermission.GROUP_WRITE,PosixFilePermission.GROUP_READ,
            PosixFilePermission.OWNER_EXECUTE,PosixFilePermission.OWNER_WRITE,PosixFilePermission.OWNER_READ};
        Set<PosixFilePermission> set=EnumSet.noneOf(PosixFilePermission.class);
        for(int i=0;i<bits.length;i++)if((value&(1<<i))!=0)set.add(bits[i]);
        Files.setPosixFilePermissions(path,set);
    }
    static void checkSpace(File destination,long needed)throws IOException {
        if(needed<0||needed>destination.getUsableSpace()-RESERVE)throw new IOException("Not enough storage for the complete session. Free space and retry.");
    }
    /** Delete owned staging/rollback trees without following guest links; read-only archive modes are valid. */
    static void removeTree(File file)throws IOException {
        Path path=file.toPath();if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS))return;
        if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS)) {
            chmod(path,mode(path)|0700);
            try(DirectoryStream<Path> children=Files.newDirectoryStream(path)){for(Path child:children)removeTree(child.toFile());}
        }
        Files.delete(path);
    }
    static void syncDirectory(File dir)throws IOException {try(java.nio.channels.FileChannel channel=java.nio.channels.FileChannel.open(dir.toPath(),StandardOpenOption.READ)){channel.force(true);}}
    static void syncDirectories(File root,Progress progress)throws IOException {
        Files.walkFileTree(root.toPath(),new SimpleFileVisitor<Path>() {
            @Override public FileVisitResult postVisitDirectory(Path p,IOException error)throws IOException {if(error!=null)throw error;progress.check();syncDirectory(p.toFile());return FileVisitResult.CONTINUE;}
        });syncDirectory(root.getParentFile());
    }
    static boolean excludedServerChild(Path relative) {
        if(relative.getNameCount()==0||relative.toString().isEmpty())return false;
        return Arrays.asList("bin","bin.staged","bin.previous","logs").contains(relative.getName(0).toString());
    }
    static void create(File rootfs,File work,File archive,String version,Progress progress)throws IOException {
        create(rootfs,work,archive,version,"custom",progress);
    }
    static void requireProfile(File archive,String profile)throws IOException {
        WorldProfiles.valid(profile);
        try(ZipFile zip=openArchive(archive)) {
            ZipEntry entry=zip.getEntry(MANIFEST);
            if(entry==null||entry.getSize()>16384)throw new IOException("This ZIP is not a supported TRASC complete session");
            Properties info=new Properties();try(InputStream in=bounded(zip.getInputStream(entry),16384)){info.load(in);}
            if(allProfiles(info))throw new IOException("Use Restore all worlds for this complete all-world backup");
            if(!profile.equals(info.getProperty("profile","custom")))
                throw new IOException("This backup belongs to a different world profile. Switch to that profile before restoring.");
        }
    }
    static final class Source {
        final String name;final Path path;final boolean server;
        Source(String name,Path path,boolean server){this.name=name;this.path=path;this.server=server;}
    }
    static List<Source> sources(File rootfs,File work,String world) {
        List<Source> sources=new ArrayList<>();
        for(Map.Entry<String,String> c:COMPONENTS.entrySet())sources.add(new Source(world+c.getKey(),
            c.getValue().equals("@runtime")?rootfs.toPath():work.toPath().resolve(c.getValue()),c.getKey().equals("server")));
        return sources;
    }
    static long unsigned32(byte[] b,int at){return (b[at]&255L)|((b[at+1]&255L)<<8)|((b[at+2]&255L)<<16)|((b[at+3]&255L)<<24);}
    static int unsigned16(byte[] b,int at){return (b[at]&255)|((b[at+1]&255)<<8);}
    static long unsigned64(byte[] b,int at)throws IOException {long value=0;for(int i=7;i>=0;i--)value=(value<<8)|(b[at+i]&255L);if(value<0)throw new IOException("ZIP64 metadata exceeds supported range");return value;}
    static final class MemoryBudget {
        long headroom(){Runtime r=Runtime.getRuntime();return r.maxMemory()-(r.totalMemory()-r.freeMemory());}
        static long reserve(){return Math.min(16L*1024*1024,Runtime.getRuntime().maxMemory()/12);}
        void check()throws IOException {require(reserve());}
        void require(long needed)throws IOException {
            if(headroom()>=needed)return;
            System.gc();
            if(headroom()<needed)throw new IOException("Not enough app memory for this backup inventory. Close the client display and retry; existing worlds are unchanged.");
        }
    }
    static long centralBudget(){return Math.min(128L*1024*1024,Runtime.getRuntime().maxMemory()/3);}
    /** Bound eager ZipFile allocation before opening a central directory, including malformed ZIP64 input. */
    static ZipFile openArchive(File archive)throws IOException {
        try(RandomAccessFile file=new RandomAccessFile(archive,"r")) {
            long length=file.length();if(length<22||length>MAX_ARCHIVE_BYTES)throw new IOException("Archive size is outside supported limits");
            byte[] tail=new byte[(int)Math.min(length,65557)];file.seek(length-tail.length);file.readFully(tail);int end=-1;
            for(int i=tail.length-22;i>=0;i--)if(unsigned32(tail,i)==0x06054b50L&&i+22+unsigned16(tail,i+20)==tail.length){end=i;break;}
            if(end<0||unsigned16(tail,end+4)!=0||unsigned16(tail,end+6)!=0)throw new IOException("Unsupported or incomplete ZIP directory");
            long count=unsigned16(tail,end+10),onDisk=unsigned16(tail,end+8),central=unsigned32(tail,end+12),offset=unsigned32(tail,end+16),endOffset=length-tail.length+end;
            if(count==65535||central==0xffffffffL||offset==0xffffffffL) {
                if(endOffset<20)throw new IOException("Missing ZIP64 locator");byte[] locator=new byte[20];file.seek(endOffset-20);file.readFully(locator);
                if(unsigned32(locator,0)!=0x07064b50L||unsigned32(locator,4)!=0||unsigned32(locator,16)!=1)throw new IOException("Unsupported ZIP64 locator");
                long zip64=unsigned64(locator,8);if(zip64>endOffset-76)throw new IOException("Invalid ZIP64 directory offset");
                byte[] record=new byte[56];file.seek(zip64);file.readFully(record);
                if(unsigned32(record,0)!=0x06064b50L||unsigned64(record,4)<44||unsigned32(record,16)!=0||unsigned32(record,20)!=0)throw new IOException("Invalid ZIP64 directory");
                onDisk=unsigned64(record,24);count=unsigned64(record,32);central=unsigned64(record,40);offset=unsigned64(record,48);
            }
            if(count!=onDisk||count>MAX_FILES+2L||offset>length||central>length-offset||offset+central>endOffset)throw new IOException("ZIP directory exceeds supported inventory limits");
            if(central>centralBudget())throw new IOException("Backup file metadata exceeds this device's memory budget. Use a device with more app memory; no worlds were changed.");
            // ZipFile eagerly loads the CEN bytes and allocates member lookup tables. Check the
            // actual remaining heap as well as the process ceiling before that allocation.
            new MemoryBudget().require(central*2+count*8+MemoryBudget.reserve());
        }
        return new ZipFile(archive);
    }
    static Properties readManifest(File archive)throws IOException {
        try(ZipFile zip=openArchive(archive)) {
            ZipEntry e=zip.getEntry(MANIFEST);if(e==null||e.getSize()<0||e.getSize()>16384)throw new IOException("This ZIP is not a supported TRASC complete session");
            Properties p=new Properties();try(InputStream in=bounded(zip.getInputStream(e),16384)){p.load(in);}return p;
        }
    }
    static boolean allProfiles(Properties manifest){return ALL_FORMAT.equals(manifest.getProperty("format"));}
    static List<String> presentProfiles(Properties manifest)throws IOException {
        archiveProfiles(manifest);List<String> result=new ArrayList<>();
        for(String id:WORLDS){String value=manifest.getProperty(id+".present");if(!Arrays.asList("true","false").contains(value))throw new IOException("Invalid world presence metadata");if(value.equals("true"))result.add(id);}return result;
    }
    static List<String> includedComponents(Properties manifest)throws IOException {
        presentProfiles(manifest);List<String> result=new ArrayList<>();
        for(String id:WORLDS){if("true".equals(manifest.getProperty(id+".runtime")))result.add(id+"/rootfs");if("true".equals(manifest.getProperty(id+".work")))result.add(id+"/work");}return result;
    }
    static boolean hasData(List<Source> sources)throws IOException {
        for(Source source:sources)if(Files.exists(source.path,LinkOption.NOFOLLOW_LINKS)) {
            if(source.name.endsWith("/runtime"))return true;
            boolean[] found={false};Files.walkFileTree(source.path,new SimpleFileVisitor<Path>() {
                @Override public FileVisitResult preVisitDirectory(Path p,BasicFileAttributes a) {
                    return source.server&&excludedServerChild(source.path.relativize(p))?FileVisitResult.SKIP_SUBTREE:FileVisitResult.CONTINUE;
                }
                @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a) {
                    if(!source.server||!excludedServerChild(source.path.relativize(p))){found[0]=true;return FileVisitResult.TERMINATE;}return FileVisitResult.CONTINUE;
                }
            });if(found[0])return true;
        }return false;
    }
    static List<String> archiveProfiles(Properties manifest)throws IOException {
        if(!allProfiles(manifest))return Collections.singletonList(WorldProfiles.valid(manifest.getProperty("profile","custom")));
        if(!"custom,traditional,takp".equals(manifest.getProperty("profiles")))throw new IOException("Invalid all-world inventory");
        WorldProfiles.valid(manifest.getProperty("selected_profile"));return WORLDS;
    }
    /** Preflight uses uncompressed size plus ZIP overhead, independent of compression ratio. */
    static long preflight(List<Source> sources,File destination,Progress progress)throws IOException {return preflight(sources,destination,progress,true);}
    static long preflight(List<Source> sources,File destination,Progress progress,boolean localArchive)throws IOException {
        long[] bytes={0},central={512},index={0};int[] files={0};
        for(Source source:sources)if(Files.exists(source.path,LinkOption.NOFOLLOW_LINKS)) {
            progress.check();progress.update("Checking backup size · "+source.name);
            Files.walkFileTree(source.path,new SimpleFileVisitor<Path>() {
                void add(Path p,BasicFileAttributes a)throws IOException {
                    progress.check();String relative=source.path.relativize(p).toString(),name=source.name+(relative.isEmpty()?"":"/"+relative);
                    int nameBytes=name.getBytes(StandardCharsets.UTF_8).length;
                    long linkBytes=a.isSymbolicLink()?Files.readSymbolicLink(p).toString().getBytes(StandardCharsets.UTF_8).length:0;
                    index[0]+=100+4L*((nameBytes+2)/3)+4L*((linkBytes+2)/3);
                    if(index[0]>MAX_INDEX_BYTES)throw new IOException("Session index exceeds supported size");
                    if(a.isRegularFile()){central[0]+=46+nameBytes+28;if(central[0]>centralBudget())throw new IOException("Backup file metadata exceeds this device's memory budget; no archive was created");}
                    if(++files[0]>MAX_FILES)throw new IOException("Session contains too many files");
                    if(a.isRegularFile()){if(a.size()>MAX_BYTES-bytes[0])throw new IOException("Session exceeds supported size");bytes[0]+=a.size();}
                    else if(!a.isDirectory()&&!a.isSymbolicLink())throw new IOException("Stop all processes before backing up");
                }
                @Override public FileVisitResult preVisitDirectory(Path p,BasicFileAttributes a)throws IOException {
                    if(source.server&&excludedServerChild(source.path.relativize(p)))return FileVisitResult.SKIP_SUBTREE;
                    add(p,a);return FileVisitResult.CONTINUE;
                }
                @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a)throws IOException {
                    if(!source.server||!excludedServerChild(source.path.relativize(p)))add(p,a);return FileVisitResult.CONTINUE;
                }
            });
        }
        long overhead=bytes[0]/500+files[0]*1024L+16L*1024*1024;
        checkSpace(destination,localArchive?bytes[0]+overhead:files[0]*1024L+16L*1024*1024);return bytes[0];
    }
    static void createAll(File base,File archive,String version,String selected,File preferences,Progress progress)throws IOException {createAll(base,archive,version,selected,preferences,progress,null);}
    static void createAll(File base,File spool,String version,String selected,File preferences,Progress progress,OutputStream external)throws IOException {
        File archive=spool;
        WorldProfiles.valid(selected);WorldProfiles profiles=new WorldProfiles(base);List<Source> list=new ArrayList<>();
        Properties manifest=new Properties();manifest.setProperty("format",ALL_FORMAT);manifest.setProperty("profiles","custom,traditional,takp");manifest.setProperty("selected_profile",selected);
        for(String id:WORLDS) {
            File home=profiles.home(id),root=new File(home,"rootfs"),work=new File(home,"work");
            List<Source> worldSources=sources(root,work,"worlds/"+id+"/"),workSources=new ArrayList<>(worldSources.subList(1,worldSources.size()));
            boolean runtimePresent=Files.exists(root.toPath(),LinkOption.NOFOLLOW_LINKS),workPresent=hasData(workSources),present=runtimePresent||workPresent;
            if(runtimePresent)list.add(worldSources.get(0));if(workPresent)list.addAll(workSources);
            manifest.setProperty(id+".present",String.valueOf(present));manifest.setProperty(id+".work",String.valueOf(workPresent));
            manifest.setProperty(id+".runtime",String.valueOf(runtimePresent));
            manifest.setProperty(id+".settings",String.valueOf(workPresent&&Files.isRegularFile(new File(work,"settings.json").toPath(),LinkOption.NOFOLLOW_LINKS)));
        }
        if(preferences!=null)list.add(new Source("global/preferences.properties",preferences.toPath(),false));
        createSources(list,archive,version,manifest,progress,external);
    }
    static void create(File rootfs,File work,File archive,String version,String profile,Progress progress)throws IOException {
        WorldProfiles.valid(profile);
        if(!Files.isRegularFile(rootfs.toPath().resolve("etc/trasc-runtime.json"),LinkOption.NOFOLLOW_LINKS))throw new IOException("Install the runtime before creating a complete session backup");
        Properties manifest=new Properties();manifest.setProperty("format","trasc-session-1");manifest.setProperty("profile",profile);
        createSources(sources(rootfs,work,""),archive,version,manifest,progress);
    }
    static void createSources(List<Source> sources,File archive,String version,Properties manifest,Progress progress)throws IOException {createSources(sources,archive,version,manifest,progress,null);}
    static void createSources(List<Source> sources,File archive,String version,Properties manifest,Progress progress,OutputStream external)throws IOException {
        Files.createDirectories(archive.getParentFile().toPath());MemoryBudget memory=new MemoryBudget();memory.check();
        long estimated=preflight(sources,archive.getParentFile(),progress,external==null);progress.bytes(0,estimated);
        File index=File.createTempFile("session-index-",".tsv",archive.getParentFile());
        long[] total={0},completed={0},indexBytes={0}; int[] count={0};
        try(ZipOutputStream zip=new ZipOutputStream(new BufferedOutputStream(external==null?new FileOutputStream(archive):external,1024*1024));
            BufferedWriter writer=Files.newBufferedWriter(index.toPath(),StandardCharsets.UTF_8)) {
            zip.setLevel(1); // Large maps/client content; prioritize device time and heat.
            byte[] transferBuffer=new byte[1024*1024];
            for(Source component:sources) {
                String prefix=component.name;
                Path source=component.path;
                if(!Files.exists(source,LinkOption.NOFOLLOW_LINKS))continue;
                progress.update("Backing up "+prefix+"…");
                Files.walkFileTree(source,new SimpleFileVisitor<Path>() {
                    void add(Path path,BasicFileAttributes attrs)throws IOException {
                        progress.check();if(count[0]%250==0)memory.check();if(++count[0]>MAX_FILES)throw new IOException("Session contains too many files");
                        Path relative=source.relativize(path);
                        Entry entry=new Entry();entry.name=prefix+(relative.toString().isEmpty()?"":"/"+relative.toString());
                        confined(archive.getParentFile().toPath(),entry.name);
                        entry.hash="-";entry.link="";entry.size=0;entry.mode=0;
                        if(attrs.isSymbolicLink()) {
                            entry.type="L";entry.link=Files.readSymbolicLink(path).toString();
                        } else if(attrs.isDirectory()) {
                            entry.type="D";entry.mode=mode(path);
                        } else if(attrs.isRegularFile()) {
                            entry.type="F";entry.mode=mode(path);entry.size=attrs.size();
                            total[0]+=entry.size;
                            if(total[0]>MAX_BYTES)throw new IOException("Session exceeds 256 GB");
                            if(external==null)checkSpace(archive.getParentFile(),Math.min(entry.size,1024*1024));
                            MessageDigest digest=sha();long copied=0;
                            zip.putNextEntry(new ZipEntry(entry.name));
                            try(InputStream in=Files.newInputStream(path)) {
                                int n;
                                while((n=in.read(transferBuffer))!=-1) {progress.check();if(external==null)checkSpace(archive.getParentFile(),n);zip.write(transferBuffer,0,n);digest.update(transferBuffer,0,n);copied+=n;completed[0]+=n;progress.bytes(completed[0],estimated);}
                            }
                            zip.closeEntry();
                            if(copied!=entry.size)throw new IOException("A session file changed during backup: "+entry.name);
                            entry.hash=hex(digest.digest());
                        } else throw new IOException("Stop all processes before backing up: "+entry.name);
                        String record=entry.line();if(record.length()>32769)throw new IOException("Session record exceeds supported length");
                        indexBytes[0]+=record.getBytes(StandardCharsets.UTF_8).length;if(indexBytes[0]>MAX_INDEX_BYTES)throw new IOException("Session index exceeds supported size");writer.write(record);
                        if(count[0]%250==0)progress.update("Backing up "+prefix+" · "+count[0]+" files");
                    }
                    @Override public FileVisitResult preVisitDirectory(Path p,BasicFileAttributes a)throws IOException {
                        if(component.server&&excludedServerChild(source.relativize(p)))return FileVisitResult.SKIP_SUBTREE;
                        add(p,a);return FileVisitResult.CONTINUE;
                    }
                    @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a)throws IOException {
                        if(!component.server||!excludedServerChild(source.relativize(p)))add(p,a);
                        return FileVisitResult.CONTINUE;
                    }
                });
            }
            writer.flush();
            zip.putNextEntry(new ZipEntry(INDEX));Files.copy(index.toPath(),zip);zip.closeEntry();
            manifest.setProperty("architecture","arm64");
            manifest.setProperty("app_version",version);manifest.setProperty("created_utc",java.time.Instant.now().toString());
            manifest.setProperty("entries",String.valueOf(count[0]));manifest.setProperty("uncompressed_bytes",String.valueOf(total[0]));
            manifest.setProperty("database_state","clean_shutdown");
            manifest.setProperty("excluded","incoming archives, exports, temporary files, process IDs and API tokens");
            zip.putNextEntry(new ZipEntry(MANIFEST));manifest.store(zip,"TRASC complete session — keep private; includes accounts and credentials");zip.closeEntry();
        } catch(IOException e) {if(external==null)archive.delete();throw e;}
        finally {index.delete();}
        if(external==null)try(FileOutputStream out=new FileOutputStream(archive,true)){out.getFD().sync();}
        progress.update("Complete session ZIP ready");
    }
    static Path destination(Path stage,String name)throws IOException {
        if(name.equals("global/preferences.properties"))return confined(stage,name);
        if(name.startsWith("worlds/")) {
            String[] parts=name.split("/",3);if(parts.length!=3)throw new IOException("Invalid world component");
            WorldProfiles.valid(parts[1]);if(parts[2].startsWith("worlds/")||parts[2].startsWith("global/"))throw new IOException("Nested world/global namespace is not supported");
            return destination(confined(stage,"worlds/"+parts[1]),parts[2]);
        }
        for(Map.Entry<String,String> c:COMPONENTS.entrySet()) {
            if(name.equals(c.getKey())||name.startsWith(c.getKey()+"/")) {
                String suffix=name.substring(c.getKey().length());
                if(c.getKey().equals("server")&&!suffix.isEmpty()&&excludedServerChild(Paths.get(suffix.substring(1))))throw new IOException("Server component overlaps separately archived binaries/logs");
                String path=c.getValue().equals("@runtime")?"rootfs"+suffix:"work/"+c.getValue()+suffix;
                return confined(stage,path);
            }
        }
        throw new IOException("Unknown session component: "+name);
    }
    static InputStream bounded(InputStream input,long max) {
        return new FilterInputStream(input){long left=max;
            @Override public int read()throws IOException {int n=super.read();if(n!=-1&&--left<0)throw new IOException("Session metadata exceeds limits");return n;}
            @Override public int read(byte[] b,int off,int len)throws IOException {
                int n=in.read(b,off,(int)Math.min(len,left+1));if(n>0){left-=n;if(left<0)throw new IOException("Session metadata exceeds limits");}return n;
            }
        };
    }
    static String limitedLine(Reader reader)throws IOException {
        StringBuilder line=new StringBuilder();int c;
        while((c=reader.read())!=-1){if(c=='\n')break;if(line.length()>=32768)throw new IOException("Session record exceeds limits");line.append((char)c);}
        return c==-1&&line.length()==0?null:line.toString();
    }
    static Properties restore(File archive,File staging,Progress progress)throws IOException {
        Path stage=staging.toPath();Files.createDirectories(stage);MemoryBudget memory=new MemoryBudget();memory.check();
        try(ZipFile zip=openArchive(archive)) {
            ZipEntry manifestEntry=zip.getEntry(MANIFEST),indexEntry=zip.getEntry(INDEX);
            if(manifestEntry==null||manifestEntry.getSize()>16384||indexEntry==null||indexEntry.getSize()>64L*1024*1024)throw new IOException("This ZIP is not a supported TRASC complete session");
            Properties manifest=new Properties();try(InputStream in=bounded(zip.getInputStream(manifestEntry),16384)){manifest.load(in);}
            if((!"trasc-session-1".equals(manifest.getProperty("format"))&&!allProfiles(manifest))||!"arm64".equals(manifest.getProperty("architecture"))||!"clean_shutdown".equals(manifest.getProperty("database_state")))throw new IOException("Unsupported session format, architecture or database state");
            archiveProfiles(manifest);
            if(allProfiles(manifest))presentProfiles(manifest);
            if(allProfiles(manifest))for(String id:WORLDS)for(String key:new String[]{"runtime","work","settings"})
                if(!Arrays.asList("true","false").contains(manifest.getProperty(id+"."+key)))throw new IOException("Invalid world presence metadata");
            Map<String,Entry> entries=new LinkedHashMap<>();long total=0;
            try(BufferedReader reader=new BufferedReader(new InputStreamReader(bounded(zip.getInputStream(indexEntry),64L*1024*1024),StandardCharsets.UTF_8))) {
                String line;
                while((line=limitedLine(reader))!=null) {
                    if(line.length()>32768||entries.size()>=MAX_FILES)throw new IOException("Session index exceeds limits");
                    progress.check();if(entries.size()%250==0)memory.check();String[] cols=line.split("\t",-1);if(cols.length!=6)throw new IOException("Invalid session file record");
                    Entry e=new Entry();e.type=cols[0];e.hash=cols[3];e.name=decode(cols[4]);e.link=decode(cols[5]);
                    try{e.mode=Integer.parseInt(cols[1]);e.size=Long.parseLong(cols[2]);}catch(NumberFormatException ex){throw new IOException("Invalid session metadata",ex);}
                    if(!Arrays.asList("F","D","L").contains(e.type)||e.mode<0||e.mode>0777||e.size<0||e.size>MAX_BYTES)throw new IOException("Invalid session file type, mode or size");
                    if(allProfiles(manifest)?(!e.name.startsWith("worlds/")&&!e.name.equals("global/preferences.properties")):e.name.startsWith("worlds/")||e.name.startsWith("global/"))throw new IOException("Session component belongs to the wrong format");
                    confined(stage,e.name);Path target=destination(stage,e.name);
                    if((e.name.equals("runtime")||e.name.matches("worlds/(custom|traditional|takp)/runtime"))&&!e.type.equals("D"))throw new IOException("Runtime root must be a directory");
                    if(entries.put(e.name,e)!=null)throw new IOException("Duplicate session path: "+e.name);
                    e.type=e.type.equals("F")?"F":e.type.equals("D")?"D":"L";if(e.link.isEmpty())e.link="";
                    if(e.type.equals("F")) {
                        ZipEntry member=zip.getEntry(e.name);
                        if(member==null||member.getSize()!=e.size||!e.hash.matches("[0-9a-f]{64}"))throw new IOException("Missing or damaged session file: "+e.name);
                        e.digest=new byte[32];for(int h=0;h<32;h++)e.digest[h]=(byte)Integer.parseInt(e.hash.substring(h*2,h*2+2),16);e.hash=null;
                        total+=e.size;if(total>MAX_BYTES)throw new IOException("Session exceeds supported size");
                    } else if(e.size!=0||!e.hash.equals("-"))throw new IOException("Invalid session link/directory metadata");
                    if(e.type.equals("L")&&(e.link.isEmpty()||e.link.indexOf('\0')>=0))throw new IOException("Invalid session symlink");
                }
            }
            if(allProfiles(manifest))for(String id:WORLDS) {
                boolean any=false,workAny=false;for(String name:entries.keySet())if(name.startsWith("worlds/"+id+"/")){any=true;if(!name.equals("worlds/"+id+"/runtime")&&!name.startsWith("worlds/"+id+"/runtime/"))workAny=true;}
                if(Boolean.parseBoolean(manifest.getProperty(id+".work"))!=workAny)throw new IOException("Work presence does not match its inventory: "+id);
                if(Boolean.parseBoolean(manifest.getProperty(id+".present"))!=any)throw new IOException("World presence does not match its inventory: "+id);
                Entry runtime=entries.get("worlds/"+id+"/runtime"),settings=entries.get("worlds/"+id+"/configuration/settings.json");
                if(Boolean.parseBoolean(manifest.getProperty(id+".runtime"))!=(runtime!=null&&runtime.type.equals("D")))throw new IOException("Runtime presence does not match the world inventory: "+id);
                if(Boolean.parseBoolean(manifest.getProperty(id+".settings"))!=(settings!=null&&settings.type.equals("F")))throw new IOException("Settings presence does not match the world inventory: "+id);
                if(runtime==null)for(String name:entries.keySet())if(name.startsWith("worlds/"+id+"/runtime/"))throw new IOException("Runtime namespace is missing its root directory: "+id);
            }
            try {
                if(total!=Long.parseLong(manifest.getProperty("uncompressed_bytes"))||entries.size()!=Integer.parseInt(manifest.getProperty("entries")))throw new IOException("Session inventory does not match its manifest");
            } catch(NumberFormatException ex){throw new IOException("Invalid session totals",ex);}
            boolean indexSeen=false,manifestSeen=false;Enumeration<? extends ZipEntry> members=zip.entries();
            while(members.hasMoreElements()) {
                String name=members.nextElement().getName();
                if(name.equals(INDEX)){if(indexSeen)throw new IOException("Duplicate ZIP index");indexSeen=true;continue;}
                if(name.equals(MANIFEST)){if(manifestSeen)throw new IOException("Duplicate ZIP manifest");manifestSeen=true;continue;}
                Entry e=entries.get(name);if(e==null||!e.type.equals("F")||e.zipped)throw new IOException("Unexpected or duplicate ZIP member: "+name);e.zipped=true;
            }
            for(String name:entries.keySet())for(int at=name.lastIndexOf('/');at>=0;at=name.lastIndexOf('/',at-1)) {
                Entry ancestor=entries.get(name.substring(0,at));if(ancestor!=null&&!ancestor.type.equals("D"))throw new IOException("A session file/link cannot contain other files: "+ancestor.name);
            }
            checkSpace(staging,total+entries.size()*8192L+16L*1024*1024);
            progress.bytes(0,total);long completed=0;int count=0;
            byte[] transferBuffer=new byte[1024*1024];
            for(Entry e:entries.values()) {
                progress.check();memory.check();Path target=destination(stage,e.name);
                if(e.type.equals("D")){checkSpace(staging,8192);Files.createDirectories(target);continue;}
                if(e.type.equals("L"))continue;
                Files.createDirectories(target.getParent());MessageDigest hash=sha();long written=0;
                Files.createFile(target);
                try(InputStream in=zip.getInputStream(zip.getEntry(e.name));FileOutputStream out=new FileOutputStream(target.toFile())) {
                    int n;
                    while((n=in.read(transferBuffer))!=-1){progress.check();checkSpace(staging,n);written+=n;if(written>e.size)throw new IOException("Session file is larger than recorded");out.write(transferBuffer,0,n);hash.update(transferBuffer,0,n);completed+=n;progress.bytes(completed,total);}
                    out.getFD().sync();
                }
                if(written!=e.size||!MessageDigest.isEqual(hash.digest(),e.digest))throw new IOException("Session checksum failed: "+e.name);
                chmod(target,e.mode);
                if(++count%250==0)progress.update("Verifying and restoring · "+count+" files");
            }
            for(Entry e:entries.values())if(e.type.equals("L")) {
                Path target=destination(stage,e.name);checkSpace(staging,8192);Files.createDirectories(target.getParent());Files.createSymbolicLink(target,Paths.get(e.link));
            }
            // Apply directory modes after contents, deepest first (some directories are read-only).
            List<Entry> directories=new ArrayList<>();for(Entry e:entries.values())if(e.type.equals("D"))directories.add(e);
            directories.sort((a,b)->Integer.compare(b.name.length(),a.name.length()));
            for(Entry e:directories)chmod(destination(stage,e.name),e.mode);
            if(allProfiles(manifest)) {
                for(String id:WORLDS) {
                    Path world=stage.resolve("worlds/"+id);Files.createDirectories(world.resolve("rootfs"));Files.createDirectories(world.resolve("work"));
                    if(Boolean.parseBoolean(manifest.getProperty(id+".settings"))&&!Files.isRegularFile(world.resolve("work/settings.json"),LinkOption.NOFOLLOW_LINKS))throw new IOException("Incomplete world settings: "+id);
                    for(String dir:new String[]{"run","incoming","exports"})Files.createDirectories(world.resolve("work/"+dir));
                }
            } else {
                for(String required:new String[]{"rootfs/etc/trasc-runtime.json","work/settings.json"})
                    if(!Files.isRegularFile(stage.resolve(required),LinkOption.NOFOLLOW_LINKS))throw new IOException("Incomplete session: "+required);
                for(String dir:new String[]{"run","incoming","exports"})Files.createDirectories(stage.resolve("work/"+dir));
            }
            progress.update("Session verified; ready to activate");return manifest;
        }
    }
}
