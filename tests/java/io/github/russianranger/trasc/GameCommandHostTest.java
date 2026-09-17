package io.github.russianranger.trasc;
import java.util.*;
import java.nio.file.*;
public final class GameCommandHostTest {
    public static void main(String[] args)throws Exception{
        List<GameCommand.Stroke> steps=GameCommand.classicNpcs();StringBuilder wire=new StringBuilder();
        for(int cancel=0;cancel<=steps.size();cancel++){
            Map<Integer,Integer> held=new HashMap<>();int[] now={0};
            DisplayInput input=new DisplayInput(new DisplayInput.Sink(){
                public void pointer(int x,int y,int buttons){}
                public void key(int symbol,boolean down){
                    if(down){if(held.put(symbol,now[0])!=null)throw new AssertionError("Repeated held key");}
                    else if(held.remove(symbol)==null)throw new AssertionError("Unbalanced release");
                }
            });
            for(int i=0;i<cancel;i++){GameCommand.Stroke step=steps.get(i);now[0]=step.delay;input.key("command:"+step.symbol,step.symbol,step.down);}
            input.releaseAll();if(!held.isEmpty())throw new AssertionError("Cancellation leaves a key held");
        }
        Map<Integer,Integer> down=new HashMap<>();int previous=0;
        for(GameCommand.Stroke step:steps){
            if(step.delay<=previous)throw new AssertionError("Keys must be paced");previous=step.delay;
            if(step.down)down.put(step.symbol,step.delay);
            else if(step.delay-down.remove(step.symbol)<100)throw new AssertionError("Insufficient key dwell");
            wire.append(step.delay).append(' ').append(step.symbol).append(' ').append(step.down?1:0).append('\n');
        }
        if(args.length>0)Files.writeString(Path.of(args[0]),wire.toString());
        System.out.println("PASS: command pacing, balanced modifiers, cancellation at every step");
    }
}
