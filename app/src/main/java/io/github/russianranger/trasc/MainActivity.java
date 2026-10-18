package io.github.russianranger.trasc;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.webkit.*;
import org.json.JSONObject;
import java.io.*;
import java.util.concurrent.*;
import java.util.Arrays;

public final class MainActivity extends Activity {
    private WebView web;
    private ManagementChromeClient managementChrome;
    private final ClientCompatibilityReview compatibilityReview=new ClientCompatibilityReview();
    private volatile boolean activityResumed;
    private RuntimeManager runtime;
    private ControllerManager controller;
    private LauncherController launcherController;
    private volatile boolean launcherMenuSuspended;
    private android.hardware.input.InputManager launcherInputManager;
    private final android.hardware.input.InputManager.InputDeviceListener launcherDevices=new android.hardware.input.InputManager.InputDeviceListener(){
        public void onInputDeviceAdded(int id){}
        public void onInputDeviceChanged(int id){if(launcherController!=null)launcherController.deviceUnavailable(id);}
        public void onInputDeviceRemoved(int id){if(launcherController!=null)launcherController.deviceUnavailable(id);}
    };
    private String controllerProfile,controllerActivation;
    private ClientRuntime clientRuntime;
    private final ExecutorService tasks=Executors.newFixedThreadPool(3);
    private String pickerId,pickerKind,exportPath;
    private boolean pickerReplace;
    private JSONObject pickerLauncher;
    private WorldProfiles.Lease pickerLease;
    private static final int IMPORT=10,EXPORT=11;
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);runtime=RuntimeManager.get(this);clientRuntime=ClientRuntime.get(this);
        getWindow().setStatusBarColor(0xff10191c); getWindow().setNavigationBarColor(0xff10191c);
        web=new WebView(this);setContentView(web);
        controller=createController();
        launcherController=new LauncherController(command->{
            if(web!=null&&!isDestroyed()&&hasWindowFocus()&&!launcherMenuSuspended&&!controller.active())
                web.evaluateJavascript("window.launcherMenuController && window.launcherMenuController.command("+JSONObject.quote(command)+")",null);
        });
        launcherInputManager=(android.hardware.input.InputManager)getSystemService(INPUT_SERVICE);
        launcherInputManager.registerInputDeviceListener(launcherDevices,null);
        WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);s.setAllowContentAccess(false);s.setAllowFileAccessFromFileURLs(false);s.setAllowUniversalAccessFromFileURLs(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new Bridge(),"Trasc");
        managementChrome=new ManagementChromeClient();web.setWebChromeClient(managementChrome);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean onRenderProcessGone(WebView view,RenderProcessGoneDetail detail){
                runtime.recordFailure("management_display",new IOException("WebView renderer exited: crashed="+detail.didCrash()+" priority="+detail.rendererPriorityAtExit()));
                managementChrome.cancelPending();compatibilityReview.cancelPending();
                web=null;controller.capture(false);
                if(launcherController!=null)launcherController.reset();
                android.view.ViewParent parent=view.getParent();if(parent instanceof android.view.ViewGroup)((android.view.ViewGroup)parent).removeView(view);
                view.destroy();
                android.widget.Button reopen=new android.widget.Button(MainActivity.this);
                reopen.setText("Management screen stopped. Tap to reopen.");reopen.setOnClickListener(v->recreate());setContentView(reopen);
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();
                if("https".equals(uri.getScheme())&&"app.trasc.local".equals(uri.getHost())){
                    String path=uri.getPath();if(path==null||path.equals("/"))path="/index.html";
                    if(!path.matches("/[a-zA-Z0-9_.-]+"))return blocked();
                    try {String mime=path.endsWith(".js")?"application/javascript":path.endsWith(".css")?"text/css":path.endsWith(".svg")?"image/svg+xml":path.endsWith(".webp")?"image/webp":path.endsWith(".ttf")?"font/ttf":"text/html";
                        WebResourceResponse response=new WebResourceResponse(mime,"UTF-8",getAssets().open("ui"+path));
                        java.util.Map<String,String> headers=new java.util.HashMap<>();
                        headers.put("Content-Security-Policy","default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'");
                        response.setResponseHeaders(headers);return response;
                    }catch(IOException e){return blocked();}
                }
                return blocked();
            }
            private WebResourceResponse blocked(){return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));}
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return !r.getUrl().toString().equals("https://app.trasc.local/index.html");}
        });
        web.loadUrl("https://app.trasc.local/index.html");
        if(android.os.Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},20);
    }
    /** WebView otherwise suppresses window.confirm and immediately returns false. */
    private final class ManagementChromeClient extends WebChromeClient {
        private AlertDialog dialog;
        private JsResult pending;
        private boolean allowed(WebView view,String url){
            return activityResumed&&!isFinishing()&&!isDestroyed()&&view!=null&&view==web
                &&"https://app.trasc.local/index.html".equals(url)
                &&"https://app.trasc.local/index.html".equals(view.getUrl());
        }
        @Override public boolean onJsConfirm(WebView view,String url,String message,JsResult result){
            if(!allowed(view,url)||pending!=null){result.cancel();return true;}
            final String profile=runtime.profiles.current();
            pending=result;
            try {
                dialog=new AlertDialog.Builder(MainActivity.this)
                    .setTitle(WorldProfiles.label(profile)+" — Confirm action")
                    .setMessage(message)
                    .setPositiveButton("Continue",(ignored,which)->resolve(result,allowed(view,url)&&profile.equals(runtime.profiles.current())))
                    .setNegativeButton(android.R.string.cancel,(ignored,which)->resolve(result,false))
                    .setOnCancelListener(ignored->resolve(result,false))
                    .create();
                dialog.setOnDismissListener(ignored->resolve(result,false));
                dialog.setOnKeyListener((ignored,key,event)->{
                    if(key==KeyEvent.KEYCODE_BUTTON_B||key==KeyEvent.KEYCODE_BACK){
                        if(event.getAction()==KeyEvent.ACTION_UP)cancelPending();
                        return true;
                    }
                    if(key==KeyEvent.KEYCODE_BUTTON_A){
                        if(event.getAction()==KeyEvent.ACTION_UP&&dialog!=null){
                            android.view.View focused=dialog.getCurrentFocus();
                            if(focused==dialog.getButton(AlertDialog.BUTTON_POSITIVE)||focused==dialog.getButton(AlertDialog.BUTTON_NEGATIVE))focused.performClick();
                        }
                        return true;
                    }
                    return false;
                });
                dialog.show();
                // Opening a confirmation must never make a held controller A approve it.
                dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setFocusableInTouchMode(true);
                dialog.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus();
            }catch(RuntimeException error){cancelPending();runtime.recordFailure("management_confirmation",error);}
            return true;
        }
        private void resolve(JsResult result,boolean accepted){
            if(pending!=result)return;
            AlertDialog previous=dialog;dialog=null;pending=null;
            if(accepted)result.confirm();else result.cancel();
            if(previous!=null)previous.dismiss();
        }
        void cancelPending(){if(pending!=null)resolve(pending,false);}
    }
    private boolean compatibilityWarningsEnabled(String profile){return getSharedPreferences("client-compatibility-warnings",MODE_PRIVATE).getBoolean(profile+".enabled",true);}
    private void compatibilityWarningsEnabled(String profile,boolean enabled){getSharedPreferences("client-compatibility-warnings",MODE_PRIVATE).edit().putBoolean(profile+".enabled",enabled).apply();}
    private boolean clientReviewAllowed(String profile){return activityResumed&&!isFinishing()&&!isDestroyed()&&web!=null&&profile.equals(runtime.profiles.current());}
    /** Compatibility is advisory. Continue always retains the user's existing launch path. */
    private boolean reviewClientLaunch(String profile,JSONObject args)throws Exception {
        if(!"custom".equals(profile)||!"client".equals(args.optString("mode","client"))||!compatibilityWarningsEnabled(profile)||!runtime.alive())return true;
        String warning;
        try {
            JSONObject response=runtime.request("client_spellbook_preflight",new JSONObject(args.toString()).put("__profile",profile));
            if(!response.optBoolean("ok"))throw new IOException(response.optString("error","Compatibility inspection could not finish."));
            JSONObject result=response.getJSONObject("result");
            if(!result.optBoolean("requires_confirmation",false)&&result.optBoolean("allowed",true))return true;
            warning=result.optString("message","The client and server may have incompatible spellbook settings.");
        }catch(Exception error){warning="Compatibility could not be checked: "+(error.getMessage()==null?error.toString():error.getMessage());}
        return compatibilityReview.confirm(profile,warning+"\n\nYou can continue launching the client with its current files.");
    }
    private final class ClientCompatibilityReview {
        private AlertDialog dialog;
        private CompletableFuture<Boolean> pending;
        boolean confirm(String profile,String message)throws Exception {
            CompletableFuture<Boolean> request=new CompletableFuture<>();
            runOnUiThread(()->show(profile,message,request));
            try{return request.get();}
            catch(InterruptedException interrupted){request.complete(false);runOnUiThread(()->resolve(request,false,null,profile));Thread.currentThread().interrupt();return false;}
        }
        private void show(String profile,String message,CompletableFuture<Boolean> request){
            if(request.isDone()||pending!=null||!clientReviewAllowed(profile)){request.complete(false);return;}
            pending=request;
            try {
                android.widget.CheckBox suppress=new android.widget.CheckBox(MainActivity.this);
                suppress.setText("Don't warn again");suppress.setChecked(false);
                if(launcherController!=null)launcherController.reset();
                dialog=new AlertDialog.Builder(MainActivity.this)
                    .setTitle(WorldProfiles.label(profile)+" — Client compatibility warning")
                    .setMessage(message).setView(suppress)
                    .setPositiveButton("Continue",(ignored,which)->resolve(request,clientReviewAllowed(profile),suppress,profile))
                    .setNegativeButton(android.R.string.cancel,(ignored,which)->resolve(request,false,null,profile))
                    .setOnCancelListener(ignored->resolve(request,false,null,profile)).create();
                dialog.setOnDismissListener(ignored->resolve(request,false,null,profile));
                dialog.setOnKeyListener((ignored,key,event)->{
                    if(key==KeyEvent.KEYCODE_BUTTON_B||key==KeyEvent.KEYCODE_BACK){if(event.getAction()==KeyEvent.ACTION_UP)cancelPending();return true;}
                    if(key==KeyEvent.KEYCODE_BUTTON_A){
                        if(event.getAction()==KeyEvent.ACTION_UP&&dialog!=null){
                            android.view.View focused=dialog.getCurrentFocus();
                            if(focused==suppress||focused==dialog.getButton(AlertDialog.BUTTON_POSITIVE)||focused==dialog.getButton(AlertDialog.BUTTON_NEGATIVE))focused.performClick();
                        }
                        return true;
                    }
                    return false;
                });
                dialog.show();
                dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setFocusableInTouchMode(true);
                dialog.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus();
            }catch(RuntimeException error){resolve(request,false,null,profile);runtime.recordFailure("client_compatibility_warning",error);}
        }
        private void resolve(CompletableFuture<Boolean> request,boolean accepted,android.widget.CheckBox suppress,String profile){
            if(pending!=request)return;
            accepted=accepted&&!request.isDone()&&clientReviewAllowed(profile);
            AlertDialog previous=dialog;dialog=null;pending=null;
            if(accepted&&suppress!=null&&suppress.isChecked())compatibilityWarningsEnabled(profile,false);
            request.complete(accepted);
            if(previous!=null)previous.dismiss();
        }
        void cancelPending(){if(pending!=null)resolve(pending,false,null,runtime.profiles.current());}
    }
    private String restoredActivation(){return getSharedPreferences("session-restoration",MODE_PRIVATE).getString("activation","");}
    private ControllerManager createController(){controllerProfile=runtime.profiles.current();controllerActivation=restoredActivation();File selectedWork;
        try{selectedWork=new File(runtime.profiles.home(controllerProfile),"work");}catch(IOException e){throw new IllegalStateException(e);}
        return new ControllerManager(this,selectedWork,controllerProfile,event->runOnUiThread(()->{
        if(!isDestroyed()&&web!=null)web.evaluateJavascript("window.clientInputEvent && window.clientInputEvent("+event+")",null);
    }));}
    interface UiResult {Object run()throws Exception;}
    private void profileUi(String id,String profile,UiResult task){runOnUiThread(()->{
        try(WorldProfiles.Lease ignored=runtime.profiles.enter(profile)){if(!profile.equals(controllerProfile)||!restoredActivation().equals(controllerActivation)){controller.close();controller=createController();}reply(id,task.run(),null);}
        catch(Exception e){reply(id,null,e);}
    });}
    private boolean submit(Runnable task){try{tasks.execute(task);return true;}catch(RejectedExecutionException ignored){return false;}}
    private void service(){startForegroundService(new Intent(this,ServerService.class));}
    private void reply(String id,Object result,Exception error){
        try {
            JSONObject json=new JSONObject().put("ok",error==null);
            if(error==null)json.put("result",result);else json.put("error",error.getMessage()==null?error.toString():error.getMessage());
            final String script="window.nativeReply("+JSONObject.quote(id)+","+json+")";
            runOnUiThread(()->{if(!isDestroyed()&&web!=null)web.evaluateJavascript(script,null);});
        }catch(Exception ignored){}
    }
    final class Bridge {
        @JavascriptInterface public void launcherKeyboard(boolean show){runOnUiThread(()->{
            if(web==null||isDestroyed()||!hasWindowFocus())return;
            android.view.inputmethod.InputMethodManager keyboard=(android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
            if(show){web.requestFocus();keyboard.showSoftInput(web,android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT);}
            else keyboard.hideSoftInputFromWindow(web.getWindowToken(),0);
        });}
        // A physical-input rebinding surface can temporarily own the controller.
        @JavascriptInterface public void launcherMenuSuspended(boolean suspended){launcherMenuSuspended=suspended;runOnUiThread(()->{if(launcherController!=null)launcherController.reset();});}
        @JavascriptInterface public void call(String id,String operation,String input){
            final String submittedProfile=runtime.profiles.current();
            submit(()->{
                WorldProfiles.Lease lease=null;
                try {
                    JSONObject args=new JSONObject(input);Object result;
                    if(!Arrays.asList("native_state","client_native_state","runtime_log","logs","session_cancel","lon_input_state","lon_input_cancel").contains(operation))runtime.requireRecovered();
                    final String profile=operation.equals("native_state")?runtime.profiles.current():args.optString("__profile",submittedProfile);
                    if(operation.equals("lon_input_state")||operation.equals("lon_input_cancel")) {
                        reply(id,operation.equals("lon_input_cancel")?SafLonImport.cancel():SafLonImport.state(),null);return;
                    }
                    if(SafLonImport.busy()) {
                        if(operation.equals("native_state")){reply(id,runtime.nativeState(),null);return;}
                        if(operation.equals("client_native_state")){reply(id,clientRuntime.state(),null);return;}
                        if(operation.equals("runtime_log")||operation.equals("logs")){reply(id,runtime.logs(operation.equals("runtime_log")?"runtime.log":args.optString("name","control.log")),null);return;}
                        throw new IOException("A Legends of Norrath input transfer is in progress. Finish or cancel it first.");
                    }
                    if(operation.equals("profile_switch")) {
                        final JSONObject changed=runtime.switchProfile(profile,args.getString("profile"));
                        runOnUiThread(()->{controller.close();controller=createController();reply(id,changed,null);});
                        return;
                    }
                    if(runtime.sessionBusy&&Arrays.asList("native_state","session_cancel").contains(operation)) {
                        reply(id,operation.equals("session_cancel")?runtime.cancelSession():runtime.nativeState(),null);return;
                    }
                    lease=runtime.profiles.enter(profile);
                    if(runtime.sessionBusy&&!operation.equals("native_state")&&!operation.equals("runtime_log")&&!operation.equals("logs")&&!operation.equals("client_native_state"))throw new IOException("A complete session transfer is in progress");
                    switch(operation){
                        case "native_state": result=runtime.nativeState();break;
                        case "native_files": result=runtime.browseFiles(args);break;
                        case "file_delete_preview": case "file_delete":
                            synchronized(clientRuntime) {synchronized(runtime) {
                                if(runtime.alive()||runtime.installing||runtime.sessionBusy||clientRuntime.alive()||clientRuntime.busy)
                                    throw new IOException("Stop the client and server runtime before deleting files");
                                runtime.profiles.beginMaintenance();
                                try {service();result=runtime.cleanupFiles(operation,args);}
                                finally {runtime.profiles.endMaintenance();if(!runtime.alive()&&!clientRuntime.alive())stopService(new Intent(MainActivity.this,ServerService.class));}
                            }}
                            break;
                        case "client_native_state": result=clientRuntime.state();break;
                        case "client_dll_license":
                            profileUi(id,profile,()->{openMicrosoftLicense(args.getString("url"));return new JSONObject();});return;
                        case "client_directx_online": service();result=clientRuntime.installDirectX(null);break;
                        case "client_runtime_online": service();result=clientRuntime.installOnline();break;
                        case "client_compatibility_warnings":
                            if(args.has("enabled")) {
                                if(!(args.get("enabled") instanceof Boolean))throw new IOException("Compatibility warnings setting must be true or false");
                                compatibilityWarningsEnabled(profile,args.getBoolean("enabled"));
                            }
                            result=new JSONObject().put("profile",profile).put("enabled",compatibilityWarningsEnabled(profile));break;
                        case "client_start":
                            if(!reviewClientLaunch(profile,args)||!clientReviewAllowed(profile)){result=new JSONObject().put("cancelled",true).put("message","Client launch cancelled");break;}
                            service();runOnUiThread(()->controller.capture(false));result=clientRuntime.start(args);break;
                        case "client_stop": clientRuntime.stop();if(!runtime.alive()&&!runtime.installing)stopService(new Intent(MainActivity.this,ServerService.class));result=clientRuntime.state();break;
                        case "client_view":
                            if(!clientRuntime.alive()||!clientRuntime.displaySocket().exists())throw new IOException("Launch Wine desktop or the game before opening its display");
                            runOnUiThread(()->startActivity(new Intent(MainActivity.this,ClientActivity.class)));result=new JSONObject();break;
                        case "runtime_install": service();runtime.installOnline();result=runtime.nativeState();break;
                        case "runtime_start": service();runtime.start();result=runtime.nativeState();break;
                        case "runtime_stop": runtime.stop();if(!clientRuntime.alive()&&!clientRuntime.busy)stopService(new Intent(MainActivity.this,ServerService.class));result=runtime.nativeState();break;
                        case "runtime_log": result=runtime.logs("runtime.log");break;
                        case "log_retention": result=runtime.logRetention(args);break;
                        case "clear_logs":
                            synchronized(clientRuntime){result=runtime.clearLogs(args,clientRuntime.alive()||clientRuntime.busy);}
                            break;
                        case "logs": result=runtime.logs(args.optString("name","control.log"));break;
                        case "export_logs": service();result=runtime.exportLogs();break;
                        case "session_cancel":result=runtime.cancelSession();break;
                        case "session_backup_all":service();runOnUiThread(()->controller.capture(false));result=runtime.backupAllSessions(args.optJSONObject("launcher_preferences"),null);break;
                        case "session_backup": service();runOnUiThread(()->controller.capture(false));result=runtime.backupSession();break;
                        case "controller_state": profileUi(id,profile,()->controller.state());return;
                        case "controller_save": profileUi(id,profile,()->{controller.configure(args,true);return controller.state();});return;
                        case "controller_capture": profileUi(id,profile,()->{controller.capture(args.optBoolean("active")&&hasWindowFocus());return controller.state();});return;
                        case "pick": runOnUiThread(()->pick(id,args.optString("kind","file"),args.optBoolean("replace"),profile,args.optJSONObject("launcher_preferences")));return;
                        case "export": runOnUiThread(()->export(id,args.optString("path"),profile));return;
                        case "era_apply": case "era_restore":
                            synchronized(clientRuntime) {
                                if(!"traditional".equals(profile))throw new IOException("Era rules belong to Traditional EQEmu");
                                if(clientRuntime.alive()||clientRuntime.busy)throw new IOException("Stop the client before switching era rules");
                                JSONObject response=runtime.request(operation,args);
                                if(!response.getBoolean("ok"))throw new IOException(response.optString("error"));
                                result=response.get("result");
                            }
                            break;
                        case "bots_generate": case "bots_socials_install": case "bots_socials_restore": case "bots_storage_enable":
                            synchronized(clientRuntime) {
                                if(clientRuntime.alive()||clientRuntime.busy)throw new IOException("Stop the client before changing bots, social buttons or bot storage");
                                JSONObject response=runtime.request(operation,args);
                                if(!response.getBoolean("ok"))throw new IOException(response.optString("error"));
                                result=response.get("result");
                            }
                            break;
                        case "client_settings_save":
                        case "client_host_save": case "client_host_restore": case "client_4gb_apply": case "client_4gb_restore": case "client_4gb_download": case "client_spellbook_apply": case "client_spellbook_restore":
                        case "import_client_zip": case "import_client_ui": case "activate_client_ui": case "restore_client_ui": case "prepare_client": case "export_client":
                        case "apply_spell_test": case "restore_spell_test":
                        case "client_addons_copy": case "client_dll_deploy":
                        case "set_takp_skeletons":
                        case "source_update_preview": case "source_update_apply":
                        case "build_update": case "deploy_update":
                        case "client_dll_sdk": case "client_dll_download":
                        case "quest_sync_apply": case "lon_data_apply": case "custom_deployment_recover":
                            // Serialize submission with native launch; start also checks queued/running jobs.
                            synchronized(clientRuntime) {
                                if(clientRuntime.alive()||clientRuntime.busy)throw new IOException("Stop the embedded client before changing its files");
                                clientRuntime.prepareFileChanges();
                                JSONObject response=runtime.request(operation,args);
                                if(!response.getBoolean("ok"))throw new IOException(response.optString("error"));
                                result=response.get("result");
                            }
                            break;
                        default:
                            JSONObject response=runtime.request(operation,args);
                            if(!response.getBoolean("ok"))throw new IOException(response.optString("error"));
                            result=response.get("result");
                    }
                    reply(id,result,null);
                }catch(Exception e){
                    if(lease!=null&&operation.startsWith("runtime_"))runtime.status=e.getMessage();
                    if(lease!=null&&(operation.startsWith("runtime_")||operation.startsWith("client_")||operation.equals("export_logs")))runtime.recordFailure(operation,e);
                    reply(id,null,e);
                }finally{if(lease!=null)lease.close();}
            });
        }
    }
    private void openMicrosoftLicense(String url)throws Exception {
        java.net.URI parsed=new java.net.URI(url);
        String host=parsed.getHost();
        if(host!=null)host=host.toLowerCase(java.util.Locale.ROOT);
        if(!"https".equalsIgnoreCase(parsed.getScheme())||parsed.getUserInfo()!=null
                ||(parsed.getPort()!=-1&&parsed.getPort()!=443)||host==null
                ||!(host.equals("microsoft.com")||host.endsWith(".microsoft.com")
                    ||host.equals("visualstudio.com")||host.endsWith(".visualstudio.com")||host.equals("aka.ms")))
            throw new IOException("Expected an HTTPS Microsoft license link");
        startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));
    }
    private void pick(String id,String kind,boolean replace,String profile,JSONObject launcher){
        if(pickerId!=null){reply(id,null,new IOException("Finish the open file picker first"));return;}
        if(SafLonImport.busy()){reply(id,null,new IOException("Finish or cancel the Legends of Norrath input transfer first"));return;}
        boolean lonFolder=kind.equals("lon-data-folder"),lonZip=kind.equals("lon-data-zip");
        if((lonFolder||lonZip)&&!"custom".equals(profile)){reply(id,null,new IOException("Legends of Norrath data belongs to the Triptych Custom profile"));return;}
        try{pickerLease=runtime.profiles.enter(profile);}catch(Exception e){reply(id,null,e);return;}
        pickerId=id;pickerKind=kind;pickerReplace=replace;pickerLauncher=launcher;
        boolean allExport=kind.equals("session-export-all");
        Intent intent=lonFolder?new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE):new Intent(allExport?Intent.ACTION_CREATE_DOCUMENT:Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(allExport?"application/zip":"*/*");
        if(lonFolder||lonZip)intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        if(allExport)intent.putExtra(Intent.EXTRA_TITLE,"TRASC-All-Worlds-"+new java.text.SimpleDateFormat("yyyyMMdd-HHmmss",java.util.Locale.ROOT).format(new java.util.Date())+".zip");
        try{startActivityForResult(intent,allExport?EXPORT:IMPORT);}catch(Exception e){pickerId=null;if(pickerLease!=null){pickerLease.close();pickerLease=null;}reply(id,null,e);}
    }
    private File exportFile(String path)throws IOException {
        File file=TarExtractor.path(runtime.work,path);
        if(!file.isFile() || file.toPath().startsWith(new File(runtime.work,"database").toPath()) || file.toPath().startsWith(new File(runtime.work,"run").toPath()))
            throw new IOException("Export a regular file; use Database backup for database data");
        return file;
    }
    private void export(String id,String path,String profile){
        if(pickerId!=null){reply(id,null,new IOException("Finish the open file picker first"));return;}
        try {
            pickerLease=runtime.profiles.enter(profile);
            File file=exportFile(path);pickerId=id;pickerKind=null;pickerLauncher=null;exportPath=path;
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE,file.getName());
            startActivityForResult(intent,EXPORT);
        }catch(Exception e){pickerId=null;if(pickerLease!=null){pickerLease.close();pickerLease=null;}reply(id,null,e);}
    }
    private static final class JSONObjectSafeCancelled {final JSONObject value=new JSONObject();JSONObjectSafeCancelled(){try{value.put("cancelled",true).put("message","File selection cancelled");}catch(Exception ignored){}}}
    @Override protected void onActivityResult(int request,int code,Intent data){
        super.onActivityResult(request,code,data);
        if(request!=IMPORT&&request!=EXPORT)return;
        String id=pickerId,kind=pickerKind,path=exportPath;boolean replace=pickerReplace;JSONObject launcher=pickerLauncher;pickerId=null;pickerKind=null;pickerLauncher=null;
        WorldProfiles.Lease transferLease=pickerLease;pickerLease=null;
        if(id==null){if(transferLease!=null)transferLease.close();return;}
        if(code!=RESULT_OK||data==null||data.getData()==null){if(transferLease!=null)transferLease.close();reply(id,new JSONObjectSafeCancelled().value,null);return;}
        if(transferLease==null){reply(id,null,new IOException("Reopen the file picker in the selected profile"));return;}
        Uri uri=data.getData();service();
        if("lon-data-folder".equals(kind)||"lon-data-zip".equals(kind)) {
            try{SafLonImport.begin(runtime.profiles.current());}
            catch(Exception e){transferLease.close();reply(id,null,e);return;}
            boolean accepted=submit(()->{
                try{reply(id,SafLonImport.stage(runtime,clientRuntime,getContentResolver(),uri,"lon-data-folder".equals(kind)),null);}
                catch(Exception e){runtime.recordFailure("lon_input_stage",e);if(e instanceof InterruptedIOException)reply(id,new JSONObjectSafeCancelled().value,null);else reply(id,null,e);}
                finally{transferLease.close();if(!runtime.alive()&&!clientRuntime.alive()&&!runtime.installing&&!clientRuntime.busy)stopService(new Intent(MainActivity.this,ServerService.class));}
            });
            if(!accepted){SafLonImport.finish();transferLease.close();reply(id,null,new IOException("Launcher closed before the input transfer could start"));}
            return;
        }
        boolean accepted=submit(()->{
            File temp=null;android.os.ParcelFileDescriptor sessionDescriptor=null;boolean sessionTransport=false,destinationFinished=false;
            boolean allExport="session-export-all".equals(kind),allImport="session-all".equals(kind);
            try {
                if(allExport||allImport){runtime.beginSessionTransport(allExport?"preparing":"copy");sessionTransport=true;}
                if(allExport) {
                    JSONObject result;
                    try(OutputStream out=getContentResolver().openOutputStream(uri,"wt")) {
                        if(out==null)throw new IOException("Cannot write the selected backup destination");
                        result=runtime.backupAllSessions(launcher,out);
                    }
                    destinationFinished=true;reply(id,result,null);return;
                }
                if(request==EXPORT){
                    try(InputStream in=new FileInputStream(exportFile(path));OutputStream out=getContentResolver().openOutputStream(uri,"wt")){
                        if(out==null)throw new IOException("Cannot write the selected destination");SessionTransfer.copy(in,out,exportFile(path).length(),null,text->runtime.status=text);
                    }
                    reply(id,new JSONObject().put("message","File exported"),null);return;
                }
                String name="import.zip";
                try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
                    if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);
                }
                name=name.replaceAll("[^a-zA-Z0-9._-]","_");if(name.length()>160)name=name.substring(name.length()-160);
                String unique=System.currentTimeMillis()+"-"+name;
                temp=("session".equals(kind)||allImport)?new File(getCacheDir(),runtime.profiles.current()+"/"+unique):new File(runtime.work,"incoming/"+unique);
                runtime.status="Copying "+name+"…";
                if(allImport) {
                    // Seekable document providers can be verified directly. This avoids an extra
                    // full private copy of large ZIPs on SD/USB storage. Pipe providers fall back
                    // to the same fixed-buffer copy with explicit space checks.
                    File archiveSource=null;
                    try{sessionDescriptor=getContentResolver().openFileDescriptor(uri,"r");}catch(IOException unreadableDescriptor){sessionDescriptor=null;}
                    if(sessionDescriptor!=null&&sessionDescriptor.getStatSize()>=0) {
                        if(sessionDescriptor.getStatSize()>SessionArchive.MAX_ARCHIVE_BYTES)throw new IOException("Archive exceeds supported size");
                        File candidate=new File("/proc/self/fd/"+sessionDescriptor.getFd());
                        // Probe seekability independently from ZIP validation: a deliberately
                        // rejected seekable archive must never trigger a second large copy.
                        try(RandomAccessFile probe=new RandomAccessFile(candidate,"r")){probe.seek(1);archiveSource=candidate;}
                        catch(IOException nonseekable){sessionDescriptor.close();sessionDescriptor=null;}
                    }
                    if(archiveSource==null) {
                    if(sessionDescriptor!=null){sessionDescriptor.close();sessionDescriptor=null;}
                    long expected=-1;
                    try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.SIZE},null,null,null)){if(cursor!=null&&cursor.moveToFirst()&&!cursor.isNull(0))expected=cursor.getLong(0);}
                    temp.getParentFile().mkdirs();
                    try(InputStream in=getContentResolver().openInputStream(uri);FileOutputStream out=new FileOutputStream(temp)) {
                        if(in==null)throw new IOException("Cannot read backup file");SessionTransfer.copy(in,out,expected,getCacheDir(),runtime.sessionProgress("copy"));out.getFD().sync();
                    }
                    archiveSource=temp;
                    }
                    JSONObject result=runtime.restoreAllSessions(archiveSource,replace);
                    runOnUiThread(()->{if(!isDestroyed()){controller.close();controller=createController();}});reply(id,result,null);return;
                }
                try(InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new IOException("Cannot read file");RuntimeManager.copy(in,temp);}
                if("session".equals(kind)){
                    try {
                        JSONObject result=runtime.restoreSession(temp,replace);
                        runOnUiThread(()->controller.reload());
                        reply(id,result,null);
                    } finally {temp.delete();}
                }else if("client-directx".equals(kind)){
                    try{reply(id,clientRuntime.installDirectX(temp),null);}finally{temp.delete();}
                }else if("client-runtime".equals(kind)){
                    try{reply(id,clientRuntime.installOffline(temp),null);}finally{temp.delete();}
                }else if("runtime".equals(kind)){
                    runtime.beginInstall();try{runtime.installArchive(temp);}finally{runtime.installing=false;temp.delete();}
                    reply(id,runtime.nativeState(),null);
                }else {runtime.status="File imported: "+name;reply(id,new JSONObject().put("file",unique).put("path","incoming/"+unique).put("name",name),null);}
            }catch(Exception e){if(temp!=null)temp.delete();runtime.status=e.getMessage();runtime.recordFailure(request==EXPORT?"save_export":"import_"+kind,e);if(e instanceof InterruptedIOException)reply(id,new JSONObjectSafeCancelled().value,null);else reply(id,null,e);}
            finally{
                if(allImport&&temp!=null)temp.delete();
                if(sessionDescriptor!=null)try{sessionDescriptor.close();}catch(IOException ignored){}
                if(allExport&&!destinationFinished)try{android.provider.DocumentsContract.deleteDocument(getContentResolver(),uri);}catch(Exception ignored){}
                if(sessionTransport)runtime.endSessionTransport();transferLease.close();
                if(!runtime.alive()&&!clientRuntime.alive()&&!runtime.installing&&!clientRuntime.busy)stopService(new Intent(MainActivity.this,ServerService.class));
            }
        });
        if(!accepted)transferLease.close();
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event){
        if(controller!=null&&controller.active()){
            if(launcherController!=null)launcherController.reset();
            return controller.key(event)||LauncherController.gamepad(event)||super.dispatchKeyEvent(event);
        }
        if(launcherController!=null&&!launcherMenuSuspended&&hasWindowFocus()&&launcherController.key(event))return true;
        return super.dispatchKeyEvent(event);
    }
    @Override public boolean dispatchGenericMotionEvent(MotionEvent event){
        if(controller!=null&&controller.active()){
            if(launcherController!=null)launcherController.reset();
            return controller.motion(event)||LauncherController.gamepad(event)||super.dispatchGenericMotionEvent(event);
        }
        if(launcherController!=null&&!launcherMenuSuspended&&hasWindowFocus()&&launcherController.motion(event))return true;
        return super.dispatchGenericMotionEvent(event);
    }
    @Override public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(!focus){if(controller!=null)controller.capture(false);if(launcherController!=null)launcherController.reset();}}
    @Override protected void onResume(){super.onResume();activityResumed=true;if(controller!=null)try(WorldProfiles.Lease ignored=runtime.profiles.enter(runtime.profiles.current())){if(!runtime.profiles.current().equals(controllerProfile)||!restoredActivation().equals(controllerActivation)){controller.close();controller=createController();}else controller.reload();}catch(IOException ignored){}if(web!=null)web.evaluateJavascript("if(typeof controllerLoaded!=='undefined'){controllerLoaded=false;if(currentTab==='client')loadController(true).catch(e=>notice(e.message,true));}",null);}
    @Override protected void onPause(){activityResumed=false;compatibilityReview.cancelPending();if(managementChrome!=null)managementChrome.cancelPending();if(controller!=null)controller.capture(false);if(launcherController!=null)launcherController.reset();super.onPause();}
    @Override public void onBackPressed(){if(controller.active()){controller.capture(false);return;}if(web!=null)web.evaluateJavascript("window.appBack && window.appBack()",null);}
    @Override protected void onDestroy(){activityResumed=false;compatibilityReview.cancelPending();if(managementChrome!=null)managementChrome.cancelPending();pickerId=null;if(pickerLease!=null){pickerLease.close();pickerLease=null;}if(launcherInputManager!=null)launcherInputManager.unregisterInputDeviceListener(launcherDevices);if(launcherController!=null)launcherController.reset();if(controller!=null)controller.close();if(web!=null){web.removeJavascriptInterface("Trasc");web.destroy();web=null;}tasks.shutdown();super.onDestroy();}
}
