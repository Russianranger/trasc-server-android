package io.github.russianranger.trasc;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.ArrayDeque;

/** Bounded asynchronous observations of sent pointer packets, without keys or chat. */
final class PointerPacketTrace implements Closeable {
    static final int LIMIT=128*1024, QUEUE_LIMIT=256;
    private static final int END_RESERVE=512;
    private static final long FLUSH_NANOS=1_000_000_000L;
    interface Opener {OutputStream open(File file)throws IOException;}
    private final ArrayDeque<String> pending=new ArrayDeque<>();
    private final Thread worker;
    private int previousMask,maxPending;
    private long lastFree=-1000,sequence,selected,sampledIdle,droppedQueue,droppedLimit,written;
    private boolean closed,stopped;
    PointerPacketTrace(File file) {this(file,FileOutputStream::new);}
    // The opener seam permits a blocked-storage regression without slowing input.
    PointerPacketTrace(File file,Opener opener) {
        worker=new Thread(()->drain(file,opener),"TRASC pointer observations");
        try {worker.setDaemon(true);worker.start();}
        catch(SecurityException unavailable){stopped=true;}
    }
    synchronized void sent(long queued,long sent,long epoch,int type,int x,int y,int mask) {
        if(closed||stopped)return;
        sequence++;
        boolean changed=mask!=previousMask,look=((mask|previousMask)&5)!=0;
        previousMask=mask;
        if(!look&&!changed&&sent-lastFree<1000){sampledIdle++;return;}
        if(!look)lastFree=sent;
        selected++;
        if(pending.size()>=QUEUE_LIMIT){droppedQueue++;return;}
        pending.addLast("queued="+queued+" sent="+sent+" epoch="+epoch+" seq="+sequence+
            " type="+type+" x="+x+" y="+y+" buttons="+mask+"\n");
        maxPending=Math.max(maxPending,pending.size());
        notifyAll();
    }

    private OutputStream open(File file,Opener opener)throws IOException {
        File parent=file.getParentFile();
        if(parent==null||!file.getName().endsWith(".log")||Files.isSymbolicLink(parent.toPath()))return null;
        Files.createDirectories(parent.toPath());
        if(Files.exists(file.toPath(),LinkOption.NOFOLLOW_LINKS)&&
                !Files.isRegularFile(file.toPath(),LinkOption.NOFOLLOW_LINKS))return null;
        // Refuse all unsafe history destinations before rotation changes any file.
        for(int i=1;i<=5;i++) {
            Path previous=LogRetention.history(file.toPath(),i);
            if(Files.exists(previous,LinkOption.NOFOLLOW_LINKS)&&
                    !Files.isRegularFile(previous,LinkOption.NOFOLLOW_LINKS))return null;
        }
        if(file.exists())LogRetention.rotate(file);
        return new BufferedOutputStream(opener.open(file),8192);
    }

    private void drain(File file,Opener opener) {
        int bytes=0;
        String reason="closed";
        try(OutputStream output=open(file,opener)) {
            if(output==null)return;
            byte[] begin=("TRASC_POINTER_PACKETS_V1 clock=android_uptime_ms stage=socket_flush_complete"+
                " max_queue="+QUEUE_LIMIT+" max_bytes="+LIMIT+" flush_ms=1000 idle_sample_ms=1000\n")
                .getBytes(StandardCharsets.US_ASCII);
            output.write(begin);bytes+=begin.length;
            long lastFlush=System.nanoTime();
            for(;;) {
                String line=null;
                synchronized(this) {
                    if(pending.isEmpty()&&!closed) {
                        long remaining=FLUSH_NANOS-(System.nanoTime()-lastFlush);
                        if(remaining>0)wait(Math.max(1,remaining/1_000_000L));
                    }
                    if(!pending.isEmpty())line=pending.removeFirst();
                    else if(closed)break;
                }
                if(line!=null) {
                    byte[] data=line.getBytes(StandardCharsets.US_ASCII);
                    if(data.length>LIMIT-END_RESERVE-bytes) {
                        synchronized(this) {
                            stopped=true;droppedLimit+=1+pending.size();pending.clear();
                        }
                        reason="byte_limit";break;
                    }
                    output.write(data);bytes+=data.length;
                    synchronized(this){written++;}
                }
                if(System.nanoTime()-lastFlush>=FLUSH_NANOS) {
                    output.flush();lastFlush=System.nanoTime();
                }
            }
            String end;
            synchronized(this) {
                stopped=true;
                end="end="+reason+" bytes_before_end="+bytes+" packets="+sequence+
                    " selected="+selected+" written="+written+" sampled_idle="+sampledIdle+
                    " dropped_queue="+droppedQueue+" dropped_limit="+droppedLimit+
                    " max_pending="+maxPending+"\n";
            }
            byte[] receipt=end.getBytes(StandardCharsets.US_ASCII);
            if(receipt.length>END_RESERVE||bytes+receipt.length>LIMIT)throw new IOException("Observation receipt exceeds its reserved bound");
            output.write(receipt);output.flush();
        } catch(IOException|SecurityException|InterruptedException unavailable) {
            // Diagnostic failure never blocks input or changes its wire packets.
            if(unavailable instanceof InterruptedException)Thread.currentThread().interrupt();
        } finally {
            synchronized(this){stopped=true;pending.clear();notifyAll();}
        }
    }
    @Override public void close() {
        synchronized(this){closed=true;notifyAll();}
        if(Thread.currentThread()!=worker)try{worker.join(50);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();}
    }
    // Used by host verification after close, never by the input writer.
    boolean awaitClosed(long milliseconds)throws InterruptedException {worker.join(milliseconds);return !worker.isAlive();}
}
