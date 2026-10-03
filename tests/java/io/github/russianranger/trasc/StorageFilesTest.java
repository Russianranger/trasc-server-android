package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.FileTime;
import java.util.*;

/** Host tests use real files, links, sparse backups and recovery records. */
public final class StorageFilesTest {
    private static final String DB="backups/database-20261003-080000-ab12.sql.gz";
    private static final String PLAYERS="backups/players-20261003-080000-a1b2c3d4.zip";
    interface Operation {void run()throws Exception;}
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static void rejects(Operation action,String message)throws Exception {
        try{action.run();throw new AssertionError("Accepted "+message);}catch(IOException expected){}
    }
    static Path write(Path root,String name,String data)throws IOException {
        Path file=root.resolve(name);Files.createDirectories(file.getParent());Files.writeString(file,data);return file;
    }
    static File work(Path root,String name)throws IOException {Path path=root.resolve(name);Files.createDirectories(path);return path.toFile();}
    static StorageFiles.Entry entry(StorageFiles.Page page,String path){for(StorageFiles.Entry entry:page.items)if(entry.path.equals(path))return entry;throw new AssertionError("Missing "+path);}
    static void remove(Path root)throws IOException {
        if(!Files.exists(root,LinkOption.NOFOLLOW_LINKS))return;
        if(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS))try(DirectoryStream<Path> entries=Files.newDirectoryStream(root)){for(Path entry:entries)remove(entry);}
        Files.delete(root);
    }
    public static void main(String[] args)throws Exception {
        Path temp=Files.createTempDirectory("trasc-storage-");
        try {
            File w=work(temp,"browse");Path root=w.toPath();
            for(String folder:new String[]{"backups","exports","incoming","database","server","maps","sources","client","run","builds"})Files.createDirectories(root.resolve(folder));
            for(String name:new String[]{"settings.json","mysql.cnf","mysql.sock","mysql.pid"})write(root,name,"PRIVATE");
            write(root,DB,"BACKUP");write(root,PLAYERS,"PLAYERS");write(root,"backups/custom.sql.gz","UNKNOWN");
            write(root,"backups/nektulos/originals.map","RECOVERY");
            StorageFiles.Page page=StorageFiles.browse(w,"","",0,200);
            check(page.path.isEmpty()&&page.total==10,"Offline root contains the ordinary folders");
            for(StorageFiles.Entry item:page.items)check(!item.deletable,"Workspace collection protected: "+item.path);
            // Missing recovery records block cleanup, while read-only browsing still works.
            check(!entry(StorageFiles.browse(w,"backups","",0,50),DB).deletable,"Missing original-map journal protects cleanup");
            rejects(()->StorageFiles.preview(w,Collections.singletonList(DB)),"missing recovery journal");
            remove(root.resolve("backups/nektulos"));
            page=StorageFiles.browse(w,"backups","",0,50);
            check(entry(page,DB).deletable&&entry(page,PLAYERS).deletable,"Generated snapshots deletable");
            check(!entry(page,"backups/custom.sql.gz").deletable,"Unknown backups protected");
            for(int i=0;i<2505;i++)write(root,"incoming/row"+String.format(Locale.ROOT,"%04d",i)+".zip","x");
            page=StorageFiles.browse(w,"incoming","ROW2055",0,30);
            check(page.total==1&&page.items.get(0).name.equals("row2055.zip"),"Search spans the entire folder and ignores case");
            page=StorageFiles.browse(w,"incoming","",3000,30);
            check(page.total==2505&&page.offset==2490&&page.items.size()==15&&page.nextOffset==null,"Last page offset clamped");
            rejects(()->StorageFiles.browse(w,"../database","",0,30),"browser traversal");
            rejects(()->StorageFiles.browse(w,"incoming",String.join("",Collections.nCopies(257,"x")),0,30),"unbounded query");

            // Sparse large files establish size without reading compressed SQL contents.
            Path sparse=root.resolve(DB);try(RandomAccessFile file=new RandomAccessFile(sparse.toFile(),"rw")){file.setLength(5L*1024*1024*1024+19);}
            StorageFiles.Preview review=StorageFiles.preview(w,Arrays.asList(PLAYERS,DB));
            check(review.bytes==5L*1024*1024*1024+26&&review.files==2,"64-bit preview measures a 5 GB backup without loading it");
            check(review.paths.equals(Arrays.asList(DB,PLAYERS)),"Selection canonical order");
            rejects(()->StorageFiles.delete(w,Collections.singletonList(DB),review.token),"changed selection");
            check(Files.exists(sparse),"Rejected selection does not delete first file");
            StorageFiles.Result result=StorageFiles.delete(w,Arrays.asList(DB,PLAYERS),review.token);
            check(result.bytes==review.bytes&&result.files==2&&!Files.exists(sparse)&&!Files.exists(root.resolve(PLAYERS)),"Reviewed snapshots removed");
            check(Files.readString(root.resolve("backups/custom.sql.gz")).equals("UNKNOWN"),"Unknown backup retained");

            File changed=work(temp,"changed");Path c=changed.toPath();write(c,DB,"FIRST");write(c,"exports/second.zip","SECOND");
            StorageFiles.Preview initialOld=StorageFiles.preview(changed,Arrays.asList(DB,"exports/second.zip"));
            Files.setLastModifiedTime(c.resolve("exports/second.zip"),FileTime.fromMillis(System.currentTimeMillis()+5000));
            rejects(()->StorageFiles.delete(changed,initialOld.paths,initialOld.token),"mtime changed in last selection");
            check(Files.exists(c.resolve(DB))&&Files.exists(c.resolve("exports/second.zip")),"All selections preflight before deletion");
            StorageFiles.Preview old=StorageFiles.preview(changed,Collections.singletonList(DB));FileTime time=Files.getLastModifiedTime(c.resolve(DB));
            Path replacement=write(c,"exports/replacement.zip","FIRST");Files.setLastModifiedTime(replacement,time);Files.move(replacement,c.resolve(DB),StandardCopyOption.REPLACE_EXISTING);
            final StorageFiles.Preview inodeReview=old;
            rejects(()->StorageFiles.delete(changed,inodeReview.paths,inodeReview.token),"same size/time replacement has another inode");
            rejects(()->StorageFiles.preview(changed,Collections.singletonList("exports")),"collection root");
            for(String unsafe:new String[]{"", ".", "../exports", "/etc/passwd", "exports/../database", "exports//second.zip", "exports\\second.zip", "database/ibdata1", "run/job.json", "sources/current/README", "client/current/eqgame.exe", "backups"})
                rejects(()->StorageFiles.preview(changed,Collections.singletonList(unsafe)),"protected or invalid path "+unsafe);
            write(c,"exports/tree/a.zip","A");
            rejects(()->StorageFiles.preview(changed,Arrays.asList("exports/tree","exports/tree/a.zip")),"overlapping paths");
            rejects(()->StorageFiles.preview(changed,Arrays.asList(DB,DB)),"duplicate paths");
            List<String> excessive=new ArrayList<>();for(int i=0;i<501;i++)excessive.add("exports/tree/"+i);
            rejects(()->StorageFiles.preview(changed,excessive),"more than 500 selections");
            StorageFiles.Preview treeReview=StorageFiles.preview(changed,Collections.singletonList("exports/tree"));
            write(c,"exports/tree/new.zip","NEW");
            rejects(()->StorageFiles.delete(changed,treeReview.paths,treeReview.token),"new descendant since review");
            check(Files.exists(c.resolve("exports/tree/a.zip")),"New descendant rejects the full tree before deletion");
            write(c,"backups/maps-before-import/base/map.bin","MAP");write(c,"backups/maps-before-import/current.json","{}");
            rejects(()->StorageFiles.preview(changed,Arrays.asList(DB,"backups/maps-before-import")),"protected descendant in one selected folder");
            check(Files.exists(c.resolve(DB)),"Protected descendant preserves earlier selected backup");

            File linked=work(temp,"links");Path l=linked.toPath();
            Path outside=write(temp,"outside/keep.txt","OUTSIDE");Path live=write(l,"database/ibdata1","LIVE");
            write(l,"exports/disposable/nested/backup.zip","BACKUP");
            Files.createSymbolicLink(l.resolve("exports/disposable/outside"),outside.getParent());
            Files.createSymbolicLink(l.resolve("exports/disposable/live"),live.getParent());
            Files.createSymbolicLink(l.resolve("exports/disposable/broken"),temp.resolve("missing"));
            StorageFiles.Preview links=StorageFiles.preview(linked,Collections.singletonList("exports/disposable"));
            check(links.files==4&&links.bytes==6,"Links are entries, and their target bytes are never scanned");
            StorageFiles.delete(linked,links.paths,links.token);
            check(!Files.exists(l.resolve("exports/disposable"),LinkOption.NOFOLLOW_LINKS),"Allowed tree and descendant links removed");
            check(Files.readString(outside).equals("OUTSIDE")&&Files.readString(live).equals("LIVE"),"External and active symlink targets retained");
            Files.createSymbolicLink(l.resolve("incoming"),outside.getParent());
            rejects(()->StorageFiles.preview(linked,Collections.singletonList("incoming/keep.txt")),"symlink ancestor");
            rejects(()->StorageFiles.browse(linked,"incoming","",0,30),"browsing symlink directory");
            Files.createSymbolicLink(temp.resolve("work-link"),l);
            rejects(()->StorageFiles.preview(temp.resolve("work-link").toFile(),Collections.singletonList("exports/test.zip")),"symlink workspace");

            File recovery=work(temp,"recovery");Path r=recovery.toPath();write(r,DB,"DATABASE");write(r,PLAYERS,"PLAYERS");
            String journal="backups/player-restore-abcdef123456.json";
            String record="{\"state\":\"staging\",\"snapshot\":\""+PLAYERS+"\",\"database_backup\":\""+DB+"\",\"tables\":{}}";
            write(r,journal,record);
            rejects(()->StorageFiles.preview(recovery,Collections.singletonList(DB)),"pending player restore");
            check(!entry(StorageFiles.browse(recovery,"backups","",0,30),DB).deletable,"Pending recovery appears protected in browser");
            write(r,journal,record.replace("staging","restored"));
            StorageFiles.Preview completed=StorageFiles.preview(recovery,Arrays.asList(DB,PLAYERS));
            rejects(()->StorageFiles.preview(recovery,Collections.singletonList(journal)),"completed control journal");
            write(r,journal,"{\"state\":\"restored\",\"state\":\"restored\"}");
            rejects(()->StorageFiles.delete(recovery,completed.paths,completed.token),"duplicate or malformed recovery fields");
            check(Files.exists(r.resolve(DB)),"Malformed recovery prevents deletion");
            Files.delete(r.resolve(journal));
            for(String control:new String[]{"run/ferry-change.json","run/content-quests.json","run/content-plugins.json","run/content-lua_modules.json","run/content-assets.json"}) {
                write(r,control,"{}");rejects(()->StorageFiles.preview(recovery,Collections.singletonList(DB)),"pending control "+control);Files.delete(r.resolve(control));
            }
            write(temp,"session-swap.properties","work=true");
            rejects(()->StorageFiles.preview(recovery,Collections.singletonList(DB)),"outer session rollback journal");
            Files.delete(temp.resolve("session-swap.properties"));
            String nektulos="backups/nektulos/current.json",saved="20261003-080000-a1b2c3";
            write(r,nektulos,"{\"state\":\"applied\",\"backup\":\""+saved+"\",\"originals\":{\"base/nektulos.map\":null,\"nav/nektulos.nav\":null}}");
            rejects(()->StorageFiles.preview(recovery,Collections.singletonList(DB)),"missing applied map recovery backup");
            Files.createDirectories(r.resolve("backups/nektulos/"+saved));
            StorageFiles.preview(recovery,Collections.singletonList(DB));
            rejects(()->StorageFiles.preview(recovery,Collections.singletonList("backups/nektulos/"+saved)),"active map originals");
            write(r,nektulos,"{\"state\":\"applied\",\"backup\":\""+saved+"\",\"originals\":{}}");
            rejects(()->StorageFiles.preview(recovery,Collections.singletonList(DB)),"malformed map original manifest");
            remove(r.resolve("backups/nektulos"));
            write(r,"backups/spire/enabled","");
            check(!entry(StorageFiles.browse(recovery,"backups/spire","",0,30),"backups/spire/enabled").deletable,"Spire control cannot be deleted");
            String spell="backups/client-spell-test/current.json",spellId="20261003-080000-abcdef123456";
            write(r,spell,"{\"format\":1,\"state\":\"applying\",\"backup_id\":\""+spellId+"\"}");
            rejects(()->StorageFiles.preview(recovery,Collections.singletonList(DB)),"in-progress spell replacement");
            remove(r.resolve("backups/client-spell-test"));

            File copies=work(temp,"copies");Path p=copies.toPath();
            String prefix="client/prefix-backups/prefix-1234567890-12345678-1234-1234-1234-1234567890ab";
            write(p,prefix+"/user.reg","ORIGINAL");Files.createDirectories(p.resolve("client/prefix"));
            rejects(()->StorageFiles.preview(copies,Collections.singletonList(prefix)),"empty fresh prefix cannot replace good backup");
            for(String registry:new String[]{"user.reg","system.reg","userdef.reg"})write(p,"client/prefix/"+registry,"REGISTRY");
            Files.createDirectories(p.resolve("client/prefix/drive_c/windows/system32"));
            Files.createSymbolicLink(p.resolve(prefix+"/dosdevices"),live.getParent());
            StorageFiles.Preview prefixReview=StorageFiles.preview(copies,Collections.singletonList(prefix));
            StorageFiles.delete(copies,prefixReview.paths,prefixReview.token);
            check(Files.exists(p.resolve("client/prefix/system.reg"))&&Files.exists(live),"Inactive prefix deletion preserves live prefix and linked database");
            write(p,"client/previous/eqgame.exe","OLD");
            rejects(()->StorageFiles.preview(copies,Collections.singletonList("client/previous")),"only copy of imported client");
            write(p,"client/current/trasc-client.json","{\"imported\":true,\"executable\":\"EQGAME.EXE\"}");
            rejects(()->StorageFiles.preview(copies,Collections.singletonList("client/previous")),"marker without current executable");
            write(p,"client/current/EQGAME.EXE","MZCURRENT");
            StorageFiles.Preview previous=StorageFiles.preview(copies,Collections.singletonList("client/previous"));
            StorageFiles.delete(copies,previous.paths,previous.token);
            check(Files.readString(p.resolve("client/current/EQGAME.EXE")).equals("MZCURRENT"),"Current client retained");
            write(p,"client/runtime-previous/etc/trasc-client-runtime.json","OLD RUNTIME");
            write(p,"client/runtime/etc/trasc-client-runtime.json","{\"format\":1,\"architecture\":\"arm64\",\"runtime\":\"client-1.0\"}");
            rejects(()->StorageFiles.preview(copies,Collections.singletonList("client/runtime-previous")),"runtime marker without executables");
            for(String binary:new String[]{"usr/bin/python3.11","usr/bin/Xtigervnc","usr/local/bin/box64","opt/wine/bin/wine","opt/wine/bin/wineserver"})write(p,"client/runtime/"+binary,"EXECUTABLE");
            StorageFiles.Preview runtime=StorageFiles.preview(copies,Collections.singletonList("client/runtime-previous"));
            StorageFiles.delete(copies,runtime.paths,runtime.token);
            check(Files.exists(p.resolve("client/runtime/opt/wine/bin/wine")),"Current runtime retained");
            write(p,"exports/heap-test/nested/tiny.zip","X");
            check(entry(StorageFiles.browse(copies,"exports","",0,20),"exports/heap-test").size==0,"Browser does not recursively measure eligible folders");
            System.out.println("Storage cleanup: offline pagination, 64-bit sizes, all-selection preflight, stale inode/tree protection, recovery journals, preserved active copies, traversal and symlink isolation passed");
        }finally{remove(temp);}
    }
}
