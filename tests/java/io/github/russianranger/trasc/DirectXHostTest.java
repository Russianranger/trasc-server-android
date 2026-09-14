package io.github.russianranger.trasc;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class DirectXHostTest {
    public static void main(String[] args)throws Exception {
        File archive=new File(args[0]),extractor=new File(args[1]),target=new File(args[2]);
        File log=new File(target.getParentFile(),"client-directx-test.log");
        DirectXInstaller.install(archive,target,extractor,log);
        if(!DirectXInstaller.installed(target))throw new AssertionError("No model helpers");
        Map<String,String> hashes=new HashMap<>();
        for(String name:DirectXInstaller.DLLS) {
            File dll=new File(target,name);DirectXInstaller.verifyPe32(dll);
            hashes.put(name,DirectXInstaller.sha256(dll));System.out.println(name+" "+dll.length()+" "+hashes.get(name));
        }
        File invalid=File.createTempFile("bad-directx-",".exe",target.getParentFile());
        try {
            try(RandomAccessFile file=new RandomAccessFile(invalid,"rw")){file.setLength(DirectXInstaller.BYTES);}
            try{DirectXInstaller.install(invalid,target,new File("/must-not-execute"),log);throw new AssertionError("Accepted changed redist");}
            catch(IOException expected){if(!expected.getMessage().contains("checksum"))throw expected;}
            for(String name:DirectXInstaller.DLLS)if(!DirectXInstaller.sha256(new File(target,name)).equals(hashes.get(name)))throw new AssertionError("Changed existing helpers");
        } finally {invalid.delete();}
        DirectXInstaller.install(archive,target,extractor,log);
        File previous=new File(target.getParentFile(),"directx-previous");
        if(!DirectXInstaller.installed(previous))throw new AssertionError("Missing previous install");
        TarExtractor.remove(target);DirectXInstaller.recover(target);
        if(!DirectXInstaller.installed(target))throw new AssertionError("Interrupted swap not recovered");
        if(!archive.isFile())throw new AssertionError("Original installer was deleted");
        System.out.println("PASS: exact Microsoft redist extraction, x86 helpers, changed-download rejection, prior install preservation and interrupted-swap recovery");
    }
}
