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
    interface Progress { void update(String text); }
    static final long RESERVE=128L*1024*1024, MAX_BYTES=256L*1024*1024*1024;
    static final int MAX_FILES=200000;
    static final String INDEX="session-index.tsv", MANIFEST="session.properties";
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
        String name, type, hash, link; int mode; long size;
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
    static boolean excludedServerChild(Path relative) {
        if(relative.getNameCount()==0||relative.toString().isEmpty())return false;
        return Arrays.asList("bin","bin.staged","bin.previous","logs").contains(relative.getName(0).toString());
    }
    static void create(File rootfs,File work,File archive,String version,Progress progress)throws IOException {
        if(!Files.isRegularFile(rootfs.toPath().resolve("etc/trasc-runtime.json"),LinkOption.NOFOLLOW_LINKS))throw new IOException("Install the runtime before creating a complete session backup");
        File index=File.createTempFile("session-index-",".tsv",archive.getParentFile());
        long[] total={0}; int[] count={0};
        try(ZipOutputStream zip=new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(archive),1024*1024));
            BufferedWriter writer=Files.newBufferedWriter(index.toPath(),StandardCharsets.UTF_8)) {
            zip.setLevel(1); // Large maps/client content; prioritize device time and heat.
            for(Map.Entry<String,String> component:COMPONENTS.entrySet()) {
                String prefix=component.getKey();
                Path source=component.getValue().equals("@runtime")?rootfs.toPath():work.toPath().resolve(component.getValue());
                if(!Files.exists(source,LinkOption.NOFOLLOW_LINKS))continue;
                progress.update("Backing up "+prefix+"…");
                Files.walkFileTree(source,new SimpleFileVisitor<Path>() {
                    void add(Path path,BasicFileAttributes attrs)throws IOException {
                        if(++count[0]>MAX_FILES)throw new IOException("Session contains too many files");
                        Path relative=source.relativize(path);
                        Entry entry=new Entry();entry.name=prefix+(relative.toString().isEmpty()?"":"/"+relative.toString());
                        confined(work.toPath(),entry.name);
                        entry.hash="-";entry.link="";entry.size=0;entry.mode=0;
                        if(attrs.isSymbolicLink()) {
                            entry.type="L";entry.link=Files.readSymbolicLink(path).toString();
                        } else if(attrs.isDirectory()) {
                            entry.type="D";entry.mode=mode(path);
                        } else if(attrs.isRegularFile()) {
                            entry.type="F";entry.mode=mode(path);entry.size=attrs.size();
                            total[0]+=entry.size;
                            if(total[0]>MAX_BYTES)throw new IOException("Session exceeds 256 GB");
                            checkSpace(archive.getParentFile(),Math.min(entry.size,1024*1024));
                            MessageDigest digest=sha();long copied=0;
                            zip.putNextEntry(new ZipEntry(entry.name));
                            try(InputStream in=Files.newInputStream(path)) {
                                byte[] buffer=new byte[1024*1024];int n;
                                while((n=in.read(buffer))!=-1) {checkSpace(archive.getParentFile(),n);zip.write(buffer,0,n);digest.update(buffer,0,n);copied+=n;}
                            }
                            zip.closeEntry();
                            if(copied!=entry.size)throw new IOException("A session file changed during backup: "+entry.name);
                            entry.hash=hex(digest.digest());
                        } else throw new IOException("Stop all processes before backing up: "+entry.name);
                        writer.write(entry.line());
                        if(count[0]%250==0)progress.update("Backing up "+prefix+" · "+count[0]+" files");
                    }
                    @Override public FileVisitResult preVisitDirectory(Path p,BasicFileAttributes a)throws IOException {
                        if(prefix.equals("server")&&excludedServerChild(source.relativize(p)))return FileVisitResult.SKIP_SUBTREE;
                        add(p,a);return FileVisitResult.CONTINUE;
                    }
                    @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a)throws IOException {
                        if(!prefix.equals("server")||!excludedServerChild(source.relativize(p)))add(p,a);
                        return FileVisitResult.CONTINUE;
                    }
                });
            }
            writer.flush();
            zip.putNextEntry(new ZipEntry(INDEX));Files.copy(index.toPath(),zip);zip.closeEntry();
            Properties manifest=new Properties();
            manifest.setProperty("format","trasc-session-1");manifest.setProperty("architecture","arm64");
            manifest.setProperty("app_version",version);manifest.setProperty("created_utc",java.time.Instant.now().toString());
            manifest.setProperty("entries",String.valueOf(count[0]));manifest.setProperty("uncompressed_bytes",String.valueOf(total[0]));
            manifest.setProperty("database_state","clean_shutdown");
            manifest.setProperty("excluded","incoming archives, exports, temporary files, process IDs and API tokens");
            zip.putNextEntry(new ZipEntry(MANIFEST));manifest.store(zip,"TRASC complete session — keep private; includes accounts and credentials");zip.closeEntry();
        } catch(IOException e) {archive.delete();throw e;}
        finally {index.delete();}
        try(FileOutputStream out=new FileOutputStream(archive,true)){out.getFD().sync();}
        progress.update("Complete session ZIP ready");
    }
    static Path destination(Path stage,String name)throws IOException {
        for(Map.Entry<String,String> c:COMPONENTS.entrySet()) {
            if(name.equals(c.getKey())||name.startsWith(c.getKey()+"/")) {
                String suffix=name.substring(c.getKey().length());
                String path=c.getValue().equals("@runtime")?"rootfs"+suffix:"work/"+c.getValue()+suffix;
                return confined(stage,path);
            }
        }
        throw new IOException("Unknown session component: "+name);
    }
    static Properties restore(File archive,File staging,Progress progress)throws IOException {
        Path stage=staging.toPath();Files.createDirectories(stage);
        try(ZipFile zip=new ZipFile(archive)) {
            ZipEntry manifestEntry=zip.getEntry(MANIFEST),indexEntry=zip.getEntry(INDEX);
            if(manifestEntry==null||manifestEntry.getSize()>16384||indexEntry==null||indexEntry.getSize()>64L*1024*1024)throw new IOException("This ZIP is not a supported TRASC complete session");
            Properties manifest=new Properties();try(InputStream in=zip.getInputStream(manifestEntry)){manifest.load(in);}
            if(!"trasc-session-1".equals(manifest.getProperty("format"))||!"arm64".equals(manifest.getProperty("architecture"))||!"clean_shutdown".equals(manifest.getProperty("database_state")))throw new IOException("Unsupported session format, architecture or database state");
            Map<String,Entry> entries=new LinkedHashMap<>();Map<Path,Entry> targets=new HashMap<>();long total=0;
            try(BufferedReader reader=new BufferedReader(new InputStreamReader(zip.getInputStream(indexEntry),StandardCharsets.UTF_8))) {
                String line;
                while((line=reader.readLine())!=null) {
                    if(line.length()>32768||entries.size()>=MAX_FILES)throw new IOException("Session index exceeds limits");
                    String[] cols=line.split("\t",-1);if(cols.length!=6)throw new IOException("Invalid session file record");
                    Entry e=new Entry();e.type=cols[0];e.hash=cols[3];e.name=decode(cols[4]);e.link=decode(cols[5]);
                    try{e.mode=Integer.parseInt(cols[1]);e.size=Long.parseLong(cols[2]);}catch(NumberFormatException ex){throw new IOException("Invalid session metadata",ex);}
                    if(!Arrays.asList("F","D","L").contains(e.type)||e.mode<0||e.mode>0777||e.size<0||e.size>MAX_BYTES)throw new IOException("Invalid session file type, mode or size");
                    confined(stage,e.name);Path target=destination(stage,e.name);
                    if(entries.put(e.name,e)!=null||targets.put(target,e)!=null)throw new IOException("Duplicate session path: "+e.name);
                    if(e.type.equals("F")) {
                        ZipEntry member=zip.getEntry(e.name);
                        if(member==null||member.getSize()!=e.size||!e.hash.matches("[0-9a-f]{64}"))throw new IOException("Missing or damaged session file: "+e.name);
                        total+=e.size;if(total>MAX_BYTES)throw new IOException("Session exceeds supported size");
                    } else if(e.size!=0||!e.hash.equals("-"))throw new IOException("Invalid session link/directory metadata");
                    if(e.type.equals("L")&&(e.link.isEmpty()||e.link.indexOf('\0')>=0))throw new IOException("Invalid session symlink");
                }
            }
            try {
                if(total!=Long.parseLong(manifest.getProperty("uncompressed_bytes"))||entries.size()!=Integer.parseInt(manifest.getProperty("entries")))throw new IOException("Session inventory does not match its manifest");
            } catch(NumberFormatException ex){throw new IOException("Invalid session totals",ex);}
            Set<String> zipNames=new HashSet<>();Enumeration<? extends ZipEntry> members=zip.entries();
            while(members.hasMoreElements()) {
                String name=members.nextElement().getName();
                if(!zipNames.add(name)||(!name.equals(INDEX)&&!name.equals(MANIFEST)&&(!entries.containsKey(name)||!entries.get(name).type.equals("F"))))throw new IOException("Unexpected or duplicate ZIP member: "+name);
            }
            for(Map.Entry<Path,Entry> pair:targets.entrySet()) {
                for(Path parent=pair.getKey().getParent();parent!=null&&parent.startsWith(stage);parent=parent.getParent()) {
                    Entry ancestor=targets.get(parent);
                    if(ancestor!=null&&!ancestor.type.equals("D"))throw new IOException("A session file/link cannot contain other files: "+ancestor.name);
                }
            }
            checkSpace(staging,total);
            int count=0;
            for(Entry e:entries.values()) {
                Path target=destination(stage,e.name);
                if(e.type.equals("D")){Files.createDirectories(target);continue;}
                if(e.type.equals("L"))continue;
                Files.createDirectories(target.getParent());MessageDigest hash=sha();long written=0;
                try(InputStream in=zip.getInputStream(zip.getEntry(e.name));OutputStream out=Files.newOutputStream(target,StandardOpenOption.CREATE_NEW)) {
                    byte[] b=new byte[1024*1024];int n;
                    while((n=in.read(b))!=-1){written+=n;if(written>e.size)throw new IOException("Session file is larger than recorded");out.write(b,0,n);hash.update(b,0,n);}
                }
                if(written!=e.size||!hex(hash.digest()).equals(e.hash))throw new IOException("Session checksum failed: "+e.name);
                chmod(target,e.mode);
                if(++count%250==0)progress.update("Verifying and restoring · "+count+" files");
            }
            for(Entry e:entries.values())if(e.type.equals("L")) {
                Path target=destination(stage,e.name);Files.createDirectories(target.getParent());Files.createSymbolicLink(target,Paths.get(e.link));
            }
            // Apply directory modes after contents, deepest first (some directories are read-only).
            List<Entry> directories=new ArrayList<>();for(Entry e:entries.values())if(e.type.equals("D"))directories.add(e);
            directories.sort((a,b)->Integer.compare(b.name.length(),a.name.length()));
            for(Entry e:directories)chmod(destination(stage,e.name),e.mode);
            for(String required:new String[]{"rootfs/etc/trasc-runtime.json","work/settings.json"})
                if(!Files.isRegularFile(stage.resolve(required),LinkOption.NOFOLLOW_LINKS))throw new IOException("Incomplete session: "+required);
            Files.createDirectories(stage.resolve("work/run"));Files.createDirectories(stage.resolve("work/incoming"));Files.createDirectories(stage.resolve("work/exports"));
            progress.update("Session verified; ready to activate");return manifest;
        }
    }
}
