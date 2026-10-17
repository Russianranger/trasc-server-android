package io.github.russianranger.trasc;

import java.io.*;
import java.nio.file.*;
import java.util.concurrent.*;

/** Exercise the production gate at the picker-to-transfer handoff. */
public final class SessionGateHostTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static void rejected(WorldProfiles profiles)throws Exception {
        try(WorldProfiles.Lease ignored=profiles.enter("custom")){throw new AssertionError("Request entered the reserved session");}
        catch(IOException expected){}
    }
    static void awaitReservation(WorldProfiles profiles)throws Exception {
        long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(2);
        while(System.nanoTime()<until) {
            try(WorldProfiles.Lease ignored=profiles.enter("custom")){}
            catch(IOException reserved){return;}
            Thread.yield();
        }
        throw new AssertionError("Session did not reserve profile admission");
    }
    public static void main(String[] args)throws Exception {
        Path base=Files.createTempDirectory("trasc-session-gate-");
        ExecutorService executor=Executors.newSingleThreadExecutor();
        try {
            WorldProfiles profiles=new WorldProfiles(base.toFile());
            // SAF callback owns the picker lease. onResume and a poll already own others.
            try(WorldProfiles.Lease picker=profiles.enter("custom")) {
                WorldProfiles.Lease resumed=profiles.enter("custom"),poll=profiles.enter("custom");
                Future<?> handoff=executor.submit(()->{profiles.beginSessionMaintenance();return null;});
                awaitReservation(profiles);check(!handoff.isDone(),"Must wait for admitted launcher requests");
                resumed.close();check(!handoff.isDone(),"Poll still owns its lease");poll.close();
                handoff.get(2,TimeUnit.SECONDS);rejected(profiles);
                try {profiles.beginSwitch("custom");throw new AssertionError("Switched during backup");}catch(IOException expected){}
                // Provider failure/cancellation must release maintenance and then the transfer lease.
                profiles.endMaintenance();
            }
            try(WorldProfiles.Lease retry=profiles.enter("custom")) {
                profiles.beginSessionMaintenance();profiles.endMaintenance();
            }
            // A genuinely active transfer/picker must not be forcibly unlocked on timeout.
            try(WorldProfiles.Lease picker=profiles.enter("custom");WorldProfiles.Lease transfer=profiles.enter("custom")) {
                Future<?> timeout=executor.submit(()->{try{profiles.beginSessionMaintenance();throw new AssertionError("Overlapping transfer accepted");}catch(IOException expected){check(!expected.getMessage().contains("storage cleanup"),"Session-specific error");}return null;});
                timeout.get(7,TimeUnit.SECONDS);
                try(WorldProfiles.Lease stillUsable=profiles.enter("custom")){check(stillUsable!=null,"Timeout releases pending reservation");}
                transfer.close();profiles.beginSessionMaintenance();rejected(profiles);profiles.endMaintenance();
            }
            // An interrupted handoff releases its reservation and preserves the interrupt flag.
            try(WorldProfiles.Lease picker=profiles.enter("custom");WorldProfiles.Lease poll=profiles.enter("custom")) {
                CountDownLatch finished=new CountDownLatch(1);
                java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
                Thread interrupted=new Thread(()->{try{profiles.beginSessionMaintenance();failure.set(new AssertionError("Interrupted handoff succeeded"));}
                    catch(InterruptedIOException expected){if(!Thread.currentThread().isInterrupted())failure.set(new AssertionError("Interrupt flag lost"));}
                    catch(Throwable e){failure.set(e);}finally{finished.countDown();}});
                interrupted.start();awaitReservation(profiles);interrupted.interrupt();
                check(finished.await(2,TimeUnit.SECONDS),"Interrupted handoff did not release");if(failure.get()!=null)throw new AssertionError(failure.get());
                poll.close();profiles.beginSessionMaintenance();profiles.endMaintenance();
            }
            // Failed acquisition must never clear another owner's maintenance reservation.
            try(WorldProfiles.Lease picker=profiles.enter("custom")) {
                profiles.beginSessionMaintenance();
                try{profiles.beginSessionMaintenance();throw new AssertionError("Second session entered");}catch(IOException expected){}
                rejected(profiles);profiles.endMaintenance();
            }
            profiles.beginSwitch("custom");profiles.endSwitch();
            System.out.println("SAF session handoff drains refreshes; overlapping transfers, timeout, interruption and retry guards passed");
        } finally {executor.shutdownNow();TarExtractor.remove(base.toFile());}
    }
}
