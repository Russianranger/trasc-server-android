package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.FileTime;
import java.util.*;

public final class LogRetentionHostTest {
    static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
    static Path write(Path root,String name,String data,long time)throws IOException {
        Path p=root.resolve(name);Files.createDirectories(p.getParent());Files.writeString(p,data);
        Files.setLastModifiedTime(p,FileTime.fromMillis(time));return p;
    }
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("log-retention-test-");
        try {
            Path work=tmp.resolve("work"),proc=tmp.resolve("proc");Files.createDirectories(proc);
            File directory=work.toFile();
            check(LogRetention.count(directory)==5,"Default is five");
            for(int keep=2;keep<=5;keep++) {
                LogRetention.save(directory,keep);
                for(int i=0;i<9;i++) {
                    Path log=write(work,"logs/client-wine.log","session "+i,i);
                    LogRetention.rotate(log.toFile());
                }
                Path log=work.resolve("logs/client-wine.log");
                for(int i=1;i<=keep;i++)check(Files.readString(LogRetention.history(log,i)).equals("session "+(9-i)),"History order");
                check(!Files.exists(LogRetention.history(log,keep+1)),"History bounded");
            }
            for(String group:new String[]{"world","login","ucs","query_server","zone/zone"})
                for(int i=1;i<=9;i++)write(work,"server/logs/"+group+"_"+(100+i)+".log","old "+i,i);
            for(int i=1;i<=3;i++)write(work,"server/logs/zone/gfaydark_version_0_inst_id_0_port_7000_"+(200+i)+".log","old zone",20+i);
            Files.createDirectory(proc.resolve("999"));
            Path active=write(work,"server/logs/world_999.log","ACTIVE",0);
            Path current=write(work,"logs/world.log","CURRENT",0);
            Path backup=write(work,"backups/world_111.log","BACKUP",0);
            Path chat=write(work,"client/current/Logs/eqlog_Yehaos.txt","CHAT",0);
            Path unknown=write(work,"server/logs/custom_111.log","CUSTOM",0);
            Path outside=write(tmp,"outside/world_1.log","OUTSIDE",0);
            Files.createSymbolicLink(work.resolve("server/logs/linked"),outside.getParent());
            Files.createSymbolicLink(work.resolve("server/logs/world_1.log"),outside);
            LogRetention.save(directory,2);
            long[] removed=LogRetention.prune(directory,proc);
            check(removed[0]>30&&removed[1]>0,"Existing collection cleaned");
            for(Path p:new Path[]{active,current,backup,chat,unknown,outside})check(Files.exists(p),"Protected "+p);
            for(String group:new String[]{"world","login","ucs","query_server"}) {
                check(Files.exists(work.resolve("server/logs/"+group+"_109.log")),"Newest retained");
                check(!Files.exists(work.resolve("server/logs/"+group+"_107.log")),"Older removed");
            }
            try(var entries=Files.list(work.resolve("server/logs/zone"))){check(entries.count()==2,"All zone PID names share one limit");}
            check(Files.readString(active).equals("ACTIVE"),"Running log unchanged");
            check(!Files.exists(work.resolve("logs/client-wine.previous.3.log")),"Lower limit applied immediately");
            check(LogRetention.prune(directory,proc)[0]==0,"Cleanup idempotent");
            try{LogRetention.save(directory,1);throw new AssertionError("Invalid count accepted");}catch(IOException expected){}
            check(LogRetention.count(directory)==2,"Invalid update did not persist");
            Path large=work.resolve("logs/large.log");
            try(RandomAccessFile f=new RandomAccessFile(large.toFile(),"rw")){f.writeBytes("START");f.setLength(LogRetention.LIMIT+4000);f.seek(f.length()-3);f.writeBytes("END");}
            LogRetention.rotate(large.toFile());
            Path archived=LogRetention.history(large,1);check(Files.size(archived)==LogRetention.LIMIT,"Archive size bounded");
            try(RandomAccessFile f=new RandomAccessFile(archived.toFile(),"r")){byte[] start=new byte[5];f.readFully(start);check(new String(start).equals("START"),"Startup kept");f.seek(f.length()-3);byte[] end=new byte[3];f.readFully(end);check(new String(end).equals("END"),"Tail kept");}
            Files.createSymbolicLink(work.resolve("logs/unsafe.log"),outside);
            try{LogRetention.rotate(work.resolve("logs/unsafe.log").toFile());throw new AssertionError("Symlink accepted");}catch(IOException expected){}
            System.out.println("Log retention: defaults, 2–5 histories, active PID protection, legacy cleanup, size bounds and symlink isolation passed");
        }finally{TarExtractor.remove(tmp.toFile());}
    }
}
