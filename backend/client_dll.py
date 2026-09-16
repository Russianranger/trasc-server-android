"""Build the upstream x86 DLL with its real Microsoft compiler under Wine."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import struct
import time
import xml.etree.ElementTree as ET
from client_addons import target_path, policy
from managed_content import digest


def compiler_status(engine,args=None):
    staged=engine.work/'builds/client-dll-staged/build.json'
    return {'compiler':(engine.work/'client/toolchain/bin/cl.exe').is_file(),
            'runtime':(engine.work/'client/runtime/etc/trasc-client-runtime.json').is_file(),
            'sdk':(engine.work/'client/toolchain/sdk.json').is_file(),
            'build':json.loads(staged.read_text()) if staged.is_file() else None}


def sdk_layout(root):
    # The accompanying PowerShell packer exports this small, explicit layout.
    required=['include/msvc','include/ucrt','include/shared','include/um','include/winrt','lib/msvc','lib/ucrt','lib/um','bin']
    for name in required:
        if not (root/name).is_dir() or (root/name).is_symlink(): raise ValueError('SDK ZIP is missing '+name)
    for name in ('include/msvc/vector','include/um/Windows.h','lib/msvc/libcmt.lib','lib/ucrt/libucrt.lib','lib/um/kernel32.lib','bin/cl.exe','bin/link.exe','bin/c1xx.dll','bin/c2.dll','bin/vcruntime140.dll','bin/msvcp140.dll'):
        if not target_path(root,name).is_file(): raise ValueError('SDK ZIP is missing '+name)
    return required


def import_sdk(engine,args):
    from engine import safe_path, extract_archive, atomic_json
    source=safe_path(engine.work/'incoming',args['file'],True)
    stage=engine.work/'client'/('toolchain-import-'+secrets.token_hex(4)); stage.mkdir()
    try:
        extract_archive(source,stage,limit=3*1024**3);sdk_layout(stage)
        manifest=stage/'sdk.json'
        if not manifest.is_file() or manifest.stat().st_size>65536: raise ValueError('Use the supplied Windows SDK packer to create sdk.json')
        metadata=json.loads(manifest.read_text())
        if metadata.get('format')!='trasc-msvc-sdk-1' or metadata.get('target')!='x86': raise ValueError('An x86 Microsoft SDK package is required')
        # Preserve the upstream v142 compiler and libraries as one matched toolset.
        if not str(metadata.get('msvc_version','')).startswith('14.29.'):
            raise ValueError('This project requires the VS2019 v142 14.29 toolset (also installable in VS2022)')
        current=engine.work/'client/toolchain'; previous=engine.work/'client/toolchain-previous'
        engine.check_cancel()
        if previous.exists(): shutil.rmtree(previous)
        if current.exists(): current.rename(previous)
        stage.rename(current)
        return {'message':'Microsoft x86 SDK imported. You can now build dinput8 from the imported source.'}
    finally:
        if stage.exists(): shutil.rmtree(stage)


def project_recipe(project):
    ns={'m':'http://schemas.microsoft.com/developer/msbuild/2003'}
    tree=ET.parse(project).getroot()
    groups=[g for g in tree.findall('m:ItemDefinitionGroup',ns) if "=='Release|Win32'" in g.get('Condition','').replace(' ', '')]
    if len(groups)!=1: raise ValueError('Project must have one Release|Win32 definition')
    group=groups[0]
    def value(name): return group.findtext('m:ClCompile/m:'+name,default='',namespaces=ns)
    if value('StructMemberAlignment')!='1Byte' or value('RuntimeLibrary')!='MultiThreaded':
        raise ValueError('Project ABI settings changed; this build recipe needs review')
    if value('Optimization')!='Disabled' or value('BufferSecurityCheck')!='false':
        raise ValueError('Project compiler settings changed; this build recipe needs review')
    definitions=[x for x in value('PreprocessorDefinitions').split(';') if x and not x.startswith('%(')]
    includes=[x.replace('\\','/') for x in value('AdditionalIncludeDirectories').split(';') if x and not x.startswith('%(')]
    sources=[x.get('Include').replace('\\','/') for x in tree.findall('m:ItemGroup/m:ClCompile',ns)]
    if not sources or any('$(' in x or '%' in x for x in definitions+includes+sources): raise ValueError('Unsupported project macros')
    if len(sources)>300: raise ValueError('Project has too many compilation units')
    return {'definitions':definitions,'includes':includes,'sources':sources}


def validate_dll(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>64*1024**2: raise ValueError('Missing or oversized DLL output')
    with path.open('rb') as stream:
        header=stream.read(64)
        if len(header)!=64 or header[:2]!=b'MZ': raise ValueError('Compiler did not produce a Windows DLL')
        offset=struct.unpack_from('<I',header,0x3c)[0]
        if offset>1024**2: raise ValueError('Invalid PE offset')
        stream.seek(offset);pe=stream.read(26)
        if len(pe)!=26 or pe[:4]!=b'PE\0\0' or struct.unpack_from('<H',pe,4)[0]!=0x14c or struct.unpack_from('<H',pe,24)[0]!=0x10b or not struct.unpack_from('<H',pe,22)[0]&0x2000:
            raise ValueError('ROF2 requires an x86 PE32 DLL')


def build_dll(engine,args):
    from engine import atomic_json
    if engine.server_running(): raise ValueError('Stop the server before compiling the client DLL')
    status=compiler_status(engine)
    if not status['compiler'] or not status['sdk']: raise ValueError('Import the Microsoft x86 toolchain and SDK first')
    root=engine.work/'sources/current/Release-NMS-Client'
    project=root/'eqgame_dll/eqgame_dll.vcxproj'
    if not project.is_file(): raise ValueError('Import source containing the ROF2 eqgame_dll project')
    recipe=project_recipe(project)
    sdk=engine.work/'client/toolchain'; sdk_layout(sdk)
    build=engine.work/'builds'/('client-dll-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4));build.mkdir()
    def winpath(path):
        return str(path) if os.name == 'nt' else 'Z:'+str(path).replace('/', '\\')
    includes=[sdk/'include'/n for n in ('msvc','ucrt','shared','um','winrt')]
    for entry in recipe['includes']:
        path=(project.parent/entry).resolve()
        if not path.is_relative_to(root.resolve()): raise ValueError('Project include escapes client source')
        includes.append(path)
    common=[sdk/'bin/cl.exe','/nologo','/c','/W3','/Od','/Oy-','/MT','/GS-','/Gy-','/GF','/Oi','/Zp1','/GR','/std:c++14','/TP']
    common+=['/D'+x for x in recipe['definitions']]+['/I'+winpath(p) for p in includes]
    objects=[]
    for i,name in enumerate(recipe['sources']):
        source=(project.parent/name).resolve()
        if not source.is_relative_to(root.resolve()) or not source.is_file(): raise ValueError('Invalid project source path')
        obj=build/(str(i)+'.obj');objects.append(obj)
        engine.log('Client DLL: '+str(i+1)+'/'+str(len(recipe['sources']))+' '+name)
        engine.run(common+['/Fo'+winpath(obj),winpath(source)],cwd=project.parent,timeout=900)
    output=build/'dinput8.dll'
    libraries=[sdk/'lib'/n for n in ('msvc','ucrt','um')]+[root/'Detours/lib',root/'dependencies/dx9/Lib']
    engine.run([sdk/'bin/link.exe','/nologo','/dll','/machine:x86','/subsystem:windows','/out:'+winpath(output),'/def:'+winpath(project.parent/'dinput8.def'),
                '/LTCG','/opt:noref','/opt:noicf',*('/libpath:'+winpath(p) for p in libraries),*(winpath(p) for p in objects),
                'kernel32.lib','user32.lib','gdi32.lib','winspool.lib','comdlg32.lib','advapi32.lib','shell32.lib','ole32.lib','oleaut32.lib','uuid.lib','odbc32.lib','odbccp32.lib'],cwd=project.parent)
    validate_dll(output)
    metadata={'sha256':digest(output),'bytes':output.stat().st_size,'project_sha256':digest(project),'compiler':'Microsoft v142 14.29, Hostx64/x86, static runtime, original source','built_at':time.time(),'file':str(output.relative_to(engine.work))}
    atomic_json(build/'build.json',metadata)
    staged=engine.work/'builds/client-dll-staged';staged.mkdir(exist_ok=True)
    # A failed build never replaces the last successful staged DLL.
    shutil.copy2(output,staged/'dinput8.dll.new');(staged/'dinput8.dll.new').replace(staged/'dinput8.dll')
    atomic_json(staged/'build.json',metadata)
    return {'message':'x86 dinput8.dll built and staged. Review/deploy separately; the installed DLL is unchanged.','build':metadata}


def deploy_dll(engine,args):
    from engine import atomic_json
    staged=engine.work/'builds/client-dll-staged'; record=json.loads((staged/'build.json').read_text()); dll=staged/'dinput8.dll'
    validate_dll(dll)
    if digest(dll)!=record['sha256']: raise ValueError('Staged DLL checksum failed')
    if 'dinput8.dll' in policy(engine)['locked']: raise ValueError('Unlock dinput8.dll in Client add-ons before deploying')
    client=engine._local_client();backup=engine._apply_client_changes(client,{target_path(client,'dinput8.dll'):dll})
    record.update(backup=backup);atomic_json(engine.work/'logs/client-dll-deploy.json',record)
    return {'message':'Built dinput8.dll deployed. Previous DLL retained in '+backup+'.','backup':backup}
