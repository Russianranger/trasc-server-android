"""Execute ClientRuntime's real state method against small Android-free dependencies.

The JSON and graphics doubles only implement dependencies of that method. The
state method and its filesystem/profile helpers come directly from production
source, and profile reads use the real WorldProfiles request lease. Browser
regressions consume these same executed snapshots through ``--fixtures``.
"""
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'app/src/main/java/io/github/russianranger/trasc'
PROFILES = ('custom', 'traditional', 'takp')


def production_method(source, signature):
    """Copy one complete method, preserving its production body unchanged."""
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    position = opening + 1
    quoted = None
    comment = None
    while depth:
        character = source[position]
        following = source[position:position + 2]
        if comment == '//':
            if character == '\n':
                comment = None
        elif comment == '/*':
            if following == '*/':
                comment = None
                position += 2
                continue
        elif quoted:
            if character == '\\':
                position += 2
                continue
            if character == quoted:
                quoted = None
        elif following in ('//', '/*'):
            comment = following
            position += 2
            continue
        elif character in ('"', "'"):
            quoted = character
        elif character == '{':
            depth += 1
        elif character == '}':
            depth -= 1
        position += 1
    return source[start:position]


JSON_SOURCE = r'''package org.json;
import java.util.*;
import java.util.regex.*;
public final class JSONObject {
    private final Map<String,Object> values=new LinkedHashMap<>();
    public JSONObject(){}
    public JSONObject(String text){
        // Saved launch/status inputs in this harness contain flat primitive values.
        String contents=text.trim();
        if(!contents.startsWith("{")||!contents.endsWith("}"))throw new IllegalArgumentException("Invalid JSON object");
        contents=contents.substring(1,contents.length()-1).trim();
        if(contents.isEmpty())return;
        Pattern field=Pattern.compile("\\s*\\\"([^\\\"]+)\\\"\\s*:\\s*(\\\"[^\\\"]*\\\"|true|false|null|[0-9]+)\\s*(,|$)");
        Matcher matcher=field.matcher(contents);int end=0;
        while(matcher.find()){
            if(matcher.start()!=end)throw new IllegalArgumentException("Unsupported JSON fixture");
            String value=matcher.group(2);Object parsed;
            if(value.startsWith("\""))parsed=value.substring(1,value.length()-1);
            else if(value.equals("true")||value.equals("false"))parsed=Boolean.valueOf(value);
            else if(value.equals("null"))parsed=null;
            else parsed=Long.valueOf(value);
            values.put(matcher.group(1),parsed);end=matcher.end();
        }
        if(end!=contents.length())throw new IllegalArgumentException("Unsupported JSON fixture");
    }
    public JSONObject put(String key,Object value){values.put(key,value);return this;}
    public boolean optBoolean(String key){return Boolean.TRUE.equals(values.get(key));}
    public String optString(String key,String fallback){Object value=values.get(key);return value==null?fallback:String.valueOf(value);}
    private static String quote(String text){return "\""+text.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";}
    private static String encode(Object value){if(value==null)return "null";if(value instanceof String)return quote((String)value);return value.toString();}
    @Override public String toString(){StringJoiner result=new StringJoiner(",","{","}");for(Map.Entry<String,Object> entry:values.entrySet())result.add(quote(entry.getKey())+":"+encode(entry.getValue()));return result.toString();}
}'''

HARNESS = r'''package io.github.russianranger.trasc;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

final class RuntimeManager {
    final WorldProfiles profiles;final File work;
    RuntimeManager(WorldProfiles profiles)throws Exception {this.profiles=profiles;this.work=new File(profiles.home(profiles.current()),"work");}
}
final class GraphicsBridge {boolean running;boolean alive(){return running;}}
final class DirectXInstaller {
    static boolean installed(File directory){return new File(directory,"rof2-installed").isFile();}
    static boolean installedTakp(File directory){return new File(directory,"takp-installed").isFile();}
}
final class ClientRuntime {
    final RuntimeManager server;
    final File root,run,directx;
    boolean busy;String status="Client stopped";
    Process process;GraphicsBridge graphics;
    ClientRuntime(RuntimeManager server)throws Exception {
        this.server=server;root=new File(server.work,"client/runtime");run=new File(server.work,"run");directx=new File(server.work,"client/directx");
        run.mkdirs();directx.mkdirs();new File(root,"etc").mkdirs();
        Files.write(new File(root,"etc/trasc-client-runtime.json").toPath(),"{}".getBytes(StandardCharsets.UTF_8));
        Files.write(new File(directx,server.profiles.current().equals("takp")?"takp-installed":"rof2-installed").toPath(),new byte[0]);
    }
    // These method bodies are copied exactly from the production class at run time.
    __PRODUCTION_METHODS__
}
public final class ClientNativeStatusHostTest {
    public static void main(String[] arguments)throws Exception {
        File base=new File(arguments[0]);base.mkdirs();WorldProfiles profiles=new WorldProfiles(base);
        JSONObject cases=new JSONObject(),fixtures=new JSONObject();
        for(String profile:new String[]{"custom","traditional","takp"}) {
            profiles.beginSwitch(profiles.current());try{profiles.select(profile);}finally{profiles.endSwitch();}
            ClientRuntime runtime=new ClientRuntime(new RuntimeManager(profiles));
            JSONObject profileCases=new JSONObject();
            for(String saved:new String[]{"missing","matching","mismatched","malformed"}) {
                File options=new File(runtime.server.work,"client/launch-options.json");options.getParentFile().mkdirs();
                if(saved.equals("missing"))Files.deleteIfExists(options.toPath());
                else {
                    String optionsText=saved.equals("malformed")?"broken metadata":new JSONObject().put("profile",saved.equals("matching")?profile:(profile.equals("custom")?"takp":"custom")).put("mode","client").toString();
                    Files.write(options.toPath(),optionsText.getBytes(StandardCharsets.UTF_8));
                }
                JSONObject states=new JSONObject();
                for(String phase:new String[]{"stopped","running","busy"}) {
                    runtime.graphics=new GraphicsBridge();runtime.graphics.running=phase.equals("running");
                    runtime.busy=phase.equals("busy");runtime.status="Client "+phase;
                    File display=runtime.displaySocket();
                    if(phase.equals("running"))Files.write(display.toPath(),new byte[0]);else Files.deleteIfExists(display.toPath());
                    // MainActivity admits client_native_state through this same real lease.
                    try(WorldProfiles.Lease ignored=profiles.enter(profile)){states.put(phase,runtime.state());}
                }
                profileCases.put(saved,states);
                // Deliberately hostile saved metadata verifies the UI consumes current identity.
                if(saved.equals("mismatched"))fixtures.put(profile,states);
            }
            cases.put(profile,profileCases);
        }
        System.out.println(new JSONObject().put("cases",cases).put("fixtures",fixtures));
    }
}'''


@lru_cache(maxsize=1)
def executed_native_snapshots():
    source = (PACKAGE / 'ClientRuntime.java').read_text()
    signatures = (
        'boolean installed()',
        'private boolean takp()',
        'boolean alive()',
        'File displaySocket()',
        'static JSONObject json(File file)',
        'JSONObject state()',
    )
    methods = '\n'.join(production_method(source, signature) for signature in signatures)
    with tempfile.TemporaryDirectory(prefix='trasc-native-state-') as temporary:
        directory = Path(temporary)
        json_file = directory / 'org/json/JSONObject.java'
        harness_file = directory / 'io/github/russianranger/trasc/ClientNativeStatusHostTest.java'
        json_file.parent.mkdir(parents=True)
        harness_file.parent.mkdir(parents=True)
        json_file.write_text(JSON_SOURCE)
        harness_file.write_text(HARNESS.replace('__PRODUCTION_METHODS__', methods))
        subprocess.run(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', str(directory),
                        str(PACKAGE / 'WorldProfiles.java'), str(json_file), str(harness_file)],
                       check=True, capture_output=True, text=True, timeout=60)
        result = subprocess.run(['java', '-cp', str(directory), 'io.github.russianranger.trasc.ClientNativeStatusHostTest',
                                 str(directory / 'worlds')], check=True, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)


class ClientNativeStatusTests(unittest.TestCase):
    def test_current_profile_is_always_top_level(self):
        cases = executed_native_snapshots()['cases']
        for profile in PROFILES:
            for metadata in ('missing', 'matching', 'mismatched', 'malformed'):
                for phase in ('stopped', 'running', 'busy'):
                    with self.subTest(profile=profile, metadata=metadata, phase=phase):
                        self.assertEqual(cases[profile][metadata][phase].get('profile'), profile)

    def test_status_flags_survive_profile_identity(self):
        for profile, cases in executed_native_snapshots()['cases'].items():
            for metadata, states in cases.items():
                for phase, state in states.items():
                    with self.subTest(profile=profile, metadata=metadata, phase=phase):
                        self.assertTrue(state['installed'])
                        self.assertTrue(state['directx_installed'])
                        self.assertEqual(state['alive'], phase == 'running')
                        self.assertEqual(state['busy'], phase == 'busy')
                        self.assertEqual(state['display_ready'], phase == 'running')
                        self.assertEqual(state['status'], 'Client ' + phase)
                        self.assertEqual(state['client_type'], 'takp' if profile == 'takp' else 'rof2')

    def test_identity_does_not_come_from_saved_launch_options(self):
        cases = executed_native_snapshots()['cases']
        for profile in PROFILES:
            for phase in ('stopped', 'running', 'busy'):
                with self.subTest(profile=profile, phase=phase):
                    self.assertNotIn('launch_options', cases[profile]['missing'][phase])
                    self.assertNotIn('launch_options', cases[profile]['malformed'][phase])
                    state = cases[profile]['mismatched'][phase]
                    self.assertNotEqual(state['launch_options']['profile'], profile)
                    self.assertEqual(state['profile'], profile)

    def test_browser_fixture_contract_uses_executed_status(self):
        results = executed_native_snapshots()
        self.assertEqual(set(results['fixtures']), set(PROFILES))
        for profile in PROFILES:
            self.assertEqual(results['fixtures'][profile], results['cases'][profile]['mismatched'])
            self.assertEqual(set(results['fixtures'][profile]), {'stopped', 'running', 'busy'})


if __name__ == '__main__':
    if sys.argv[1:] == ['--fixtures']:
        print(json.dumps(executed_native_snapshots()['fixtures'], separators=(',', ':')))
    else:
        unittest.main()
