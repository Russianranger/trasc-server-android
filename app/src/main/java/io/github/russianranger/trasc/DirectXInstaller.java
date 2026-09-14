package io.github.russianranger.trasc;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Extract only the two ROF2 model helpers from a pinned Microsoft redistributable. */
final class DirectXInstaller {
    static final String URL="https://download.microsoft.com/download/8/4/A/84A35BF1-DAFE-4AE8-82AF-AD2AE20B6B14/directx_Jun2010_redist.exe";
    static final String SHA256="053f76dcbb28802e23341b6a787e3b0791c0fa5c8d4d011b1044172dbf89c73b";
    static final long BYTES=100275120;
    static final String[] DLLS={"d3dx9_30.dll","d3dx9_35.dll"};

    static boolean installed(File target) {
        if(!new File(target,"directx.json").isFile())return false;
        for(String name:DLLS)if(!Files.isRegularFile(new File(target,name).toPath(),LinkOption.NOFOLLOW_LINKS))return false;
        return true;
    }
    static String sha256(File file)throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        try(InputStream in=new FileInputStream(file)) {byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)md.update(b,0,n);}
        StringBuilder s=new StringBuilder();for(byte b:md.digest())s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();
    }
    static void verifyPe32(File file)throws IOException {
        if(!Files.isRegularFile(file.toPath(),LinkOption.NOFOLLOW_LINKS)||file.length()<128||file.length()>16*1024*1024)
            throw new IOException("Invalid DirectX library: "+file.getName());
        try(RandomAccessFile in=new RandomAccessFile(file,"r")) {
            if(in.readUnsignedByte()!='M'||in.readUnsignedByte()!='Z')throw new IOException("Missing Windows header: "+file.getName());
            in.seek(0x3c);long offset=Integer.toUnsignedLong(Integer.reverseBytes(in.readInt()));
            if(offset<64||offset>file.length()-6)throw new IOException("Invalid Windows header offset");
            in.seek(offset);
            if(in.readInt()!=0x50450000||in.readUnsignedByte()!=0x4c||in.readUnsignedByte()!=0x01)
                throw new IOException("DirectX library must be 32-bit x86: "+file.getName());
        }
    }
    static void run(File extractor,File archive,File directory,String filter,File log)throws Exception {
        Process process=new ProcessBuilder(extractor.getAbsolutePath(),"-q","-L","-F",filter,"-d",directory.getAbsolutePath(),archive.getAbsolutePath())
            .redirectErrorStream(true).redirectOutput(ProcessBuilder.Redirect.appendTo(log)).start();
        try {
            if(!process.waitFor(60,TimeUnit.SECONDS))throw new IOException("DirectX extraction timed out; export Logs");
            if(process.exitValue()!=0)throw new IOException("DirectX extraction failed; see client-directx.log");
        } finally {if(process.isAlive()){process.destroyForcibly();process.waitFor(5,TimeUnit.SECONDS);}}
    }
    static void recover(File target)throws IOException {
        File previous=new File(target.getParentFile(),"directx-previous");
        if(!target.exists()&&previous.exists())Files.move(previous.toPath(),target.toPath());
    }
    static void install(File archive,File target,File extractor,File log)throws Exception {
        // Check before invoking an extractor or altering an existing installation.
        if(!Files.isRegularFile(archive.toPath(),LinkOption.NOFOLLOW_LINKS)||archive.length()!=BYTES||!sha256(archive).equals(SHA256))
            throw new IOException("Choose the matching Microsoft June 2010 DirectX redistributable (directx_Jun2010_redist.exe); checksum did not match");
        if(!extractor.canExecute())throw new IOException("This APK is missing its DirectX archive helper");
        Files.createDirectories(target.getParentFile().toPath());log.getParentFile().mkdirs();recover(target);
        Path stage=Files.createTempDirectory(target.getParentFile().toPath(),"directx-install-");
        File cabs=stage.resolve("cabs").toFile(),ready=stage.resolve("ready").toFile();
        cabs.mkdirs();ready.mkdirs();
        try {
            StringBuilder manifest=new StringBuilder("{\"format\":1,\"source_sha256\":\""+SHA256+"\",\"files\":{");
            for(int i=0;i<DLLS.length;i++) {
                String name=DLLS[i],stem=name.substring(0,name.length()-4);
                run(extractor,archive,cabs,"*"+stem+"*x86*",log);
                File[] matches=cabs.listFiles((dir,entry)->entry.contains(stem)&&entry.contains("x86")&&entry.endsWith(".cab"));
                if(matches==null||matches.length!=1)throw new IOException("Missing or ambiguous cabinet for "+name);
                run(extractor,matches[0],ready,name,log);
                File dll=new File(ready,name);verifyPe32(dll);
                if(i>0)manifest.append(',');
                manifest.append('"').append(name).append("\":{\"sha256\":\"").append(sha256(dll)).append("\",\"bytes\":").append(dll.length()).append('}');
            }
            manifest.append("}}\n");
            Files.write(new File(ready,"directx.json").toPath(),manifest.toString().getBytes(StandardCharsets.UTF_8));
            File previous=new File(target.getParentFile(),"directx-previous");
            TarExtractor.remove(previous);
            if(target.exists())Files.move(target.toPath(),previous.toPath());
            try {Files.move(ready.toPath(),target.toPath());}
            catch(IOException error){recover(target);throw error;}
            try(PrintWriter out=new PrintWriter(new FileOutputStream(log,true))) {
                out.println("Installed verified Microsoft x86 d3dx9_30.dll and d3dx9_35.dll. Imported client and existing Wine prefix retained.");
                out.println(manifest);
            }
        } finally {TarExtractor.remove(stage.toFile());}
    }
}
