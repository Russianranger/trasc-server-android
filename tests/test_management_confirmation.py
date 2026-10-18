"""Execute the shipped WebChromeClient callback with Android dialog doubles.

The callback and completion/lifecycle guard are copied unchanged from production
MainActivity. Doubles model Android's dialog callbacks, button focus and JsResult;
WorldProfiles is the real implementation. This catches the native integration
gap hidden by browser tests that replace window.confirm with an always-true stub.
"""
from functools import lru_cache
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_client_native_status import production_method


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'app/src/main/java/io/github/russianranger/trasc'

HARNESS = r'''package io.github.russianranger.trasc;
import java.io.*;
import java.nio.file.*;
import java.util.*;

final class JsResult {
    int confirmed,cancelled;
    void confirm(){confirmed++;}
    void cancel(){cancelled++;}
}
class WebChromeClient {boolean onJsConfirm(WebView view,String url,String message,JsResult result){return false;}}
final class WebView {String url="https://app.trasc.local/index.html";String getUrl(){return url;}}
final class KeyEvent {
    static final int KEYCODE_BUTTON_A=96,KEYCODE_BUTTON_B=97,KEYCODE_BACK=4,KEYCODE_DPAD_RIGHT=22;
    static final int ACTION_DOWN=0,ACTION_UP=1;
    final int action;KeyEvent(int value){action=value;}int getAction(){return action;}
}
final class RuntimeManager {
    final WorldProfiles profiles;int failures;
    RuntimeManager(WorldProfiles value){profiles=value;}
    void recordFailure(String operation,RuntimeException failure){failures++;}
}
final class AlertDialog {
    static final int BUTTON_POSITIVE=-1,BUTTON_NEGATIVE=-2;
    static AlertDialog latest;static boolean failShow;
    interface Click {void call(AlertDialog dialog,int button);}
    interface Event {void call(AlertDialog dialog);}
    interface Key {boolean call(AlertDialog dialog,int code,KeyEvent event);}
    static final class Button extends android.view.View {
        final AlertDialog owner;final int which;final Click click;
        Button(AlertDialog owner,int which,Click click){this.owner=owner;this.which=which;this.click=click;}
        @Override public boolean requestFocus(){owner.focused=this;return true;}
        @Override public boolean performClick(){if(click!=null)click.call(owner,which);owner.dismiss();return true;}
    }
    static final class Builder {
        final AlertDialog dialog=new AlertDialog();
        Builder(MainActivity activity){}
        Builder setTitle(String text){dialog.title=text;return this;}
        Builder setMessage(String text){dialog.message=text;return this;}
        Builder setPositiveButton(String text,Click callback){dialog.positive=new Button(dialog,BUTTON_POSITIVE,callback);return this;}
        Builder setNegativeButton(int text,Click callback){dialog.negative=new Button(dialog,BUTTON_NEGATIVE,callback);return this;}
        Builder setOnCancelListener(Event callback){dialog.cancel=callback;return this;}
        AlertDialog create(){latest=dialog;return dialog;}
    }
    String title,message;Button positive,negative;android.view.View focused;
    Event cancel,dismiss;Key keys;boolean shown;int dismissals;
    void setOnDismissListener(Event callback){dismiss=callback;}
    void setOnKeyListener(Key callback){keys=callback;}
    void show(){if(failShow)throw new IllegalStateException("Activity window is gone");shown=true;}
    Button getButton(int which){return which==BUTTON_POSITIVE?positive:negative;}
    android.view.View getCurrentFocus(){return focused;}
    void dismiss(){shown=false;dismissals++;if(dismiss!=null)dismiss.call(this);}
    void cancel(){if(cancel!=null)cancel.call(this);dismiss();}
    boolean key(int key,int action){return keys.call(this,key,new KeyEvent(action));}
}

final class MainActivity {
    private WebView web=new WebView();
    private RuntimeManager runtime;
    private boolean activityResumed=true,finishing,destroyed;
    private final ManagementChromeClient chrome=new ManagementChromeClient();
    MainActivity(WorldProfiles profiles){runtime=new RuntimeManager(profiles);}
    boolean isFinishing(){return finishing;}boolean isDestroyed(){return destroyed;}
    __PRODUCTION_CALLBACK__

    static void expect(boolean value,String message){if(!value)throw new AssertionError(message);}
    JsResult open(String message){JsResult result=new JsResult();expect(chrome.onJsConfirm(web,web.url,message,result),"Native client must handle confirmation");return result;}
    void done(JsResult result,int confirmed,int cancelled,String name){expect(result.confirmed==confirmed&&result.cancelled==cancelled,name+": result must finish exactly once");}
    void verify(String scenario)throws Exception {
        switch(scenario){
        case "positive": {
            JsResult result=open("Synchronize 12 files?");AlertDialog shown=AlertDialog.latest;
            expect(shown.shown,"Confirmation must be visible");expect(shown.message.equals("Synchronize 12 files?"),"Show exact proposal");
            expect(shown.title.equals("TRASC Custom — Confirm action"),"Show active profile");
            done(result,0,0,"Before click");shown.positive.performClick();done(result,1,0,"Continue");
            shown.cancel();shown.positive.performClick();chrome.cancelPending();done(result,1,0,"Repeated callbacks");break;
        }
        case "cancel": {
            JsResult result=open("Replace?");AlertDialog.latest.negative.performClick();done(result,0,1,"Cancel");break;
        }
        case "dismiss": {
            JsResult result=open("Replace?");AlertDialog.latest.dismiss();done(result,0,1,"Dismiss");break;
        }
        case "back":case "controller_b": {
            JsResult result=open("Replace?");AlertDialog shown=AlertDialog.latest;
            int key=scenario.equals("back")?KeyEvent.KEYCODE_BACK:KeyEvent.KEYCODE_BUTTON_B;
            expect(shown.key(key,KeyEvent.ACTION_DOWN),"Consume Back/B down");done(result,0,0,"Key down");
            expect(shown.key(key,KeyEvent.ACTION_UP),"Consume Back/B up");done(result,0,1,"Back/B");break;
        }
        case "controller_a_cancel":case "controller_a_continue": {
            JsResult result=open("Replace?");AlertDialog shown=AlertDialog.latest;
            expect(shown.focused==shown.negative,"Cancel starts focused");
            expect(!shown.key(KeyEvent.KEYCODE_DPAD_RIGHT,KeyEvent.ACTION_DOWN),"Android keeps directional focus navigation");
            if(scenario.equals("controller_a_continue"))shown.positive.requestFocus();
            shown.key(KeyEvent.KEYCODE_BUTTON_A,KeyEvent.ACTION_DOWN);done(result,0,0,"A down");
            shown.key(KeyEvent.KEYCODE_BUTTON_A,KeyEvent.ACTION_UP);
            done(result,scenario.equals("controller_a_continue")?1:0,scenario.equals("controller_a_continue")?0:1,"Focused A");break;
        }
        case "paused":case "destroyed":case "finishing":case "wrong_origin":case "wrong_page":case "other_webview": {
            JsResult result=new JsResult();WebView view=web;String url=web.url;
            if(scenario.equals("paused"))activityResumed=false;
            if(scenario.equals("destroyed"))destroyed=true;
            if(scenario.equals("finishing"))finishing=true;
            if(scenario.equals("wrong_origin"))url="https://evil.test/index.html";
            if(scenario.equals("wrong_page"))web.url="https://app.trasc.local/untrusted.html";
            if(scenario.equals("other_webview"))view=new WebView();
            expect(chrome.onJsConfirm(view,url,"Replace?",result),"Blocked confirmation remains handled");
            done(result,0,1,scenario);expect(AlertDialog.latest==null,"Blocked page cannot show dialog");break;
        }
        case "profile_changed": {
            JsResult result=open("Replace?");AlertDialog shown=AlertDialog.latest;
            runtime.profiles.beginSwitch("custom");try{runtime.profiles.select("takp");}finally{runtime.profiles.endSwitch();}
            shown.positive.performClick();done(result,0,1,"Changed profile");break;
        }
        case "paused_while_open":case "renderer_gone":case "destroyed_while_open": {
            JsResult result=open("Replace?");AlertDialog shown=AlertDialog.latest;
            if(scenario.equals("paused_while_open"))activityResumed=false;
            if(scenario.equals("renderer_gone"))web=null;
            if(scenario.equals("destroyed_while_open"))destroyed=true;
            chrome.cancelPending();shown.positive.performClick();done(result,0,1,"Lifecycle cancellation");expect(!shown.shown,"Stale dialog dismissed");break;
        }
        case "stale_positive": {
            JsResult result=open("Replace?");activityResumed=false;AlertDialog.latest.positive.performClick();done(result,0,1,"Positive lifecycle recheck");break;
        }
        case "duplicate": {
            JsResult first=open("First?");AlertDialog shown=AlertDialog.latest;JsResult second=open("Second?");
            done(first,0,0,"Original pending");done(second,0,1,"Duplicate rejected");expect(AlertDialog.latest==shown,"No replacement dialog");
            shown.positive.performClick();done(first,1,0,"Original approved");break;
        }
        case "show_failure": {
            AlertDialog.failShow=true;JsResult result=open("Replace?");done(result,0,1,"Window failure");
            expect(runtime.failures==1,"Window failure is recorded");break;
        }
        case "profiles": {
            for(String profile:new String[]{"custom","traditional","takp"}){
                runtime.profiles.beginSwitch(runtime.profiles.current());try{runtime.profiles.select(profile);}finally{runtime.profiles.endSwitch();}
                JsResult result=open("Confirm?");expect(AlertDialog.latest.title.equals(WorldProfiles.label(profile)+" — Confirm action"),"Active profile label");
                AlertDialog.latest.negative.performClick();done(result,0,1,"Profile cancel");
            }break;
        }
        default:throw new AssertionError("Unknown scenario "+scenario);
        }
    }
    public static void main(String[] args)throws Exception {new MainActivity(new WorldProfiles(new File(args[1]))).verify(args[0]);System.out.println("PASS "+args[0]);}
}
'''


@lru_cache(maxsize=1)
def executed_confirmations():
    source = (PACKAGE / 'MainActivity.java').read_text()
    callback = production_method(source, 'private final class ManagementChromeClient')
    scenarios = (
        'positive', 'cancel', 'dismiss', 'back', 'controller_b',
        'controller_a_cancel', 'controller_a_continue', 'paused', 'destroyed',
        'finishing', 'wrong_origin', 'wrong_page', 'other_webview',
        'profile_changed', 'paused_while_open', 'renderer_gone',
        'destroyed_while_open', 'stale_positive', 'duplicate', 'show_failure',
        'profiles',
    )
    with tempfile.TemporaryDirectory(prefix='trasc-native-confirmation-') as temporary:
        directory = Path(temporary)
        view = directory / 'android/view/View.java'
        resources = directory / 'android/R.java'
        harness = directory / 'io/github/russianranger/trasc/MainActivity.java'
        view.parent.mkdir(parents=True)
        harness.parent.mkdir(parents=True)
        view.write_text('package android.view; public class View {public void setFocusableInTouchMode(boolean value){} public boolean requestFocus(){return true;} public boolean performClick(){return true;}}')
        resources.write_text('package android; public final class R {public static final class string {public static final int cancel=17039360;}}')
        harness.write_text(HARNESS.replace('__PRODUCTION_CALLBACK__', callback))
        subprocess.run(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', str(directory),
                        str(PACKAGE / 'WorldProfiles.java'), str(view), str(resources), str(harness)],
                       check=True, capture_output=True, text=True, timeout=60)
        outputs = {}
        for scenario in scenarios:
            world = directory / 'worlds' / scenario
            world.mkdir(parents=True)
            result = subprocess.run(['java', '-cp', str(directory), 'io.github.russianranger.trasc.MainActivity',
                                     scenario, str(world)], check=True, capture_output=True, text=True, timeout=15)
            outputs[scenario] = result.stdout.strip()
        return outputs


class ManagementConfirmationTests(unittest.TestCase):
    def test_real_callback_requires_explicit_continue(self):
        outcomes = executed_confirmations()
        for scenario in ('positive', 'cancel', 'dismiss', 'duplicate', 'show_failure'):
            with self.subTest(scenario=scenario):
                self.assertEqual(outcomes[scenario], 'PASS ' + scenario)

    def test_controller_uses_focused_button_and_back_cancels(self):
        outcomes = executed_confirmations()
        for scenario in ('back', 'controller_b', 'controller_a_cancel', 'controller_a_continue'):
            with self.subTest(scenario=scenario):
                self.assertEqual(outcomes[scenario], 'PASS ' + scenario)

    def test_untrusted_or_stale_confirmation_cannot_approve(self):
        outcomes = executed_confirmations()
        for scenario in ('paused', 'destroyed', 'finishing', 'wrong_origin', 'wrong_page', 'other_webview',
                         'profile_changed', 'paused_while_open', 'renderer_gone', 'destroyed_while_open', 'stale_positive', 'profiles'):
            with self.subTest(scenario=scenario):
                self.assertEqual(outcomes[scenario], 'PASS ' + scenario)

    def test_activity_installs_callback_and_cancels_before_teardown(self):
        source = (PACKAGE / 'MainActivity.java').read_text()
        create = production_method(source, 'public void onCreate(Bundle saved)')
        self.assertLess(create.index('web.setWebChromeClient(managementChrome)'), create.index('web.loadUrl('))
        pause = production_method(source, 'protected void onPause()')
        self.assertIn('activityResumed=false', pause)
        self.assertIn('managementChrome.cancelPending()', pause)
        destroy = production_method(source, 'protected void onDestroy()')
        self.assertLess(destroy.index('managementChrome.cancelPending()'), destroy.index('web.destroy()'))
        renderer = production_method(source, 'public boolean onRenderProcessGone(')
        self.assertLess(renderer.index('managementChrome.cancelPending()'), renderer.index('view.destroy()'))


if __name__ == '__main__':
    unittest.main()
