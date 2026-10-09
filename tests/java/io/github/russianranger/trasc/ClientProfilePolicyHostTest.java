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
            for(String option:new String[]{"native_dinput8","reduce_load_pauses","fast_spell_parse"})
                check(Boolean.FALSE.equals(effective.get(option)),"Traditional ignores saved Custom hook: "+option);
            check(effective.get("mouse_warp").equals("client".equals(mode)),"Camera-only recentering is optional for Traditional game and disabled on desktop");
            check("off".equals(effective.get("particle_mode"))&&"off".equals(effective.get("boat_mode")),"Traditional excludes Custom visual hooks");
            check("turnip".equals(effective.get("renderer"))&&"native_surface".equals(effective.get("presentation_mode"))&&effective.get("display_fps").equals(60),"Traditional retains selected renderer and native display");
        }
        check(Boolean.TRUE.equals(requested.get("native_dinput8")),"Applying a profile never changes caller settings");
        check(!ClientProfilePolicy.overrides("traditional","client").containsKey("mouse_warp"),"Traditional does not enable camera without the user's opt-in");
        for(String mode:new String[]{"client","desktop"}) {
            Map<String,Object> effective=new LinkedHashMap<>(requested);
            effective.put("name_sky_compatibility",true);effective.put("native_d3dx",true);
            effective.putAll(ClientProfilePolicy.overrides("takp",mode));
            for(String option:new String[]{"native_dinput8","mouse_warp","reduce_load_pauses","fast_spell_parse","name_sky_compatibility","native_d3dx"})
                check(Boolean.FALSE.equals(effective.get(option)),"TAKP rejects RoF2 hook: "+option);
            check("off".equals(effective.get("particle_mode"))&&"off".equals(effective.get("boat_mode")),"TAKP excludes RoF2 visual hooks");
            check("standard".equals(effective.get("npc_rendering")),"TAKP uses independent shader policy");
            check("turnip".equals(effective.get("renderer"))&&"native_surface".equals(effective.get("presentation_mode")),"TAKP retains selected graphics and presentation");
        }
        try{ClientProfilePolicy.overrides("takp","compiler");throw new AssertionError("TAKP accepted RoF2 compiler");}
        catch(IOException expected){}
        for(String mode:new String[]{"client","desktop","compiler"})
            check(ClientProfilePolicy.overrides("custom",mode).isEmpty(),"Custom launch keeps existing settings");
        try{ClientProfilePolicy.overrides("traditional","compiler");throw new AssertionError("Traditional accepted Custom DLL compilation");}
        catch(IOException expected){check(expected.getMessage().contains("TRASC Custom"),"Compiler error names the correct profile");}
        try{ClientProfilePolicy.overrides("other","client");throw new AssertionError("Unknown profile accepted");}
        catch(IOException expected){}
        System.out.println("PASS: Traditional/TAKP client policy, clean hooks, retained graphics/display and Custom compiler isolation");
    }
}
