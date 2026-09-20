package io.github.russianranger.trasc;

import java.io.*;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.*;
import java.util.*;

/** Explicit cleanup of diagnostic text logs. Call only after all writers stop. */
final class LogCleanup {
    static final long TWO_DAYS=48L*60*60*1000;

    static long[] clear(File work,String mode,long now,boolean writersActive)throws IOException {
        if(!mode.equals("older_2_days")&&!mode.equals("reset"))throw new IOException("Choose old-log cleanup or reset");
        if(writersActive)throw new IOException("Stop the client and server runtime before clearing logs");
        long[] result={0,0};
        for(Map.Entry<String,Path> item:LocalLogs.inventory(work).entrySet()) {
            Path path=item.getValue();String name=item.getKey();
            // JSON build/deploy manifests, retention settings, chat, backups and
            // saved exports are not diagnostic text logs and must stay intact.
            if(!(name.toLowerCase(Locale.ROOT).endsWith(".log")||
                 (name.startsWith("client/")&&LocalLogs.clientDiagnostic(name.substring(7)))))continue;
            LocalLogs.checked(work.toPath(),work.toPath().relativize(path).toString());
            if(!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS))continue;
            if(mode.equals("older_2_days")&&Files.getLastModifiedTime(path,LinkOption.NOFOLLOW_LINKS).toMillis()>=now-TWO_DAYS)continue;
            // Truncate the existing file instead of unlinking/recreating it.
            try(SeekableByteChannel log=Files.newByteChannel(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
                long bytes=log.size();
                if(bytes>0){log.truncate(0);result[0]++;result[1]+=bytes;}
            }
        }
        return result;
    }
}
