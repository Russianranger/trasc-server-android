package io.github.russianranger.trasc;

import java.util.*;

/** Paced physical keys: EQ polls input and does not implement Ctrl+A in chat. */
final class GameCommand {
    static final class Stroke {
        final int delay,symbol;final boolean down;
        Stroke(int delay,int symbol,boolean down){this.delay=delay;this.symbol=symbol;this.down=down;}
    }
    static List<Stroke> classicNpcs(){return chat("#tim");}
    static String stoneViewport(String resolution){
        if(!"1280x720".equals(resolution))throw new IllegalArgumentException("StoneUI viewport requires 1280×720 in Client launch options");
        return "/viewport 179 0 920 480";
    }
    static String fullViewport(String resolution){
        if(!Arrays.asList("640x480","800x600","960x540","1024x768","1280x720").contains(resolution))
            throw new IllegalArgumentException("Cannot determine the active client resolution; reopen the client display");
        return "/viewport 0 0 "+resolution.replace('x',' ');
    }
    static List<Stroke> chat(String command){
        if(command.isEmpty()||command.length()>256)throw new IllegalArgumentException("Invalid game command");
        for(char symbol:command.toCharArray())if(symbol<32||symbol>126)throw new IllegalArgumentException("Invalid game command character");
        List<Stroke> steps=new ArrayList<>();int time=200;
        // Cancel an existing chat edit without sending it. Slash opens command
        // entry; Backspace removes it. Explicit Shift+3 supplies the US # key.
        List<Integer> keys=new ArrayList<>(Arrays.asList(0xff1b,(int)'/',0xff08));
        for(char symbol:command.toCharArray()){
            if(symbol=='#')keys.add(0xffe1);
            keys.add((int)symbol);
        }
        keys.add(0xff0d);
        for(int key:keys){
            if(key==0xffe1){steps.add(new Stroke(time,key,true));time+=100;continue;}
            steps.add(new Stroke(time,key,true));time+=120;
            steps.add(new Stroke(time,key,false));time+=100;
            if(key=='#'){steps.add(new Stroke(time,0xffe1,false));time+=100;}
        }
        return steps;
    }
}
