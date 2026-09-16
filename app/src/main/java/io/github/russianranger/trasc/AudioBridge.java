package io.github.russianranger.trasc;

import android.content.Context;
import android.media.*;
import android.net.*;
import android.os.Handler;
import android.os.Looper;
import android.system.Os;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.*;

/** App-private ALSA to AudioTrack bridge. No TCP, capture device or root access. */
final class AudioBridge implements AutoCloseable {
    private final File path,log;
    private final LocalSocket bound=new LocalSocket();
    private LocalServerSocket server;
    private final Set<Connection> connections=new HashSet<>();
    private volatile boolean closed;
    private volatile float volume=1;
    private final AudioManager manager;
    private final AudioFocusRequest focus;
    private final AudioAttributes attributes=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();
    private int opened;

    static AudioBridge start(Context context,File path,File log)throws Exception {
        AudioBridge bridge=new AudioBridge(context,path,log);
        try{bridge.listen();return bridge;}catch(Exception e){bridge.close();throw e;}
    }
    private AudioBridge(Context context,File path,File log)throws IOException {
        this.path=path;this.log=log;manager=(AudioManager)context.getSystemService(Context.AUDIO_SERVICE);
        focus=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).setAudioAttributes(attributes)
            .setOnAudioFocusChangeListener(change->{
                volume=change==AudioManager.AUDIOFOCUS_GAIN?1:change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK?.2f:0;
                synchronized(connections){for(Connection c:connections)c.volume(volume);}
                record("focus="+change);
            },new Handler(Looper.getMainLooper())).build();
        if(log.exists())Files.move(log.toPath(),new File(log.getParentFile(),"client-audio.previous.log").toPath(),StandardCopyOption.REPLACE_EXISTING);
    }
    private void listen()throws Exception {
        Files.deleteIfExists(path.toPath());
        bound.bind(new LocalSocketAddress(path.getPath(),LocalSocketAddress.Namespace.FILESYSTEM));
        Os.chmod(path.getPath(),0600);server=new LocalServerSocket(bound.getFileDescriptor());
        int granted=manager.requestAudioFocus(focus);volume=granted==AudioManager.AUDIOFOCUS_REQUEST_GRANTED?1:0;
        record("bridge=alsa-audiotrack protocol=1 rate=48000 channels=2 focus="+granted+" media_volume="+manager.getStreamVolume(AudioManager.STREAM_MUSIC));
        Thread listener=new Thread(()->{
            try {
                while(!closed) {
                    LocalSocket socket=server.accept();
                    synchronized(connections) {
                        if(closed||connections.size()>=8||socket.getPeerCredentials().getUid()!=android.os.Process.myUid()){socket.close();continue;}
                        Connection c=new Connection(socket);connections.add(c);opened++;
                        Thread worker=new Thread(c,"client-audio-playback");worker.setDaemon(true);worker.start();
                    }
                }
            } catch(Exception e){if(!closed)record("listener_error="+e);}
        },"client-audio-listener");listener.setDaemon(true);listener.start();
    }
    private synchronized void record(String text) {
        try {
            if(log.length()>256*1024)return;
            try(FileWriter out=new FileWriter(log,true)){out.write(java.time.Instant.now()+" "+text+"\n");}
        }catch(IOException ignored){}
    }
    private final class Connection implements Runnable,AudioPcmSession.Sink {
        final LocalSocket socket;AudioTrack track;int capacity;boolean ended;
        Connection(LocalSocket socket){this.socket=socket;}
        public void run(){
            AudioPcmSession session=new AudioPcmSession();
            try{session.run(socket.getInputStream(),socket.getOutputStream(),this);}
            catch(Exception e){if(!closed)record("stream_error="+e);}
            finally{close();synchronized(connections){connections.remove(this);}record("stream_closed frames="+session.frames+" nonzero_samples="+session.nonzeroSamples);}
        }
        public synchronized void configure(int frames)throws IOException{capacity=frames;reset();}
        public synchronized void reset()throws IOException {
            if(ended)throw new IOException("Audio stream closed");
            if(track!=null){track.release();track=null;}
            int minimum=AudioTrack.getMinBufferSize(48000,AudioFormat.CHANNEL_OUT_STEREO,AudioFormat.ENCODING_PCM_16BIT);
            if(minimum<=0)throw new IOException("Stereo audio format unavailable");
            track=new AudioTrack.Builder().setAudioAttributes(attributes)
                .setAudioFormat(new AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(48000).setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build())
                .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(Math.max(minimum,capacity*4)).build();
            if(track.getState()!=AudioTrack.STATE_INITIALIZED)throw new IOException("Could not initialize Android audio");
            track.setVolume(volume);
        }
        public synchronized void start(){if(track!=null)track.play();}
        public synchronized void stop(){if(track!=null){track.pause();track.flush();}}
        public synchronized int position()throws IOException{if(track==null)throw new IOException("Audio stream closed");return track.getPlaybackHeadPosition();}
        public synchronized int write(byte[] bytes,int length)throws IOException{if(track==null)throw new IOException("Audio stream closed");return track.write(bytes,0,length,AudioTrack.WRITE_NON_BLOCKING);}
        synchronized void volume(float value){if(track!=null)track.setVolume(value);}
        public synchronized void close(){ended=true;if(track!=null){track.release();track=null;}try{socket.close();}catch(IOException ignored){}}
    }
    public void close() {
        if(closed)return;closed=true;
        try{if(server!=null)server.close();}catch(IOException ignored){}
        try{bound.close();}catch(IOException ignored){}
        synchronized(connections){for(Connection c:connections)c.close();connections.clear();}
        manager.abandonAudioFocusRequest(focus);path.delete();record("bridge_closed streams="+opened);
    }
}
