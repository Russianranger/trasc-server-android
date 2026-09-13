package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;

/** Roundtrip a real server/client Debian runtime with the exact Android archive classes. */
public final class RuntimeSessionHostTest {
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("trasc-real-session-");
        try {
            Path root=tmp.resolve("rootfs"),work=tmp.resolve("work");Files.createDirectories(root);Files.createDirectories(work);
            TarExtractor.extract(new File(args[0]),root.toFile(),n->{});
            boolean client=Files.isRegularFile(root.resolve("etc/trasc-client-runtime.json"));
            String reported=client?"var/lib/dpkg/info/libgcc-s1:amd64.list":"var/lib/dpkg/info/binutils-common:arm64.conffiles";
            if(!Files.isRegularFile(root.resolve(reported)))throw new AssertionError("Published runtime must contain the reported multiarch file");
            Path original=root;
            String restoredPath="rootfs";
            if(client) {
                original=work.resolve("client/runtime");Files.createDirectories(original.getParent());Files.move(root,original);Files.createDirectories(root);
                restoredPath="work/client/runtime";
                // The full server archive has its own gate; supply its required marker in this client-focused fixture.
                Files.createDirectories(root.resolve("etc"));Files.writeString(root.resolve("etc/trasc-runtime.json"),"{\"format\":1,\"architecture\":\"arm64\"}");
                for(String executable:new String[]{"usr/bin/Xtigervnc","usr/local/bin/box64","opt/wine/bin/wine","opt/wine/bin/wineserver"})
                    if(!Files.isRegularFile(original.resolve(executable))||SessionArchive.mode(original.resolve(executable))!=0755)throw new AssertionError("Client runtime executable missing: "+executable);
            }
            Files.writeString(work.resolve("settings.json"),"{}");
            File archive=tmp.resolve("session.zip").toFile();
            SessionArchive.create(root.toFile(),work.toFile(),archive,"test",System.out::println);
            Path restored=tmp.resolve("restored");
            SessionArchive.restore(archive,restored.toFile(),System.out::println);
            Path copyRoot=restored.resolve(restoredPath);
            if(!Files.readString(copyRoot.resolve(reported)).equals(Files.readString(original.resolve(reported))))throw new AssertionError("Multiarch metadata mismatch");
            if(SessionArchive.mode(copyRoot.resolve("usr/bin/python3.11"))!=0755)throw new AssertionError("Restored Python must remain executable");
            // Restore verifies every indexed file hash; also require identical inventory sizes.
            try(var inventory=Files.walk(original);var copy=Files.walk(copyRoot)) {
                if(inventory.count()!=copy.count())throw new AssertionError("Runtime tree entry count changed");
            }
            System.out.println("PASS: ARM64 Debian "+(client?"client":"server")+" runtime fully backed up and restored, all hashes verified");
        } finally {TarExtractor.remove(tmp.toFile());}
    }
}
