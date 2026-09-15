package io.github.russianranger.trasc;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class ProotAccelerationHostTest {
    public static void main(String[] args)throws Exception {
        File log=Files.createTempFile("trasc-preflight-",".log").toFile();
        Map<String,String> env=new HashMap<>(System.getenv());env.put("PROOT_NO_SECCOMP","0");
        ProotAcceleration.configure(env,true);
        if(env.containsKey("PROOT_NO_SECCOMP"))throw new AssertionError("Presence disables acceleration even with value 0");
        String success="printf '%s\\n' '"+ProotAcceleration.OBSERVED+"' 'TRASC runtime probe passed'";
        if(!ProotAcceleration.preflight(Arrays.asList("/bin/sh","-c",success),env,log,2000))throw new AssertionError("Verified mode rejected");
        if(ProotAcceleration.preflight(Arrays.asList("/bin/sh","-c",success+"; exit 23"),env,log,2000))throw new AssertionError("Failed probe accepted");
        if(ProotAcceleration.preflight(Arrays.asList("/bin/sh","-c","echo 'TRASC runtime probe passed'"),env,log,2000))throw new AssertionError("Unobserved accelerator accepted");
        try {ProotAcceleration.preflight(Arrays.asList("/bin/sleep","2"),env,log,10);throw new AssertionError("Timeout ignored");}
        catch(IOException expected) {if(!expected.getMessage().contains("timed out"))throw expected;}
        ProotAcceleration.configure(env,false);
        if(!"1".equals(env.get("PROOT_NO_SECCOMP")))throw new AssertionError("Compatibility mode changed");
        Files.delete(log.toPath());
        System.out.println("PASS: runtime preflight requires exit success and accelerator evidence; failed/unsupported mode falls back; timeout aborts cleanly");
    }
}
