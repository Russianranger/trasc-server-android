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
import client_mouse

SOURCE_FORMAT = 1
SOURCE_FILE_LIMIT = 25000
SOURCE_BYTE_LIMIT = 1024 * 1024**2
SOURCE_SINGLE_LIMIT = 64 * 1024**2
BUILD_RECIPE = 'msvc142-x86-static-v2-compileas'


def _source_path(root, path):
    """Validate the actual ancestors before resolving parent components."""
    root = root.absolute()
    path = path.absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
        raise ValueError('Linked client compiler input paths are not supported')
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Project input escapes client source')
    return path


def _include_path(root, parent, entry):
    # Wine resolves Windows include paths without case sensitivity. Resolve the
    # same spelling for inspection on Android's case-sensitive host filesystem.
    path = parent
    for part in Path(entry).parts:
        if part == '..':
            if path.is_symlink(): raise ValueError('Linked client compiler input paths are not supported')
            path = path.parent
        elif part != '.':
            if path.is_symlink(): raise ValueError('Linked client compiler input paths are not supported')
            choices = [p for p in path.iterdir() if p.name.casefold() == part.casefold()] if path.is_dir() else []
            if len(choices) != 1: raise ValueError('Missing or ambiguous project include: ' + entry)
            path = choices[0]
    return _source_path(root, path)


def source_identity(engine, project=None, recipe=None):
    """Hash actual compiler inputs, including transitive headers and libraries.

    Keep the complete per-file inventory in a separate build manifest; status
    responses expose only its small deterministic summary.
    """
    root = engine.work/'sources/current/Release-NMS-Client'
    project = project or root/'eqgame_dll/eqgame_dll.vcxproj'
    _source_path(root, project)
    if not project.is_file(): raise ValueError('Import source containing the ROF2 eqgame_dll project')
    recipe = recipe or project_recipe(project)
    roots = [project.parent]
    roots += [_include_path(root, project.parent, p) for p in recipe['includes']]
    # Some upstream headers include these bundled dependencies with a relative
    # ../ path rather than an AdditionalIncludeDirectories entry.
    roots += [p for p in (root/'Blech',root/'dxsdk81',root/'Detours',root/'dependencies') if p.exists()]
    inputs = {}; total = 0
    previous = getattr(engine, '_client_dll_input_cache', {})
    cached = {}
    check = getattr(engine, 'check_cancel', lambda: None)
    def inspect(path, key, limit=None):
        nonlocal total
        if limit is None: limit=SOURCE_SINGLE_LIMIT
        if key in inputs: return
        info = path.stat()
        size = info.st_size
        if not path.is_file() or size > limit:
            raise ValueError('Invalid or oversized client compiler input: ' + key)
        total += size
        if len(inputs) >= SOURCE_FILE_LIMIT or total > SOURCE_BYTE_LIMIT:
            raise ValueError('Client compiler source exceeds inspection limits')
        # ctime catches replacement and writes that preserve size/mtime. Cache
        # only hashes; enumerate every path again so additions/removals matter.
        signature = (str(path),info.st_dev,info.st_ino,size,info.st_mtime_ns,info.st_ctime_ns)
        before = previous.get(key)
        if before and before[0] == signature:
            record = before[1]
        else:
            value = hashlib.sha256(); count = 0
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(256*1024), b''):
                    check(); count += len(chunk)
                    if count > limit: raise ValueError('Client compiler input grew during inspection: ' + key)
                    value.update(chunk)
            after = path.stat()
            if signature != (str(path),after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise ValueError('Client compiler input changed during inspection: ' + key)
            record = {'sha256':value.hexdigest(),'bytes':count}
        cached[key] = (signature,record)
        inputs[key] = record
    for folder in roots:
        folder = _source_path(root, folder)
        if not folder.is_dir(): raise ValueError('Project input is not a directory')
        for parent, dirs, files in os.walk(folder, followlinks=False):
            check()
            dirs.sort(); files.sort()
            for name in dirs:
                _source_path(root, Path(parent)/name)
            for name in files:
                path = _source_path(root, Path(parent)/name)
                # Local compiler output is not a source dependency. Never hash
                # it as evidence that source is current.
                if path.suffix.casefold() in ('.obj','.dll','.pdb','.ilk','.exp','.idb','.pch','.log','.tlog'):
                    continue
                key = path.relative_to(root.resolve()).as_posix()
                inspect(path,key)
    for name in recipe['sources']:
        path = _source_path(root,project.parent/name)
        inspect(path,path.relative_to(root.resolve()).as_posix())
    for name in ('client_dll.py','client_mouse.py', *client_mouse.HEADERS):
        path = Path(__file__).with_name(name)
        inspect(path,'@launcher/'+name)
    sdk_manifest = engine.work/'client/toolchain/sdk.json'
    if sdk_manifest.exists():
        if sdk_manifest.is_symlink(): raise ValueError('Invalid SDK manifest')
        inspect(sdk_manifest,'@sdk/sdk.json',1024*1024)
    manifest_path = engine.work/'sources/current/trasc-source.json'
    commit = None
    if manifest_path.exists():
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 1024*1024:
            raise ValueError('Invalid selected source revision manifest')
        metadata = json.loads(manifest_path.read_text())
        if not isinstance(metadata,dict): raise ValueError('Invalid selected source revision manifest')
        commit = metadata.get('commit')
        if commit is not None and (not isinstance(commit,str) or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit)):
            raise ValueError('Invalid selected source commit')
    payload = {'format':SOURCE_FORMAT,'recipe':BUILD_RECIPE,'commit':commit,'inputs':inputs}
    sha = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    engine._client_dll_input_cache = cached
    return {'format':SOURCE_FORMAT,'recipe':BUILD_RECIPE,'commit':commit,'sha256':sha,
            'files':len(inputs),'bytes':sum(p['bytes'] for p in inputs.values()),'inputs':inputs}


def _identity_summary(identity):
    return {k:v for k,v in identity.items() if k != 'inputs'}


def _receipt(path):
    if not path.exists(): return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024*1024:
        raise ValueError('Invalid client DLL build receipt')
    value = json.loads(path.read_text())
    if not isinstance(value,dict): raise ValueError('Invalid client DLL build receipt')
    return value


def _freshness(record, path, source):
    if path is None or not path.exists(): return {'state':'missing','reason':'No DLL is present'}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > SOURCE_SINGLE_LIMIT:
        return {'state':'modified','reason':'The DLL path is linked, invalid or oversized'}
    if not record or not isinstance(record.get('source_identity'),dict):
        return {'state':'unknown','reason':'This older DLL has no verified source inventory. Rebuild from the selected source.'}
    if digest(path) != record.get('sha256'):
        return {'state':'modified','reason':'The DLL differs from its build receipt'}
    built = record['source_identity']
    def hexadecimal(value, length):
        return isinstance(value,str) and len(value)==length and all(c in '0123456789abcdef' for c in value)
    if (built.get('format') != SOURCE_FORMAT or built.get('recipe') != BUILD_RECIPE
            or not hexadecimal(built.get('sha256'),64)
            or (built.get('commit') is not None and not hexadecimal(built['commit'],40))
            or type(built.get('files')) is not int or not 0 < built['files'] <= SOURCE_FILE_LIMIT
            or type(built.get('bytes')) is not int or not 0 <= built['bytes'] <= SOURCE_BYTE_LIMIT):
        return {'state':'unknown','reason':'The DLL source inventory receipt is invalid. Rebuild from the selected source.'}
    result = {'source_commit':built.get('commit'),'source_sha256':built.get('sha256'),
              'hash_verified':True,'source_identity_verified':True}
    if not source.get('available'):
        return {**result,'state':'unknown','reason':'The selected source cannot be inspected'}
    if built.get('format') != SOURCE_FORMAT or built.get('sha256') != source.get('sha256'):
        return {**result,'state':'stale','reason':'Selected source or launcher adapter inputs changed. Rebuild before deployment.'}
    return {**result,'state':'current','reason':'DLL matches the selected source and launcher adapters'}


def compiler_status(engine,args=None):
    staged=engine.work/'builds/client-dll-staged'
    errors = []
    def read(path):
        try: return _receipt(path)
        except (OSError,ValueError,UnicodeError) as error:
            errors.append(str(error)); return None
    record = read(staged/'build.json')
    installed = read(engine.work/'logs/client-dll-deploy.json')
    try: source = {'available':True,**_identity_summary(source_identity(engine))}
    except (OSError,ValueError,UnicodeError) as error: source = {'available':False,'error':str(error)}
    client = engine.work/'client/current'
    try: installed_path = target_path(client,'dinput8.dll')
    except ValueError: installed_path = None; errors.append('The installed DLL path is ambiguous or linked')
    freshness = {'staged':_freshness(record,staged/'dinput8.dll',source),
                 'installed':_freshness(installed,installed_path,source)}
    if errors: freshness['errors'] = errors
    return {'compiler':(engine.work/'client/toolchain/bin/cl.exe').is_file(),
            'runtime':(engine.work/'client/runtime/etc/trasc-client-runtime.json').is_file(),
            'sdk':(engine.work/'client/toolchain/sdk.json').is_file(),
            'build':record,'source':source,'freshness':freshness}


def sdk_layout(root):
    # The accompanying PowerShell packer exports this small, explicit layout.
    required=['include/msvc','include/ucrt','include/shared','include/um','include/winrt','lib/msvc','lib/ucrt','lib/um','bin']
    for name in required:
        if not (root/name).is_dir() or (root/name).is_symlink(): raise ValueError('SDK ZIP is missing '+name)
    for name in ('include/msvc/vector','include/um/Windows.h','lib/msvc/libcmt.lib','lib/ucrt/libucrt.lib','lib/um/kernel32.lib','bin/cl.exe','bin/link.exe','bin/c1xx.dll','bin/c2.dll','bin/vcruntime140.dll','bin/msvcp140.dll'):
        if not target_path(root,name).is_file(): raise ValueError('SDK ZIP is missing '+name)
    return required


def recover_sdk(engine):
    """Restore the installed compiler if an interrupted swap moved it aside."""
    current = engine.work / 'client/toolchain'
    previous = engine.work / 'client/toolchain-previous'
    if not current.exists() and previous.is_dir():
        sdk_layout(previous)
        previous.rename(current)


def import_sdk(engine,args):
    if engine.profile == 'takp': raise ValueError('The RoF2 DLL compiler is unavailable for TAKP. Its eqw/eqgame updates are prepared from the bundled TAKP pair')
    from engine import safe_path, extract_archive, atomic_json
    recover_sdk(engine)
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
        try: stage.rename(current)
        except BaseException:
            recover_sdk(engine)
            raise
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
    units=tree.findall('m:ItemGroup/m:ClCompile',ns)
    sources=[x.get('Include','').replace('\\','/') for x in units]
    if not sources or any('$(' in x or '%' in x for x in definitions+includes+sources): raise ValueError('Unsupported project macros')
    if any(not x for x in sources) or len({x.casefold() for x in sources}) != len(sources): raise ValueError('Invalid or duplicate compilation units')
    if len(sources)>300: raise ValueError('Project has too many compilation units')
    default=value('CompileAs') or 'CompileAsCpp'  # Preserve the original v142 recipe's C++ default.
    if default not in ('CompileAsC','CompileAsCpp','Default'): raise ValueError('Unsupported project CompileAs setting')
    languages={}
    for name,unit in zip(sources,units):
        if unit.get('Condition'): raise ValueError('Conditional compilation units need review')
        overrides=[]
        for option in unit.findall('m:CompileAs',ns):
            condition=option.get('Condition','')
            if condition and "=='Release|Win32'" not in condition.replace(' ',''):
                # Explicit settings for another standard configuration do not
                # participate in the selected Release|Win32 recipe.
                if any("=='"+config+"'" in condition.replace(' ','') for config in ('Debug|Win32','Debug|x64','Release|x64')):
                    continue
                raise ValueError('Unsupported conditional CompileAs setting')
            overrides.append(option.text or 'Default')
        if len(overrides)>1: raise ValueError('Ambiguous project CompileAs setting')
        mode=overrides[0] if overrides else default
        if mode not in ('CompileAsC','CompileAsCpp','Default'): raise ValueError('Unsupported project CompileAs setting')
        languages[name]='c' if mode=='CompileAsC' or (mode=='Default' and name.casefold().endswith('.c')) else 'cpp'
    return {'definitions':definitions,'includes':includes,'sources':sources,'languages':languages}


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
    if engine.profile == 'takp': raise ValueError('The RoF2 DLL compiler is unavailable for TAKP')
    from engine import atomic_json
    if engine.server_running(): raise ValueError('Stop the server before compiling the client DLL')
    status=compiler_status(engine)
    if not status['compiler'] or not status['sdk']: raise ValueError('Import the Microsoft x86 toolchain and SDK first')
    root=engine.work/'sources/current/Release-NMS-Client'
    project=root/'eqgame_dll/eqgame_dll.vcxproj'
    if not project.is_file(): raise ValueError('Import source containing the ROF2 eqgame_dll project')
    recipe=project_recipe(project)
    identity=source_identity(engine,project,recipe)
    sdk=engine.work/'client/toolchain'; sdk_layout(sdk)
    build=engine.work/'builds'/('client-dll-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4));build.mkdir()
    camera_sources=client_mouse.prepare_sources(project,build)
    def winpath(path):
        return str(path) if os.name == 'nt' else 'Z:'+str(path).replace('/', '\\')
    includes=[project.parent]+[sdk/'include'/n for n in ('msvc','ucrt','shared','um','winrt')]
    for entry in recipe['includes']:
        path=_include_path(root,project.parent,entry)
        includes.append(path)
    common=[sdk/'bin/cl.exe','/nologo','/c','/W3','/Od','/Oy-','/MT','/GS-','/Gy-','/GF','/Oi','/Zp1']
    common+=['/D'+x for x in recipe['definitions']]+['/I'+winpath(p) for p in includes]
    objects=[]
    for i,name in enumerate(recipe['sources']):
        source=_source_path(root,project.parent/name)
        if not source.is_relative_to(root.resolve()) or not source.is_file(): raise ValueError('Invalid project source path')
        source=camera_sources.get(name,source)
        obj=build/(str(i)+'.obj');objects.append(obj)
        engine.log('Client DLL: '+str(i+1)+'/'+str(len(recipe['sources']))+' '+name)
        language=['/TC'] if recipe['languages'][name]=='c' else ['/GR','/std:c++14','/TP']
        engine.run(common+language+['/Fo'+winpath(obj),winpath(source)],cwd=project.parent,timeout=900)
    output=build/'dinput8.dll'
    libraries=[sdk/'lib'/n for n in ('msvc','ucrt','um')]+[root/'Detours/lib',root/'dependencies/dx9/Lib']
    engine.run([sdk/'bin/link.exe','/nologo','/dll','/machine:x86','/subsystem:windows','/out:'+winpath(output),'/def:'+winpath(project.parent/'dinput8.def'),
                '/LTCG','/opt:noref','/opt:noicf',*('/libpath:'+winpath(p) for p in libraries),*(winpath(p) for p in objects),
                'kernel32.lib','user32.lib','gdi32.lib','winspool.lib','comdlg32.lib','advapi32.lib','shell32.lib','ole32.lib','oleaut32.lib','uuid.lib','odbc32.lib','odbccp32.lib'],cwd=project.parent)
    validate_dll(output)
    if any(marker.encode() not in output.read_bytes() for marker in (client_mouse.MARKER, client_mouse.LOADING_MARKER, client_mouse.DISPLAY_MARKER, client_mouse.PARTICLE_MARKER, client_mouse.BOAT_MARKER)):
        raise ValueError('Compiled DLL is missing a client adapter')
    if source_identity(engine,project,recipe)['sha256'] != identity['sha256']:
        raise ValueError('Client source or launcher adapters changed during compilation. Build again; the previous staged and installed DLLs are unchanged.')
    metadata={'sha256':digest(output),'bytes':output.stat().st_size,'project_sha256':digest(project),'compiler':'Microsoft v142 14.29, Hostx64/x86, static runtime','patches':[client_mouse.MARKER,client_mouse.LOADING_MARKER,client_mouse.DISPLAY_MARKER,client_mouse.PARTICLE_MARKER,client_mouse.BOAT_MARKER],'adapter_headers_sha256':{name:digest(Path(__file__).with_name(name)) for name in client_mouse.HEADERS},'built_at':time.time(),'file':str(output.relative_to(engine.work))}
    metadata['source_identity']=_identity_summary(identity)
    metadata['source_manifest']=str((build/'source-inputs.json').relative_to(engine.work))
    atomic_json(build/'source-inputs.json',identity)
    atomic_json(build/'build.json',metadata)
    staged=engine.work/'builds/client-dll-staged';staged.mkdir(exist_ok=True)
    # A failed build never replaces the last successful staged DLL.
    shutil.copy2(output,staged/'dinput8.dll.new');(staged/'dinput8.dll.new').replace(staged/'dinput8.dll')
    atomic_json(staged/'source-inputs.json',identity)
    atomic_json(staged/'build.json',metadata)
    return {'message':'x86 dinput8.dll built and staged. Review/deploy separately; the installed DLL is unchanged.','build':metadata}


def deploy_dll(engine,args):
    if engine.profile == 'takp': raise ValueError('Do not deploy RoF2 dinput8 hooks into TAKP; prepare its native client updates instead')
    from engine import atomic_json
    staged=engine.work/'builds/client-dll-staged'; record=json.loads((staged/'build.json').read_text()); dll=staged/'dinput8.dll'
    validate_dll(dll)
    if digest(dll)!=record['sha256']: raise ValueError('Staged DLL checksum failed')
    if engine.profile == 'custom':
        freshness=compiler_status(engine)['freshness']['staged']
        if freshness['state'] != 'current':
            raise ValueError('Rebuild dinput8 from the selected Custom source before deploying. '+freshness['reason'])
    if 'dinput8.dll' in policy(engine)['locked']: raise ValueError('Unlock dinput8.dll in Client add-ons before deploying')
    client=engine._local_client();backup=engine._apply_client_changes(client,{target_path(client,'dinput8.dll'):dll})
    record.update(backup=backup);atomic_json(engine.work/'logs/client-dll-deploy.json',record)
    return {'message':'Built dinput8.dll deployed. Previous DLL retained in '+backup+'.','backup':backup}
