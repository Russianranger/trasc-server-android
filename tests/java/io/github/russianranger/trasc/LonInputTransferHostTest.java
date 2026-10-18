package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Exercises the same SAF transport without Android, using a streaming fake provider. */
public final class LonInputTransferHostTest {
    private static final class Provider implements LonInputTransfer.Documents {
        final Map<String,List<LonInputTransfer.Entry>> children=new HashMap<>();final Map<String,Long> payloads=new HashMap<>();int opened;
        LonInputTransfer.Entry dir(String id,String name,LonInputTransfer.Entry... entries){LonInputTransfer.Entry e=new LonInputTransfer.Entry(id,name,true,0,0);children.put(id,Arrays.asList(entries));return e;}
        LonInputTransfer.Entry file(String id,String name,long size){payloads.put(id,size);return new LonInputTransfer.Entry(id,name,false,size,1700000000000L);}
        public List<LonInputTransfer.Entry> children(LonInputTransfer.Entry dir)throws IOException {List<LonInputTransfer.Entry> result=children.get(dir.id);if(result==null)throw new IOException("unreadable");return result;}
        public InputStream open(LonInputTransfer.Entry file)throws IOException {opened++;Long count=payloads.get(file.id);if(count==null)throw new IOException("unreadable");return new InputStream(){long remaining=count;public int read(){if(remaining==0)return -1;remaining--;return 0x42;}public int read(byte[] buffer,int start,int length){if(remaining==0)return -1;int n=(int)Math.min(remaining,length);Arrays.fill(buffer,start,start+n,(byte)0x42);remaining-=n;return n;}};}
    }
    private static final class Progress implements LonInputTransfer.Progress {
        long bytes;boolean cancel;
        public void check()throws IOException {if(cancel&&bytes>=1024*1024)throw new InterruptedIOException("cancelled");}
        public void update(String phase,long files,long done,long total,String name){bytes=done;}
    }
    interface Throwing {void run()throws Exception;}
    static void fails(Throwing operation,String message)throws Exception {try{operation.run();throw new AssertionError(message);}catch(IOException expected){}}
    static void require(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception {
        File temp=Files.createTempDirectory("trasc-lon-saf-").toFile();
        try {
            Provider docs=new Provider();
            LonInputTransfer.Entry ban=docs.file("ban","ban.dat",1024),campaign=docs.file("campaign","campaign.dat",65);
            LonInputTransfer.Entry decks=docs.dir("decks","decks",docs.file("starter","starter.dat",17));
            LonInputTransfer.Entry empty=docs.dir("tutorial","tutorial");
            LonInputTransfer.Entry data=docs.dir("data","data",ban,campaign,decks,empty);
            LonInputTransfer.Entry lon=docs.dir("lon","LegendsOfNorrath",data);
            LonInputTransfer.Entry unrelated=docs.dir("unrelated","textures",docs.file("huge","huge.s3d",20L*1024*1024*1024));
            LonInputTransfer.Entry client=docs.dir("client","EverQuest_RoF2PT",unrelated,lon);
            LonInputTransfer.Entry wrapper=docs.dir("wrapper","downloads",docs.dir("outer","archive",client));
            Progress progress=new Progress();
            require(LonInputTransfer.discover(docs,wrapper,progress)==data,"nested client LoN discovered");
            require(docs.opened==0,"discovery reads directory metadata only");
            require(LonInputTransfer.discover(docs,lon,progress)==data,"selected LoN folder discovered");
            require(LonInputTransfer.discover(docs,data,progress)==data,"selected data folder accepted");
            File staged=LonInputTransfer.stage(temp);LonInputTransfer.Result result=LonInputTransfer.directory(docs,data,new File(staged,"data"),progress);
            require(result.files==3&&result.bytes==1106&&result.total==1106,"accurate transfer counts");
            require(new File(staged,"data/decks/starter.dat").length()==17,"relative folder structure preserved");
            require(new File(staged,"data/tutorial").isDirectory(),"empty directories preserved");
            require(!new File(staged,"data/data").exists()&&!new File(staged,"data/LegendsOfNorrath").exists(),"no extra data nesting");
            Files.createFile(new File(staged,".incomplete").toPath());LonInputTransfer.complete(staged,true);
            String marker=Files.readString(new File(staged,"trasc-lon-import.json").toPath());
            require(marker.contains("\"id\":\""+staged.getName().substring("lon-import-".length())+"\"")&&marker.contains("\"source\":\"data\"")&&marker.contains("\"kind\":\"directory\"")&&marker.contains("\"complete\":true"),"ownership receipt identifies only the staged data folder");
            require(!new File(staged,".incomplete").exists()&&!new File(staged,".trasc-lon-import.json.tmp").exists(),"receipt completion leaves no incomplete marker or temporary file");
            File premature=LonInputTransfer.stage(temp);Files.createFile(new File(premature,".incomplete").toPath());
            fails(()->LonInputTransfer.complete(premature,false),"ownership receipt cannot complete a missing archive");
            require(new File(premature,".incomplete").isFile()&&!new File(premature,"trasc-lon-import.json").exists(),"failed completion retains interruption marker");
            require(docs.opened==3,"unrelated client payload not read");
            try(InputStream in=new FileInputStream(new File(staged,"data/ban.dat"))){for(int i=0;i<1024;i++)require(in.read()==0x42,"copied bytes correct");}
            LonInputTransfer.Entry ambiguous=docs.dir("ambiguous","client",lon,docs.dir("other","other",docs.dir("lon2","LegendsOfNorrath",docs.dir("data2","data",ban))));
            fails(()->LonInputTransfer.discover(docs,ambiguous,progress),"ambiguous LoN selection rejected");
            fails(()->LonInputTransfer.discover(docs,unrelated,progress),"missing LoN rejected");
            fails(()->LonInputTransfer.validName("../escape"),"traversal rejected");
            fails(()->LonInputTransfer.validName("a\\b"),"Windows traversal rejected");
            LonInputTransfer.Entry unsafe=docs.dir("unsafe","data",docs.file("evil","../escape",1));
            fails(()->LonInputTransfer.directory(docs,unsafe,new File(temp,"unsafe"),progress),"unsafe provider name rejected");
            LonInputTransfer.Entry duplicates=docs.dir("duplicates","data",docs.file("one","Ban.dat",1),docs.file("two","ban.dat",1));
            fails(()->LonInputTransfer.directory(docs,duplicates,new File(temp,"duplicates"),progress),"case-colliding names rejected");
            // This exceeds the host JVM heap by four times. The provider generates bytes,
            // and the production copy loop only holds its fixed 256 KiB buffer.
            LonInputTransfer.Entry large=docs.file("large","client.zip",128L*1024*1024);
            LonInputTransfer.Result largeResult=LonInputTransfer.archive(docs,large,new File(temp,"large.zip"),new Progress());
            require(largeResult.bytes==128L*1024*1024&&new File(temp,"large.zip").length()==largeResult.bytes,"large fixed-buffer archive copy");
            Progress cancelled=new Progress();cancelled.cancel=true;
            fails(()->LonInputTransfer.archive(docs,large,new File(temp,"cancelled.zip"),cancelled),"cancellation stops transfer");
            require(new File(temp,"cancelled.zip").length()<largeResult.bytes,"cancel does not finish copying");
            LonInputTransfer.Entry truncated=new LonInputTransfer.Entry("ban","truncated.zip",false,2048,0);
            fails(()->LonInputTransfer.archive(docs,truncated,new File(temp,"truncated.zip"),new Progress()),"truncated provider data rejected");
            LonInputTransfer.Entry growing=new LonInputTransfer.Entry("ban","growing.zip",false,512,0);
            fails(()->LonInputTransfer.archive(docs,growing,new File(temp,"growing.zip"),new Progress()),"growing provider data rejected");
            File outside=new File(temp,"outside");outside.mkdir();File linked=new File(temp,"linked");linked.mkdir();Files.createSymbolicLink(new File(linked,"incoming").toPath(),outside.toPath());
            fails(()->LonInputTransfer.stage(linked),"symlink staging rejected");
            LonInputTransfer.remove(linked);require(outside.isDirectory(),"cleanup never traverses symlink");
            System.out.println("LoN SAF transport host tests passed (128 MiB transfer with 32 MiB heap)");
        } finally {LonInputTransfer.remove(temp);}
    }
}
