package io.github.russianranger.trasc;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.webkit.*;
import org.json.JSONObject;
import java.io.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    private WebView web;
    private RuntimeManager runtime;
    private final ExecutorService tasks=Executors.newFixedThreadPool(3);
    private String pickerId,pickerKind,exportPath;
    private static final int IMPORT=10,EXPORT=11;
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);runtime=RuntimeManager.get(this);
        getWindow().setStatusBarColor(0xff10191c); getWindow().setNavigationBarColor(0xff10191c);
        web=new WebView(this);setContentView(web);
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
                    switch(operation){
                        case "native_state": result=runtime.nativeState();break;
                        case "runtime_install": service();runtime.installOnline();result=runtime.nativeState();break;
                        case "runtime_start": service();runtime.start();result=runtime.nativeState();break;
                        case "runtime_stop": runtime.stop();stopService(new Intent(MainActivity.this,ServerService.class));result=runtime.nativeState();break;
                        case "runtime_log": {
                            File log=new File(runtime.work,"logs/runtime.log");String text="No runtime log yet.";
                            if(log.exists())try(RandomAccessFile f=new RandomAccessFile(log,"r")){f.seek(Math.max(0,f.length()-64000));byte[] b=new byte[(int)(f.length()-f.getFilePointer())];f.readFully(b);text=new String(b,java.nio.charset.StandardCharsets.UTF_8);}
                            result=new JSONObject().put("text",text);break;
                        }
                        case "pick": runOnUiThread(()->pick(id,args.optString("kind","file")));return;
                        case "export": runOnUiThread(()->export(id,args.optString("path")));return;
                        default:
                            JSONObject response=runtime.request(operation,args);
                            if(!response.getBoolean("ok"))throw new IOException(response.optString("error"));
                            result=response.get("result");
                    }
                    reply(id,result,null);
                }catch(Exception e){if(operation.startsWith("runtime_"))runtime.status=e.getMessage();reply(id,null,e);}
            });
        }
    }
    private void pick(String id,String kind){
        if(pickerId!=null){reply(id,null,new IOException("Finish the open file picker first"));return;}
        pickerId=id;pickerKind=kind;
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
        String id=pickerId,kind=pickerKind,path=exportPath;pickerId=null;
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
                temp=new File(runtime.work,"incoming/"+unique);
                runtime.status="Copying "+name+"…";
                try(InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new IOException("Cannot read file");RuntimeManager.copy(in,temp);}
                if("runtime".equals(kind)){
                    runtime.beginInstall();try{runtime.installArchive(temp);}finally{runtime.installing=false;temp.delete();}
                    reply(id,runtime.nativeState(),null);
                }else {runtime.status="File imported: "+name;reply(id,new JSONObject().put("file",unique).put("path","incoming/"+unique).put("name",name),null);}
            }catch(Exception e){if(temp!=null)temp.delete();runtime.status=e.getMessage();reply(id,null,e);}
        });
    }
    @Override public void onBackPressed(){web.evaluateJavascript("window.appBack && window.appBack()",null);}
    @Override protected void onDestroy(){web.removeJavascriptInterface("Trasc");web.destroy();tasks.shutdown();super.onDestroy();}
}
