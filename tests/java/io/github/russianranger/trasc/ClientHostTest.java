package io.github.russianranger.trasc;

import java.io.*;
import java.util.*;
import java.nio.file.*;

public final class ClientHostTest {
    static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    static byte[] server(boolean invalid)throws IOException {
        ByteArrayOutputStream data=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(data);
        out.writeBytes("RFB 003.008\n");out.write(new byte[]{1,1});out.writeInt(0);
        out.writeShort(3);out.writeShort(2);out.write(new byte[16]);out.writeInt(4);out.writeBytes("test");
        out.writeByte(0);out.writeByte(0);out.writeShort(1);
        out.writeShort(invalid?3:0);out.writeShort(0);out.writeShort(3);out.writeShort(2);out.writeInt(0);
        for(int i=0;i<6;i++)out.write(new byte[]{96,72,24,0});
        return data.toByteArray();
    }
    public static void main(String[] args)throws Exception {
        int[] pixels=new int[6];ByteArrayOutputStream wire=new ByteArrayOutputStream();
        RfbConnection.Screen screen=new RfbConnection.Screen(){public void resize(int w,int h){check(w==3&&h==2,"Display dimensions");}public void pixels(int x,int y,int w,int h,int[] colors){System.arraycopy(colors,0,pixels,0,6);}public void copy(int x,int y,int w,int h,int sx,int sy){}public void updated(){}};
        RfbConnection r=new RfbConnection(new ByteArrayInputStream(server(false)),wire,screen);r.handshake();r.readUpdate();
        check(pixels[0]==0xff184860&&pixels[5]==0xff184860,"RFB little-endian RGB must render correct ARGB pixels");
        int start=wire.size();r.key('t',true);r.key('t',false);r.pointer(99,-1,4);
        byte[] events=Arrays.copyOfRange(wire.toByteArray(),start,wire.size());
        check(Arrays.equals(events,new byte[]{4,1,0,0,0,0,0,116,4,0,0,0,0,0,0,116,5,4,0,2,0,0}),"RFB key/pointer wire messages and clamping");
        try{RfbConnection bad=new RfbConnection(new ByteArrayInputStream(server(true)),new ByteArrayOutputStream(),screen);bad.handshake();bad.readUpdate();throw new AssertionError("Invalid rectangle accepted");}catch(IOException expected){}
        try{byte[] partial=server(false);RfbConnection bad=new RfbConnection(new ByteArrayInputStream(Arrays.copyOf(partial,partial.length-1)),new ByteArrayOutputStream(),screen);bad.handshake();bad.readUpdate();throw new AssertionError("Truncated framebuffer accepted");}catch(EOFException expected){}
        List<String> sent=new ArrayList<>();DisplayInput input=new DisplayInput(new DisplayInput.Sink(){public void key(int k,boolean d){sent.add("key:"+k+":"+d);}public void pointer(int x,int y,int b){sent.add("pointer:"+x+":"+y+":"+b);}});
        input.action("KeyW",true);input.key("physical-w",'w',true);input.action("KeyW",false);
        check(sent.equals(Arrays.asList("key:119:true")),"Controller releasing must not release a physical key still held");input.key("physical-w",0,false);check(sent.get(1).equals("key:119:false"),"Last source releases key");
        input.mouse("pad",1,true);input.mouse("touch",1,true);input.mouse("touch",1,false);check(sent.get(sent.size()-1).endsWith(":1"),"Touch release must retain controller mouse hold");
        input.action("ShiftLeft",true);input.action("KeyA",true);input.action("ShiftLeft",false);input.action("KeyA",false);check(sent.contains("key:65:true")&&sent.contains("key:65:false"),"Shifted key releases its original symbol");
        input.action("KeyT",true);input.releaseAll();check(sent.contains("key:116:false")&&sent.get(sent.size()-1).endsWith(":0"),"Focus loss releases keyboard and mouse");
        sent.clear();input.text("hello",true);check(sent.get(sent.size()-1).equals("key:65293:false"),"Send + Enter actually sends chat");
        for(String action:ControllerInput.ACTIONS)if(!action.equals("None")&&!action.startsWith("Pointer")&&!action.startsWith("Mouse")&&!action.startsWith("Wheel"))check(DisplayInput.symbol(action)!=0,"Every advertised keyboard binding reaches the client: "+action);
        Path tree=Files.createTempDirectory("trasc-prefix-");
        try {
            Path prefix=tree.resolve("prefix"),game=tree.resolve("current");Files.createDirectories(prefix.resolve("dosdevices"));Files.createDirectories(game);
            Files.writeString(prefix.resolve("user.reg"),"existing Wine settings");Files.writeString(game.resolve("eqgame.exe"),"owned client");
            Files.createSymbolicLink(prefix.resolve("dosdevices/d:"),Path.of("/client"));
            File saved=ClientPrefix.preserve(prefix.toFile());
            check(Files.readString(saved.toPath().resolve("user.reg")).equals("existing Wine settings"),"Repair preserves Wine settings");
            check(Files.readSymbolicLink(saved.toPath().resolve("dosdevices/d:")).toString().equals("/client"),"Repair preserves guest drive links");
            check(Files.isDirectory(prefix)&&!Files.exists(prefix.resolve("user.reg")),"Fresh prefix ready without deleting backup");
            check(Files.readString(game.resolve("eqgame.exe")).equals("owned client"),"Repair never touches imported game files");
        } finally {TarExtractor.remove(tree.toFile());}
        System.out.println("PASS: native RFB pixels/events, malformed frames, combined controller/physical/touch holds, focus releases and typed Enter");
    }
}
