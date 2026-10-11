package io.github.russianranger.trasc;

import java.io.*;
/** Fixed-buffer SAF transport. Never materialize an archive in Java memory. */
final class SessionTransfer {
    static final int BUFFER_BYTES=1024*1024;
    static long copy(InputStream in,OutputStream out,long expected,File storage,SessionArchive.Progress progress)throws IOException {
        if(expected>SessionArchive.MAX_ARCHIVE_BYTES||expected< -1)throw new IOException("Archive exceeds supported size");
        if(storage!=null&&expected>=0)SessionArchive.checkSpace(storage,expected);
        byte[] buffer=new byte[BUFFER_BYTES];long copied=0;progress.bytes(0,expected);
        int n;while((n=in.read(buffer))!=-1) {
            progress.check();if(copied>SessionArchive.MAX_ARCHIVE_BYTES-n)throw new IOException("Archive exceeds supported size");
            if(storage!=null)SessionArchive.checkSpace(storage,n);
            out.write(buffer,0,n);copied+=n;progress.bytes(copied,expected);
        }
        if(expected>=0&&copied!=expected)throw new IOException("Archive changed or transfer was truncated");
        out.flush();progress.check();return copied;
    }
    private SessionTransfer(){}
}
