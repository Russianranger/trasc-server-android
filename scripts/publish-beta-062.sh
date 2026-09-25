#!/usr/bin/env bash
# One-time promotion explicitly requested by the user; never rebuild the APK.
set -euo pipefail
[[ "${GITHUB_REPOSITORY:?}" == 'Russianranger/trasc-server-android' ]]
[[ "${GITHUB_EVENT_NAME:?}" == 'push' || "$GITHUB_EVENT_NAME" == 'workflow_dispatch' ]]
[[ "${GITHUB_REF:?}" == 'refs/heads/codex/release-beta-062' || "$GITHUB_REF" == 'refs/heads/main' ]]
repo="$GITHUB_REPOSITORY"
build_commit='2cd9d50c2de3b6c2607187702452fb87d0b954bd'
mkdir -p dist/beta-062
gh api "repos/$repo/actions/runs/36119436611" > dist/beta-062/run.json
gh api "repos/$repo/actions/runs/36119436611/jobs?per_page=100" > dist/beta-062/jobs.json
gh api "repos/$repo/actions/artifacts/10857210885" > dist/beta-062/artifact.json
python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/beta-062')
run=json.loads((p/'run.json').read_text())
assert run['head_sha']=='2cd9d50c2de3b6c2607187702452fb87d0b954bd'
assert run['head_branch']=='main' and run['event']=='push'
assert run['path']=='.github/workflows/build.yml'
assert run['status']=='completed' and run['conclusion']=='success'
jobs=json.loads((p/'jobs.json').read_text())
expected={'display-auth','database','wined3d / wined3d','client-dll / compile',
          'vulkan / vulkan','ferry-server / native','apk','client-runtime / client-runtime','preview'}
assert jobs['total_count']==9 and {j['name'] for j in jobs['jobs']}==expected
assert all(j['status']=='completed' and j['conclusion']=='success' for j in jobs['jobs'])
a=json.loads((p/'artifact.json').read_text())
assert a['id']==10857210885 and a['workflow_run']['id']==36119436611 and not a['expired']
assert a['workflow_run']['head_sha']==run['head_sha'] and a['name']=='trasc-server-android-debug'
assert a['digest']=='sha256:3c1f1e12b329007ba0cb2766d3498372a169772b1d43d82fbb7695eaa461b229'
PY
gh api "repos/$repo/actions/artifacts/10857210885/zip" > dist/beta-062/artifact.zip
python3 - <<'PY'
import hashlib,json,pathlib,zipfile
p=pathlib.Path('dist/beta-062')
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((p/'artifact.zip').read_bytes())=='3c1f1e12b329007ba0cb2766d3498372a169772b1d43d82fbb7695eaa461b229'
files={'app/build/outputs/apk/debug/app-debug.apk':'trasc-server-android-beta-0.6.2.apk',
       'dist/launcher-sources.tar.gz':'launcher-sources.tar.gz',
       'dist/preview-signing.sha256':'preview-signing.sha256'}
with zipfile.ZipFile(p/'artifact.zip') as z:
    assert len(z.namelist())==len(files) and set(z.namelist())==set(files)
    assert z.testzip() is None
    for source,dest in files.items(): (p/dest).write_bytes(z.read(source))
apk=p/'trasc-server-android-beta-0.6.2.apk'
source=p/'launcher-sources.tar.gz'
assert apk.stat().st_size==15204739
assert sha(apk.read_bytes())=='d9a4dce3e6657c8fdb9713cab1aeebf5cf65b8d87a678bad723353045652483b'
assert sha(source.read_bytes())=='228c60708d8edae71be5ef0b575f5eca3b0ea926e85507eb93cb10f6aa46e3b4'
cert='ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869'
assert (p/'preview-signing.sha256').read_text().strip()==cert
manifest={'commit':'2cd9d50c2de3b6c2607187702452fb87d0b954bd','sha256':sha(apk.read_bytes()),
          'file':apk.name,'version':'0.6.2','version_code':51,'bytes':apk.stat().st_size,
          'application_id':'io.github.russianranger.trasc.preview','signing_certificate_sha256':cert,
          'release':'Beta version 0.6.2','source_archive_sha256':sha(source.read_bytes()),
          'build_run':36119436611,'artifact_id':10857210885}
(p/'beta-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Reused before and after publication; compare uploaded bytes via GitHub digests.
(p/'expected-assets.json').write_text(json.dumps({n:{'size':(p/n).stat().st_size,
    'digest':'sha256:'+sha((p/n).read_bytes())} for n in (apk.name,source.name,'beta-build.json')}))
PY
if ! gh api "repos/$repo/git/ref/tags/v0.6.2" > dist/beta-062/tag.json 2>/dev/null; then
    gh api --method POST "repos/$repo/git/refs" -f ref=refs/tags/v0.6.2 -f sha="$build_commit" > /dev/null
    gh api "repos/$repo/git/ref/tags/v0.6.2" > dist/beta-062/tag.json
fi
python3 - <<'PY'
import json
t=json.load(open('dist/beta-062/tag.json'))['object']
assert t['type']=='commit' and t['sha']=='2cd9d50c2de3b6c2607187702452fb87d0b954bd', 'Existing tag belongs to another build'
PY
if gh api "repos/$repo/releases/tags/v0.6.2" > dist/beta-062/release.json 2>/dev/null; then
    python3 - <<'PY'
import json
r=json.load(open('dist/beta-062/release.json'))
assert r['draft'], 'Release already published; refusing to overwrite it'
assert r['target_commitish']=='2cd9d50c2de3b6c2607187702452fb87d0b954bd', 'Existing draft belongs to another build'
PY
else
    gh release create v0.6.2 --draft --target "$build_commit" --title 'Beta version 0.6.2' --notes-file docs/beta-062-release.md
fi
gh release upload v0.6.2 dist/beta-062/trasc-server-android-beta-0.6.2.apk dist/beta-062/launcher-sources.tar.gz dist/beta-062/beta-build.json --clobber
gh api "repos/$repo/releases/tags/v0.6.2" > dist/beta-062/release.json
python3 - <<'PY'
import json
r=json.load(open('dist/beta-062/release.json'))
assert r['draft'] and r['tag_name']=='v0.6.2'
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.load(open('dist/beta-062/expected-assets.json')), 'Uploaded assets do not match the verified build'
PY
gh release edit v0.6.2 --draft=false --prerelease=false --latest --notes-file docs/beta-062-release.md
gh api "repos/$repo/releases/latest" > dist/beta-062/latest.json
python3 - <<'PY'
import json
r=json.load(open('dist/beta-062/latest.json'))
assert r['tag_name']=='v0.6.2' and not r['draft'] and not r['prerelease']
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.load(open('dist/beta-062/expected-assets.json'))
print('Published the verified Beta 0.6.2 APK as the latest release.')
PY
