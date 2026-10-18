package io.github.russianranger.trasc;

import android.content.ContentResolver;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.file.Files;
import java.util.*;

/** SAF access is URI based, including removable SD and pipe-backed document providers. */
final class SafLonImport {
    private static volatile boolean busy,cancelled;
    private static volatile long files,bytes,total=-1;
    private static volatile String phase="idle",status="Choose a LoN data folder or client ZIP",profile="custom";
    static synchronized void begin(String selected)throws IOException {
        if(busy)throw new IOException("A Legends of Norrath input transfer is already in progress");
        if(!"custom".equals(selected))throw new IOException("Legends of Norrath import belongs to the Triptych Custom profile");
        busy=true;cancelled=false;files=0;bytes=0;total=-1;phase="preparing";status="Preparing LoN input transfer";profile=selected;
    }
    static boolean busy(){return busy;}
    static JSONObject state()throws Exception {return new JSONObject().put("busy",busy).put("cancellable",busy).put("phase",phase).put("files",files).put("bytes",bytes).put("total",total).put("status",status).put("profile",profile);}
    static JSONObject cancel()throws Exception {if(busy){cancelled=true;status="Cancelling LoN input transfer…";}return state();}
    static void finish(){busy=false;}
    private static void check()throws IOException {if(cancelled||Thread.currentThread().isInterrupted())throw new InterruptedIOException("LoN input transfer cancelled");}
    static JSONObject stage(RuntimeManager runtime,ClientRuntime client,ContentResolver resolver,Uri uri,boolean folder)throws Exception {
        File staging=null;boolean maintenance=false,success=false;
        try {
            // The picker lease belongs to this transfer. Drain older bridge operations, then
            // prevent new imports, profile switches, cleanup and native launches from entering.
            runtime.profiles.beginSessionMaintenance();maintenance=true;
            synchronized(client) {synchronized(runtime) {
                if(runtime.sessionBusy||runtime.installing||client.busy||client.alive())throw new IOException("Finish other transfers and stop the embedded client before staging LoN data");
                if(!runtime.alive())throw new IOException("Start the Custom runtime before selecting LoN data");
                JSONObject response=runtime.request("state",new JSONObject());
                if(!response.optBoolean("ok"))throw new IOException(response.optString("error","Cannot inspect current transfers"));
                JSONObject current=response.optJSONObject("result");JSONArray jobs=current==null?null:current.optJSONArray("jobs");
                if(jobs==null)throw new IOException("Cannot inspect current server transfers; refresh the Custom runtime and retry");
                for(int i=0;i<jobs.length();i++){JSONObject job=jobs.optJSONObject(i);if(job==null)throw new IOException("Invalid server transfer status");if(Arrays.asList("queued","running").contains(job.optString("status")))throw new IOException("Finish or cancel the current server operation before selecting LoN data");}
            }}
            check();cleanupInterrupted(runtime.work);staging=LonInputTransfer.stage(runtime.work);
            Files.createFile(new File(staging,".incomplete").toPath());
            Provider provider=new Provider(resolver,uri,folder);LonInputTransfer.Entry selected=folder?provider.root():provider.document();
            LonInputTransfer.Progress progress=new LonInputTransfer.Progress(){
                public void check()throws IOException {SafLonImport.check();}
                public void update(String next,long count,long copied,long expected,String name){phase=next;files=count;bytes=copied;total=expected;status=(next.equals("copying")?"Copying ":next.equals("discovering")?"Finding LoN data: ":"Inspecting ")+name;}
            };
            LonInputTransfer.Result result;
            File source;
            if(folder){LonInputTransfer.Entry data=LonInputTransfer.discover(provider,selected,progress);source=new File(staging,"data");result=LonInputTransfer.directory(provider,data,source,progress);}
            else {source=new File(staging,"source.zip");result=LonInputTransfer.archive(provider,selected,source,progress);}
            check();phase="finalizing";status="Verifying private LoN input receipt";LonInputTransfer.complete(staging,folder);check();
            phase="ready";status="LoN input ready for read-only validation and preview";files=result.files;bytes=result.bytes;total=result.total;success=true;
            String relative="incoming/"+staging.getName()+"/"+source.getName();
            return new JSONObject().put("source",relative).put("path",relative).put("kind",folder?"directory":"zip").put("files",files).put("bytes",bytes).put("name",selected.name).put("message",status);
        } catch(Exception e){phase=e instanceof InterruptedIOException?"cancelled":"failed";status=e.getMessage()==null?"LoN input transfer failed":e.getMessage();throw e;}
        finally {try{if(!success&&staging!=null)LonInputTransfer.remove(staging);}finally{if(maintenance)runtime.profiles.endMaintenance();finish();}}
    }
    private static void cleanupInterrupted(File work)throws IOException {
        File incoming=new File(work,"incoming");
        if(Files.isSymbolicLink(incoming.toPath()))throw new IOException("Invalid incoming staging directory");
        File[] stages=incoming.listFiles(file->file.getName().matches("lon-import-[a-f0-9-]{36}"));
        if(stages==null)return;
        for(File stage:stages){check();if(!Files.isSymbolicLink(stage.toPath())&&Files.isRegularFile(new File(stage,".incomplete").toPath(),java.nio.file.LinkOption.NOFOLLOW_LINKS))LonInputTransfer.remove(stage);}
    }
    private static final class Provider implements LonInputTransfer.Documents {
        private final ContentResolver resolver;private final Uri uri;private final boolean folder;
        Provider(ContentResolver resolver,Uri uri,boolean folder){this.resolver=resolver;this.uri=uri;this.folder=folder;}
        LonInputTransfer.Entry root()throws IOException {
            try{Uri document=DocumentsContract.buildDocumentUriUsingTree(uri,DocumentsContract.getTreeDocumentId(uri));return metadata(document);}
            catch(RuntimeException e){throw new IOException("Cannot open the selected document folder",e);}
        }
        LonInputTransfer.Entry document()throws IOException {
            try(Cursor cursor=resolver.query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null)) {
                if(cursor==null||!cursor.moveToFirst())throw new IOException("Cannot inspect the selected ZIP document");
                String name=cursor.getString(0);if(name==null)name="client.zip";
                return new LonInputTransfer.Entry(uri.toString(),name,false,cursor.isNull(1)?-1:cursor.getLong(1),0);
            }catch(RuntimeException e){throw new IOException("Cannot inspect the selected ZIP document",e);}
        }
        private LonInputTransfer.Entry metadata(Uri document)throws IOException {
            try(Cursor cursor=resolver.query(document,COLUMNS,null,null,null)){if(cursor==null||!cursor.moveToFirst())throw new IOException("Cannot inspect the selected document folder");return entry(cursor);}
            catch(RuntimeException e){throw new IOException("Cannot inspect the selected document folder",e);}
        }
        private static final String[] COLUMNS={DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE,DocumentsContract.Document.COLUMN_SIZE,DocumentsContract.Document.COLUMN_LAST_MODIFIED};
        private LonInputTransfer.Entry entry(Cursor cursor)throws IOException {
            String id=cursor.getString(0),name=cursor.getString(1);if(id==null||name==null)throw new IOException("Document provider omitted a document identity or name");
            return new LonInputTransfer.Entry(id,name,DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2)),cursor.isNull(3)?-1:cursor.getLong(3),cursor.isNull(4)?0:cursor.getLong(4));
        }
        public List<LonInputTransfer.Entry> children(LonInputTransfer.Entry parent)throws IOException {
            check();List<LonInputTransfer.Entry> result=new ArrayList<>();
            try(Cursor cursor=resolver.query(DocumentsContract.buildChildDocumentsUriUsingTree(uri,parent.id),COLUMNS,null,null,null)) {
                if(cursor==null)throw new IOException("Cannot list "+parent.name);
                while(cursor.moveToNext()){check();if(result.size()>=LonInputTransfer.MAX_FILES)throw new IOException("Too many documents in "+parent.name);result.add(entry(cursor));}
                return result;
            }catch(RuntimeException e){throw new IOException("Cannot list "+parent.name,e);}
        }
        public InputStream open(LonInputTransfer.Entry entry)throws IOException {
            check();try{return resolver.openInputStream(folder?DocumentsContract.buildDocumentUriUsingTree(uri,entry.id):uri);}
            catch(RuntimeException e){throw new IOException("Cannot open "+entry.name,e);}
        }
    }
    private SafLonImport(){}
}
