package io.github.russianranger.trasc;

import java.io.IOException;

/** Dependency image identity is distinct from the world owning its installed copy. */
final class ServerRuntimeIdentity {
    static final String TRADITIONAL_VERSION="traditional-1.0";
    static final String TAKP_VERSION="takp-1.0";
    static String release(String profile)throws IOException {
        WorldProfiles.valid(profile);
        return "https://github.com/Russianranger/trasc-server-android/releases/download/"
            +("custom".equals(profile)?"runtime-v1/":"traditional-runtime-v1/");
    }
    static boolean buildReady(String selected,int format,String architecture,String profile,String runtime,int adapter) {
        if(format!=1||!"arm64".equals(architecture))return false;
        if("traditional".equals(selected))
            return "traditional".equals(profile)&&TRADITIONAL_VERSION.equals(runtime)&&adapter==1;
        if("takp".equals(selected))
            return "takp".equals(profile)&&TAKP_VERSION.equals(runtime)&&adapter==1;
        return "custom".equals(selected)&&(profile.isEmpty()||"custom".equals(profile))
            &&!runtime.startsWith("traditional-")&&!runtime.startsWith("takp-");
    }
    static boolean reusableTakpImage(String selected,int format,String architecture,String profile,String runtime,int adapter) {
        return "takp".equals(selected)&&buildReady("traditional",format,architecture,profile,runtime,adapter);
    }
    static void validateInstall(String selected,int format,String architecture,String profile,String runtime,int adapter)throws IOException {
        WorldProfiles.valid(selected);
        // TAKP uses a separate copy of the proven Debian toolchain image. Only
        // installation may accept that source marker; installed/session markers
        // are stamped TAKP by RuntimeManager before activating the rootfs.
        if(!buildReady(selected,format,architecture,profile,runtime,adapter)
                &&!reusableTakpImage(selected,format,architecture,profile,runtime,adapter))
            throw new IOException("traditional".equals(selected)
                ?"Install the Traditional EQEmu runtime for this profile. The older preparation runtime cannot build this server."
                :"takp".equals(selected)?"Install the TAKP-compatible Traditional ARM64 runtime image for this profile."
                :"This runtime archive belongs to a different world profile or is unsupported.");
    }
    static void validateSession(String selected,int format,String architecture,String profile,String runtime,int adapter)throws IOException {
        WorldProfiles.valid(selected);
        if(format!=1||!"arm64".equals(architecture))throw new IOException("Unsupported runtime inside session");
        // Existing Traditional sessions used the generic runtime. They may be
        // restored for content management but do not pass buildReady().
        if(!"takp".equals(selected)&&profile.isEmpty()&&!runtime.startsWith("traditional-")&&!runtime.startsWith("takp-"))return;
        if(!selected.equals(profile))throw new IOException("Session runtime belongs to a different world profile");
        if(!buildReady(selected,format,architecture,profile,runtime,adapter))
            throw new IOException("Unsupported runtime inside session");
    }
}
