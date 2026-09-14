package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.util.UUID;

/** Preserve Wine settings before explicitly creating a fresh prefix. Game files stay beside it. */
final class ClientPrefix {
    static File preserve(File prefix)throws IOException {
        Path source=prefix.toPath();
        if(!Files.exists(source,LinkOption.NOFOLLOW_LINKS)){Files.createDirectories(source);return null;}
        if(Files.isSymbolicLink(source)||!Files.isDirectory(source))throw new IOException("Wine prefix must be a directory");
        Path backups=source.getParent().resolve("prefix-backups");
        if(Files.isSymbolicLink(backups))throw new IOException("Wine prefix backups must be a directory");
        Files.createDirectories(backups);
        Path saved=backups.resolve("prefix-"+System.currentTimeMillis()+"-"+UUID.randomUUID());
        Files.move(source,saved,StandardCopyOption.ATOMIC_MOVE);
        try{Files.createDirectory(source);}
        catch(IOException error){Files.move(saved,source,StandardCopyOption.ATOMIC_MOVE);throw error;}
        return saved.toFile();
    }
}
