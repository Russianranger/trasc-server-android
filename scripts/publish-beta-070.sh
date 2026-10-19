#!/usr/bin/env bash
# Publish only the main-branch APK qualified by this workflow; keep stable/preview unchanged.
set -euo pipefail
[[ "${GITHUB_REPOSITORY:?}" == 'Russianranger/trasc-server-android' ]]
[[ "${GITHUB_REF:?}" == 'refs/heads/main' && "${GITHUB_EVENT_NAME:?}" == 'push' ]]
repo="$GITHUB_REPOSITORY"
tag='v0.7.0-beta'
gh api "repos/$repo/git/ref/heads/main" > dist/main.json
python3 - <<'PY'
import hashlib,json,os,pathlib
p=pathlib.Path('dist')
m=json.loads((p/'release-build.json').read_text())
assert m['commit']==os.environ['GITHUB_SHA']==json.loads((p/'main.json').read_text())['object']['sha']
assert m['version']=='0.7.0-beta' and m['version_code']==92 and m['prerelease']
for name,expected in json.loads((p/'expected-assets.json').read_text()).items():
    f=p/name
    assert f.stat().st_size==expected['size']
    assert 'sha256:'+hashlib.file_digest(f.open('rb'),'sha256').hexdigest()==expected['digest'], name
PY
if ! gh api "repos/$repo/git/ref/tags/$tag" > dist/tag.json 2>/dev/null; then
    gh api --method POST "repos/$repo/git/refs" -f "ref=refs/tags/$tag" -f "sha=$GITHUB_SHA" > /dev/null
    gh api "repos/$repo/git/ref/tags/$tag" > dist/tag.json
fi
python3 - <<'PY'
import json,os
obj=json.load(open('dist/tag.json'))['object']
assert obj['type']=='commit' and obj['sha']==os.environ['GITHUB_SHA'], 'Tag belongs to a different build'
PY
# Include drafts when finding an existing release; never replace a published release.
gh api --paginate --slurp "repos/$repo/releases?per_page=100" > dist/releases.json
release_id=$(python3 - <<'PY'
import json,os
r=[r for page in json.load(open('dist/releases.json')) for r in page if r['tag_name']=='v0.7.0-beta']
assert len(r)<=1
if r:
    assert r[0]['draft'], 'Beta already published; refusing to overwrite it'
    assert r[0]['target_commitish']==os.environ['GITHUB_SHA']
    print(r[0]['id'])
PY
)
if [[ -z "$release_id" ]]; then
    python3 - <<'PYCREATE'
import json,os,pathlib
pathlib.Path('dist/create-release.json').write_text(json.dumps({'tag_name':'v0.7.0-beta',
    'target_commitish':os.environ['GITHUB_SHA'],'name':'TRASC Android — Beta 0.7.0',
    'body':pathlib.Path('docs/release-070-beta-notes.md').read_text(),'draft':True,'prerelease':True}))
PYCREATE
    release_id=$(gh api --method POST "repos/$repo/releases" --input dist/create-release.json --jq '.id')
fi
gh release upload "$tag" dist/trasc-server-android-beta-0.7.0.apk dist/launcher-sources.tar.gz dist/release-build.json dist/native-reuse.json dist/apk-signing.txt --clobber
[[ "$release_id" =~ ^[0-9]+$ ]]
for delay in 1 2 4 8 0; do
    if gh api "repos/$repo/releases/$release_id" > dist/uploaded-release.json; then break; fi
    [[ "$delay" == 0 ]] && exit 1
    sleep "$delay"
done
python3 - <<'PY'
import json
r=json.load(open('dist/uploaded-release.json'))
assert r['draft'] and r['prerelease']
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.load(open('dist/expected-assets.json')), 'Uploaded assets differ from qualified build'
PY
[[ "$(gh api "repos/$repo/git/ref/heads/main" --jq '.object.sha')" == "$GITHUB_SHA" ]]
gh release edit "$tag" --draft=false --prerelease --latest=false --notes-file docs/release-070-beta-notes.md
gh api "repos/$repo/releases/tags/$tag" > dist/public-release.json
python3 - <<'PY'
import hashlib,json,os,pathlib,urllib.request
p=pathlib.Path('dist')
r=json.loads((p/'public-release.json').read_text())
assert not r['draft'] and r['prerelease'] and r['tag_name']=='v0.7.0-beta'
assert r['target_commitish']==os.environ['GITHUB_SHA']
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.loads((p/'expected-assets.json').read_text())
m=json.loads((p/'release-build.json').read_text())
url=next(a['browser_download_url'] for a in r['assets'] if a['name']==m['file'])
with urllib.request.urlopen(url) as response:
    h=hashlib.sha256(); size=0
    while chunk:=response.read(1024*1024):
        h.update(chunk);size+=len(chunk)
assert h.hexdigest()==m['sha256'] and size==m['bytes'], 'Public APK download differs'
print('Published and verified public Beta 0.7.0 APK:',url)
PY
