package io.github.russianranger.trasc;

import android.os.Handler;
import android.os.Looper;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.KeyEvent;
import android.view.MotionEvent;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.Set;

/** Menu-only gamepad input. MainActivity gives active gameplay capture priority. */
final class LauncherController {
    interface Commands {void emit(String command);}
    private final Commands commands;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Set<String> keys=new HashSet<>(),hats=new HashSet<>(),held=new LinkedHashSet<>();
    private int device=-1;
    private final Runnable repeat=new Runnable(){@Override public void run(){
        if(held.isEmpty())return;
        for(String command:held)if(direction(command))commands.emit(command);
        handler.postDelayed(this,120);
    }};
    LauncherController(Commands commands){this.commands=commands;}
    static boolean gamepad(InputEvent event){return event.isFromSource(InputDevice.SOURCE_GAMEPAD)||event.isFromSource(InputDevice.SOURCE_JOYSTICK)||event.isFromSource(InputDevice.SOURCE_DPAD);}
    private boolean owns(InputEvent event){if(device<0)device=event.getDeviceId();return device==event.getDeviceId();}
    private static boolean direction(String command){return command.equals("up")||command.equals("down")||command.equals("left")||command.equals("right");}
    private static String command(int key){switch(key){
        case KeyEvent.KEYCODE_BUTTON_A: case KeyEvent.KEYCODE_DPAD_CENTER:return "accept";
        case KeyEvent.KEYCODE_BUTTON_B:return "back";
        case KeyEvent.KEYCODE_BUTTON_L1:return "previousTab";
        case KeyEvent.KEYCODE_BUTTON_R1:return "nextTab";
        case KeyEvent.KEYCODE_DPAD_UP:return "up";
        case KeyEvent.KEYCODE_DPAD_DOWN:return "down";
        case KeyEvent.KEYCODE_DPAD_LEFT:return "left";
        case KeyEvent.KEYCODE_DPAD_RIGHT:return "right";
        default:return null;
    }}
    boolean key(KeyEvent event){
        String command=command(event.getKeyCode());
        if(command==null||!gamepad(event)||!owns(event))return false;
        if(event.getAction()==KeyEvent.ACTION_DOWN){if(event.getRepeatCount()==0)keys.add(command);}
        else if(event.getAction()==KeyEvent.ACTION_UP)keys.remove(command);
        else return false;
        update();return true; // Consume down and up: WebView must not activate a second time.
    }
    boolean motion(MotionEvent event){
        if(event.getAction()!=MotionEvent.ACTION_MOVE||!gamepad(event))return false;
        float x=event.getAxisValue(MotionEvent.AXIS_HAT_X),y=event.getAxisValue(MotionEvent.AXIS_HAT_Y);
        if(hats.isEmpty()&&Math.abs(x)<.55f&&Math.abs(y)<.55f)return false;
        if(!owns(event))return false;
        hats.clear();if(x<=-.55f)hats.add("left");else if(x>=.55f)hats.add("right");
        if(y<=-.55f)hats.add("up");else if(y>=.55f)hats.add("down");
        update();return true;
    }
    private void update(){
        Set<String> next=new LinkedHashSet<>(keys);next.addAll(hats);
        boolean changed=!next.equals(held);
        for(String command:next)if(!held.contains(command))commands.emit(command);
        held.clear();held.addAll(next);
        if(changed){handler.removeCallbacks(repeat);if(held.stream().anyMatch(LauncherController::direction))handler.postDelayed(repeat,380);}
        if(held.isEmpty())device=-1;
    }
    void reset(){handler.removeCallbacks(repeat);keys.clear();hats.clear();held.clear();device=-1;}
    void deviceUnavailable(int id){if(device==id)reset();}
}
