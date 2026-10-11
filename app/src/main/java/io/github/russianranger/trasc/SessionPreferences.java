package io.github.russianranger.trasc;

import java.io.IOException;
import java.util.*;

/** Keep native overlay preferences with work trees omitted from a partial restore. */
final class SessionPreferences {
    static <T> Map<String,T> merge(Map<String,T> archived,Map<String,T> current,Collection<String> preserved)throws IOException {
        if(archived.size()>1000||current.size()>1000)throw new IOException("Too many control preferences");
        List<String> prefixes=new ArrayList<>();for(String id:preserved)prefixes.add(WorldProfiles.valid(id)+".");
        Map<String,T> result=new LinkedHashMap<>();
        for(Map.Entry<String,T> e:archived.entrySet())if(!belongs(e.getKey(),prefixes))result.put(e.getKey(),e.getValue());
        for(Map.Entry<String,T> e:current.entrySet())if(belongs(e.getKey(),prefixes))result.put(e.getKey(),e.getValue());
        if(result.size()>1000)throw new IOException("Too many merged control preferences");return result;
    }
    private static boolean belongs(String key,List<String> prefixes){for(String prefix:prefixes)if(key.startsWith(prefix))return true;return false;}
    private SessionPreferences(){}
}
