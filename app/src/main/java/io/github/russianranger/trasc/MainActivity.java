package io.github.russianranger.trasc;

import android.Manifest;
import android.app.Activity;
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

public final class MainActivity extends Activity {
    private WebView web;
    private RuntimeManager runtime;
    private ControllerManager controller;
    private ClientRuntime clientRuntime;
    private final ExecutorService tasks=Executors.newFixedThreadPool(3);
    private String pickerId,pickerKind,exportPath;
    private boolean pickerReplace;
    private static final int IMPORT=10,EXPORT=11;
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);runtime=RuntimeManager.get(this);clientRuntime=ClientRuntime.get(this);
        getWindow().setStatusBarColor(0xff10191c); getWindow().setNavigationBarColor(0xff10191c);
        web=new WebView(this);setContentView(web);
        controller=new ControllerManager(this,runtime.work,event->runOnUiThread(()->{
            if(!isDestroyed())web.evaluateJavascript("window.clientInputEvent && window.clientInputEvent("+event+")",null);
        }));
        WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);s.setAllowContentAccess(false);s.setAllowFileAccessFromFileURLs(false);s.setAllowUniversalAccessFromFileURLs(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.addJavascriptInterface(new Bridge(),"Trasc");
        web.setWebViewClient(new WebViewClient(){
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();
                if("https".equals(uri.getScheme())&&"app.trasc.local".equals(uri.getHost())){
                    String path=uri.getPath();if(path==null||path.equals("/"))path="/index.html";
                    if(!path.matches("/[a-zA-Z0-9_.-]+"))return blocked();
                    try {String mime=path.endsWith(".js")?"application/javascript":path.endsWith(".css")?"text/css":"text/html";
                        WebResourceResponse response=new WebResourceResponse(mime,"UTF-8",getAssets().open("ui"+path));
                        java.util.Map<String,String> headers=new java.util.HashMap<>();
                        headers.put("Content-Security-Policy","default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'");
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
    private void service(){startForegroundService(new Intent(this,ServerService.class));}
    private void reply(String id,Object result,Exception error){
        try {
            JSONObject json=new JSONObject().put("ok",error==null);
            if(error==null)json.put("result",result);else json.put("error",error.getMessage()==null?error.toString():error.getMessage());
            final String script="window.nativeReply("+JSONObject.quote(id)+","+json+")";
            runOnUiThread(()->{if(!isDestroyed())web.evaluateJavascript(script,null);});
        }catch(Exception ignored){}
    }
    final class Bridge {
        @JavascriptInterface public void call(String id,String operation,String input){
            tasks.execute(()->{
                try {
                    JSONObject args=new JSONObject(input);Object result;
                    if(runtime.sessionBusy&&!operation.equals("native_state")&&!operation.equals("runtime_log")&&!operation.equals("logs")&&!operation.equals("client_native_state"))throw new IOException("A complete session transfer is in progress");
                    switch(operation){
                        case "native_state": result=runtime.nativeState();break;
                        case "client_native_state": result=clientRuntime.state();break;
                        case "client_directx_online": service();result=clientRuntime.installDirectX(null);break;
                        case "client_runtime_online": service();result=clientRuntime.installOnline();break;
                        case "client_start": service();runOnUiThread(()->controller.capture(false));result=clientRuntime.start(args);break;
                        case "client_stop": clientRuntime.stop();if(!runtime.alive()&&!runtime.installing)stopService(new Intent(MainActivity.this,ServerService.class));result=clientRuntime.state();break;
                        case "client_view":
                            if(!clientRuntime.alive()||!clientRuntime.displaySocket().exists())throw new IOException("Launch Wine desktop or ROF2 before opening its display");
                            runOnUiThread(()->startActivity(new Intent(MainActivity.this,ClientActivity.class)));result=new JSONObject();break;
                        case "runtime_install": service();runtime.installOnline();result=runtime.nativeState();break;
                        case "runtime_start": service();runtime.start();result=runtime.nativeState();break;
                        case "runtime_stop": runtime.stop();if(!clientRuntime.alive()&&!clientRuntime.busy)stopService(new Intent(MainActivity.this,ServerService.class));result=runtime.nativeState();break;
                        case "runtime_log": result=runtime.logs("runtime.log");break;
                        case "logs": result=runtime.logs(args.optString("name","control.log"));break;
                        case "export_logs": service();result=runtime.exportLogs();break;
                        case "session_backup": service();runOnUiThread(()->controller.capture(false));result=runtime.backupSession();break;
                        case "controller_state": runOnUiThread(()->{try{reply(id,controller.state(),null);}catch(Exception e){reply(id,null,e);}});return;
                        case "controller_save": runOnUiThread(()->{try{controller.configure(args,true);reply(id,controller.state(),null);}catch(Exception e){reply(id,null,e);}});return;
                        case "controller_capture": runOnUiThread(()->{try{controller.capture(args.optBoolean("active")&&hasWindowFocus());reply(id,controller.state(),null);}catch(Exception e){reply(id,null,e);}});return;
                        case "pick": runOnUiThread(()->pick(id,args.optString("kind","file"),args.optBoolean("replace")));return;
                        case "export": runOnUiThread(()->export(id,args.optString("path")));return;
                        case "import_client_zip": case "prepare_client": case "export_client":
                        case "apply_spell_test": case "restore_spell_test":
                            // Serialize submission with native launch; start also checks queued/running jobs.
                            synchronized(clientRuntime) {
                                if(clientRuntime.alive()||clientRuntime.busy)throw new IOException("Stop the embedded client before changing its files");
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
                    if(operation.startsWith("runtime_"))runtime.status=e.getMessage();
                    if(operation.startsWith("runtime_")||operation.startsWith("client_")||operation.equals("export_logs"))runtime.recordFailure(operation,e);
                    reply(id,null,e);
                }
            });
        }
    }
    private void pick(String id,String kind,boolean replace){
        if(pickerId!=null){reply(id,null,new IOException("Finish the open file picker first"));return;}
        pickerId=id;pickerKind=kind;pickerReplace=replace;
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
        try{startActivityForResult(intent,IMPORT);}catch(Exception e){pickerId=null;reply(id,null,e);}
    }
    private File exportFile(String path)throws IOException {
        File file=TarExtractor.path(runtime.work,path);
        if(!file.isFile() || file.toPath().startsWith(new File(runtime.work,"database").toPath()) || file.toPath().startsWith(new File(runtime.work,"run").toPath()))
            throw new IOException("Export a regular file; use Database backup for database data");
        return file;
    }
    private void export(String id,String path){
        if(pickerId!=null){reply(id,null,new IOException("Finish the open file picker first"));return;}
        try {
            File file=exportFile(path);pickerId=id;exportPath=path;
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE,file.getName());
            startActivityForResult(intent,EXPORT);
        }catch(Exception e){pickerId=null;reply(id,null,e);}
    }
    @Override protected void onActivityResult(int request,int code,Intent data){
        super.onActivityResult(request,code,data);
        if(request!=IMPORT&&request!=EXPORT)return;
        String id=pickerId,kind=pickerKind,path=exportPath;boolean replace=pickerReplace;pickerId=null;
        if(id==null)return;
        if(code!=RESULT_OK||data==null||data.getData()==null){reply(id,null,new IOException("File selection cancelled"));return;}
        Uri uri=data.getData();service();
        tasks.execute(()->{
            File temp=null;
            try {
                if(request==EXPORT){
                    try(InputStream in=new FileInputStream(exportFile(path));OutputStream out=getContentResolver().openOutputStream(uri,"wt")){
                        if(out==null)throw new IOException("Cannot write the selected destination");byte[] b=new byte[1024*1024];int n;while((n=in.read(b))!=-1)out.write(b,0,n);
                    }
                    reply(id,new JSONObject().put("message","File exported"),null);return;
                }
                String name="import.zip";
                try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
                    if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);
                }
                name=name.replaceAll("[^a-zA-Z0-9._-]","_");if(name.length()>160)name=name.substring(name.length()-160);
                String unique=System.currentTimeMillis()+"-"+name;
                temp="session".equals(kind)?new File(getCacheDir(),unique):new File(runtime.work,"incoming/"+unique);
                runtime.status="Copying "+name+"…";
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
            }catch(Exception e){if(temp!=null)temp.delete();runtime.status=e.getMessage();runtime.recordFailure(request==EXPORT?"save_export":"import_"+kind,e);reply(id,null,e);}
        });
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event){return controller!=null&&controller.key(event)||super.dispatchKeyEvent(event);}
    @Override public boolean dispatchGenericMotionEvent(MotionEvent event){return controller!=null&&controller.motion(event)||super.dispatchGenericMotionEvent(event);}
    @Override public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(!focus&&controller!=null)controller.capture(false);}
    @Override protected void onPause(){if(controller!=null)controller.capture(false);super.onPause();}
    @Override public void onBackPressed(){if(controller.active()){controller.capture(false);return;}web.evaluateJavascript("window.appBack && window.appBack()",null);}
    @Override protected void onDestroy(){controller.close();web.removeJavascriptInterface("Trasc");web.destroy();tasks.shutdown();super.onDestroy();}
}
