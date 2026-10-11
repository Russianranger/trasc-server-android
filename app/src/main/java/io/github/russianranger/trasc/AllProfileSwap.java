package io.github.russianranger.trasc;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;

/** One crash-recoverable activation for three worlds and device settings. */
final class AllProfileSwap {
    static final String JOURNAL="all-session-swap.properties";
    interface Hook {void moved(int index)throws IOException;}
    static boolean exists(File f){return Files.exists(f.toPath(),LinkOption.NOFOLLOW_LINKS);}
    static void syncDirectory(File dir)throws IOException {SessionArchive.syncDirectory(dir);}
    static void ensureDirectory(File dir)throws IOException {
        List<File> missing=new ArrayList<>();File current=dir;
        while(current!=null&&!exists(current)){missing.add(current);current=current.getParentFile();}
        if(current==null||!Files.isDirectory(current.toPath(),LinkOption.NOFOLLOW_LINKS))throw new IOException("Invalid restore destination directory");
        Collections.reverse(missing);for(File next:missing){Files.createDirectory(next.toPath());syncDirectory(next);syncDirectory(next.getParentFile());}
    }
    static void store(File base,Properties p)throws IOException {
        File temp=new File(base,JOURNAL+".new"),live=new File(base,JOURNAL);
        try(FileOutputStream out=new FileOutputStream(temp)){p.store(out,"TRASC all-world activation");out.getFD().sync();}
        Files.move(temp.toPath(),live.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);syncDirectory(base);
    }
    static List<String> worldComponents() {
        List<String> list=new ArrayList<>();for(String id:SessionArchive.WORLDS)for(String part:new String[]{"rootfs","work"})list.add(id+"/"+part);return list;
    }
    static List<String> components(){List<String> list=worldComponents();list.add("global/preferences.properties");list.add("global/world-profile.properties");return list;}
    static List<String> components(String included)throws IOException {
        List<String> list=new ArrayList<>();int previous=-1;
        if(!included.isEmpty())for(String component:included.split(",",-1)){int index=worldComponents().indexOf(component);if(index<0||index<=previous)throw new IOException("Invalid all-world recovery component inventory");previous=index;list.add(component);}
        list.add("global/preferences.properties");list.add("global/world-profile.properties");return list;
    }
    static File live(File base,String component)throws IOException {
        if(component.equals("global/preferences.properties"))return new File(base,"session-preferences.properties");
        if(component.equals("global/world-profile.properties"))return new File(base,"world-profile.properties");
        String[] parts=component.split("/");if(parts.length!=2||!Arrays.asList("rootfs","work").contains(parts[1]))throw new IOException("Invalid session component");
        return new File(new WorldProfiles(base).home(WorldProfiles.valid(parts[0])),parts[1]);
    }
    static File previous(File base,int i){return new File(base,"all-session-rollback/"+i);}
    static void move(File from,File to)throws IOException {
        ensureDirectory(to.getParentFile());
        Files.move(from.toPath(),to.toPath(),StandardCopyOption.ATOMIC_MOVE);syncDirectory(from.getParentFile());syncDirectory(to.getParentFile());
    }
    static boolean pending(File base){return new File(base,JOURNAL).isFile();}
    static void recover(File base)throws IOException {
        File journal=new File(base,JOURNAL);if(!journal.isFile())return;
        if(journal.length()>16384)throw new IOException("Invalid all-world recovery journal");
        Properties p=new Properties();try(InputStream in=new FileInputStream(journal)){p.load(in);}
        if(!"2".equals(p.getProperty("format"))||!Arrays.asList("activating","committed").contains(p.getProperty("phase")))throw new IOException("Unsupported all-world recovery journal");
        if(p.getProperty("components")==null||!p.getProperty("recovery","").matches("[0-9a-f-]{36}"))throw new IOException("Invalid recovery destination");
        List<String> components=components(p.getProperty("components"));
        for(int i=0;i<components.size();i++)if(!Arrays.asList("true","false").contains(p.getProperty("had."+i)))throw new IOException("Invalid all-world recovery inventory");
        if(p.getProperty("phase").equals("committed")) {
            File retainedRoot=new File(base,"all-session-recovery");if(Files.isSymbolicLink(retainedRoot.toPath()))throw new IOException("Recovery copy folder cannot be a symbolic link");
            File retained=new File(retainedRoot,p.getProperty("recovery")),rollback=new File(base,"all-session-rollback");
            if(exists(rollback)) {
                if(exists(retained))throw new IOException("Recovery copies conflict; retained data requires review");
                try(FileOutputStream out=new FileOutputStream(new File(rollback,"recovery.properties"))){p.store(out,"Prior complete world trees retained after restore");out.getFD().sync();}
                syncDirectory(rollback);move(rollback,retained);
            }
            Files.delete(journal.toPath());syncDirectory(base);return;
        }
        for(int i=0;i<components.size();i++) {
            File current=live(base,components.get(i)),old=previous(base,i);
            if(exists(old)){SessionArchive.removeTree(current);move(old,current);}
            else if(!Boolean.parseBoolean(p.getProperty("had."+i)))SessionArchive.removeTree(current);
            // An old tree already moved back during an interrupted recovery remains intact.
        }
        SessionArchive.removeTree(new File(base,"all-session-rollback"));Files.delete(journal.toPath());syncDirectory(base);
    }
    static String activate(File base,File staging,String selected,boolean replace)throws IOException {return activate(base,staging,selected,replace,worldComponents(),i->{});}
    static String activate(File base,File staging,String selected,boolean replace,Hook hook)throws IOException {return activate(base,staging,selected,replace,worldComponents(),hook);}
    static String activate(File base,File staging,String selected,boolean replace,List<String> included)throws IOException {return activate(base,staging,selected,replace,included,i->{});}
    static String activate(File base,File staging,String selected,boolean replace,List<String> included,Hook hook)throws IOException {
        WorldProfiles.valid(selected);recover(base);List<String> parts=components(String.join(",",included));SessionArchive.syncDirectories(staging,s->{});
        File rollback=new File(base,"all-session-rollback");if(exists(rollback))throw new IOException("Previous recovery files require review before restoring");
        File global=new File(staging,"global");Files.createDirectories(global.toPath());
        Properties selection=new Properties();selection.setProperty("active",selected);
        try(FileOutputStream out=new FileOutputStream(new File(global,"world-profile.properties"))){selection.store(out,"Selected restored world");out.getFD().sync();}
        if(!new File(global,"preferences.properties").isFile())throw new IOException("All-world backup is missing device settings");
        Properties journal=new Properties();journal.setProperty("format","2");journal.setProperty("phase","activating");journal.setProperty("components",String.join(",",included));String recovery=UUID.randomUUID().toString();journal.setProperty("recovery",recovery);
        for(int i=0;i<parts.size();i++) {
            String part=parts.get(i);File current=live(base,part),next=new File(staging,part.startsWith("global/")?part:"worlds/"+part);
            if(Files.isSymbolicLink(current.toPath())||Files.isSymbolicLink(next.toPath()))throw new IOException("A restored world component cannot be a symbolic link");
            if(!exists(next))throw new IOException("Missing staged world component: "+part);
            if(!replace&&!part.startsWith("global/")&&exists(current)) {
                File[] children=current.listFiles();if(children==null||children.length>0)throw new IOException("Select Replace all worlds before restoring existing sessions");
            }
            journal.setProperty("had."+i,String.valueOf(exists(current)));
        }
        store(base,journal);
        try {
            for(int i=0;i<parts.size();i++) {
                String part=parts.get(i);File current=live(base,part),next=new File(staging,part.startsWith("global/")?part:"worlds/"+part);
                if(exists(current))move(current,previous(base,i));move(next,current);hook.moved(i);
            }
            journal.setProperty("phase","committed");store(base,journal);
        } catch(IOException e){try{recover(base);}catch(IOException rollbackError){e.addSuppressed(rollbackError);}throw e;}
        // The committed journal persists until cleanup succeeds. A restart never reverts committed worlds.
        try {recover(base);}catch(IOException cleanupError) {
            // Activation is already durable. Keep the committed journal for startup recovery-copy retention.
        }
        return "all-session-recovery/"+recovery;
    }
    private AllProfileSwap(){}
}
