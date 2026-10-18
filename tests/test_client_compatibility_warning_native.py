"""Execute the shipped compatibility warning callback with Android dialog doubles."""
from functools import lru_cache
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_client_native_status import production_method
from test_management_confirmation import HARNESS as MANAGEMENT_HARNESS

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'app/src/main/java/io/github/russianranger/trasc'

NATIVE = r'''final class MainActivity {
    static final int MODE_PRIVATE=0;
    private WebView web=new WebView();
    private RuntimeManager runtime;
    private boolean activityResumed=true,finishing,destroyed;
    private LauncherController launcherController=new LauncherController();
    private final Map<String,Preferences> preferences=new HashMap<>();
    private final ClientCompatibilityReview review=new ClientCompatibilityReview();
    private final ClientCompatibilityReview compatibilityReview=review;
    MainActivity(WorldProfiles profiles){runtime=new RuntimeManager(profiles);}
    boolean isFinishing(){return finishing;}boolean isDestroyed(){return destroyed;}
    void runOnUiThread(Runnable runnable){runnable.run();}
    Preferences getSharedPreferences(String name,int mode){return preferences.computeIfAbsent(name,key->new Preferences());}
    static final class Preferences {
        final Map<String,Boolean> values=new HashMap<>();int saves;
        boolean getBoolean(String key,boolean fallback){return values.getOrDefault(key,fallback);}
        Preferences edit(){return this;}Preferences putBoolean(String key,boolean value){values.put(key,value);return this;}
        void apply(){saves++;}
    }
    static final class LauncherController {void reset(){}}
    __PRODUCTION_ENABLED_GET__
    __PRODUCTION_ENABLED_SET__
    __PRODUCTION_ALLOWED__
    __PRODUCTION_REVIEW__
    __PRODUCTION_LAUNCH_REVIEW__
    static void expect(boolean value,String message){if(!value)throw new AssertionError(message);}
    CompletableFuture<Boolean> open(){CompletableFuture<Boolean> request=new CompletableFuture<>();review.show(runtime.profiles.current(),"DLL compatibility warning",request);return request;}
    void complete(CompletableFuture<Boolean> result,boolean value,String message){expect(result.isDone()&&result.join()==value,message);}
    void select(String profile)throws Exception {runtime.profiles.beginSwitch(runtime.profiles.current());try{runtime.profiles.select(profile);}finally{runtime.profiles.endSwitch();}}
    void verify(String scenario)throws Exception {
        switch(scenario){
        case "continue":case "continue_suppress": {
            CompletableFuture<Boolean> result=open();AlertDialog shown=AlertDialog.latest;
            expect(shown.shown,"Dialog is visible");expect(shown.message.contains("DLL compatibility"),"Warning describes mismatch");
            expect(shown.title.equals("TRASC Custom — Client compatibility warning"),"Active profile label");
            expect(shown.checkbox.text.equals("Don't warn again")&&!shown.checkbox.isChecked(),"Suppression is explicit and initially unchecked");
            if(scenario.equals("continue_suppress"))shown.checkbox.setChecked(true);
            shown.positive.performClick();complete(result,true,"Continue launches");
            expect(compatibilityWarningsEnabled("custom")==!scenario.equals("continue_suppress"),"Persist only checked Continue");
            shown.cancel();shown.positive.performClick();review.cancelPending();complete(result,true,"Completion remains once");break;
        }
        case "cancel":case "dismiss":case "back":case "controller_b":case "pause":case "destroy":case "renderer":case "stale_positive":case "profile_changed": {
            CompletableFuture<Boolean> result=open();AlertDialog shown=AlertDialog.latest;shown.checkbox.setChecked(true);
            if(scenario.equals("cancel"))shown.negative.performClick();
            if(scenario.equals("dismiss"))shown.dismiss();
            if(scenario.equals("back")||scenario.equals("controller_b")){
                int key=scenario.equals("back")?KeyEvent.KEYCODE_BACK:KeyEvent.KEYCODE_BUTTON_B;
                expect(shown.key(key,KeyEvent.ACTION_DOWN),"B/Back down handled");expect(!result.isDone(),"Key down cannot accept/cancel twice");
                shown.key(key,KeyEvent.ACTION_UP);
            }
            if(scenario.equals("pause")){activityResumed=false;review.cancelPending();}
            if(scenario.equals("destroy")){destroyed=true;review.cancelPending();}
            if(scenario.equals("renderer")){web=null;review.cancelPending();}
            if(scenario.equals("stale_positive")){activityResumed=false;shown.positive.performClick();}
            if(scenario.equals("profile_changed")){select("takp");shown.positive.performClick();}
            complete(result,false,"Review cancellation prevents launch");expect(compatibilityWarningsEnabled("custom"),"Cancel never saves checkbox");
            shown.positive.performClick();complete(result,false,"Stale positive cannot revive cancelled launch");break;
        }
        case "controller": {
            CompletableFuture<Boolean> result=open();AlertDialog shown=AlertDialog.latest;
            expect(shown.focused==shown.negative,"Initial focus is Cancel");
            expect(!shown.key(KeyEvent.KEYCODE_DPAD_RIGHT,KeyEvent.ACTION_DOWN),"Android owns directional focus");
            shown.checkbox.requestFocus();shown.key(KeyEvent.KEYCODE_BUTTON_A,KeyEvent.ACTION_UP);expect(shown.checkbox.isChecked(),"A toggles checkbox");expect(!result.isDone(),"Checkbox does not launch");
            shown.positive.requestFocus();shown.key(KeyEvent.KEYCODE_BUTTON_A,KeyEvent.ACTION_DOWN);expect(!result.isDone(),"Held A does not launch");
            shown.key(KeyEvent.KEYCODE_BUTTON_A,KeyEvent.ACTION_UP);complete(result,true,"Focused Continue A launches");expect(!compatibilityWarningsEnabled("custom"),"Focused positive persists suppression");break;
        }
        case "profiles": {
            for(String profile:new String[]{"custom","traditional","takp"})expect(compatibilityWarningsEnabled(profile),"Each profile starts enabled");
            compatibilityWarningsEnabled("custom",false);expect(compatibilityWarningsEnabled("traditional")&&compatibilityWarningsEnabled("takp"),"Custom suppression is isolated");
            select("takp");CompletableFuture<Boolean> result=open();AlertDialog shown=AlertDialog.latest;shown.checkbox.setChecked(true);shown.positive.performClick();complete(result,true,"TAKP callback");
            expect(!compatibilityWarningsEnabled("takp")&&compatibilityWarningsEnabled("traditional"),"TAKP preference isolated");
            compatibilityWarningsEnabled("custom",true);expect(compatibilityWarningsEnabled("custom")&&!compatibilityWarningsEnabled("takp"),"Explicit reenable supported");break;
        }
        case "duplicate": {
            CompletableFuture<Boolean> first=open();AlertDialog shown=AlertDialog.latest;CompletableFuture<Boolean> second=open();complete(second,false,"Concurrent review cancelled");expect(AlertDialog.latest==shown,"Original dialog retained");shown.positive.performClick();complete(first,true,"Original launches");break;
        }
        case "window_failure":case "widget_failure": {
            if(scenario.equals("window_failure"))AlertDialog.failShow=true;else android.widget.CheckBox.failConstruction=true;CompletableFuture<Boolean> result=open();complete(result,false,"Window teardown cancels");expect(runtime.failures==1,"Window failure recorded");expect(compatibilityWarningsEnabled("custom"),"Failed dialog cannot suppress");break;
        }
        case "invalid_lifecycle": {
            activityResumed=false;CompletableFuture<Boolean> result=open();complete(result,false,"Paused screen cannot begin review");expect(AlertDialog.latest==null,"No paused dialog");break;
        }
        case "advisory_mismatch":case "legacy_mismatch":case "inspection_error":case "inspection_exception":case "suppressed":case "matching":case "mode_bypass":case "profile_bypass":case "offline_bypass": {
            runtime.response=new JSONObject().put("ok",true).put("result",new JSONObject().put("allowed",true));
            if(scenario.equals("advisory_mismatch"))runtime.response=new JSONObject().put("ok",true).put("result",new JSONObject().put("requires_confirmation",true).put("message","Mismatched DLL"));
            if(scenario.equals("legacy_mismatch"))runtime.response=new JSONObject().put("ok",true).put("result",new JSONObject().put("allowed",false).put("message","Legacy mismatch"));
            if(scenario.equals("inspection_error"))runtime.response=new JSONObject().put("ok",false).put("error","No compatibility module");
            if(scenario.equals("inspection_exception"))runtime.inspectionFailure=new IOException("Transport unavailable");
            if(scenario.equals("suppressed")){runtime.inspectionFailure=new IOException("Must not inspect");compatibilityWarningsEnabled("custom",false);}
            if(scenario.equals("profile_bypass"))select("traditional");
            if(scenario.equals("offline_bypass"))runtime.running=false;
            final JSONObject args=new JSONObject().put("mode",scenario.equals("mode_bypass")?"compiler":"client");
            boolean shouldWarn=scenario.equals("advisory_mismatch")||scenario.equals("legacy_mismatch")||scenario.equals("inspection_error")||scenario.equals("inspection_exception");
            final boolean[] accepted={false};final Exception[] failure={null};
            Thread waiter=new Thread(()->{try{accepted[0]=reviewClientLaunch(runtime.profiles.current(),args);}catch(Exception error){failure[0]=error;}});waiter.start();
            long deadline=System.nanoTime()+2_000_000_000L;while(AlertDialog.latest==null&&waiter.isAlive()&&System.nanoTime()<deadline)Thread.yield();
            if(shouldWarn){expect(AlertDialog.latest!=null,"Advisory offers user a choice");if(scenario.startsWith("inspection"))expect(AlertDialog.latest.message.contains("could not be checked"),"Inspection error is explained");AlertDialog.latest.positive.performClick();}
            waiter.join(2000);expect(!waiter.isAlive()&&accepted[0]&&failure[0]==null,"Mismatch or failed inspection cannot prohibit Continue");
            if(!shouldWarn)expect(AlertDialog.latest==null,"Matching, suppressed and unrelated launch paths remain silent");
            if(scenario.endsWith("bypass")||scenario.equals("suppressed"))expect(runtime.inspections==0,"Bypassed review does not inspect or require backend");break;
        }
        case "interrupted_callback": {
            final boolean[] accepted={true};Thread waiter=new Thread(()->{try{accepted[0]=review.confirm("custom","Mismatch");}catch(Exception failure){throw new RuntimeException(failure);}});waiter.start();
            long deadline=System.nanoTime()+2_000_000_000L;while(AlertDialog.latest==null&&System.nanoTime()<deadline)Thread.yield();
            expect(AlertDialog.latest!=null,"Background review is shown");AlertDialog shown=AlertDialog.latest;shown.checkbox.setChecked(true);waiter.interrupt();waiter.join(2000);
            expect(!waiter.isAlive()&&!accepted[0],"Interrupted worker cancels pending launch");shown.positive.performClick();expect(compatibilityWarningsEnabled("custom"),"Interrupted review cannot save suppression");break;
        }
        case "blocking_callback": {
            final boolean[] accepted={false};Thread waiter=new Thread(()->{try{accepted[0]=review.confirm("custom","Mismatch");}catch(Exception failure){throw new RuntimeException(failure);}});waiter.start();
            long deadline=System.nanoTime()+2_000_000_000L;while(AlertDialog.latest==null&&System.nanoTime()<deadline)Thread.yield();
            expect(AlertDialog.latest!=null,"Background request reaches dialog");AlertDialog.latest.positive.performClick();waiter.join(2000);expect(!waiter.isAlive()&&accepted[0],"Positive resolves waiting launcher worker");break;
        }
        default:throw new AssertionError(scenario);
        }
    }
    public static void main(String[] args)throws Exception {new MainActivity(new WorldProfiles(new File(args[1]))).verify(args[0]);System.out.println("PASS "+args[0]);}
}
'''

@lru_cache(maxsize=1)
def executed_reviews():
    source=(PACKAGE/'MainActivity.java').read_text()
    prefix=MANAGEMENT_HARNESS.split('final class MainActivity {',1)[0]
    prefix=prefix.replace('import java.util.*;', 'import java.util.*;\nimport java.util.concurrent.*;')
    prefix=prefix.replace('static AlertDialog latest;', 'static volatile AlertDialog latest;')
    prefix=prefix.replace('final WorldProfiles profiles;int failures;', 'final WorldProfiles profiles;int failures,inspections;boolean running=true;JSONObject response;Exception inspectionFailure;boolean alive(){return running;}JSONObject request(String operation,JSONObject args)throws Exception {inspections++;if(inspectionFailure!=null)throw inspectionFailure;return response;}')
    prefix += r'''final class JSONObject {
        final Map<String,Object> values=new HashMap<>();JSONObject(){}JSONObject(String serialized){}
        JSONObject put(String key,Object value){values.put(key,value);return this;}
        boolean optBoolean(String key){return optBoolean(key,false);}boolean optBoolean(String key,boolean fallback){Object value=values.get(key);return value instanceof Boolean?(Boolean)value:fallback;}
        String optString(String key,String fallback){Object value=values.get(key);return value==null?fallback:String.valueOf(value);}
        JSONObject getJSONObject(String key){Object value=values.get(key);if(!(value instanceof JSONObject))throw new IllegalArgumentException("Missing object");return (JSONObject)value;}
        public String toString(){return "{}";}
    }
'''
    prefix=prefix.replace('String title,message;Button positive,negative;', 'String title,message;android.widget.CheckBox checkbox;Button positive,negative;')
    prefix=prefix.replace('Builder setMessage(String text){dialog.message=text;return this;}', 'Builder setMessage(String text){dialog.message=text;return this;}\n        Builder setView(android.widget.CheckBox view){dialog.checkbox=view;view.dialogFocus=()->dialog.focused=view;return this;}')
    replacements={
        '__PRODUCTION_ENABLED_GET__':production_method(source,'private boolean compatibilityWarningsEnabled(String profile)'),
        '__PRODUCTION_ENABLED_SET__':production_method(source,'private void compatibilityWarningsEnabled(String profile,boolean enabled)'),
        '__PRODUCTION_ALLOWED__':production_method(source,'private boolean clientReviewAllowed(String profile)'),
        '__PRODUCTION_REVIEW__':production_method(source,'private final class ClientCompatibilityReview'),
        '__PRODUCTION_LAUNCH_REVIEW__':production_method(source,'private boolean reviewClientLaunch('),
    }
    harness=NATIVE
    for key,value in replacements.items():harness=harness.replace(key,value)
    scenarios=('continue','continue_suppress','cancel','dismiss','back','controller_b','pause','destroy','renderer','stale_positive','profile_changed','controller','profiles','duplicate','window_failure','widget_failure','invalid_lifecycle','blocking_callback','interrupted_callback','advisory_mismatch','legacy_mismatch','inspection_error','inspection_exception','suppressed','matching','mode_bypass','profile_bypass','offline_bypass')
    with tempfile.TemporaryDirectory(prefix='trasc-compat-warning-') as temporary:
        directory=Path(temporary)
        files={
            'android/view/View.java':'package android.view; public class View {public void setFocusableInTouchMode(boolean value){} public boolean requestFocus(){return true;} public boolean performClick(){return true;}}',
            'android/R.java':'package android; public final class R {public static final class string {public static final int cancel=17039360;}}',
            'android/widget/CheckBox.java':'''package android.widget; public class CheckBox extends android.view.View {public String text;boolean checked;public static boolean failConstruction;public Runnable dialogFocus;public CheckBox(Object context){if(failConstruction)throw new IllegalStateException("Widget construction failed");}public void setText(String value){text=value;}public void setChecked(boolean value){checked=value;}public boolean isChecked(){return checked;}@Override public boolean requestFocus(){dialogFocus.run();return true;}@Override public boolean performClick(){checked=!checked;return true;}}''',
            'io/github/russianranger/trasc/MainActivity.java':prefix+harness,
        }
        paths=[]
        for name,text in files.items():
            path=directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);paths.append(str(path))
        subprocess.run(['java','-m','jdk.compiler/com.sun.tools.javac.Main','-d',str(directory),str(PACKAGE/'WorldProfiles.java'),*paths],check=True,capture_output=True,text=True,timeout=60)
        outcomes={}
        for scenario in scenarios:
            world=directory/'worlds'/scenario;world.mkdir(parents=True)
            result=subprocess.run(['java','-cp',str(directory),'io.github.russianranger.trasc.MainActivity',scenario,str(world)],check=True,capture_output=True,text=True,timeout=15)
            outcomes[scenario]=result.stdout.strip()
        return outcomes

class ClientCompatibilityWarningNativeTests(unittest.TestCase):
    def test_warning_callbacks_only_save_suppression_on_explicit_continue(self):
        outcomes=executed_reviews()
        for scenario in ('continue','continue_suppress','cancel','dismiss','profiles','duplicate','window_failure','widget_failure','blocking_callback'):
            with self.subTest(scenario=scenario):self.assertEqual(outcomes[scenario],'PASS '+scenario)

    def test_controller_and_lifecycle_cancel_stale_reviews(self):
        outcomes=executed_reviews()
        for scenario in ('back','controller_b','pause','destroy','renderer','stale_positive','profile_changed','controller','invalid_lifecycle','interrupted_callback'):
            with self.subTest(scenario=scenario):self.assertEqual(outcomes[scenario],'PASS '+scenario)

    def test_real_launch_review_allows_continue_on_mismatch_and_inspection_failure(self):
        outcomes=executed_reviews()
        for scenario in ('advisory_mismatch','legacy_mismatch','inspection_error','inspection_exception','suppressed','matching','mode_bypass','profile_bypass','offline_bypass'):
            with self.subTest(scenario=scenario):self.assertEqual(outcomes[scenario],'PASS '+scenario)

    def test_launch_integration_is_advisory_and_cancelled_launch_never_starts(self):
        main=(PACKAGE/'MainActivity.java').read_text()
        review=production_method(main,'private boolean reviewClientLaunch(')
        self.assertIn('requires_confirmation',review)
        self.assertIn('result.optBoolean("allowed",true)',review)
        self.assertIn('catch(Exception error)',review)
        self.assertIn('compatibilityReview.confirm(',review)
        bridge=main[main.index('case "client_start":'):main.index('case "client_stop":')]
        self.assertLess(bridge.index('reviewClientLaunch'),bridge.index('clientRuntime.start'))
        self.assertIn('.put("cancelled",true)',bridge)
        start=production_method((PACKAGE/'ClientRuntime.java').read_text(),'synchronized JSONObject start(')
        self.assertNotIn('client_spellbook_preflight',start)
        self.assertIn('Wait for client file changes',start)
        for marker in ('protected void onPause()','protected void onDestroy()','public boolean onRenderProcessGone('):
            self.assertIn('compatibilityReview.cancelPending()',production_method(main,marker))
