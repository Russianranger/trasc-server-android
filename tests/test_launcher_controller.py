"""Run the real native menu router with deterministic Android input/clock stubs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'app/src/main/java/io/github/russianranger/trasc'
STUBS = {
    'android/os/Looper.java': '''package android.os; public class Looper {public static Looper getMainLooper(){return new Looper();}}''',
    'android/os/Handler.java': '''package android.os; import java.util.*; public class Handler {
        public static final List<Runnable> queued=new ArrayList<>(); public Handler(Looper loop){}
        public void postDelayed(Runnable task,long delay){queued.add(task);} public void removeCallbacks(Runnable task){queued.removeIf(r->r==task);}
        public static void tick(){List<Runnable> pending=new ArrayList<>(queued);queued.clear();pending.forEach(Runnable::run);}
    }''',
    'android/view/InputDevice.java': '''package android.view; public class InputDevice {
        public static final int SOURCE_GAMEPAD=0x401,SOURCE_JOYSTICK=0x1000010,SOURCE_DPAD=0x201,SOURCE_KEYBOARD=0x101;
    }''',
    'android/view/InputEvent.java': '''package android.view; public class InputEvent {
        private final int source,device; public InputEvent(int source,int device){this.source=source;this.device=device;}
        public boolean isFromSource(int requested){return (source&requested)==requested;} public int getDeviceId(){return device;}
    }''',
    'android/view/KeyEvent.java': '''package android.view; public class KeyEvent extends InputEvent {
        public static final int ACTION_DOWN=0,ACTION_UP=1,KEYCODE_BUTTON_A=96,KEYCODE_BUTTON_B=97,
            KEYCODE_BUTTON_L1=102,KEYCODE_BUTTON_R1=103,KEYCODE_DPAD_CENTER=23,KEYCODE_DPAD_UP=19,
            KEYCODE_DPAD_DOWN=20,KEYCODE_DPAD_LEFT=21,KEYCODE_DPAD_RIGHT=22;
        private final int action,key,repeat;
        public KeyEvent(int source,int device,int action,int key,int repeat){super(source,device);this.action=action;this.key=key;this.repeat=repeat;}
        public int getAction(){return action;} public int getKeyCode(){return key;} public int getRepeatCount(){return repeat;}
    }''',
    'android/view/MotionEvent.java': '''package android.view; public class MotionEvent extends InputEvent {
        public static final int ACTION_MOVE=2,AXIS_HAT_X=15,AXIS_HAT_Y=16; private final float x,y;
        public MotionEvent(int device,float x,float y){super(InputDevice.SOURCE_JOYSTICK,device);this.x=x;this.y=y;}
        public int getAction(){return ACTION_MOVE;} public float getAxisValue(int axis){return axis==AXIS_HAT_X?x:y;}
    }''',
    'io/github/russianranger/trasc/LauncherControllerHostTest.java': '''package io.github.russianranger.trasc;
        import android.os.Handler; import android.view.*; import java.util.*;
        public class LauncherControllerHostTest {
            static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
            static KeyEvent key(int device,int action,int code,int repeat){return new KeyEvent(InputDevice.SOURCE_GAMEPAD,device,action,code,repeat);}
            public static void main(String[] args){
                List<String> sent=new ArrayList<>();LauncherController router=new LauncherController(sent::add);
                check(router.key(key(1,0,96,0)),"A down consumed");check(router.key(key(1,0,96,1)),"A OS repeat consumed");
                Handler.tick();check(sent.equals(Arrays.asList("accept")),"A only activates once");check(router.key(key(1,1,96,0)),"A up consumed to prevent browser click");
                sent.clear();router.key(key(1,0,103,0));Handler.tick();router.key(key(1,0,103,1));router.key(key(1,1,103,0));
                check(sent.equals(Arrays.asList("nextTab")),"RB never repeats while held");router.key(key(1,0,102,0));router.key(key(1,1,102,0));
                check(sent.get(1).equals("previousTab"),"LB previous tab");
                sent.clear();router.key(key(1,0,20,0));router.motion(new MotionEvent(1,0,1));
                check(sent.equals(Arrays.asList("down")),"Dpad key plus hat is deduplicated");
                check(!router.key(key(2,0,96,0)),"Second pad cannot interrupt held input");Handler.tick();
                check(sent.equals(Arrays.asList("down","down")),"Held direction repeats");
                router.key(key(1,1,20,0));Handler.tick();check(sent.size()==3,"Hat keeps direction held after key up");
                router.motion(new MotionEvent(1,0,0));Handler.tick();check(sent.size()==3,"Neutral hat stops repeat");
                router.motion(new MotionEvent(2,-1,0));check(sent.get(3).equals("left"),"Ownership releases when idle");
                router.reset();Handler.tick();check(sent.size()==4&&Handler.queued.isEmpty(),"Focus loss resets all held repeats");
                check(!router.key(new KeyEvent(InputDevice.SOURCE_KEYBOARD,1,0,20,0)),"Hardware keyboard stays with WebView");
                check(!router.key(key(1,0,100,0)),"Unmapped gamepad key is not stolen");
                check(!router.motion(new MotionEvent(1,.3f,0)),"Hat deadzone rejects noise");
                router.key(key(1,0,97,0));router.key(key(1,1,97,0));check(sent.get(4).equals("back"),"B maps to menu back");
                router.key(key(3,0,19,0));router.deviceUnavailable(4);Handler.tick();check(sent.size()==7,"Other device changes preserve held direction");
                router.deviceUnavailable(3);Handler.tick();check(sent.size()==7&&Handler.queued.isEmpty(),"Disconnect ends held navigation");
                System.out.println("Native launcher controller input checks passed");
            }
        }''',
}


class LauncherControllerTests(unittest.TestCase):
    def test_native_gamepad_routing(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            sources = []
            for name, source in STUBS.items():
                destination = directory / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source)
                sources.append(str(destination))
            subprocess.run(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', str(directory),
                            str(PACKAGE / 'LauncherController.java'), *sources], check=True, capture_output=True, text=True)
            result = subprocess.run(['java', '-cp', str(directory), 'io.github.russianranger.trasc.LauncherControllerHostTest'],
                                    check=True, capture_output=True, text=True)
            self.assertIn('input checks passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
