package io.github.russianranger.trasc;

import android.app.*;
import android.graphics.*;
import android.net.*;
import android.os.*;
import android.view.*;
import android.widget.*;
import org.json.JSONObject;
import java.io.*;
import java.util.concurrent.*;

/** The embedded Wine display. Android Back returns to management without killing the server. */
public final class ClientActivity extends Activity {
    private ClientRuntime runtime;
    private ControllerManager controller;
    private ClientView display;
    private TextView status;
    private String displayError;
    private boolean failureShown;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable refresh=new Runnable(){@Override public void run(){
        try {
            JSONObject state=runtime.state(),launch=state.optJSONObject("launch");
            String phase=launch==null?runtime.status:launch.optString("phase").replace('_',' ');
            if(!runtime.alive())phase="Client stopped · return to Client tab to launch again";
            if(launch!=null&&launch.has("error"))phase=launch.optString("error");
            if(displayError!=null&&(launch==null||!launch.has("error")))phase=displayError;
            status.setText(phase+(launch!=null&&launch.optBoolean("native_loaded")?" · native dinput8 loaded":"")+
                (launch!=null&&launch.optBoolean("system_dinput8_loaded")?" · system DirectInput loaded":"")+display.measure(launch));
            if(launch!=null&&launch.has("error")&&!failureShown&&hasWindowFocus()&&!isFinishing()) {
                failureShown=true;controller.capture(false);display.input.releaseAll();
                new AlertDialog.Builder(ClientActivity.this).setTitle("Client startup failed").setMessage(launch.optString("error"))
                    .setPositiveButton("Back to Client",(dialog,which)->finish()).setCancelable(false).show();
            }
        }catch(Exception e){status.setText(e.getMessage());}
        handler.postDelayed(this,1000);
    }};
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);runtime=ClientRuntime.get(this);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(0xff10191c);getWindow().setNavigationBarColor(0xff10191c);
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setBackgroundColor(0xff10191c);
        LinearLayout bar=new LinearLayout(this);bar.setPadding(8,0,8,0);bar.setGravity(Gravity.CENTER_VERTICAL);
        Button back=new Button(this);back.setText("Back");back.setOnClickListener(v->finish());bar.addView(back);
        status=new TextView(this);status.setTextColor(0xffe2eded);status.setTextSize(12);bar.addView(status,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        Button keyboard=new Button(this);keyboard.setText("Keyboard");keyboard.setOnClickListener(v->textDialog());bar.addView(keyboard);
        Button escape=new Button(this);escape.setText("Esc");escape.setOnClickListener(v->{display.input.key("escape",0xff1b,true);display.input.key("escape",0xff1b,false);});bar.addView(escape);
        layout.addView(bar);display=new ClientView();layout.addView(display,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,1));setContentView(layout);
        controller=new ControllerManager(this,runtime.server.work,event->{
            switch(event.optString("type")) {
                case "button":display.input.action(event.optString("action"),event.optBoolean("down"));break;
                case "pointer":display.input.move((float)event.optDouble("x"),(float)event.optDouble("y"));break;
                case "wheel":display.input.wheel(event.optInt("y"));break;
            }
        });
        display.connect();handler.post(refresh);
    }
    private void textDialog() {
        controller.capture(false);display.input.releaseAll();
        EditText text=new EditText(this);text.setSingleLine(true);text.setHint("Type into the focused client field");
        text.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(4096)});
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Client keyboard").setView(text)
            .setPositiveButton("Type",(d,w)->display.input.text(text.getText().toString(),false))
            .setNeutralButton("Send + Enter",(d,w)->display.input.text(text.getText().toString(),true))
            .setNegativeButton("Cancel",null).create();
        dialog.setOnDismissListener(d->{if(hasWindowFocus())controller.capture(true);});dialog.show();
        text.requestFocus();dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        if(controller!=null&&controller.key(event))return true;
        if(display!=null&&hasWindowFocus()&&event.getKeyCode()!=KeyEvent.KEYCODE_BACK&&
                (event.getSource()&InputDevice.SOURCE_KEYBOARD)==InputDevice.SOURCE_KEYBOARD) {
            int symbol=physicalSymbol(event);
            if(symbol!=0&&(event.getAction()==KeyEvent.ACTION_DOWN||event.getAction()==KeyEvent.ACTION_UP)) {
                display.input.key("physical:"+event.getKeyCode(),symbol,event.getAction()==KeyEvent.ACTION_DOWN);return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }
    static int physicalSymbol(KeyEvent event) {
        switch(event.getKeyCode()) {
            case KeyEvent.KEYCODE_ENTER:return 0xff0d;case KeyEvent.KEYCODE_ESCAPE:return 0xff1b;case KeyEvent.KEYCODE_TAB:return 0xff09;case KeyEvent.KEYCODE_DEL:return 0xff08;
            case KeyEvent.KEYCODE_DPAD_LEFT:return 0xff51;case KeyEvent.KEYCODE_DPAD_UP:return 0xff52;case KeyEvent.KEYCODE_DPAD_RIGHT:return 0xff53;case KeyEvent.KEYCODE_DPAD_DOWN:return 0xff54;
            case KeyEvent.KEYCODE_SHIFT_LEFT:return 0xffe1;case KeyEvent.KEYCODE_SHIFT_RIGHT:return 0xffe2;case KeyEvent.KEYCODE_CTRL_LEFT:return 0xffe3;case KeyEvent.KEYCODE_CTRL_RIGHT:return 0xffe4;
            case KeyEvent.KEYCODE_ALT_LEFT:return 0xffe9;case KeyEvent.KEYCODE_ALT_RIGHT:return 0xffea;
            case KeyEvent.KEYCODE_MOVE_HOME:return 0xff50;case KeyEvent.KEYCODE_MOVE_END:return 0xff57;case KeyEvent.KEYCODE_PAGE_UP:return 0xff55;case KeyEvent.KEYCODE_PAGE_DOWN:return 0xff56;case KeyEvent.KEYCODE_INSERT:return 0xff63;case KeyEvent.KEYCODE_FORWARD_DEL:return 0xffff;
        }
        if(event.getKeyCode()>=KeyEvent.KEYCODE_F1&&event.getKeyCode()<=KeyEvent.KEYCODE_F12)return 0xffbe+event.getKeyCode()-KeyEvent.KEYCODE_F1;
        // Ignore Ctrl/Alt when resolving the symbol; modifiers are sent separately.
        int code=event.getUnicodeChar(event.getMetaState()&(KeyEvent.META_SHIFT_ON|KeyEvent.META_CAPS_LOCK_ON));
        return code<=255?code:code<=0x10ffff?0x01000000|code:0;
    }
    @Override public boolean dispatchGenericMotionEvent(MotionEvent event){return controller!=null&&controller.motion(event)||super.dispatchGenericMotionEvent(event);}
    @Override public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(controller!=null)controller.capture(focus);if(!focus&&display!=null)display.input.releaseAll();}
    @Override protected void onPause(){if(controller!=null)controller.capture(false);if(display!=null)display.input.releaseAll();super.onPause();}
    @Override protected void onDestroy(){handler.removeCallbacks(refresh);if(controller!=null)controller.close();if(display!=null)display.close();super.onDestroy();}

    private final class ClientView extends View implements RfbConnection.Screen {
        private final Object pixelsLock=new Object();
        private Bitmap bitmap;
        private int[] copyBuffer=new int[0];
        private long measuredAt=System.nanoTime();
        private double displayRate;
        private final Paint paint=new Paint(Paint.FILTER_BITMAP_FLAG);
        private final RectF bounds=new RectF();
        private final ExecutorService writer=Executors.newSingleThreadExecutor();
        private volatile LocalSocket socket;
        private volatile RfbConnection connection;
        private volatile boolean closed;
        final DisplayInput input=new DisplayInput(new DisplayInput.Sink(){
            public void key(int sym,boolean down){send(r->r.key(sym,down));}
            public void pointer(int x,int y,int buttons){send(r->r.pointer(x,y,buttons));}
        });
        interface Send {void write(RfbConnection connection)throws IOException;}
        ClientView(){super(ClientActivity.this);setFocusable(true);setFocusableInTouchMode(true);}
        void send(Send send){if(!closed)writer.execute(()->{try{RfbConnection r=connection;if(r!=null)send.write(r);}catch(IOException e){failure(e);}});}
        void connect(){new Thread(()->{
            try {
                LocalSocket local=new LocalSocket();socket=local;
                if(closed)return;
                local.connect(new LocalSocketAddress(runtime.displaySocket().getPath(),LocalSocketAddress.Namespace.FILESYSTEM));
                local.setSoTimeout(15000);
                RfbConnection r=new RfbConnection(local.getInputStream(),local.getOutputStream(),this);r.handshake();
                local.setSoTimeout(0);connection=r;
                while(!closed)r.readUpdate();
            }catch(IOException e){if(!closed)failure(e);}
            finally {try{if(socket!=null)socket.close();}catch(IOException ignored){}connection=null;}
        },"TRASC client display").start();}
        void failure(Exception error){if(closed)return;runtime.server.recordFailure("client_display",error);post(()->{displayError="Display disconnected: "+error.getMessage()+" · Back to Client to reconnect";if(!isDestroyed())status.setText(displayError);});}
        @Override public void resize(int w,int h){synchronized(pixelsLock){bitmap=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);}post(()->input.size(w,h));}
        @Override public void pixels(int x,int y,int w,int h,int[] colors){synchronized(pixelsLock){bitmap.setPixels(colors,0,w,x,y,w,h);}}
        @Override public void copy(int x,int y,int w,int h,int sx,int sy){synchronized(pixelsLock){if(copyBuffer.length<w*h)copyBuffer=new int[w*h];bitmap.getPixels(copyBuffer,0,w,sx,sy,w,h);bitmap.setPixels(copyBuffer,0,w,x,y,w,h);}}
        @Override public void updated(){postInvalidateOnAnimation();}
        @Override protected void onDraw(Canvas canvas) {
            long started=System.nanoTime();
            canvas.drawColor(Color.BLACK);
            synchronized(pixelsLock){if(bitmap!=null){float scale=Math.min((float)getWidth()/bitmap.getWidth(),(float)getHeight()/bitmap.getHeight());float w=bitmap.getWidth()*scale,h=bitmap.getHeight()*scale;bounds.set((getWidth()-w)/2,(getHeight()-h)/2,(getWidth()+w)/2,(getHeight()+h)/2);canvas.drawBitmap(bitmap,null,bounds,paint);}}
            RfbConnection r=connection;if(r!=null)r.stats.drawn(System.nanoTime()-started);
        }
        String measure(JSONObject launch) {
            RfbConnection r=connection;if(r==null||closed)return "";
            JSONObject wine=launch==null?null:launch.optJSONObject("wine_present");
            boolean fresh=wine!=null&&System.currentTimeMillis()/1000.0-wine.optDouble("sampled_at",0)<5;
            long now=System.nanoTime();
            if(now-measuredAt>=TimeUnit.SECONDS.toNanos(5)) {
                measuredAt=now;double[] sample=r.stats.sample(now);
                if(sample!=null)try {
                    displayRate=sample[2];
                    JSONObject info=new JSONObject().put("created_utc",java.time.Instant.now().toString());
                    String[] keys={"window_seconds","rfb_updates_per_second","new_bitmap_draws_per_second","receive_ms_per_update","decode_apply_ms_per_update","canvas_submit_ms_per_draw","raw_pixels_per_second","last_update_age_seconds"};
                    for(int i=0;i<keys.length;i++)info.put(keys[i],sample[i]);
                    if(fresh)info.put("wine_present",wine);
                    if(launch!=null)info.put("graphics_threading",launch.optString("graphics_threading_observed","unknown"))
                        .put("graphics_threading_requested",launch.optString("graphics_threading","multi"))
                        .put("mesa_glthread_observed",launch.optBoolean("mesa_glthread_observed",false));
                    String line=info.toString()+"\n";
                    writer.execute(()->{
                        try {
                            File log=new File(runtime.server.work,"logs/client-presentation.log");
                            if(log.length()>1024*1024)java.nio.file.Files.move(log.toPath(),new File(log.getParentFile(),"client-presentation.overflow.log").toPath(),java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                            try(FileOutputStream out=new FileOutputStream(log,true)){out.write(line.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
                        }catch(IOException error){android.util.Log.w("TRASC","Could not record display measurements",error);}
                    });
                }catch(org.json.JSONException ignored){}
            }
            return String.format(java.util.Locale.ROOT," · Wine %s/s · Display %.1f/s",fresh?String.format(java.util.Locale.ROOT,"%.1f",wine.optDouble("per_second")):"—",displayRate);
        }
        private boolean position(MotionEvent event) {
            if(bitmap==null||bounds.width()==0||!bounds.contains(event.getX(),event.getY()))return false;
            input.position((event.getX()-bounds.left)*bitmap.getWidth()/bounds.width(),(event.getY()-bounds.top)*bitmap.getHeight()/bounds.height());return true;
        }
        @Override public boolean onTouchEvent(MotionEvent event) {
            boolean mouse=event.isFromSource(InputDevice.SOURCE_MOUSE);
            if(event.getActionMasked()==MotionEvent.ACTION_CANCEL){input.releaseAll();return true;}
            if(event.getActionMasked()==MotionEvent.ACTION_UP){input.mouse("touch",1,false);if(mouse)mouseButtons(event);performClick();return true;}
            if(!position(event))return true;
            if(mouse)mouseButtons(event);else if(event.getActionMasked()==MotionEvent.ACTION_DOWN){requestFocus();input.mouse("touch",1,true);}
            return true;
        }
        private void mouseButtons(MotionEvent event){int mask=event.getButtonState();input.mouse("mouse-left",1,(mask&MotionEvent.BUTTON_PRIMARY)!=0);input.mouse("mouse-right",4,(mask&MotionEvent.BUTTON_SECONDARY)!=0);input.mouse("mouse-middle",2,(mask&MotionEvent.BUTTON_TERTIARY)!=0);}
        @Override public boolean onGenericMotionEvent(MotionEvent event) {
            if(event.isFromSource(InputDevice.SOURCE_MOUSE)){position(event);mouseButtons(event);if(event.getAction()==MotionEvent.ACTION_SCROLL)input.wheel(Math.round(event.getAxisValue(MotionEvent.AXIS_VSCROLL)));return true;}
            return super.onGenericMotionEvent(event);
        }
        @Override public boolean performClick(){super.performClick();return true;}
        private void closeSocket(){try{if(socket!=null)socket.close();}catch(IOException ignored){}}
        void close(){input.releaseAll();closed=true;writer.execute(this::closeSocket);writer.shutdown();handler.postDelayed(this::closeSocket,250);}
    }
}
