package io.github.russianranger.trasc;
import java.util.*;
import java.nio.file.*;
public final class GameCommandHostTest {
    public static void main(String[] args)throws Exception{
        verify(GameCommand.classicNpcs(),"#tim",args.length>0?Path.of(args[0]):null);
        Path folder=args.length>0?Path.of(args[0]).toAbsolutePath().getParent():null;
        verify(GameCommand.chat(GameCommand.stoneViewport("1280x720")),"/viewport 179 0 920 480",folder==null?null:folder.resolve("viewport-keys.txt"));
        verify(GameCommand.chat(GameCommand.fullViewport("1280x720")),"/viewport 0 0 1280 720",folder==null?null:folder.resolve("viewport-reset-keys.txt"));
        for(String resolution:Arrays.asList("640x480","800x600","960x540","1024x768","1280x720")){
            String command="/viewport 0 0 "+resolution.replace('x',' ');
            if(!GameCommand.fullViewport(resolution).equals(command))throw new AssertionError("Restore resolution mismatch");
            verify(GameCommand.chat(command),command,null);
        }
        try{GameCommand.stoneViewport("800x600");throw new AssertionError("Wrong StoneUI resolution accepted");}catch(IllegalArgumentException expected){}
        try{GameCommand.fullViewport("");throw new AssertionError("Unknown restore resolution accepted");}catch(IllegalArgumentException expected){}
        System.out.println("PASS: exact native chat commands and Enter, resolution-aware viewport reset, balanced pacing and cancellation at every step");
    }
    private static void verify(List<GameCommand.Stroke> steps,String expected,Path output)throws Exception{
        StringBuilder wire=new StringBuilder();
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
        Map<Integer,Integer> down=new HashMap<>();int previous=0,submissions=0;
        StringBuilder chat=new StringBuilder("unsent draft");boolean editing=true;
        for(GameCommand.Stroke step:steps){
            if(step.delay<=previous)throw new AssertionError("Keys must be paced");previous=step.delay;
            if(step.down){
                down.put(step.symbol,step.delay);
                if(step.symbol==0xff1b){chat.setLength(0);editing=false;}
                else if(step.symbol=='/'&&!editing){chat.setLength(0);editing=true;chat.append('/');}
                else if(editing&&step.symbol==0xff08){if(chat.length()>0)chat.setLength(chat.length()-1);}
                else if(editing&&step.symbol==0xff0d){
                    if(!chat.toString().equals(expected))throw new AssertionError("Unexpected submitted command: "+chat);
                    submissions++;editing=false;
                }else if(editing&&step.symbol>=32&&step.symbol<=126)chat.append((char)step.symbol);
            }
            else if(step.delay-down.remove(step.symbol)<100)throw new AssertionError("Insufficient key dwell");
            wire.append(step.delay).append(' ').append(step.symbol).append(' ').append(step.down?1:0).append('\n');
        }
        if(submissions!=1||!down.isEmpty())throw new AssertionError("Command must submit once and release every key");
        if(output!=null)Files.writeString(output,wire.toString());
    }
}
