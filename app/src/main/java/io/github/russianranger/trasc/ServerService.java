package io.github.russianranger.trasc;

import android.app.*;
import android.content.*;
import android.os.*;
import java.util.concurrent.Executors;

public final class ServerService extends Service {
    static final String STOP="io.github.russianranger.trasc.STOP";
    private PowerManager.WakeLock lock;
    @Override public void onCreate(){
        super.onCreate();
        NotificationManager nm=getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("server","Local server",NotificationManager.IMPORTANCE_LOW));
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,ServerService.class).setAction(STOP),PendingIntent.FLAG_IMMUTABLE);
        Notification n=new Notification.Builder(this,"server").setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("TRASC Server Preview").setContentText("Local runtime active · tap to manage")
            .setContentIntent(open).addAction(new Notification.Action.Builder(null,"Shut down",stop).build()).setOngoing(true).build();
        startForeground(1,n);
        lock=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"TRASC:runtime");lock.acquire();
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        if(intent!=null&&STOP.equals(intent.getAction()))Executors.newSingleThreadExecutor().execute(()->{
            try{RuntimeManager.get(this).stop();}catch(Exception e){RuntimeManager.get(this).status=e.getMessage();}
            stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();
        });
        return START_NOT_STICKY;
    }
    @Override public void onDestroy(){if(lock!=null&&lock.isHeld())lock.release();super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
