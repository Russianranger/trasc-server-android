package io.github.russianranger.trasc;

import android.system.Os;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPOutputStream;

/** Regress the Fold6 failure with link(2) denied, plus copy permissions and limits. */
public final class TarExtractorHostTest {
    record Entry(String name,char type,String target,int mode,byte[] data) {}
    static Entry file(String name,int mode,String data){return new Entry(name,'0',"",mode,data.getBytes(StandardCharsets.UTF_8));}
    static Entry link(String name,String target){return new Entry(name,'1',target,0,new byte[0]);}
    static Entry sym(String name,String target){return new Entry(name,'2',target,0777,new byte[0]);}
    static void field(byte[] h,int at,String value){byte[] b=value.getBytes(StandardCharsets.UTF_8);System.arraycopy(b,0,h,at,b.length);}
    static Path archive(Path dir,Entry... entries)throws IOException {
        Path archive=Files.createTempFile(dir,"fixture-",".tar.gz");
        try(OutputStream out=new GZIPOutputStream(Files.newOutputStream(archive))) {
            for(Entry e:entries) {
                byte[] h=new byte[512];field(h,0,e.name);field(h,100,String.format("%07o",e.mode));
                field(h,124,String.format("%011o",e.data.length));Arrays.fill(h,148,156,(byte)' ');
                h[156]=(byte)e.type;field(h,157,e.target);field(h,257,"ustar");
                int checksum=0;for(byte b:h)checksum+=b&255;field(h,148,String.format("%06o\0 ",checksum));
                out.write(h);out.write(e.data);out.write(new byte[(512-e.data.length%512)%512]);
            }
            out.write(new byte[1024]);
        }
        return archive;
    }
    static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    static void rejected(Path tmp,String reason,long limit,Entry... entries)throws Exception {
        Path root=Files.createTempDirectory(tmp,"reject-");
        try {
            TarExtractor.extract(archive(tmp,entries).toFile(),root.toFile(),n->{},limit);
            throw new AssertionError("Accepted "+reason);
        } catch(IOException expected) {
            check(expected.getMessage().contains(reason),"Unexpected failure for "+reason+": "+expected);
        }
    }
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("trasc-hardlink-test-");
        try {
            // Make sure every runtime test really uses the restrictive host adapter.
            Path probe=tmp.resolve("probe");Files.writeString(probe,"test");
            try{Os.link(probe.toString(),tmp.resolve("denied").toString());throw new AssertionError("Host adapter permits hardlinks");}
            catch(IOException expected){check(expected.getMessage().contains("EACCES"),"Wrong simulated denial");}
            Path root=Files.createDirectory(tmp.resolve("root"));
            TarExtractor.extract(archive(tmp,
                file("usr/bin/tool",0755,"executable bytes"),file("usr/share/data",0644,"data bytes"),
                link("usr/bin/alias","usr/bin/tool"),link("usr/bin/alias2","usr/bin/alias"),
                link("usr/share/copy","usr/share/data"),file("usr/share/empty",0644,""),link("usr/share/empty-copy","usr/share/empty"),
                sym("bin","usr/bin"),sym("guest-absolute","/usr/bin/tool")
            ).toFile(),root.toFile(),n->{});
            for(String name:new String[]{"usr/bin/alias","usr/bin/alias2"}) {
                Path p=root.resolve(name);
                check(Files.readString(p).equals("executable bytes"),"Executable contents lost");
                check(SessionArchive.mode(p)==0755,"Executable permission bits lost");
                check(!Files.isSymbolicLink(p)&&!Files.isSameFile(root.resolve("usr/bin/tool"),p),"Hardlink was not expanded to an independent regular file");
            }
            check(Files.readString(root.resolve("usr/share/copy")).equals("data bytes"),"Data copy corrupted");
            check(SessionArchive.mode(root.resolve("usr/share/copy"))==0644,"Data copy became executable");
            check(Files.size(root.resolve("usr/share/empty-copy"))==0,"Empty hardlink failed");
            check(Files.readSymbolicLink(root.resolve("bin")).toString().equals("usr/bin"),"Relative guest symlink changed");
            check(Files.readSymbolicLink(root.resolve("guest-absolute")).toString().equals("/usr/bin/tool"),"Absolute guest symlink changed");
            Files.writeString(root.resolve("usr/bin/alias"),"changed");
            check(Files.readString(root.resolve("usr/bin/tool")).equals("executable bytes"),"Copy writes changed the target");
            rejected(tmp,"Unsafe archive path",100,file("file",0644,"x"),link("../escaped","file"));
            rejected(tmp,"Unsafe archive path",100,link("copy","../probe"));
            rejected(tmp,"Unsafe archive path",100,link("copy","/etc/passwd"));
            rejected(tmp,"Invalid hardlink",100,link("copy","missing"));
            rejected(tmp,"Invalid hardlink",100,new Entry("directory",'5',"",0755,new byte[0]),link("copy","directory"));
            rejected(tmp,"Invalid hardlink",100,file("file",0644,"x"),link("file","file"));
            rejected(tmp,"Invalid hardlink",100,file("file",0644,"x"),file("copy",0644,"original"),link("copy","file"));
            rejected(tmp,"Invalid hardlink",100,file("file",0644,"x"),link("copy","file"),link("copy","file"));
            rejected(tmp,"Invalid hardlink",100,file("file",0644,"x"),sym("symlink","file"),link("copy","symlink"));
            rejected(tmp,"exceeds limits after expanding hardlinks",2,file("file",0644,"x"),link("copy","file"),link("copy2","copy"));
            check(!Files.exists(tmp.resolve("escaped")),"Traversal escaped the extraction root");
            System.out.println("PASS: hard-link denial regression, independent copies, executable/data modes, empty files, link chains, guest symlinks, traversal/target rejection and expanded-size limit");
        } finally {TarExtractor.remove(tmp.toFile());}
    }
}
