package io.github.russianranger.trasc;
import java.io.File;
import java.nio.file.Files;
public final class TarHostTest {
    public static void main(String[] args)throws Exception {
        File archive=new File(args[0]),dest=new File(args[1]);dest.mkdirs();
        TarExtractor.extract(archive,dest,n->{});
        if(!new File(dest,"etc/trasc-runtime.json").isFile())throw new AssertionError("Missing runtime marker");
        for(String name:new String[]{"usr/bin/python3.11","usr/sbin/mariadbd","usr/bin/cmake","usr/bin/git","usr/bin/g++"})
            if(!new File(dest,name).isFile())throw new AssertionError("Missing runtime component: "+name);
        if(!Files.isSymbolicLink(new File(dest,"bin").toPath()))throw new AssertionError("Debian /bin symlink not preserved");
        System.out.println("PASS: APK tar parser extracted the real runtime, preserved links and found all required executables");
    }
}
