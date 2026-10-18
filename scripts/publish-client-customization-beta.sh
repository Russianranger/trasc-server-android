#!/usr/bin/env bash
# Publish only the qualified main artifact; resume an interrupted publication safely.
set -euo pipefail
[[ "${GITHUB_REPOSITORY:?}" == 'Russianranger/trasc-server-android' ]]
[[ "${GITHUB_REF:?}" == 'refs/heads/main' ]]
[[ "${GITHUB_EVENT_NAME:?}" == 'push' || "$GITHUB_EVENT_NAME" == 'workflow_dispatch' ]]
[[ "${GITHUB_SHA:?}" =~ ^[0-9a-f]{40}$ ]]
repo="$GITHUB_REPOSITORY"
tag='v0.6.35-beta'
notes='docs/beta-0635-release.md'
mkdir -p dist/publication

require_current_main() {
    local current_main
    current_main=$(gh api "repos/$repo/git/ref/heads/main" --jq '.object.sha')
    [[ "$current_main" == "$GITHUB_SHA" ]] || {
        echo 'Main advanced after this build; refusing to publish an outdated APK.' >&2
        exit 1
    }
}

require_current_main
python3 - <<'PY'
import hashlib,json,os,pathlib
p=pathlib.Path('dist')
sha=lambda path: hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
manifest=json.loads((p/'beta-build.json').read_text())
apk=p/'trasc-server-android-beta-0.6.35.apk'
assert manifest['commit']==os.environ['GITHUB_SHA']
assert manifest['file']==apk.name and manifest['sha256']==sha(apk)
assert manifest['bytes']==apk.stat().st_size
assert manifest['version']=='0.6.35' and manifest['version_code']==84
assert manifest['application_id']=='io.github.russianranger.trasc.preview'
assert manifest['signing_certificate_sha256']==pathlib.Path('docs/preview-signing.sha256').read_text().strip()
assert manifest['native_payload_reused_from']=='0.6.34'
assert manifest['source_archive_sha256']==sha(p/'launcher-sources.tar.gz')
assert manifest['native_reuse_manifest_sha256']==sha(p/'native-reuse.json')
receipt=json.loads((p/'native-reuse.json').read_text())
assert receipt['baseline_version']=='0.6.34'
assert receipt['baseline_apk_sha256']=='7d787bc90c7c53a73f60c1eb1f79820cbb310d90db8149c5e929512d7971f307'
preview=json.loads((p/'preview-build.json').read_text())
assert preview==dict(manifest,file='trasc-server-android-preview.apk')
assert sha(p/preview['file'])==manifest['sha256']
for channel,names in {
    'beta': (apk.name,'launcher-sources.tar.gz','beta-build.json','native-reuse.json'),
    'preview': ('trasc-server-android-preview.apk','launcher-sources.tar.gz','preview-build.json','native-reuse.json'),
}.items():
    expected={name:{'size':(p/name).stat().st_size,'digest':'sha256:'+sha(p/name)} for name in names}
    (p/'publication'/f'{channel}-expected.json').write_text(json.dumps(expected))
PY

if ! gh api "repos/$repo/git/ref/tags/$tag" > dist/publication/beta-tag.json 2>/dev/null; then
    require_current_main
    gh api --method POST "repos/$repo/git/refs" -f "ref=refs/tags/$tag" -f "sha=$GITHUB_SHA" > /dev/null
    gh api "repos/$repo/git/ref/tags/$tag" > dist/publication/beta-tag.json
fi
python3 - <<'PY'
import json,os,pathlib
obj=json.loads(pathlib.Path('dist/publication/beta-tag.json').read_text())['object']
assert obj['type']=='commit' and obj['sha']==os.environ['GITHUB_SHA'], 'Versioned beta tag belongs to another build'
PY

# Listing also finds an interrupted draft, which the tag endpoint hides.
find_release() {
    gh api --paginate --slurp "repos/$repo/releases?per_page=100" > dist/publication/releases.json
    python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/publication')
matches=[r for page in json.loads((p/'releases.json').read_text()) for r in page if r['tag_name']=='v0.6.35-beta']
assert len(matches)<=1, 'Multiple releases have the beta tag'
if matches:
    (p/'beta-release.json').write_text(json.dumps(matches[0]))
    print(matches[0]['id'])
PY
}
release_id=$(find_release)
if [[ -z "$release_id" ]]; then
    require_current_main
    gh release create "$tag" --draft --prerelease --latest=false --target "$GITHUB_SHA" \
        --title 'TRASC Android 0.6.35 beta' --notes-file "$notes"
    release_id=$(find_release)
fi
[[ "$release_id" =~ ^[0-9]+$ ]]
draft=$(python3 - <<'PY'
import json,os,pathlib
r=json.loads(pathlib.Path('dist/publication/beta-release.json').read_text())
assert r['target_commitish']==os.environ['GITHUB_SHA'], 'Existing beta belongs to another commit'
if not r['draft']:
    assert r['prerelease'], 'Existing named beta is not a prerelease'
    actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
    assert actual==json.loads(pathlib.Path('dist/publication/beta-expected.json').read_text()), 'Published beta bytes differ; refusing to overwrite'
print('true' if r['draft'] else 'false')
PY
)

if [[ "$draft" == 'true' ]]; then
    require_current_main
    gh release upload "$tag" dist/trasc-server-android-beta-0.6.35.apk dist/launcher-sources.tar.gz \
        dist/beta-build.json dist/native-reuse.json --clobber
    gh api "repos/$repo/releases/$release_id" > dist/publication/beta-release.json
    python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/publication')
r=json.loads((p/'beta-release.json').read_text())
assert r['draft'] and r['tag_name']=='v0.6.35-beta'
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.loads((p/'beta-expected.json').read_text()), 'Uploaded beta differs from qualified artifact'
PY
    require_current_main
    gh release edit "$tag" --draft=false --prerelease=true --latest=false --notes-file "$notes"
fi
gh api "repos/$repo/releases/$release_id" > dist/publication/beta-release.json
python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/publication')
r=json.loads((p/'beta-release.json').read_text())
assert not r['draft'] and r['prerelease'] and r['tag_name']=='v0.6.35-beta'
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.loads((p/'beta-expected.json').read_text())
PY

require_current_main
if ! gh release view preview >/dev/null 2>&1; then
    gh release create preview --prerelease --latest=false --target "$GITHUB_SHA" \
        --title 'TRASC Android preview' --notes-file docs/preview-notes.md
fi
gh api --method PATCH "repos/$repo/git/refs/tags/preview" -f "sha=$GITHUB_SHA" -F force=true > /dev/null
gh release upload preview dist/trasc-server-android-preview.apk dist/launcher-sources.tar.gz \
    dist/preview-build.json dist/native-reuse.json --clobber
require_current_main
gh release edit preview --notes-file docs/preview-notes.md
gh api "repos/$repo/releases/tags/preview" > dist/publication/preview-release.json
gh api "repos/$repo/git/ref/tags/preview" > dist/publication/preview-tag.json
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path('dist/publication')
r=json.loads((p/'preview-release.json').read_text())
assert not r['draft'] and r['tag_name']=='preview'
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
for name,expected in json.loads((p/'preview-expected.json').read_text()).items():
    assert actual[name]==expected, 'Preview asset differs: '+name
obj=json.loads((p/'preview-tag.json').read_text())['object']
assert obj['type']=='commit' and obj['sha']==os.environ['GITHUB_SHA']
print('Published verified 0.6.35 beta and matching compatibility preview from current main.')
PY
