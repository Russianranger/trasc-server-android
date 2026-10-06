package io.github.russianranger.trasc;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.attribute.PosixFilePermissions;

/** Short, disposable host paths for PRoot and Unix sockets; imports never move. */
final class ClientTransientPaths {
    // Diagnostic upper bound: PRoot runs the guest as uid 0. Wine may append
    // two unsigned 64-bit stat identifiers before its socket filename.
    static final String WINE_SOCKET_SUFFIX="/.wine-0/server-ffffffffffffffff-ffffffffffffffff/socket";
    static final String PROOT_SOCKET_SUFFIX="/prootshm-2147483647-XXXXXX";
    static final String PROOT_FALLBACK_SOCKET_SUFFIX="/proot-2147483647-XXXXXX";
    static final int MAX_SOCKET_BYTES=107;
    final File data,tmp,run;

    ClientTransientPaths(File appFiles,String profile) {
        final String directory;
        if("custom".equals(profile))directory="c";
        else if("traditional".equals(profile))directory="t";
        else throw new IllegalArgumentException("Unknown world profile");
        data=appFiles.getAbsoluteFile().getParentFile();
        if(data==null)throw new IllegalArgumentException("Missing app-private data directory");
        tmp=new File(data,directory);run=new File(tmp,"s");
    }
    static int bytes(File path){return path.getAbsolutePath().getBytes(StandardCharsets.UTF_8).length;}
    static void validateSocket(File path)throws IOException {
        if(bytes(path)>MAX_SOCKET_BYTES)
            throw new IOException("The private client socket path exceeds the Unix socket limit: "+path);
    }
    void validate()throws IOException {
        for(File directory:new File[]{data,tmp,run}) {
            if(Files.isSymbolicLink(directory.toPath()))throw new IOException("Client temporary directories cannot be symbolic links");
            if(Files.exists(directory.toPath(),LinkOption.NOFOLLOW_LINKS)&&!directory.isDirectory())
                throw new IOException("Invalid client temporary directory: "+directory);
        }
        // PRoot remaps overlong translated Wine sockets via its own temporary
        // binding. Bound those generated names, rather than rejecting a valid
        // Android home for Wine's theoretical device/inode upper bound.
        // PRoot canonicalizes PROOT_TMP_DIR before creating these names.
        File canonicalTmp=tmp.getCanonicalFile();
        validateSocket(new File(canonicalTmp.getPath()+PROOT_SOCKET_SUFFIX));
        validateSocket(new File(canonicalTmp.getPath()+PROOT_FALLBACK_SOCKET_SUFFIX));
        for(String name:new String[]{"display.sock","frames.sock","input.sock","audio.sock"})
            validateSocket(new File(run,name));
        validateSocket(new File(tmp,".virgl_test"));
    }
    void prepare()throws IOException {
        validate();
        // Only this profile's disposable directory is reset. Other profile
        // sockets and every game, Wine prefix and server file remain outside it.
        TarExtractor.remove(tmp);
        Files.createDirectory(tmp.toPath());
        Files.setPosixFilePermissions(tmp.toPath(),PosixFilePermissions.fromString("rwx------"));
        Files.createDirectory(run.toPath());
        Files.setPosixFilePermissions(run.toPath(),PosixFilePermissions.fromString("rwx------"));
    }
}
