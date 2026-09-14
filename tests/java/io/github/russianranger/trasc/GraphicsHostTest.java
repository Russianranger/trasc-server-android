package io.github.russianranger.trasc;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class GraphicsHostTest {
    public static void main(String[] args)throws Exception {
        File executable=new File(args[0]);Path root=Files.createTempDirectory("trasc-gpu-");
        File socket=root.resolve("gpu.sock").toFile(),log=root.resolve("client-gpu.log").toFile();
        GraphicsBridge bridge=GraphicsBridge.start(executable,socket,log);
        try {
            if(!bridge.alive()||!socket.exists())throw new AssertionError("GPU bridge did not start");
            // bind() creates a 0777 socket; the native 0077 umask restricts it to its owner.
            if(!Files.getPosixFilePermissions(socket.toPath()).equals(java.nio.file.attribute.PosixFilePermissions.fromString("rwx------")))
                throw new AssertionError("GPU socket is not private");
            String text="";long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(3);
            do {
                if(log.exists())text=Files.readString(log.toPath());
                if(text.contains("TRASC GPU version:"))break;
                Thread.sleep(50);
            }while(System.nanoTime()<deadline);
            if(!text.contains("TRASC GPU renderer:")||!text.contains("TRASC GPU version:"))throw new AssertionError("Missing real driver identity");
        } finally{bridge.stop();}
        if(bridge.alive()||socket.exists())throw new AssertionError("GPU process/socket leaked after stop");
        try{GraphicsBridge.start(new File("/bin/false"),socket,log);throw new AssertionError("Failed process accepted");}
        catch(IOException expected){}
        if(socket.exists())throw new AssertionError("Failed start left a socket");
        System.out.println("PASS: native GLES driver probe, private socket, Java lifecycle cleanup and failed-start recovery");
    }
}
