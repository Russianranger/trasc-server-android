package io.github.russianranger.trasc;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;

public final class ClientTransientPathsHostTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    interface Attempt {void run()throws Exception;}
    static void rejected(Attempt attempt)throws Exception {
        try{attempt.run();throw new AssertionError("Unsafe transient layout accepted");}catch(IOException expected){}
    }
    public static void main(String[] args)throws Exception {
        for(String home:new String[]{"/data/data/io.github.russianranger.trasc.preview","/data/user/0/io.github.russianranger.trasc.preview"}) {
            File files=new File(home,"files");
            ClientTransientPaths custom=new ClientTransientPaths(files,"custom"),traditional=new ClientTransientPaths(files,"traditional");
            check(custom.tmp.equals(new File(home,"c"))&&traditional.tmp.equals(new File(home,"t")),"Compact temp roots belong to distinct worlds");
            check(traditional.run.equals(new File(traditional.tmp,"s")),"All session sockets use the compact temp root");
            custom.validate();traditional.validate();
            File old=new File(files,"profiles/traditional/tmp/client/tmp"+ClientTransientPaths.PROOT_SOCKET_SUFFIX);
            check(ClientTransientPaths.bytes(old)>ClientTransientPaths.MAX_SOCKET_BYTES,"The old Traditional PRoot helper path exceeds the Unix limit");
        }
        ClientTransientPaths.validateSocket(new File("/"+"a".repeat(106)));
        rejected(()->ClientTransientPaths.validateSocket(new File("/"+"a".repeat(107))));
        rejected(()->ClientTransientPaths.validateSocket(new File("/"+"é".repeat(54))));
        try{new ClientTransientPaths(new File("/private/files"),"other");throw new AssertionError("Unknown profile accepted");}catch(IllegalArgumentException expected){}
        Path root=Files.createTempDirectory("client-paths-");
        try {
            Path files=root.resolve("files");Files.createDirectories(files);
            Path customData=files.resolve("work/client/prefix/user.reg"),traditionalData=files.resolve("profiles/traditional/work/client/current/eqgame.exe");
            Files.createDirectories(customData.getParent());Files.writeString(customData,"existing Wine settings");
            Files.createDirectories(traditionalData.getParent());Files.writeString(traditionalData,"owned client");
            ClientTransientPaths custom=new ClientTransientPaths(files.toFile(),"custom"),traditional=new ClientTransientPaths(files.toFile(),"traditional");
            custom.prepare();Files.writeString(custom.run.toPath().resolve("status.json"),"custom session");
            traditional.prepare();Files.writeString(traditional.run.toPath().resolve("status.json"),"traditional session");
            custom.prepare();
            check(!Files.exists(custom.run.toPath().resolve("status.json")),"Starting a client clears only its old transient session");
            check(Files.readString(traditional.run.toPath().resolve("status.json")).equals("traditional session"),"Custom restart preserves Traditional session files");
            check(Files.readString(customData).equals("existing Wine settings")&&Files.readString(traditionalData).equals("owned client"),"Persistent prefixes and imported clients never move or reset");
            check(Files.getPosixFilePermissions(custom.tmp.toPath()).equals(PosixFilePermissions.fromString("rwx------")),"Socket/temp directory is private");
            TarExtractor.remove(traditional.tmp);
            Files.createSymbolicLink(traditional.tmp.toPath(),custom.tmp.toPath());
            rejected(traditional::prepare);
            check(Files.isDirectory(custom.run.toPath()),"Linked profile temp never deletes another profile");
            Files.delete(traditional.tmp.toPath());Files.createDirectory(traditional.tmp.toPath());
            Files.createSymbolicLink(traditional.run.toPath(),custom.run.toPath());
            rejected(traditional::prepare);
            check(Files.isDirectory(custom.run.toPath()),"Linked session never deletes another profile");
            Path longParent=root.resolve("p".repeat(80));Files.createDirectories(longParent.resolve("private/files"));
            Path shortAlias=root.resolve("l");Files.createSymbolicLink(shortAlias,longParent);
            ClientTransientPaths aliased=new ClientTransientPaths(shortAlias.resolve("private/files").toFile(),"traditional");
            check(ClientTransientPaths.bytes(new File(aliased.tmp.getAbsolutePath()+ClientTransientPaths.PROOT_SOCKET_SUFFIX))<=ClientTransientPaths.MAX_SOCKET_BYTES,"The alias superficially fits the socket limit");
            rejected(aliased::prepare);
            check(Files.isDirectory(longParent.resolve("private/files")),"Canonical PRoot budget rejection preserves persistent files");
        } finally {TarExtractor.remove(root.toFile());}
        System.out.println("PASS: compact Android client paths, Unix byte limits, private temp permissions, separate profile cleanup and unchanged persistent imports/prefixes");
    }
}
