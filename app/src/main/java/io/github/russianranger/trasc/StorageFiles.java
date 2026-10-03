package io.github.russianranger.trasc;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.BasicFileAttributeView;
import java.security.*;
import java.util.*;

/** Explicit cleanup of retained copies. The caller must reserve both stopped runtimes and transfers. */
final class StorageFiles {
    private static final LinkOption[] NOFOLLOW={LinkOption.NOFOLLOW_LINKS};
    private static final int MAX_NODES=100000, MAX_PATHS=500, MAX_CONTROL=1048576;
    private static final String DB="database-[0-9]{8}-[0-9]{6}-[0-9a-f]{4}\\.sql\\.gz";
    private static final String PLAYERS="players-[0-9]{8}-[0-9]{6}-[0-9a-f]{8}\\.zip";
    private static final Set<String> HIDDEN=new HashSet<>(Arrays.asList("settings.json","mysql.cnf","mysql.sock","mysql.pid"));
    private static final Set<String> RECOVERY=new HashSet<>(Arrays.asList("nektulos","client-spell-test","content","ferry-quests","spire","client-setup"));

    static final class Entry {
        final String name,path,protection;
        final boolean directory,deletable;
        final long size;
        Entry(String name,String path,boolean directory,long size,String protection){
            this.name=name;this.path=path;this.directory=directory;this.size=size;this.protection=protection;deletable=protection.isEmpty();
        }
    }
    static final class Page {
        final String path;
        final List<Entry> items;
        final int total,offset,limit;
        final Integer nextOffset;
        Page(String path,List<Entry> items,int total,int offset,int limit){
            this.path=path;this.items=Collections.unmodifiableList(items);this.total=total;this.offset=offset;this.limit=limit;
            nextOffset=offset+limit<total?offset+limit:null;
        }
    }
    static final class Preview {
        final String token;
        final List<String> paths;
        final long bytes,files;
        Preview(String token,List<String> paths,long bytes,long files){this.token=token;this.paths=Collections.unmodifiableList(paths);this.bytes=bytes;this.files=files;}
    }
    static final class Result {
        final long bytes,files;
        final List<String> paths;
        Result(long bytes,long files,List<String> paths){this.bytes=bytes;this.files=files;this.paths=Collections.unmodifiableList(paths);}
    }
    /** Some earlier entries may already be gone; the UI must refresh and never report full success. */
    static final class DeleteException extends IOException {
        final long bytes,files;
        final List<String> paths;
        DeleteException(String message,IOException cause,long bytes,long files,List<String> paths){
            super(message,cause);this.bytes=bytes;this.files=files;this.paths=Collections.unmodifiableList(new ArrayList<>(paths));
        }
    }

    static Page browse(File work,String path,String query,int offset,int limit)throws IOException {
        if(offset<0||limit<1||limit>2000)throw new IOException("Invalid file page");
        if(query==null)query="";
        if(query.length()>256)throw new IOException("File search is limited to 256 characters");
        String relative=normalize(path,true),needle=query.trim().toLowerCase(Locale.ROOT);
        Store store=new Store(work);Path folder=store.resolve(relative);store.requireDirectory(folder);
        Policy policy=new Policy(store);List<Entry> entries=new ArrayList<>();int examined=0;
        try(DirectoryStream<Path> children=Files.newDirectoryStream(folder)) {
            for(Path child:children) {
                if(++examined>MAX_NODES)throw new IOException("This folder exceeds the supported file count");
                String name=child.getFileName().toString();
                if(HIDDEN.contains(name)||!name.toLowerCase(Locale.ROOT).contains(needle))continue;
                BasicFileAttributes a;
                try{a=store.attributes(child);}catch(NoSuchFileException gone){continue;}
                if(a.isSymbolicLink())continue; // Existing browser never exposes link targets.
                String item=store.relative(child),reason=policy.reason(item),error=policy.block;
                long size=a.isRegularFile()?a.size():0;
                if(reason.isEmpty()&&!error.isEmpty())reason=error;
                // Folder sizes and every descendant's eligibility are measured only by explicit review.
                entries.add(new Entry(name,item,a.isDirectory(),size,reason));
            }
        }catch(DirectoryIteratorException e){throw e.getCause();}
        entries.sort(Comparator.comparing((Entry e)->!e.directory).thenComparing(e->e.name.toLowerCase(Locale.ROOT)).thenComparing(e->e.name));
        int total=entries.size();offset=Math.min(offset,total==0?0:((total-1)/limit)*limit);
        store.requireDirectory(folder);
        return new Page(relative,new ArrayList<>(entries.subList(offset,Math.min(total,offset+limit))),total,offset,limit);
    }

    static Preview preview(File work,List<String> paths)throws IOException {
        Store store=new Store(work);List<String> selected=selection(paths);Policy policy=new Policy(store);policy.requireReady();
        Snapshot snapshot=store.snapshot(selected,policy);
        // A journal or active generation changed while measuring: require another review.
        if(!policy.signature.equals(new Policy(store).signature))throw new IOException("Storage protection changed. Refresh and review the files again");
        return new Preview(snapshot.token,selected,snapshot.bytes,snapshot.files);
    }

    static Result delete(File work,List<String> paths,String token)throws IOException {
        if(token==null||!token.matches("[0-9a-f]{64}"))throw new IOException("Review the selected files before deleting them");
        Store store=new Store(work);List<String> selected=selection(paths);Policy policy=new Policy(store);policy.requireReady();
        Snapshot snapshot=store.snapshot(selected,policy); // Preflight every selected tree before the first deletion.
        if(!MessageDigest.isEqual(token.getBytes(StandardCharsets.US_ASCII),snapshot.token.getBytes(StandardCharsets.US_ASCII)))
            throw new IOException("The selected files changed after review. Refresh and review them again");
        Policy current=new Policy(store);current.requireReady();
        if(!policy.signature.equals(current.signature))throw new IOException("Storage protection changed. Refresh and review the files again");
        Counter removed=new Counter();List<String> complete=new ArrayList<>();
        try {
            for(Node root:snapshot.roots) {
                store.requireRoot();
                try(Handles handles=store.parent(root.path)) {store.remove(root,handles.directory,removed);}
                complete.add(root.path);
            }
            return new Result(removed.bytes,removed.files,complete);
        }catch(IOException e){
            throw new DeleteException("Deletion stopped: "+e.getMessage()+". "+removed.files+" files were removed; refresh to review what remains",e,removed.bytes,removed.files,complete);
        }
    }

    private static String normalize(String value,boolean root)throws IOException {
        if(value==null||value.equals("."))value="";
        if(value.length()>4096||value.indexOf('\\')>=0||value.indexOf('\0')>=0||value.startsWith("/"))throw new IOException("Invalid storage path");
        if(value.isEmpty()){if(root)return "";throw new IOException("The workspace root is protected");}
        for(String part:value.split("/",-1))if(part.isEmpty()||part.equals(".")||part.equals(".."))throw new IOException("Invalid storage path");
        return value;
    }
    private static List<String> selection(List<String> values)throws IOException {
        if(values==null||values.isEmpty()||values.size()>MAX_PATHS)throw new IOException("Select between 1 and "+MAX_PATHS+" files or folders");
        TreeSet<String> paths=new TreeSet<>();
        for(String value:values)if(!paths.add(normalize(value,false)))throw new IOException("A file was selected more than once");
        for(String path:paths) {
            String parent=path;
            while(parent.contains("/")){parent=parent.substring(0,parent.lastIndexOf('/'));if(paths.contains(parent))throw new IOException("Select a folder or its contents, without overlapping selections");}
        }
        return new ArrayList<>(paths);
    }
    private static boolean within(String path,String prefix){return path.equals(prefix)||path.startsWith(prefix+"/");}
    private static MessageDigest digest(){try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}
    private static void hash(MessageDigest digest,String value){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);digest.update(Integer.toString(bytes.length).getBytes(StandardCharsets.US_ASCII));digest.update((byte)':');digest.update(bytes);}
    private static String hex(byte[] bytes){StringBuilder result=new StringBuilder(bytes.length*2);for(byte b:bytes)result.append(String.format(Locale.ROOT,"%02x",b&255));return result.toString();}
    private static final class Counter {long bytes,files;int nodes;}
    private static final class Node {
        final String path;final BasicFileAttributes attributes;final List<Node> children=new ArrayList<>();
        Node(String path,BasicFileAttributes attributes){this.path=path;this.attributes=attributes;}
    }
    private static final class Snapshot {
        final List<Node> roots;final String token;final long bytes,files;
        Snapshot(List<Node> roots,String token,Counter count){this.roots=roots;this.token=token;bytes=count.bytes;files=count.files;}
    }

    private static final class Store {
        final Path root;final BasicFileAttributes identity;
        Store(File work)throws IOException {
            if(Files.isSymbolicLink(work.toPath()))throw new IOException("The workspace must not be a symbolic link");
            root=work.getCanonicalFile().toPath();identity=Files.readAttributes(root,BasicFileAttributes.class,NOFOLLOW);
            if(!identity.isDirectory())throw new IOException("The workspace is unavailable");
        }
        Path resolve(String path){return path.isEmpty()?root:root.resolve(path);}
        String relative(Path path){return root.relativize(path).toString().replace(File.separatorChar,'/');}
        void requireRoot()throws IOException {
            BasicFileAttributes now=Files.readAttributes(root,BasicFileAttributes.class,NOFOLLOW);
            if(!now.isDirectory()||!sameIdentity(identity,now))throw new IOException("The active workspace changed");
        }
        void ancestors(Path target)throws IOException {
            requireRoot();Path next=root;
            for(Path component:root.relativize(target.getParent()==null?target:target.getParent())) {
                next=next.resolve(component);BasicFileAttributes a=Files.readAttributes(next,BasicFileAttributes.class,NOFOLLOW);
                if(!a.isDirectory()||a.isSymbolicLink())throw new IOException("Linked or missing storage folder: "+relative(next));
            }
        }
        BasicFileAttributes attributes(Path path)throws IOException {if(!path.equals(root))ancestors(path);else requireRoot();return Files.readAttributes(path,BasicFileAttributes.class,NOFOLLOW);}
        void requireDirectory(Path path)throws IOException {BasicFileAttributes a=attributes(path);if(!a.isDirectory()||a.isSymbolicLink())throw new IOException("Choose a real storage folder");}
        boolean realFile(String path)throws IOException {try{return attributes(resolve(path)).isRegularFile();}catch(NoSuchFileException e){return false;}}
        boolean realDirectory(String path)throws IOException {try{return attributes(resolve(path)).isDirectory();}catch(NoSuchFileException e){return false;}}
        boolean exists(String path)throws IOException {try{attributes(resolve(path));return true;}catch(NoSuchFileException e){return false;}}
        Handles parent(String relative)throws IOException {
            ancestors(resolve(relative));Handles chain=new Handles();
            try {
                DirectoryStream<Path> directory=Files.newDirectoryStream(root);chain.all.add(directory);
                if(directory instanceof SecureDirectoryStream) {
                    chain.directory=(SecureDirectoryStream<Path>)directory;
                    Path parent=Paths.get(relative).getParent();
                    if(parent!=null)for(Path part:parent) {
                        SecureDirectoryStream<Path> child=chain.directory.newDirectoryStream(part,LinkOption.NOFOLLOW_LINKS);
                        chain.all.add(child);chain.directory=child;
                    }
                }
                return chain;
            }catch(IOException e){chain.close();throw e;}
        }
        BasicFileAttributes read(String path,SecureDirectoryStream<Path> parent)throws IOException {
            if(parent==null)return attributes(resolve(path));
            BasicFileAttributeView view=parent.getFileAttributeView(Paths.get(path).getFileName(),BasicFileAttributeView.class,NOFOLLOW);
            if(view==null)throw new IOException("Cannot inspect storage file: "+path);
            return view.readAttributes();
        }
        Snapshot snapshot(List<String> selected,Policy policy)throws IOException {
            MessageDigest digest=digest();hash(digest,"TRASC cleanup v1");hash(digest,root.toString());metadata(digest,"workspace",identity);hash(digest,policy.signature);
            for(String selectedPath:selected)hash(digest,selectedPath);
            Counter count=new Counter();List<Node> roots=new ArrayList<>();
            for(String selectedPath:selected)try(Handles handles=parent(selectedPath)) {roots.add(scan(selectedPath,handles.directory,policy,count,digest));}
            requireRoot();return new Snapshot(roots,hex(digest.digest()),count);
        }
        Node scan(String path,SecureDirectoryStream<Path> parent,Policy policy,Counter count,MessageDigest digest)throws IOException {
            if(++count.nodes>MAX_NODES)throw new IOException("Selection exceeds "+MAX_NODES+" entries. Select fewer folders");
            String protectedReason=policy.reason(path);if(!protectedReason.isEmpty())throw new IOException(path+": "+protectedReason);
            BasicFileAttributes a=read(path,parent);
            if(!a.isDirectory()&&!a.isRegularFile()&&!a.isSymbolicLink())throw new IOException("Special files are protected: "+path);
            Node node=new Node(path,a);metadata(digest,path,a);
            if(a.isDirectory()) {
                try(DirectoryStream<Path> children=parent==null?Files.newDirectoryStream(resolve(path)):parent.newDirectoryStream(Paths.get(path).getFileName(),LinkOption.NOFOLLOW_LINKS)) {
                    SecureDirectoryStream<Path> secure=children instanceof SecureDirectoryStream?(SecureDirectoryStream<Path>)children:null;
                    List<String> names=new ArrayList<>();
                    for(Path child:children){if(names.size()+count.nodes>=MAX_NODES)throw new IOException("Selection exceeds "+MAX_NODES+" entries. Select fewer folders");names.add(child.getFileName().toString());}
                    Collections.sort(names);
                    for(String name:names)node.children.add(scan(path+"/"+name,secure,policy,count,digest));
                }catch(DirectoryIteratorException e){throw e.getCause();}
                if(!unchanged(a,read(path,parent)))throw new IOException("Folder changed during review: "+path);
            } else {count.files++;if(a.isRegularFile())count.bytes=Math.addExact(count.bytes,a.size());}
            return node;
        }
        void remove(Node node,SecureDirectoryStream<Path> parent,Counter removed)throws IOException {
            BasicFileAttributes now=read(node.path,parent);
            if(!unchanged(node.attributes,now))throw new IOException("File changed after review: "+node.path);
            Path name=Paths.get(node.path).getFileName();
            if(now.isDirectory()) {
                try(DirectoryStream<Path> directory=parent==null?Files.newDirectoryStream(resolve(node.path)):parent.newDirectoryStream(name,LinkOption.NOFOLLOW_LINKS)) {
                    SecureDirectoryStream<Path> secure=directory instanceof SecureDirectoryStream?(SecureDirectoryStream<Path>)directory:null;
                    for(Node child:node.children)remove(child,secure,removed);
                }
                BasicFileAttributes after=read(node.path,parent);
                if(!after.isDirectory()||!sameIdentity(now,after))throw new IOException("Folder changed during deletion: "+node.path);
                if(parent!=null)parent.deleteDirectory(name);else {ancestors(resolve(node.path));Files.delete(resolve(node.path));}
            }else {
                if(parent!=null)parent.deleteFile(name);else {ancestors(resolve(node.path));Files.delete(resolve(node.path));}
                removed.files++;if(now.isRegularFile())removed.bytes+=now.size();
            }
        }
        Map<String,Object> json(String path,MessageDigest signature)throws IOException {
            Path target=resolve(path);BasicFileAttributes before=attributes(target);
            if(!before.isRegularFile()||before.size()>MAX_CONTROL)throw new IOException("Invalid recovery record: "+path);
            byte[] bytes;
            try(InputStream input=Files.newInputStream(target,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS);ByteArrayOutputStream output=new ByteArrayOutputStream()) {
                byte[] buffer=new byte[4096];int n,total=0;
                while((n=input.read(buffer))!=-1){if((total+=n)>MAX_CONTROL)throw new IOException("Recovery record is too large: "+path);output.write(buffer,0,n);}bytes=output.toByteArray();
            }
            if(!unchanged(before,attributes(target)))throw new IOException("Recovery record changed: "+path);
            metadata(signature,path,before);signature.update(bytes);
            Object value=new Json(new String(bytes,StandardCharsets.UTF_8)).parse();
            if(!(value instanceof Map))throw new IOException("Invalid recovery record: "+path);
            return (Map<String,Object>)value;
        }
    }
    private static final class Handles implements AutoCloseable {
        final List<DirectoryStream<Path>> all=new ArrayList<>();SecureDirectoryStream<Path> directory;
        public void close()throws IOException {IOException error=null;for(int i=all.size()-1;i>=0;i--)try{all.get(i).close();}catch(IOException e){if(error==null)error=e;else error.addSuppressed(e);}if(error!=null)throw error;}
    }
    private static boolean sameIdentity(BasicFileAttributes a,BasicFileAttributes b){
        return Objects.equals(a.fileKey(),b.fileKey())&&a.isDirectory()==b.isDirectory()&&a.isRegularFile()==b.isRegularFile()&&a.isSymbolicLink()==b.isSymbolicLink()
                &&(a.fileKey()!=null||a.creationTime().equals(b.creationTime()));
    }
    private static boolean unchanged(BasicFileAttributes a,BasicFileAttributes b){return sameIdentity(a,b)&&a.size()==b.size()&&a.lastModifiedTime().equals(b.lastModifiedTime());}
    private static void metadata(MessageDigest digest,String path,BasicFileAttributes a){hash(digest,path);hash(digest,String.valueOf(a.fileKey()));hash(digest,a.creationTime().toString());hash(digest,a.lastModifiedTime().toString());hash(digest,Long.toString(a.size()));hash(digest,a.isDirectory()?"directory":a.isSymbolicLink()?"link":a.isRegularFile()?"file":"special");}

    private static final class Policy {
        final Store store;final String signature;String block="";
        boolean activePrefix,activeClient,activeRuntime;
        Policy(Store store)throws IOException {
            this.store=store;MessageDigest digest=digest();
            try {controls(digest);}catch(IOException e){block="Cleanup protected: "+e.getMessage();hash(digest,block);}
            signature=hex(digest.digest());
        }
        void requireReady()throws IOException {if(!block.isEmpty())throw new IOException(block);}
        String reason(String path) {
            if(path.isEmpty()||!path.contains("/"))return "Essential workspace folder or configuration";
            String[] parts=path.split("/");
            if(parts[0].equals("exports")||parts[0].equals("incoming"))return "";
            if(parts[0].equals("backups")) {
                if(RECOVERY.contains(parts[1]))return "Recovery records and their original files are protected";
                if(parts[parts.length-1].toLowerCase(Locale.ROOT).endsWith(".json"))return "Recovery and control records are protected";
                if(parts.length==2&&(parts[1].matches(DB)||parts[1].matches(PLAYERS)))return "";
                if(within(path,"backups/maps-before-import")||within(path,"backups/client-settings"))return "";
                return "Unrecognized backup or recovery file is protected";
            }
            if(within(path,"client/prefix-backups")) {
                if(path.equals("client/prefix-backups"))return "The backup collection folder is protected";
                if(!activePrefix)return "Retained prefixes are protected until an active Wine prefix exists";
                if(parts[2].matches("prefix-[0-9]+-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))return "";
                return "Unrecognized Wine prefix backup is protected";
            }
            if(within(path,"client/previous"))return activeClient?"":"Previous client is protected until the current imported client is valid";
            if(within(path,"client/runtime-previous"))return activeRuntime?"":"Previous runtime is protected until its replacement is valid";
            return "Active server, database, maps, source, client or configuration is protected";
        }
        void controls(MessageDigest digest)throws IOException {
            // The outer session journal belongs to this profile and may replace the whole workspace.
            if(Files.exists(store.root.getParent().resolve("session-swap.properties"),LinkOption.NOFOLLOW_LINKS))throw new IOException("Finish complete session recovery before deleting files");
            for(String name:new String[]{"content-quests.json","content-plugins.json","content-lua_modules.json","content-assets.json","ferry-change.json"})
                if(store.exists("run/"+name))throw new IOException("Finish recovery of run/"+name+" before deleting files");
            for(String zone:new String[]{"backups/nektulos","backups/client-spell-test"}) {
                if(!store.exists(zone))continue;
                if(!store.realDirectory(zone))throw new IOException("Invalid recovery folder: "+zone);
                String marker=zone+"/current.json";
                if(!store.exists(marker)) {
                    try(DirectoryStream<Path> entries=Files.newDirectoryStream(store.resolve(zone))){if(entries.iterator().hasNext())throw new IOException("Missing recovery record: "+marker);}
                    continue;
                }
                Map<String,Object> record=store.json(marker,digest);String state=string(record,"state");
                if(zone.endsWith("nektulos")) {
                    if(!Arrays.asList("applying","applied","reverting","reverted").contains(state)||!(record.get("originals") instanceof Map))throw new IOException("Invalid recovery record: "+marker);
                    Map<?,?> originals=(Map<?,?>)record.get("originals");
                    if(originals.size()!=2||!originals.containsKey("base/nektulos.map")||!originals.containsKey("nav/nektulos.nav"))throw new IOException("Invalid Nektulos recovery originals");
                    for(Object original:originals.values())if(original!=null&&(!(original instanceof String)||!((String)original).matches("[0-9a-f]{64}")))throw new IOException("Invalid Nektulos recovery checksum");
                    String backup=string(record,"backup");normalize(backup,false);
                    if(!backup.matches("[0-9]{8}-[0-9]{6}-[0-9a-f]{6}"))throw new IOException("Invalid Nektulos recovery backup");
                    if(state.equals("applying")||state.equals("reverting"))throw new IOException("Finish Nektulos recovery before deleting files");
                    if(state.equals("applied")&&!store.realDirectory(zone+"/"+backup))throw new IOException("Missing Nektulos recovery backup");
                }else {
                    if(!Objects.equals(record.get("format"),1L)||!Arrays.asList("applying","applied","restoring","restored").contains(state))throw new IOException("Invalid recovery record: "+marker);
                    String backup=string(record,"backup_id");normalize(backup,false);
                    if(!backup.matches("[0-9]{8}-[0-9]{6}-[0-9a-f]{12}"))throw new IOException("Invalid spell-file recovery backup");
                    if(state.equals("applying")||state.equals("restoring"))throw new IOException("Finish spell-file recovery before deleting files");
                    if(state.equals("applied")&&!store.realDirectory(zone+"/"+backup))throw new IOException("Missing spell-file recovery backup");
                }
            }
            if(store.exists("backups")) {
                if(!store.realDirectory("backups"))throw new IOException("Invalid backup folder");
                int count=0;
                try(DirectoryStream<Path> backups=Files.newDirectoryStream(store.resolve("backups"))) {
                    for(Path backup:backups) {
                        if(++count>MAX_NODES)throw new IOException("Too many backup records");
                        String name=backup.getFileName().toString();if(!name.startsWith("player-restore-")||!name.endsWith(".json"))continue;
                        Map<String,Object> record=store.json("backups/"+name,digest);
                        String state=string(record,"state"),snapshot=normalize(string(record,"snapshot"),false),db=normalize(string(record,"database_backup"),false);
                        if(!Arrays.asList("staging","ready","restored").contains(state)||!(record.get("tables") instanceof Map)||!(snapshot.startsWith("incoming/")||snapshot.startsWith("backups/"))||!db.matches("backups/"+DB))
                            throw new IOException("Invalid player recovery record: "+name);
                        if(!state.equals("restored"))throw new IOException("Finish player restoration before deleting files; its recovery backups are retained");
                    }
                }catch(DirectoryIteratorException e){throw e.getCause();}
            }
            activePrefix=store.realDirectory("client/prefix")&&store.realFile("client/prefix/user.reg")&&store.realFile("client/prefix/system.reg")
                    &&store.realFile("client/prefix/userdef.reg")&&store.realDirectory("client/prefix/drive_c/windows/system32");
            hash(digest,"activePrefix="+activePrefix);
            if(store.realFile("client/current/trasc-client.json")) {
                Map<String,Object> record=store.json("client/current/trasc-client.json",digest);
                if(Boolean.TRUE.equals(record.get("imported"))) {
                    String executable=string(record,"executable");
                    if(executable.equalsIgnoreCase("eqgame.exe")&&store.realFile("client/current/"+executable))activeClient=true;
                }
            }
            hash(digest,"activeClient="+activeClient);
            if(store.realFile("client/runtime/etc/trasc-client-runtime.json")) {
                Map<String,Object> record=store.json("client/runtime/etc/trasc-client-runtime.json",digest);
                activeRuntime=Objects.equals(record.get("format"),1L)&&"arm64".equals(record.get("architecture"))&&"client-1.0".equals(record.get("runtime"));
                for(String required:new String[]{"usr/bin/python3.11","usr/bin/Xtigervnc","usr/local/bin/box64","opt/wine/bin/wine","opt/wine/bin/wineserver"})
                    if(!store.realFile("client/runtime/"+required))activeRuntime=false;
            }
            hash(digest,"activeRuntime="+activeRuntime);
        }
    }
    private static String string(Map<String,Object> record,String key)throws IOException {Object value=record.get(key);if(!(value instanceof String)||((String)value).isEmpty())throw new IOException("Invalid recovery field: "+key);return (String)value;}

    /** Small strict parser for bounded control records; never opens backup payloads. */
    private static final class Json {
        final String value;int pos,depth;
        Json(String value){this.value=value;}
        Object parse()throws IOException {Object result=read();space();if(pos!=value.length())throw invalid();return result;}
        IOException invalid(){return new IOException("Malformed recovery or installation record");}
        void space(){while(pos<value.length()&&" \t\r\n".indexOf(value.charAt(pos))>=0)pos++;}
        Object read()throws IOException {
            space();if(++depth>128||pos>=value.length())throw invalid();Object result;char c=value.charAt(pos);
            if(c=='{') {
                pos++;Map<String,Object> map=new LinkedHashMap<>();space();
                if(take('}'))result=map;
                else {while(true){space();if(pos>=value.length()||value.charAt(pos)!='"')throw invalid();String key=text();space();if(!take(':')||map.containsKey(key))throw invalid();map.put(key,read());space();if(take('}'))break;if(!take(','))throw invalid();}result=map;}
            }else if(c=='[') {
                pos++;List<Object> list=new ArrayList<>();space();if(!take(']'))while(true){list.add(read());space();if(take(']'))break;if(!take(','))throw invalid();}result=list;
            }else if(c=='"')result=text();
            else if(value.startsWith("true",pos)){pos+=4;result=Boolean.TRUE;}
            else if(value.startsWith("false",pos)){pos+=5;result=Boolean.FALSE;}
            else if(value.startsWith("null",pos)){pos+=4;result=null;}
            else {
                int start=pos;while(pos<value.length()&&"-+0123456789.eE".indexOf(value.charAt(pos))>=0)pos++;
                String number=value.substring(start,pos);if(!number.matches("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?"))throw invalid();
                try{if(number.indexOf('.')<0&&number.indexOf('e')<0&&number.indexOf('E')<0)result=Long.valueOf(number);else result=Double.valueOf(number);}catch(NumberFormatException e){throw invalid();}
            }
            depth--;return result;
        }
        boolean take(char c){if(pos<value.length()&&value.charAt(pos)==c){pos++;return true;}return false;}
        String text()throws IOException {
            if(!take('"'))throw invalid();StringBuilder result=new StringBuilder();
            while(pos<value.length()) {
                char c=value.charAt(pos++);if(c=='"')return result.toString();if(c<32)throw invalid();
                if(c=='\\') {
                    if(pos>=value.length())throw invalid();c=value.charAt(pos++);
                    if(c=='u'){if(pos+4>value.length())throw invalid();try{c=(char)Integer.parseInt(value.substring(pos,pos+4),16);}catch(NumberFormatException e){throw invalid();}pos+=4;}
                    else if(c=='b')c='\b';else if(c=='f')c='\f';else if(c=='n')c='\n';else if(c=='r')c='\r';else if(c=='t')c='\t';else if(c!='"'&&c!='\\'&&c!='/')throw invalid();
                }
                result.append(c);
            }
            throw invalid();
        }
    }
}
