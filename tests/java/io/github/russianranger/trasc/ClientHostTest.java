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
        relativeInput();frameMeasurements();reusedPixels();controllerLayers();namedLayers();
        int[] pixels=new int[6];ByteArrayOutputStream wire=new ByteArrayOutputStream();
        RfbConnection.Screen screen=new RfbConnection.Screen(){public void resize(int w,int h){check(w==3&&h==2,"Display dimensions");}public void pixels(int x,int y,int w,int h,int[] colors){System.arraycopy(colors,0,pixels,0,6);}public void copy(int x,int y,int w,int h,int sx,int sy){}public void updated(){}};
        RfbConnection r=new RfbConnection(new ByteArrayInputStream(server(false)),wire,screen);r.handshake();r.readUpdate();
        ByteArrayOutputStream inputOnly=new ByteArrayOutputStream();RfbConnection noFrames=new RfbConnection(new ByteArrayInputStream(server(false)),inputOnly,screen);noFrames.handshake(false);
        check(inputOnly.size()==wire.size()-20,"Native presentation handshake sends no initial or incremental pixel request");
        int inputStart=inputOnly.size();noFrames.key('t',true);check(inputOnly.size()==inputStart+8,"Input-only connection still transmits keys");
        noFrames.request(false);check(inputOnly.size()==inputStart+18,"Fallback can explicitly resume full RFB pixel delivery");
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
        for(String action:ControllerInput.ACTIONS)if(!action.equals("None")&&!action.startsWith("Pointer")&&!action.startsWith("Mouse")&&!action.startsWith("Wheel")){if(!action.equals("ClientMenu")&&!ControllerInput.isLayerAction(action))for(String atom:action.split("\\+"))check(DisplayInput.symbol(atom)!=0,"Every advertised keyboard binding reaches the client: "+atom);}
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
    static void relativeInput()throws Exception {
        ByteArrayOutputStream wire=new ByteArrayOutputStream();RelativeInput channel=new RelativeInput(new ByteArrayInputStream("TRASCIN1".getBytes("US-ASCII")),wire);
        channel.send(1,-40,5,4);DataInputStream data=new DataInputStream(new ByteArrayInputStream(wire.toByteArray()));
        check(data.readInt()==1&&data.readInt()==-40&&data.readInt()==5&&data.readInt()==4,"Signed relative motion and held button wire format");
        try{channel.send(1,5000,0,0);throw new AssertionError("Oversized motion accepted");}catch(IOException expected){}
        final int[] dx={0},held={0},absolute={0};
        DisplayInput input=new DisplayInput(new DisplayInput.Sink(){public void key(int k,boolean down){}public void pointer(int x,int y,int mask){absolute[0]++;}
            public boolean relative(int x,int y,int mask){dx[0]+=x;held[0]=mask;return true;}public boolean buttons(int mask){held[0]=mask;return true;}});
        input.size(800,600);input.action("MouseRight",true);
        for(int i=0;i<24000;i++)input.move(.25f,0);
        check(dx[0]==6000&&held[0]==4&&absolute[0]==0,"Stick deltas accumulate past screen bounds without absolute recenter jumps");
        input.position(25,40);check(absolute[0]==1,"Touch remains absolute");input.releaseAll();check(held[0]==0,"Focus loss releases relative mouse buttons");
        System.out.println("PASS: relative mouse wire, fractional deltas beyond screen bounds, absolute touch and held-button release");
    }
    static void controllerLayers(){
        List<String> events=new ArrayList<>();
        ControllerInput input=new ControllerInput(new ControllerInput.Sink(){public void button(String a,boolean d){events.add(a+":"+d);}public void pointer(float x,float y){}public void wheel(int n){}});
        Map<String,String> base=ControllerInput.defaults(),shifted=ControllerInput.inherited();base.put("A","Digit1");shifted.put("A","AltLeft+Digit2");
        input.configure(base,shifted,"L1",.2f,700);input.activate(true);input.value("A",1);input.value("L1",1);
        check(events.equals(Arrays.asList("Digit1:true","Digit1:false","AltLeft:true","Digit2:true")),"Layer change releases old key before pressing chord in modifier-first order");
        input.value("L1",0);check(events.subList(4,7).equals(Arrays.asList("Digit2:false","AltLeft:false","Digit1:true")),"Releasing layer returns held source to base without stuck chord");
        input.activate(false);check(events.get(events.size()-1).equals("Digit1:false"),"Focus loss releases layered actions");
        events.clear();base.put("A","AltLeft+Digit1");base.put("B","AltLeft+Digit2");input.configure(base,.2f,700);input.activate(true);
        input.value("A",1);input.value("B",1);input.value("A",0);check(!events.contains("AltLeft:false"),"Overlapping chords retain common modifier");input.value("B",0);check(events.get(events.size()-1).equals("AltLeft:false"),"Final chord releases modifier last");
        events.clear();input.value("A",Float.NaN);check(events.isEmpty(),"Invalid analog value is ignored");
        for(String name:Arrays.asList("legacy","adventure","spells","inventory"))input.configure(ControllerInput.preset(name,false),ControllerInput.preset(name,true),name.equals("legacy")?"None":"L1",.2f,700);
        events.clear();input.activate(true);input.value("Start",1);check(events.equals(Arrays.asList("ClientMenu:true")),"Preset opens app controls without sending a game key");
    }
    static void namedLayers(){
        List<String> events=new ArrayList<>(),names=new ArrayList<>();
        ControllerInput input=new ControllerInput(new ControllerInput.Sink(){public void button(String a,boolean d){events.add(a+":"+d);}public void pointer(float x,float y){}public void wheel(int n){}public void layer(int i,String name){names.add(i+":"+name);}});
        List<ControllerInput.Layer> layers=ControllerInput.defaultLayers();Map<String,String> expected=new LinkedHashMap<>();
        String[] sources={"A","X","Y","B","R1","L1","L2","R2","DpadUp","DpadRight","DpadDown","DpadLeft","Select","Start","L3","R3","LeftUp","LeftDown","LeftLeft","LeftRight","RightUp","RightDown","RightLeft","RightRight"};
        String[] actions={"KeyF","Digit1","Digit2","Digit3","MouseLeft","MouseRight","LayerNext","Tab","Digit4","Digit5","Digit6","Digit7","Escape","KeyI","Home","KeyC","KeyW","KeyS","KeyA","KeyD","PointerUp","PointerDown","PointerLeft","PointerRight"};
        for(int i=0;i<sources.length;i++)expected.put(sources[i],actions[i]);check(layers.get(0).bindings.equals(expected),"Thor Main exactly matches all requested bindings");
        input.configure(layers,.2f,700);input.activate(true);input.value("X",1);input.value("L2",1);input.value("L2",1);input.value("L2",.6f);
        check(input.currentLayer()==1,"Analog/key repeat does not cycle a held trigger again");check(events.equals(Arrays.asList("Digit1:true","Digit1:false","Digit8:true")),"Cycling releases the old hotkey before rebinding the held button");
        input.value("L2",0);check(input.currentLayer()==1,"Cycling is persistent on release");input.value("X",0);
        for(int i=0;i<3;i++){input.value("L2",1);input.value("L2",0);}check(input.currentLayer()==0,"Four layers cycle and wrap");
        Map<String,String> main=new LinkedHashMap<>(layers.get(0).bindings);main.put("R2","LayerPrevious");main.put("L1","HoldLayer3");main.put("R1","HoldLayer4");main.put("Select","Layer2");
        layers=new ArrayList<>(layers);layers.set(0,new ControllerInput.Layer("Main",main));input.configure(layers,.2f,700);input.activate(true);
        input.value("R2",1);input.value("R2",0);check(input.currentLayer()==3,"Previous wraps backward");input.value("Select",1);input.value("Select",0);check(input.currentLayer()==1,"Direct selection reaches a named layer");
        input.value("L1",1);check(input.currentLayer()==2,"Hold temporarily overrides the selected layer");input.value("R1",1);check(input.currentLayer()==3,"Latest held layer wins");input.value("R1",0);check(input.currentLayer()==2,"Nested hold release restores the earlier hold");input.value("L1",0);check(input.currentLayer()==1,"Hold release restores the selected persistent layer");
        input.value("L1",1);input.value("X",1);input.activate(false);check(input.currentLayer()==1&&events.get(events.size()-1).equals("AltLeft:false"),"Focus loss releases the chord and temporary layer, retaining selected layer");
        List<ControllerInput.Layer> invalid=new ArrayList<>(layers);Map<String,String> bad=new LinkedHashMap<>(main);bad.put("A","Layer6");invalid.set(0,new ControllerInput.Layer("Main",bad));
        try{input.configure(invalid,.2f,700);throw new AssertionError("Missing target accepted");}catch(IllegalArgumentException expectedError){}
        check(input.currentLayer()==1,"Invalid profile does not mutate active selection");
        List<ControllerInput.Layer> migrated=ControllerInput.legacyLayers(ControllerInput.legacyDefaults(),ControllerInput.inherited(),"L1");check(migrated.get(0).bindings.get("L1").equals("HoldLayer2")&&migrated.get(0).bindings.get("X").equals("KeyE"),"Old held modifier and custom bindings migrate");
        check(names.contains("3:Inventory"),"Layer notification carries index and actual name");
        System.out.println("PASS: exact Thor defaults, named cycling/wrap/direct/held layers, repeat suppression, focus recovery and legacy migration");
    }
    static void frameMeasurements(){
        ClientFrameStats stats=new ClientFrameStats(0);
        stats.received(100,2000000,1000000,480000);stats.drawn(500000);stats.drawn(500000);
        stats.received(200,2000000,1000000,480000);stats.received(300,2000000,1000000,480000);
        double[] sample=stats.sample(1000000000L);
        check(sample[1]==3&&sample[2]==1,"Transport updates differ from coalesced bitmap draws");
        check(sample[3]==2&&sample[4]==1&&sample[5]==.5,"Measured work has explicit millisecond units");
        stats.drawn(500000);stats.drawn(500000);
        sample=stats.sample(2000000000L);check(sample[1]==0&&sample[2]==1,"Pending generation drawn once after sample rollover");
        stats.drawn(500000);sample=stats.sample(3000000000L);check(sample[1]==0&&sample[2]==0,"Idle UI redraws are not counted as new client frames");
    }
    static void reusedPixels()throws Exception {
        byte[] first=server(false),second=Arrays.copyOfRange(first,first.length-40,first.length);
        for(int i=16;i<second.length;i+=4){second[i]=(byte)0xcc;second[i+1]=(byte)0xbb;second[i+2]=(byte)0xaa;}
        ByteArrayOutputStream stream=new ByteArrayOutputStream();stream.write(first);stream.write(second);
        List<int[]> borrowed=new ArrayList<>();List<Integer> snapshots=new ArrayList<>();
        RfbConnection.Screen screen=new RfbConnection.Screen(){
            public void resize(int w,int h){}public void copy(int x,int y,int w,int h,int sx,int sy){}
            public void pixels(int x,int y,int w,int h,int[] colors){borrowed.add(colors);snapshots.add(colors[0]);}public void updated(){}
        };
        RfbConnection r=new RfbConnection(new ByteArrayInputStream(stream.toByteArray()),new ByteArrayOutputStream(),screen);
        r.handshake();r.readUpdate();r.readUpdate();
        check(borrowed.get(0)==borrowed.get(1),"Repeated raw updates reuse the pixel storage");
        check(snapshots.equals(Arrays.asList(0xff184860,0xffaabbcc)),"Reused buffers still decode each update correctly");
        check(r.stats.sample(System.nanoTime())[1]>0,"RFB updates populate measured transport statistics");
    }
}
