package android.system;
import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermission;
import java.util.EnumSet;
/** Host adapter so the APK's actual tar parser can be exercised on Linux. */
public final class Os {
    public static void chmod(String path,int mode)throws IOException {
        EnumSet<PosixFilePermission> permissions=EnumSet.noneOf(PosixFilePermission.class);
        PosixFilePermission[] flags=PosixFilePermission.values();
        for(int i=0;i<9;i++)if((mode&(1<<(8-i)))!=0)permissions.add(flags[i]);
        Files.setPosixFilePermissions(Path.of(path),permissions);
    }
    public static void symlink(String target,String link)throws IOException {Files.createSymbolicLink(Path.of(link),Path.of(target));}
    public static void link(String source,String target)throws IOException {Files.createLink(Path.of(target),Path.of(source));}
}
