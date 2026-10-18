package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Bounded, provider-independent transport for an explicitly selected LoN data source. */
final class LonInputTransfer {
    static final int BUFFER_BYTES=256*1024,MAX_FILES=200000,MAX_DIRECTORIES=20000,MAX_DEPTH=64;
    static final long MAX_BYTES=512L*1024*1024*1024,FREE_RESERVE=64L*1024*1024;
    static final class Entry {
        final String id,name; final boolean directory; final long size,modified;
        Entry(String id,String name,boolean directory,long size,long modified){this.id=id;this.name=name;this.directory=directory;this.size=size;this.modified=modified;}
    }
    interface Documents {
        List<Entry> children(Entry entry)throws IOException;
        InputStream open(Entry entry)throws IOException;
    }
    interface Progress {
        void check()throws IOException;
        void update(String phase,long files,long bytes,long total,String name);
    }
    static final class Result {
        long files,bytes,total=-1;
        final String name;
        Result(String name){this.name=name;}
    }
    static void validName(String name)throws IOException {
        if(name==null||name.isEmpty()||name.equals(".")||name.equals("..")||name.indexOf('/')>=0||name.indexOf('\\')>=0||name.length()>255)
            throw new IOException("Unsafe or unsupported document name");
        for(int i=0;i<name.length();i++)if(name.charAt(i)<32||name.charAt(i)==127)throw new IOException("Unsafe document name");
    }
    /** Search directory metadata only; never copy the rest of a multi-gigabyte client. */
    static Entry discover(Documents documents,Entry selected,Progress progress)throws IOException {
        if(!selected.directory)throw new IOException("Choose a client, LegendsOfNorrath, or data folder");
        if(selected.name.equalsIgnoreCase("data"))return selected;
        ArrayDeque<Entry> queue=new ArrayDeque<>();ArrayDeque<Integer> depths=new ArrayDeque<>();
        Set<String> visited=new HashSet<>();List<Entry> found=new ArrayList<>();queue.add(selected);depths.add(0);int directories=0;
        while(!queue.isEmpty()) {
            progress.check();Entry dir=queue.remove();int depth=depths.remove();
            if(!visited.add(dir.id))throw new IOException("The document provider contains a repeated directory");
            if(++directories>MAX_DIRECTORIES)throw new IOException("Too many folders to inspect; select LegendsOfNorrath or its data folder directly");
            progress.update("discovering",0,0,-1,dir.name);
            List<Entry> children=documents.children(dir);checkedChildren(children);
            if(dir.name.equalsIgnoreCase("LegendsOfNorrath")) {
                for(Entry entry:children)if(entry.directory&&entry.name.equalsIgnoreCase("data"))found.add(entry);
                continue;
            }
            if(depth>=10)continue;
            for(Entry entry:children)if(entry.directory){queue.add(entry);depths.add(depth+1);}
        }
        if(found.isEmpty())throw new IOException("No LegendsOfNorrath/data folder found. Select that folder directly or choose the client ZIP.");
        if(found.size()!=1)throw new IOException("Several LegendsOfNorrath/data folders were found. Select the intended data folder directly.");
        return found.get(0);
    }
    private static void checkedChildren(List<Entry> children)throws IOException {
        if(children==null||children.size()>MAX_FILES)throw new IOException("The document provider returned too many entries");
        Set<String> names=new HashSet<>();
        for(Entry entry:children){validName(entry.name);if(entry.id==null||!names.add(entry.name.toLowerCase(Locale.ROOT)))throw new IOException("Ambiguous or duplicate document name: "+entry.name);if(entry.size< -1)throw new IOException("Invalid document size");}
    }
    private static final class Item {
        final Entry entry;final String relative;final int depth;
        Item(Entry entry,String relative,int depth){this.entry=entry;this.relative=relative;this.depth=depth;}
    }
    static Result directory(Documents documents,Entry source,File target,Progress progress)throws IOException {
        if(!target.mkdir())throw new IOException("Cannot prepare LoN data staging directory");
        Result result=new Result(source.name);List<Item> files=new ArrayList<>();ArrayDeque<Item> queue=new ArrayDeque<>();Set<String> visited=new HashSet<>();
        queue.add(new Item(source,"",0));long total=0;boolean known=true;int directories=0;
        while(!queue.isEmpty()) {
            progress.check();Item current=queue.remove();
            if(!visited.add(current.entry.id)||++directories>MAX_DIRECTORIES||current.depth>MAX_DEPTH)throw new IOException("Repeated or excessively deep LoN folder structure");
            List<Entry> children=documents.children(current.entry);checkedChildren(children);
            for(Entry entry:children) {
                String relative=current.relative.isEmpty()?entry.name:current.relative+"/"+entry.name;
                if(relative.length()>4096)throw new IOException("LoN document path is too long");
                Item item=new Item(entry,relative,current.depth+1);
                if(entry.directory){File directory=new File(target,relative);if(!directory.mkdir())throw new IOException("Cannot stage directory: "+relative);queue.add(item);}
                else {if(files.size()>=MAX_FILES)throw new IOException("Too many LoN data files");files.add(item);if(entry.size<0)known=false;else {if(total>MAX_BYTES-entry.size)throw new IOException("LoN input exceeds the supported size");total+=entry.size;}}
            }
            progress.update("inspecting",files.size(),0,known?total:-1,current.relative);
        }
        if(files.isEmpty())throw new IOException("The selected LoN data folder is empty");
        result.total=known?total:-1;if(known)checkSpace(target,total);
        byte[] buffer=new byte[BUFFER_BYTES];
        for(Item item:files) {
            progress.check();File file=new File(target,item.relative);
            try(InputStream in=documents.open(item.entry);FileOutputStream out=new FileOutputStream(file)) {
                if(in==null)throw new IOException("Cannot read "+item.relative);
                long count=copy(in,out,item.entry.size,target,buffer,result,progress,item.relative);out.getFD().sync();
                if(item.entry.size>=0&&count!=item.entry.size)throw new IOException("Document changed or was truncated: "+item.relative);
            }
            result.files++;if(item.entry.modified>0)file.setLastModified(item.entry.modified);
            progress.update("copying",result.files,result.bytes,result.total,item.relative);
        }
        return result;
    }
    static Result archive(Documents documents,Entry source,File target,Progress progress)throws IOException {
        if(source.directory)throw new IOException("Choose a ZIP document");
        if(source.size>MAX_BYTES)throw new IOException("LoN archive exceeds the supported size");
        if(source.size>=0)checkSpace(target.getParentFile(),source.size);
        Result result=new Result(source.name);result.total=source.size;
        try(InputStream in=documents.open(source);FileOutputStream out=new FileOutputStream(target)) {
            if(in==null)throw new IOException("Cannot read the selected ZIP document");
            long count=copy(in,out,source.size,target.getParentFile(),new byte[BUFFER_BYTES],result,progress,source.name);out.getFD().sync();
            if(source.size>=0&&count!=source.size)throw new IOException("ZIP document changed or transfer was truncated");
        }
        result.files=1;progress.update("ready",result.files,result.bytes,result.total,source.name);return result;
    }
    private static long copy(InputStream in,OutputStream out,long expected,File storage,byte[] buffer,Result result,Progress progress,String name)throws IOException {
        long copied=0;progress.update("copying",result.files,result.bytes,result.total,name);
        for(int count;(count=in.read(buffer))!=-1;){progress.check();if(count==0)continue;if(result.bytes>MAX_BYTES-count)throw new IOException("LoN input exceeds the supported size");if(expected>=0&&copied>expected-count)throw new IOException("Document grew during transfer: "+name);checkSpace(storage,count);out.write(buffer,0,count);copied+=count;result.bytes+=count;progress.update("copying",result.files,result.bytes,result.total,name);}
        out.flush();progress.check();return copied;
    }
    static void checkSpace(File storage,long bytes)throws IOException {if(bytes<0||storage.getUsableSpace()<FREE_RESERVE||storage.getUsableSpace()-FREE_RESERVE<bytes)throw new IOException("Not enough private app storage to stage LoN data. Free space and retry.");}
    static File stage(File work)throws IOException {
        File incoming=new File(work,"incoming");
        File root=work.getAbsoluteFile();for(File part=incoming;part!=null;part=part.getParentFile()){if(Files.isSymbolicLink(part.toPath()))throw new IOException("LoN staging cannot use symbolic links");if(part.equals(root))break;}
        // Android may expose the application's home through /data/user/0 aliases.
        // Reject links below work while accepting that platform-owned parent alias.
        if(!incoming.getCanonicalFile().getParentFile().equals(work.getCanonicalFile()))throw new IOException("Invalid LoN staging directory");
        Files.createDirectories(incoming.toPath());
        File stage=new File(incoming,"lon-import-"+UUID.randomUUID());Files.createDirectory(stage.toPath());return stage;
    }
    /** Durable ownership receipt allows the backend to remove only its consumed private input. */
    static void complete(File stage,boolean folder)throws IOException {
        String prefix="lon-import-",name=stage.getName();
        if(!name.matches("lon-import-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
                ||Files.isSymbolicLink(stage.toPath())||!stage.getParentFile().getName().equals("incoming"))
            throw new IOException("Invalid private LoN input staging identity");
        File source=new File(stage,folder?"data":"source.zip"),incomplete=new File(stage,".incomplete");
        if(!Files.isRegularFile(incomplete.toPath(),LinkOption.NOFOLLOW_LINKS)
                ||(folder?!Files.isDirectory(source.toPath(),LinkOption.NOFOLLOW_LINKS):!Files.isRegularFile(source.toPath(),LinkOption.NOFOLLOW_LINKS)))
            throw new IOException("Cannot complete unfinished LoN input staging");
        // File payloads were fsynced by the copy loop. Persist directory entries too.
        Files.walkFileTree(stage.toPath(),new SimpleFileVisitor<Path>(){
            @Override public FileVisitResult postVisitDirectory(Path directory,IOException error)throws IOException {
                if(error!=null)throw error;syncDirectory(directory);return FileVisitResult.CONTINUE;
            }
        });
        String json="{\"format\":1,\"profile\":\"custom\",\"id\":\""+name.substring(prefix.length())
                +"\",\"kind\":\""+(folder?"directory":"zip")+"\",\"source\":\""+(folder?"data":"source.zip")+"\",\"complete\":true}";
        Path temporary=new File(stage,".trasc-lon-import.json.tmp").toPath(),marker=new File(stage,"trasc-lon-import.json").toPath();
        try {
            Files.createFile(temporary);
            try(FileOutputStream out=new FileOutputStream(temporary.toFile())){out.write(json.getBytes(java.nio.charset.StandardCharsets.UTF_8));out.getFD().sync();}
            Files.move(temporary,marker,StandardCopyOption.ATOMIC_MOVE);syncDirectory(stage.toPath());
            Files.delete(incomplete.toPath());syncDirectory(stage.toPath());syncDirectory(stage.getParentFile().toPath());
        } finally {Files.deleteIfExists(temporary);}
    }
    private static void syncDirectory(Path directory)throws IOException {try(java.nio.channels.FileChannel channel=java.nio.channels.FileChannel.open(directory,StandardOpenOption.READ)){channel.force(true);}}
    static void remove(File file)throws IOException {
        if(Files.isSymbolicLink(file.toPath())||!file.isDirectory()){Files.deleteIfExists(file.toPath());return;}
        File[] children=file.listFiles();if(children==null)throw new IOException("Cannot inspect interrupted LoN staging directory");
        for(File child:children)remove(child);Files.deleteIfExists(file.toPath());
    }
    private LonInputTransfer(){}
}
