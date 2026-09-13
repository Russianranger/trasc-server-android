package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;

/** Roundtrip the actual published Debian runtime with the exact Android archive classes. */
public final class RuntimeSessionHostTest {
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("trasc-real-session-");
        try {
            Path root=tmp.resolve("rootfs"),work=tmp.resolve("work");Files.createDirectories(root);Files.createDirectories(work);
            TarExtractor.extract(new File(args[0]),root.toFile(),n->{});
            String reported="var/lib/dpkg/info/binutils-common:arm64.conffiles";
            if(!Files.isRegularFile(root.resolve(reported)))throw new AssertionError("Published runtime must contain the reported multiarch file");
            Files.writeString(work.resolve("settings.json"),"{}");
            File archive=tmp.resolve("session.zip").toFile();
            SessionArchive.create(root.toFile(),work.toFile(),archive,"test",System.out::println);
            Path restored=tmp.resolve("restored");
            SessionArchive.restore(archive,restored.toFile(),System.out::println);
            if(!Files.readString(restored.resolve("rootfs/"+reported)).equals(Files.readString(root.resolve(reported))))throw new AssertionError("Multiarch metadata mismatch");
            if(SessionArchive.mode(restored.resolve("rootfs/usr/bin/python3.11"))!=0755)throw new AssertionError("Restored Python must remain executable");
            // Restore verifies every indexed file hash; also require identical inventory sizes.
            try(var original=Files.walk(root);var copy=Files.walk(restored.resolve("rootfs"))) {
                if(original.count()!=copy.count())throw new AssertionError("Runtime tree entry count changed");
            }
            System.out.println("PASS: published ARM64 Debian runtime fully backed up and restored, all hashes verified");
        } finally {TarExtractor.remove(tmp.toFile());}
    }
}
