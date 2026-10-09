package io.github.russianranger.trasc;

import java.io.IOException;

/** Archive routing must never install the other profile's toolchain. */
public final class ServerRuntimeIdentityHostTest {
    interface Task {void run()throws Exception;}
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static void rejected(Task task)throws Exception {
        try{task.run();throw new AssertionError("Unsupported runtime accepted");}catch(IOException expected){}
    }
    public static void main(String[] args)throws Exception {
        check(ServerRuntimeIdentity.release("custom").endsWith("/runtime-v1/"),"Custom release is retained");
        check(ServerRuntimeIdentity.release("traditional").endsWith("/traditional-runtime-v1/"),"Traditional release is separate");
        check(ServerRuntimeIdentity.release("takp").endsWith("/traditional-runtime-v1/"),"TAKP reuses the compatible dependency image");
        rejected(()->ServerRuntimeIdentity.release("unknown"));
        ServerRuntimeIdentity.validateInstall("custom",1,"arm64","","1.1",0);
        ServerRuntimeIdentity.validateInstall("traditional",1,"arm64","traditional","traditional-1.0",1);
        ServerRuntimeIdentity.validateInstall("takp",1,"arm64","traditional","traditional-1.0",1);
        check(ServerRuntimeIdentity.reusableTakpImage("takp",1,"arm64","traditional","traditional-1.0",1),"Approved downloaded image can be stamped TAKP");
        check(!ServerRuntimeIdentity.buildReady("takp",1,"arm64","traditional","traditional-1.0",1),"Raw dependency image is not an installed TAKP session");
        ServerRuntimeIdentity.validateInstall("takp",1,"arm64","takp","takp-1.0",1);
        check(ServerRuntimeIdentity.buildReady("takp",1,"arm64","takp","takp-1.0",1),"Installed TAKP identity is build ready");
        rejected(()->ServerRuntimeIdentity.validateInstall("takp",1,"arm64","","1.1",0));
        rejected(()->ServerRuntimeIdentity.validateInstall("takp",1,"arm64","traditional","traditional-1.0",0));
        rejected(()->ServerRuntimeIdentity.validateInstall("takp",1,"amd64","traditional","traditional-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateInstall("takp",1,"arm64","custom","1.1",0));
        rejected(()->ServerRuntimeIdentity.validateInstall("custom",1,"arm64","takp","takp-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateInstall("traditional",1,"arm64","takp","takp-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateInstall("custom",1,"arm64","traditional","traditional-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateInstall("traditional",1,"arm64","","1.1",0));
        rejected(()->ServerRuntimeIdentity.validateInstall("traditional",1,"arm64","traditional","traditional-1.0",0));
        rejected(()->ServerRuntimeIdentity.validateInstall("traditional",1,"amd64","traditional","traditional-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateInstall("traditional",2,"arm64","traditional","traditional-1.0",1));
        // Older profile-marked session ZIPs contain a generic preparation rootfs.
        ServerRuntimeIdentity.validateSession("traditional",1,"arm64","","1.1",0);
        check(!ServerRuntimeIdentity.buildReady("traditional",1,"arm64","","1.1",0),"Preparation restore cannot build");
        ServerRuntimeIdentity.validateSession("custom",1,"arm64","","1.1",0);
        ServerRuntimeIdentity.validateSession("traditional",1,"arm64","traditional","traditional-1.0",1);
        ServerRuntimeIdentity.validateSession("takp",1,"arm64","takp","takp-1.0",1);
        rejected(()->ServerRuntimeIdentity.validateSession("takp",1,"arm64","traditional","traditional-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateSession("takp",1,"arm64","","1.1",0));
        rejected(()->ServerRuntimeIdentity.validateSession("takp",1,"arm64","custom","1.1",0));
        rejected(()->ServerRuntimeIdentity.validateSession("traditional",1,"arm64","takp","takp-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateSession("custom",1,"arm64","takp","takp-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateSession("custom",1,"arm64","","takp-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateSession("traditional",1,"arm64","custom","1.1",0));
        rejected(()->ServerRuntimeIdentity.validateSession("custom",1,"arm64","traditional","traditional-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateSession("custom",1,"arm64","custom","traditional-1.0",1));
        rejected(()->ServerRuntimeIdentity.validateSession("traditional",1,"amd64","","1.1",0));
        System.out.println("Three-world runtime routing, TAKP dependency image reuse, strict session identity and legacy preparation restores passed");
    }
}
