#!/usr/bin/env python3
"""Repack docker export in the exact GNU tar subset understood by the APK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile

p=argparse.ArgumentParser()
p.add_argument('input')
p.add_argument('output')
p.add_argument('--runtime', default='1.1')
p.add_argument('--profile', choices=('custom', 'traditional'))
p.add_argument('--build-adapter', type=int)
p.add_argument('--manifest-name', default='runtime-manifest.json')
a=p.parse_args()
if Path(a.manifest_name).name != a.manifest_name or a.manifest_name in ('', '.', '..'):
    p.error('Manifest name must be a filename')
if a.build_adapter is not None and a.build_adapter < 1:
    p.error('Build adapter must be positive')
out=Path(a.output)
with tarfile.open(a.input,'r|') as source, tarfile.open(out,'w:gz',format=tarfile.GNU_FORMAT,compresslevel=6) as dest:
    for member in source:
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()): continue
        if member.name.split('/')[0] in ('dev','proc','sys') and '/' in member.name.rstrip('/'): continue
        member.uid=member.gid=0
        member.uname=member.gname='root'
        member.mode &= 0o777
        dest.addfile(member,source.extractfile(member) if member.isfile() else None)
digest=hashlib.sha256()
with out.open('rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):digest.update(b)
manifest={'format':1,'architecture':'arm64','file':out.name,'sha256':digest.hexdigest(),'bytes':out.stat().st_size,'runtime':a.runtime,'source_commit':os.environ.get('GITHUB_SHA','local')}
if a.profile is not None: manifest['profile']=a.profile
if a.build_adapter is not None: manifest['build_adapter']=a.build_adapter
out.with_name(a.manifest_name).write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
