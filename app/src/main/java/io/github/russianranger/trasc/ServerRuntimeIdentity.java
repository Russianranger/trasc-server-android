package io.github.russianranger.trasc;

import java.io.IOException;

/** Keep archive identity separate from the older preparation runtime's presence. */
final class ServerRuntimeIdentity {
    static final String TRADITIONAL_VERSION="traditional-1.0";
    static String release(String profile)throws IOException {
        WorldProfiles.valid(profile);
        return "https://github.com/Russianranger/trasc-server-android/releases/download/"
            +("traditional".equals(profile)?"traditional-runtime-v1/":"runtime-v1/");
    }
    static boolean buildReady(String selected,int format,String architecture,String profile,String runtime,int adapter) {
        if(format!=1||!"arm64".equals(architecture))return false;
        if("traditional".equals(selected))
            return "traditional".equals(profile)&&TRADITIONAL_VERSION.equals(runtime)&&adapter==1;
        return "custom".equals(selected)&&(profile.isEmpty()||"custom".equals(profile))&&!runtime.startsWith("traditional-");
    }
    static void validateInstall(String selected,int format,String architecture,String profile,String runtime,int adapter)throws IOException {
        WorldProfiles.valid(selected);
        if(!buildReady(selected,format,architecture,profile,runtime,adapter))
            throw new IOException("traditional".equals(selected)
                ?"Install the Traditional EQEmu runtime for this profile. The older preparation runtime cannot build this server."
                :"This runtime archive belongs to a different world profile or is unsupported.");
    }
    static void validateSession(String selected,int format,String architecture,String profile,String runtime,int adapter)throws IOException {
        WorldProfiles.valid(selected);
        if(format!=1||!"arm64".equals(architecture))throw new IOException("Unsupported runtime inside session");
        // Existing Traditional sessions used the generic runtime. They may be
        // restored for content management but do not pass buildReady().
        if(profile.isEmpty()&&!runtime.startsWith("traditional-"))return;
        if(!selected.equals(profile))throw new IOException("Session runtime belongs to a different world profile");
        if(!buildReady(selected,format,architecture,profile,runtime,adapter))
            throw new IOException("Unsupported runtime inside session");
    }
}
