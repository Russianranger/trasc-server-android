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
            check(profiles.home("takp").equals(root.resolve("profiles/takp").toFile()),"TAKP has its own home");
            check(WorldProfiles.label("takp").equals("TAKP World"),"TAKP uses the world selector label");
            Path traditional=root.resolve("profiles/traditional/work/settings.json");Files.createDirectories(traditional.getParent());Files.writeString(traditional,"traditional world");
            rejected(()->profiles.enter("custom"));
            rejected(()->profiles.beginSwitch("custom"));
            rejected(()->profiles.home("../work"));
            try(WorldProfiles.Lease cleanup=profiles.enter("traditional")) {
                try(WorldProfiles.Lease transfer=profiles.enter("traditional")) {rejected(profiles::beginMaintenance);}
                profiles.beginMaintenance();
                try {rejected(()->profiles.enter("traditional"));rejected(()->profiles.beginSwitch("traditional"));}
                finally {profiles.endMaintenance();}
                try(WorldProfiles.Lease request=profiles.enter("traditional")) {check(request!=null,"Maintenance releases requests");}
            }
            try(WorldProfiles.Lease operation=profiles.enter("traditional")) {operation.close();} // Closing twice must not underflow.
            profiles.beginSwitch("traditional");profiles.select("takp");profiles.endSwitch();
            check(new WorldProfiles(root.toFile()).current().equals("takp"),"TAKP selection survives restart");
            Path takp=profiles.home("takp").toPath().resolve("work");Files.createDirectories(takp);
            Files.writeString(takp.resolve("settings.json"),"{\"profile\":\"takp\",\"database\":\"takp\"}");
            rejected(()->profiles.enter("traditional"));
            try(WorldProfiles.Lease operation=profiles.enter("takp")){rejected(()->profiles.beginSwitch("takp"));}
            Path takpBackup=takp.resolve("backups/database-20261009-120000-ab12.sql.gz"),traditionalBackup=traditional.getParent().resolve("backups/database-20261009-120000-ab12.sql.gz");
            Files.createDirectories(takpBackup.getParent());Files.createDirectories(traditionalBackup.getParent());
            Files.writeString(takpBackup,"TAKP backup");Files.writeString(traditionalBackup,"Traditional backup");
            StorageFiles.Preview review=StorageFiles.preview(traditional.getParent().toFile(),java.util.Collections.singletonList("backups/"+traditionalBackup.getFileName()));
            rejected(()->StorageFiles.delete(takp.toFile(),review.paths,review.token));
            check(Files.readString(takpBackup).equals("TAKP backup"),"Old-profile cleanup review cannot delete TAKP data");
            profiles.beginSwitch("takp");profiles.select("custom");profiles.endSwitch();
            check(Files.readString(custom).equals("existing world"),"Switch back preserves Custom settings");
            check(Files.readString(traditional).equals("traditional world")&&Files.readString(takp.resolve("settings.json")).contains("takp"),"All inactive world settings stay intact");
            for(String id:new String[]{"traditional","takp"}){
                Path path=root.resolve("profiles/"+id),saved=root.resolve("profiles/"+id+"-saved");Files.move(path,saved);
                Files.createSymbolicLink(path,root.resolve("work"));rejected(()->profiles.home(id));Files.delete(path);Files.move(saved,path);
            }
            Files.writeString(root.resolve("world-profile.properties"),"active=unknown\n");
            WorldProfiles corrupt=new WorldProfiles(root.toFile());rejected(()->corrupt.enter("custom"));
            Path runtime=root.resolve("rootfs");Files.createDirectories(runtime.resolve("etc"));Files.writeString(runtime.resolve("etc/trasc-runtime.json"),"{}");
            File archive=root.resolve("traditional.zip").toFile();
            SessionArchive.create(runtime.toFile(),custom.getParent().toFile(),archive,"test","traditional",s->{});
            SessionArchive.requireProfile(archive,"traditional");rejected(()->SessionArchive.requireProfile(archive,"custom"));
            rejected(()->SessionArchive.requireProfile(archive,"takp"));
            Path takpRuntime=root.resolve("profiles/takp/rootfs");Files.createDirectories(takpRuntime.resolve("etc"));
            Files.writeString(takpRuntime.resolve("etc/trasc-runtime.json"),"{\"format\":1,\"architecture\":\"arm64\",\"profile\":\"takp\",\"runtime\":\"takp-1.0\",\"build_adapter\":1}");
            for(String file:new String[]{"client/current/eqgame.exe","client/prefix/user.reg","database/ibdata1"}){
                Path path=takp.resolve(file);Files.createDirectories(path.getParent());Files.writeString(path,"TAKP "+file);
            }
            File takpArchive=root.resolve("takp.zip").toFile();
            SessionArchive.create(takpRuntime.toFile(),takp.toFile(),takpArchive,"test","takp",s->{});
            SessionArchive.requireProfile(takpArchive,"takp");
            rejected(()->SessionArchive.requireProfile(takpArchive,"custom"));rejected(()->SessionArchive.requireProfile(takpArchive,"traditional"));
            Path restored=root.resolve("restored-takp");SessionArchive.restore(takpArchive,restored.toFile(),s->{});
            for(String file:new String[]{"settings.json","client/current/eqgame.exe","client/prefix/user.reg","database/ibdata1"})
                check(Files.readString(restored.resolve("work/"+file)).equals(Files.readString(takp.resolve(file))),"TAKP session preserves "+file);
            File legacy=root.resolve("legacy.zip").toFile();ManagementHostTest.rewriteZip(archive,legacy,SessionArchive.MANIFEST,"format=1\napp_version=old\n");
            SessionArchive.requireProfile(legacy,"custom");rejected(()->SessionArchive.requireProfile(legacy,"traditional"));
            rejected(()->SessionArchive.requireProfile(legacy,"takp"));
            System.out.println("Three-world isolation, selection persistence, stale cleanup rejection, operation guards and TAKP session roundtrip passed");
        } finally {TarExtractor.remove(root.toFile());}
    }
}
