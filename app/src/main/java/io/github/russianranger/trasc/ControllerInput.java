package io.github.russianranger.trasc;

import java.util.*;

/** Platform-independent input state, reusable by a future embedded client host. */
final class ControllerInput {
    interface Sink {void button(String action,boolean down);void pointer(float dx,float dy);void wheel(int amount);}
    static final List<String> SOURCES=Collections.unmodifiableList(Arrays.asList(
        "A","B","X","Y","L1","R1","L2","R2","L3","R3","Start","Select",
        "DpadUp","DpadDown","DpadLeft","DpadRight","LeftUp","LeftDown","LeftLeft","LeftRight",
        "RightUp","RightDown","RightLeft","RightRight"));
    static final List<String> ACTIONS;
    static {
        List<String> list=new ArrayList<>(Arrays.asList("None","MouseLeft","MouseRight","MouseMiddle","PointerUp","PointerDown","PointerLeft","PointerRight","WheelUp","WheelDown"));
        for(char c='A';c<='Z';c++)list.add("Key"+c);
        for(int i=0;i<=9;i++)list.add("Digit"+i);
        for(int i=1;i<=12;i++)list.add("F"+i);
        list.addAll(Arrays.asList("Space","Enter","Escape","Tab","Backspace","ArrowUp","ArrowDown","ArrowLeft","ArrowRight","ShiftLeft","ControlLeft","AltLeft","Home","End","PageUp","PageDown","Insert","Delete","Minus","Equal","BracketLeft","BracketRight","Semicolon","Quote","Comma","Period","Slash","Backslash","Backquote","NumLock","ClientMenu"));
        List<String> keys=new ArrayList<>(list);
        for(String mod:Arrays.asList("ShiftLeft","ControlLeft","AltLeft"))
            for(String key:keys)if(key.startsWith("Key")||key.startsWith("Digit")||key.matches("F[0-9]+")||key.equals("Tab"))list.add(mod+"+"+key);
        ACTIONS=Collections.unmodifiableList(list);
    }
    static Map<String,String> defaults() {
        Map<String,String> m=new LinkedHashMap<>();for(String s:SOURCES)m.put(s,"None");
        m.put("A","Space");m.put("B","Escape");m.put("X","KeyE");m.put("Y","Tab");
        m.put("L1","ShiftLeft");m.put("R1","ControlLeft");m.put("L2","MouseRight");m.put("R2","MouseLeft");
        m.put("L3","KeyR");m.put("R3","MouseMiddle");m.put("Start","Enter");m.put("Select","KeyI");
        for(String dir:Arrays.asList("Up","Down","Left","Right")){m.put("Dpad"+dir,"Arrow"+dir);m.put("Right"+dir,"Pointer"+dir);}
        m.put("LeftUp","KeyW");m.put("LeftDown","KeyS");m.put("LeftLeft","KeyA");m.put("LeftRight","KeyD");
        return m;
    }
    private final Sink sink;
    private Map<String,String> bindings=defaults();
    private final Map<String,Float> held=new LinkedHashMap<>();
    private Map<String,String> shifted=inherited();
    private String modifier="None";
    private boolean layer;
    static Map<String,String> inherited(){Map<String,String> m=new LinkedHashMap<>();for(String s:SOURCES)m.put(s,"Inherit");return m;}
    static Map<String,String> preset(String name,boolean alternate){
        if(!Arrays.asList("legacy","adventure","spells","inventory").contains(name))throw new IllegalArgumentException("Unknown EQ preset");
        Map<String,String> m=alternate?inherited():defaults();
        if(name.equals("legacy"))return m;
        if(!alternate){
            m.put("L1","None");m.put("R1","Tab");m.put("Y","F8");m.put("X","KeyQ");
            m.put("L2","MouseLeft");m.put("R2","MouseRight");m.put("L3","NumLock");m.put("R3","F9");m.put("Start","ClientMenu");
            String[] dirs={"Up","Right","Down","Left"};
            for(int i=0;i<4;i++)m.put("Dpad"+dirs[i],(name.equals("spells")?"AltLeft+":"")+"Digit"+(i+1));
            if(name.equals("inventory")){m.put("A","MouseLeft");m.put("X","KeyI");m.put("Y","ShiftLeft+KeyB");m.put("DpadUp","WheelUp");m.put("DpadDown","WheelDown");}
        }else{
            String[] buttons={"A","B","X","Y"};for(int i=0;i<4;i++)m.put(buttons[i],(name.equals("spells")?"AltLeft+":"")+"Digit"+(i+5));
            m.put("DpadUp","Digit9");m.put("DpadRight","Digit0");m.put("DpadDown","Minus");m.put("DpadLeft","Equal");
            m.put("R1","ShiftLeft+Tab");m.put("R3","F1");m.put("Select","ShiftLeft+KeyB");
        }
        return m;
    }
    private final Map<String,Integer> counts=new HashMap<>();
    private boolean active;
    float deadzone=.20f, sensitivity=700;
    ControllerInput(Sink sink){this.sink=sink;}
    void configure(Map<String,String> next,float deadzone,float sensitivity) {
        configure(next,inherited(),"None",deadzone,sensitivity);
    }
    void configure(Map<String,String> next,Map<String,String> alternate,String modifier,float deadzone,float sensitivity) {
        if(!Float.isFinite(deadzone)||deadzone<.05f||deadzone>.8f)throw new IllegalArgumentException("Controller deadzone must be between 0.05 and 0.8");
        if(!Float.isFinite(sensitivity)||sensitivity<50||sensitivity>2500)throw new IllegalArgumentException("Pointer speed must be between 50 and 2500");
        if(!next.keySet().equals(new HashSet<>(SOURCES))||!alternate.keySet().equals(new HashSet<>(SOURCES)))throw new IllegalArgumentException("Controller profile must contain all supported buttons and directions");
        if(!modifier.equals("None")&&!SOURCES.subList(0,12).contains(modifier))throw new IllegalArgumentException("Choose a controller button for the modifier");
        for(String value:next.values())if(!ACTIONS.contains(value))throw new IllegalArgumentException("Unknown controller action: "+value);
        for(String value:alternate.values())if(!value.equals("Inherit")&&!ACTIONS.contains(value))throw new IllegalArgumentException("Unknown modifier action: "+value);
        releaseAll();bindings=new LinkedHashMap<>(next);shifted=new LinkedHashMap<>(alternate);this.modifier=modifier;this.deadzone=deadzone;this.sensitivity=sensitivity;
    }
    void activate(boolean enabled){if(!enabled)releaseAll();active=enabled;}
    boolean active(){return active;}
    private String action(String source){String a=layer?shifted.get(source):"Inherit";return a.equals("Inherit")?bindings.get(source):a;}
    private void reconcile(){
        Map<String,Integer> next=new LinkedHashMap<>();
        for(String source:held.keySet()){
            if(source.equals(modifier))continue;
            String action=action(source);
            if(action.equals("None")||action.startsWith("Pointer")||action.startsWith("Wheel")||action.equals("ClientMenu"))continue;
            for(String atom:action.split("\\+"))next.put(atom,next.getOrDefault(atom,0)+1);
        }
        // Release ordinary keys before modifiers, press modifiers before ordinary keys.
        List<String> old=new ArrayList<>(counts.keySet());old.sort(Comparator.comparing(ControllerInput::isModifier));
        for(String a:old)if(!next.containsKey(a))sink.button(a,false);
        List<String> fresh=new ArrayList<>(next.keySet());fresh.sort(Comparator.comparing(ControllerInput::isModifier).reversed());
        for(String a:fresh)if(!counts.containsKey(a))sink.button(a,true);
        counts.clear();counts.putAll(next);
    }
    private static boolean isModifier(String action){return action.equals("ShiftLeft")||action.equals("ControlLeft")||action.equals("AltLeft");}
    void value(String source,float magnitude) {
        if(!active||!bindings.containsKey(source)||!Float.isFinite(magnitude))return;
        magnitude=Math.max(0,Math.min(1,magnitude));
        boolean before=held.containsKey(source);
        boolean down=action(source).startsWith("Pointer")?magnitude>0:magnitude>(before?.20f:.45f);
        if(down)held.put(source,magnitude);else held.remove(source);
        if(source.equals(modifier))layer=down;
        if(down==before)return;
        reconcile();
        if(down&&!source.equals(modifier)){
            String a=action(source);
            if(a.startsWith("Wheel"))sink.wheel(a.equals("WheelUp")?1:-1);
            if(a.equals("ClientMenu"))sink.button(a,true);
        }
    }
    void axis(String negative,String positive,float value) {
        float amount=Math.abs(value)<=deadzone?0:(Math.abs(value)-deadzone)/(1-deadzone);
        value(negative,value<0?amount:0);value(positive,value>0?amount:0);
    }
    void tick(float seconds) {
        if(!active)return;
        float dx=0,dy=0;
        for(Map.Entry<String,Float> e:held.entrySet())switch(e.getKey().equals(modifier)?"None":action(e.getKey())) {
            case "PointerLeft":dx-=e.getValue();break;case "PointerRight":dx+=e.getValue();break;
            case "PointerUp":dy-=e.getValue();break;case "PointerDown":dy+=e.getValue();break;
        }
        if(dx!=0||dy!=0)sink.pointer(dx*sensitivity*Math.min(seconds,.05f),dy*sensitivity*Math.min(seconds,.05f));
    }
    void releaseAll(){for(String action:new ArrayList<>(counts.keySet()))sink.button(action,false);counts.clear();held.clear();layer=false;}
}
