package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.util.Properties;

/** Fixed, independent homes. The existing custom installation never moves. */
final class WorldProfiles {
    final File base;
    private volatile String current="custom";
    private int operations;
    private boolean switching;
    private String error;
    WorldProfiles(File base) {
        this.base=base;
        try {current=read(base);} catch(IOException e){error="Cannot read the selected world profile: "+e.getMessage();}
    }
    static String valid(String id)throws IOException {
        if(!"custom".equals(id)&&!"traditional".equals(id))throw new IOException("Unknown world profile");
        return id;
    }
    static String read(File base)throws IOException {
        File file=new File(base,"world-profile.properties");
        if(!file.exists())return "custom";
        if(file.length()>4096)throw new IOException("Invalid profile selection");
        Properties p=new Properties();try(InputStream in=new FileInputStream(file)){p.load(in);}
        return valid(p.getProperty("active"));
    }
    String current(){return current;}
    static String label(String id){return "traditional".equals(id)?"Traditional EQEmu":"TRASC Custom";}
    File home(String id)throws IOException {
        valid(id);
        File home="custom".equals(id)?base:new File(base,"profiles/traditional");
        if(!"custom".equals(id)&&(Files.isSymbolicLink(new File(base,"profiles").toPath())||Files.isSymbolicLink(home.toPath())))throw new IOException("Profile home cannot be a symbolic link");
        return home;
    }
    synchronized Lease enter(String expected)throws IOException {
        if(error!=null)throw new IOException(error);
        if(switching)throw new IOException("World profile is switching. Wait a moment.");
        if(!current.equals(expected))throw new IOException("World profile changed. Reopen the screen and retry.");
        operations++;
        return new Lease();
    }
    final class Lease implements AutoCloseable {
        private boolean closed;
        @Override public void close(){synchronized(WorldProfiles.this){if(!closed){closed=true;operations--;WorldProfiles.this.notifyAll();}}}
    }
    synchronized void beginSwitch(String expected)throws IOException {
        if(error!=null)throw new IOException(error);
        if(switching||!current.equals(expected))throw new IOException("World profile changed. Refresh and retry.");
        // Short status reads may finish; active imports, exports and pickers must finish first.
        switching=true;
        long until=System.nanoTime()+1_000_000_000L;
        while(operations>0&&System.nanoTime()<until)try{wait(50);}catch(InterruptedException e){switching=false;Thread.currentThread().interrupt();throw new IOException("Profile switch interrupted",e);}
        if(operations>0){switching=false;throw new IOException("Close the client display and file picker, and finish transfers before switching worlds");}
    }
    synchronized void select(String id)throws IOException {
        if(!switching)throw new IOException("Profile switch is not locked");
        valid(id);base.mkdirs();
        File temp=new File(base,"world-profile.properties.new");
        Properties p=new Properties();p.setProperty("active",id);
        try {
            try(FileOutputStream out=new FileOutputStream(temp)){p.store(out,"Selected TRASC world");out.getFD().sync();}
            Files.move(temp.toPath(),new File(base,"world-profile.properties").toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            current=id;
        } finally {Files.deleteIfExists(temp.toPath());}
    }
    synchronized void endSwitch(){switching=false;notifyAll();}
}
