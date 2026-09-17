package io.github.russianranger.trasc;

import java.util.*;

/** Paced physical keys: EQ polls input and does not implement Ctrl+A in chat. */
final class GameCommand {
    static final class Stroke {
        final int delay,symbol;final boolean down;
        Stroke(int delay,int symbol,boolean down){this.delay=delay;this.symbol=symbol;this.down=down;}
    }
    static List<Stroke> classicNpcs(){
        List<Stroke> steps=new ArrayList<>();int time=200;
        // Cancel an existing chat edit without sending it. Slash opens command
        // entry; Backspace removes it. Explicit Shift+3 supplies the US # key.
        for(int key:new int[]{0xff1b,'/',0xff08,0xffe1,'#','t','i','m',0xff0d}){
            if(key==0xffe1){steps.add(new Stroke(time,key,true));time+=100;continue;}
            steps.add(new Stroke(time,key,true));time+=120;
            steps.add(new Stroke(time,key,false));time+=100;
            if(key=='#'){steps.add(new Stroke(time,0xffe1,false));time+=100;}
        }
        return steps;
    }
}
