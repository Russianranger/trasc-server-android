package io.github.russianranger.trasc;

import java.io.*;
import java.util.*;

public final class AudioHostTest {
    static class Sink implements AudioPcmSession.Sink {
        boolean closed,started;int capacity,resets;byte[] pcm;
        public void configure(int frames){capacity=frames;}
        public void start(){started=true;}
        public void stop(){started=false;}
        public void reset(){resets++;}
        public int position(){return 0xf1234567;}
        public int write(byte[] bytes,int size){pcm=Arrays.copyOf(bytes,size);return 4;}
        public void close(){closed=true;}
    }
    static byte[] words(int... words)throws Exception {
        ByteArrayOutputStream data=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(data);
        for(int w:words)out.writeInt(Integer.reverseBytes(w));return data.toByteArray();
    }
    static void check(boolean value){if(!value)throw new AssertionError();}
    // Android starts only once its watermark is met, including after an underrun.
    // The producer cannot queue beyond its smaller ALSA ring while its head is frozen.
    static class BufferedTrack implements AudioBufferPolicy.Track {
        int size=8192,threshold=8192,queued,played;boolean flowing;
        public int resize(int frames){size=frames;return size;}
        public int startThreshold(int frames){threshold=frames;return threshold;}
        void write(int frames){check(queued+frames<=size);queued+=frames;}
        void advance(int frames){
            if(queued>=Math.min(size,threshold))flowing=true;
            if(flowing){int n=Math.min(queued,frames);played+=n;queued-=n;if(queued==0)flowing=false;}
        }
    }
    static void checkStartup()throws Exception {
        BufferedTrack old=new BufferedTrack();old.write(1920);old.advance(48000);
        check(old.played==0); // Reproduces the observed one-buffer stalemate.
        for(boolean modern:new boolean[]{false,true})for(int ring:new int[]{480,1920,3840}) {
            BufferedTrack fixed=new BufferedTrack();AudioBufferPolicy.configure(fixed,ring,modern);
            for(int restart=0;restart<3;restart++) {
                // Begin with silence, then permit the caller to keep feeding real samples.
                int before=fixed.played;fixed.write(ring);fixed.advance(48000);
                check(fixed.played-before==ring&&fixed.queued==0);
                for(int i=0;i<10;i++){fixed.write(ring);fixed.advance(48000);}
                check(fixed.played-before==ring*11);
            }
        }
        boolean rejected=false;
        try{AudioBufferPolicy.configure(new AudioBufferPolicy.Track(){
            public int resize(int frames){return 8192;}
            public int startThreshold(int frames){return 8192;}
        },1920,true);}catch(IOException expected){rejected=true;}
        check(rejected);
        System.out.println("PASS: old hardware watermark stalls a 1920-frame producer; configured buffers progress after startup and repeated underruns");
    }
    public static void main(String[] args)throws Exception {
        checkStartup();
        byte[] request=words(0x50414c54,1,48000,2,3840,5,1,4,2,0xfffe0001,0x12345678,3,2);
        Sink sink=new Sink();AudioPcmSession session=new AudioPcmSession();ByteArrayOutputStream response=new ByteArrayOutputStream();
        session.run(new ByteArrayInputStream(request),response,sink);
        check(Arrays.equals(response.toByteArray(),words(0,0,0,1,0xf1234567,0)));
        check(sink.capacity==3840&&sink.resets==1&&sink.closed&&!sink.started);
        check(Arrays.equals(sink.pcm,new byte[]{1,0,-2,-1,0x78,0x56,0x34,0x12}));
        check(session.frames==1&&session.nonzeroSamples==2);
        for(byte[] bad:new byte[][]{words(0,1,48000,2,3840),words(0x50414c54,1,48000,2,48001),words(0x50414c54,1,48000,2,3840,4,4097),words(0x50414c54,1,48000,2,3840,4,2,1)}) {
            sink=new Sink();boolean rejected=false;
            try{new AudioPcmSession().run(new ByteArrayInputStream(bad),new ByteArrayOutputStream(),sink);}catch(IOException expected){rejected=true;}
            check(rejected&&sink.closed);
        }
        System.out.println("PASS: audio wire format, stereo PCM, partial writes, playback head, invalid/truncated messages and sink cleanup");
    }
}
