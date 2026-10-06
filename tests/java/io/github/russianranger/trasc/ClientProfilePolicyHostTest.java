package io.github.russianranger.trasc;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

public final class ClientProfilePolicyHostTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception {
        Map<String,Object> requested=new LinkedHashMap<>();
        requested.put("renderer","turnip");requested.put("presentation_mode","native_surface");
        requested.put("display_fps",60);requested.put("native_dinput8",true);
        requested.put("mouse_warp",true);requested.put("reduce_load_pauses",true);
        requested.put("fast_spell_parse",true);requested.put("particle_mode","repair");
        requested.put("boat_mode","profile");
        for(String mode:new String[]{"client","desktop"}) {
            Map<String,Object> effective=new LinkedHashMap<>(requested);
            effective.putAll(ClientProfilePolicy.overrides("traditional",mode));
            for(String option:new String[]{"native_dinput8","mouse_warp","reduce_load_pauses","fast_spell_parse"})
                check(Boolean.FALSE.equals(effective.get(option)),"Traditional ignores saved Custom hook: "+option);
            check("off".equals(effective.get("particle_mode"))&&"off".equals(effective.get("boat_mode")),"Traditional excludes Custom visual hooks");
            check("turnip".equals(effective.get("renderer"))&&"native_surface".equals(effective.get("presentation_mode"))&&effective.get("display_fps").equals(60),"Traditional retains selected renderer and native display");
        }
        check(Boolean.TRUE.equals(requested.get("native_dinput8")),"Applying a profile never changes caller settings");
        for(String mode:new String[]{"client","desktop","compiler"})
            check(ClientProfilePolicy.overrides("custom",mode).isEmpty(),"Custom launch keeps existing settings");
        try{ClientProfilePolicy.overrides("traditional","compiler");throw new AssertionError("Traditional accepted Custom DLL compilation");}
        catch(IOException expected){check(expected.getMessage().contains("TRASC Custom"),"Compiler error names the correct profile");}
        try{ClientProfilePolicy.overrides("other","client");throw new AssertionError("Unknown profile accepted");}
        catch(IOException expected){}
        System.out.println("PASS: Traditional client/desktop launch, clean hooks, unchanged renderer/display and Custom compiler isolation");
    }
}
