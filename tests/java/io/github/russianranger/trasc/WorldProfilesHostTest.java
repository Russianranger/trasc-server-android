package io.github.russianranger.trasc;
import java.io.*;
import java.nio.file.*;
import java.util.concurrent.*;

public final class WorldProfilesHostTest {
    interface Task {void run()throws Exception;}
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static void rejected(Task task)throws Exception {try{task.run();throw new AssertionError("Unsafe operation accepted");}catch(IOException expected){}}
    public static void main(String[] args)throws Exception {
        Path root=Files.createTempDirectory("trasc-worlds-");
        try {
            WorldProfiles profiles=new WorldProfiles(root.toFile());
            check(profiles.current().equals("custom"),"Existing installs stay Custom");
            check(profiles.home("custom").equals(root.toFile()),"Existing home never moves");
            Path custom=root.resolve("work/settings.json");Files.createDirectories(custom.getParent());Files.writeString(custom,"existing world");
            try(WorldProfiles.Lease picker=profiles.enter("custom")) {rejected(()->profiles.beginSwitch("custom"));}
            profiles.beginSwitch("custom");
            rejected(()->profiles.enter("custom"));
            profiles.select("traditional");profiles.endSwitch();
            check(Files.readString(custom).equals("existing world"),"Switch must not touch Custom data");
            check(new WorldProfiles(root.toFile()).current().equals("traditional"),"Selection survives restart");
            check(profiles.home("traditional").equals(root.resolve("profiles/traditional").toFile()),"Traditional home is separate");
            rejected(()->profiles.enter("custom"));
            rejected(()->profiles.beginSwitch("custom"));
            rejected(()->profiles.home("../work"));
            try(WorldProfiles.Lease operation=profiles.enter("traditional")) {operation.close();} // Closing twice must not underflow.
            profiles.beginSwitch("traditional");profiles.select("custom");profiles.endSwitch();
            check(Files.readString(custom).equals("existing world"),"Switch back preserves Custom settings");
            Files.createDirectories(root.resolve("profiles"));Files.createSymbolicLink(root.resolve("profiles/traditional"),root.resolve("work"));
            rejected(()->profiles.home("traditional"));Files.delete(root.resolve("profiles/traditional"));
            Files.writeString(root.resolve("world-profile.properties"),"active=unknown\n");
            WorldProfiles corrupt=new WorldProfiles(root.toFile());rejected(()->corrupt.enter("custom"));
            Path runtime=root.resolve("rootfs");Files.createDirectories(runtime.resolve("etc"));Files.writeString(runtime.resolve("etc/trasc-runtime.json"),"{}");
            File archive=root.resolve("traditional.zip").toFile();
            SessionArchive.create(runtime.toFile(),custom.getParent().toFile(),archive,"test","traditional",s->{});
            SessionArchive.requireProfile(archive,"traditional");rejected(()->SessionArchive.requireProfile(archive,"custom"));
            File legacy=root.resolve("legacy.zip").toFile();ManagementHostTest.rewriteZip(archive,legacy,SessionArchive.MANIFEST,"format=1\napp_version=old\n");
            SessionArchive.requireProfile(legacy,"custom");rejected(()->SessionArchive.requireProfile(legacy,"traditional"));
            System.out.println("World profile isolation, persistence, operation guards and backup identity passed");
        } finally {TarExtractor.remove(root.toFile());}
    }
}
