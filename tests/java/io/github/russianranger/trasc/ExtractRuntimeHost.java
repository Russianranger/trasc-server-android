package io.github.russianranger.trasc;

import java.io.File;

/** Install the real archive with the Android extractor before the PRoot launch test. */
public final class ExtractRuntimeHost {
    public static void main(String[] args)throws Exception {
        File root=new File(args[1]);root.mkdirs();
        TarExtractor.extract(new File(args[0]),root,n->{});
    }
}
