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
        list.addAll(Arrays.asList("Space","Enter","Escape","Tab","Backspace","ArrowUp","ArrowDown","ArrowLeft","ArrowRight","ShiftLeft","ControlLeft","AltLeft","Home","End","PageUp","PageDown","Insert","Delete","Minus","Equal","BracketLeft","BracketRight","Semicolon","Quote","Comma","Period","Slash","Backslash","Backquote"));
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
    private final Map<String,Float> held=new HashMap<>();
    private final Map<String,Integer> counts=new HashMap<>();
    private boolean active;
    float deadzone=.20f, sensitivity=700;
    ControllerInput(Sink sink){this.sink=sink;}
    void configure(Map<String,String> next,float deadzone,float sensitivity) {
        if(!Float.isFinite(deadzone)||deadzone<.05f||deadzone>.8f)throw new IllegalArgumentException("Controller deadzone must be between 0.05 and 0.8");
        if(!Float.isFinite(sensitivity)||sensitivity<50||sensitivity>2500)throw new IllegalArgumentException("Pointer speed must be between 50 and 2500");
        if(!next.keySet().equals(new HashSet<>(SOURCES)))throw new IllegalArgumentException("Controller profile must contain all supported buttons and directions");
        for(String value:next.values())if(!ACTIONS.contains(value))throw new IllegalArgumentException("Unknown controller action: "+value);
        releaseAll();bindings=new LinkedHashMap<>(next);this.deadzone=deadzone;this.sensitivity=sensitivity;
    }
    void activate(boolean enabled){if(!enabled)releaseAll();active=enabled;}
    boolean active(){return active;}
    void value(String source,float magnitude) {
        if(!active||!bindings.containsKey(source))return;
        magnitude=Math.max(0,Math.min(1,magnitude));
        String action=bindings.get(source);
        // Mouse axes stay analog. Digital actions use hysteresis to avoid chatter.
        float threshold=held.containsKey(source)?.20f:.45f;
        boolean down=action.startsWith("Pointer")?magnitude>0:magnitude>threshold;
        boolean before=held.containsKey(source);
        if(down)held.put(source,magnitude);else held.remove(source);
        if(down==before||action.equals("None")||action.startsWith("Pointer"))return;
        if(action.startsWith("Wheel")){if(down)sink.wheel(action.equals("WheelUp")?1:-1);return;}
        int count=counts.getOrDefault(action,0)+(down?1:-1);
        if(count<=0){counts.remove(action);sink.button(action,false);}
        else{counts.put(action,count);if(count==1&&down)sink.button(action,true);}
    }
    void axis(String negative,String positive,float value) {
        float amount=Math.abs(value)<=deadzone?0:(Math.abs(value)-deadzone)/(1-deadzone);
        value(negative,value<0?amount:0);value(positive,value>0?amount:0);
    }
    void tick(float seconds) {
        if(!active)return;
        float dx=0,dy=0;
        for(Map.Entry<String,Float> e:held.entrySet())switch(bindings.get(e.getKey())) {
            case "PointerLeft":dx-=e.getValue();break;case "PointerRight":dx+=e.getValue();break;
            case "PointerUp":dy-=e.getValue();break;case "PointerDown":dy+=e.getValue();break;
        }
        if(dx!=0||dy!=0)sink.pointer(dx*sensitivity*Math.min(seconds,.05f),dy*sensitivity*Math.min(seconds,.05f));
    }
    void releaseAll(){for(String action:new ArrayList<>(counts.keySet()))sink.button(action,false);counts.clear();held.clear();}
}
