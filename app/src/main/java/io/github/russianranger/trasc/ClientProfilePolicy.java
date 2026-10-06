package io.github.russianranger.trasc;

import java.io.IOException;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** Keep a clean Traditional client independent of Custom's executable hooks. */
final class ClientProfilePolicy {
    static Map<String,Object> overrides(String profile,String mode)throws IOException {
        if("custom".equals(profile))return Collections.emptyMap();
        if(!"traditional".equals(profile))throw new IOException("Unknown world profile");
        if("compiler".equals(mode))
            throw new IOException("The custom client DLL compiler belongs to TRASC Custom. Import a clean ROF2 client for Traditional EQEmu.");
        Map<String,Object> options=new LinkedHashMap<>();
        for(String name:new String[]{"native_dinput8","mouse_warp","reduce_load_pauses","fast_spell_parse"})
            options.put(name,false);
        options.put("particle_mode","off");options.put("boat_mode","off");
        return Collections.unmodifiableMap(options);
    }
}
