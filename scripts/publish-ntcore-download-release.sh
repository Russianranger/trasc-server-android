#!/usr/bin/env bash
# Publish qualified current-main bytes as a discoverable latest release.
set -euo pipefail
[[ "${GITHUB_REPOSITORY:?}" == 'Russianranger/trasc-server-android' ]]
[[ "${GITHUB_REF:?}" == 'refs/heads/main' ]]
[[ "${GITHUB_EVENT_NAME:?}" == 'push' || "$GITHUB_EVENT_NAME" == 'workflow_dispatch' ]]
[[ "${GITHUB_SHA:?}" =~ ^[0-9a-f]{40}$ ]]
repo="$GITHUB_REPOSITORY"
tag='v0.6.40'
title='TRASC Android 0.6.40'
notes='docs/release-0640-notes.md'
mkdir -p dist/publication

require_current_main() {
    local current_main
    current_main=$(gh api "repos/$repo/git/ref/heads/main" --jq '.object.sha')
    [[ "$current_main" == "$GITHUB_SHA" ]] || {
        echo 'Main advanced after this build; refusing to publish an outdated APK.' >&2
        exit 1
    }
}

# Read a known release directly by ID. Creation returns the ID, so eventual
# consistency in the release list cannot strand a newly created draft.
read_release() {
    local release_id="$1" destination="$2" delay
    for delay in 1 2 4 8 0; do
        if gh api "repos/$repo/releases/$release_id" > "$destination.tmp"; then
            mv "$destination.tmp" "$destination"
            return
        fi
        [[ "$delay" == 0 ]] || sleep "$delay"
    done
    echo "Cannot read release $release_id after bounded retries." >&2
    return 1
}

require_current_main
python3 - <<'PY'
import hashlib,json,os,pathlib,re
p=pathlib.Path('dist')
sha=lambda path: hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
manifest=json.loads((p/'release-build.json').read_text())
apk=p/'trasc-server-android-0.6.40.apk'
assert manifest['commit']==os.environ['GITHUB_SHA']
assert manifest['file']==apk.name and manifest['sha256']==sha(apk)
assert manifest['bytes']==apk.stat().st_size
assert manifest['version']=='0.6.40' and manifest['version_code']==89
assert manifest['application_id']=='io.github.russianranger.trasc.preview'
certificate=pathlib.Path('docs/preview-signing.sha256').read_text().strip()
assert manifest['signing_certificate_sha256']==certificate
report=(p/'apk-signing.txt').read_text()
assert re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]+)',report).group(1)==certificate
assert manifest['native_payload_reused_from']=='0.6.36'
assert manifest['source_archive_sha256']==sha(p/'launcher-sources.tar.gz')
assert manifest['native_reuse_manifest_sha256']==sha(p/'native-reuse.json')
receipt=json.loads((p/'native-reuse.json').read_text())
assert receipt['baseline_version']=='0.6.36'
assert receipt['baseline_apk_sha256']=='cca20ad712e14f9ba600a6921b7913d4b8e14711308b3b65f6d09ab9acfa3c4b'
preview=json.loads((p/'preview-build.json').read_text())
assert preview==dict(manifest,file='trasc-server-android-preview.apk')
assert sha(p/preview['file'])==manifest['sha256']
for channel,names in {
    'release': (apk.name,'launcher-sources.tar.gz','release-build.json','native-reuse.json'),
    'preview': ('trasc-server-android-preview.apk','launcher-sources.tar.gz','preview-build.json','native-reuse.json'),
}.items():
    expected={name:{'size':(p/name).stat().st_size,'digest':'sha256:'+sha(p/name)} for name in names}
    (p/'publication'/f'{channel}-expected.json').write_text(json.dumps(expected))
PY

if ! gh api "repos/$repo/git/ref/tags/$tag" > dist/publication/release-tag.json 2>/dev/null; then
    require_current_main
    gh api --method POST "repos/$repo/git/refs" -f "ref=refs/tags/$tag" -f "sha=$GITHUB_SHA" > /dev/null
    gh api "repos/$repo/git/ref/tags/$tag" > dist/publication/release-tag.json
fi
python3 - <<'PY'
import json,os,pathlib
obj=json.loads(pathlib.Path('dist/publication/release-tag.json').read_text())['object']
assert obj['type']=='commit' and obj['sha']==os.environ['GITHUB_SHA'], 'Versioned release tag belongs to another build'
PY

if ! gh api "repos/$repo/releases/tags/$tag" > dist/publication/release.json 2>/dev/null; then
    # The tag endpoint hides drafts; listing allows interrupted runs to resume.
    gh api --paginate --slurp "repos/$repo/releases?per_page=100" > dist/publication/releases.json
    python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/publication')
matches=[r for page in json.loads((p/'releases.json').read_text()) for r in page if r['tag_name']=='v0.6.40']
assert len(matches)<=1, 'Multiple releases have the version tag'
if matches:
    (p/'release.json').write_text(json.dumps(matches[0]))
else:
    (p/'release.json').unlink(missing_ok=True)
PY
fi
if [[ ! -s dist/publication/release.json ]]; then
    require_current_main
    gh api --method POST "repos/$repo/releases" -f "tag_name=$tag" -f "target_commitish=$GITHUB_SHA" \
        -f "name=$title" -f "body=$(cat "$notes")" -F draft=true -F prerelease=false -f make_latest=false \
        > dist/publication/release.json
fi
release_id=$(python3 - <<'PY'
import json,os,pathlib
r=json.loads(pathlib.Path('dist/publication/release.json').read_text())
assert r['tag_name']=='v0.6.40' and r['target_commitish']==os.environ['GITHUB_SHA'], 'Existing release belongs to another commit'
assert isinstance(r['id'],int) and r['id']>0
print(r['id'])
PY
)
read_release "$release_id" dist/publication/release.json
draft=$(python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/publication')
r=json.loads((p/'release.json').read_text())
if not r['draft']:
    assert not r['prerelease'], 'Existing version is a prerelease'
    actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
    assert actual==json.loads((p/'release-expected.json').read_text()), 'Published bytes differ; refusing to overwrite'
print('true' if r['draft'] else 'false')
PY
)

if [[ "$draft" == true ]]; then
    # Operate on draft assets by release ID instead of relying on draft discovery.
    python3 - <<'PY' > dist/publication/delete-assets.txt
import json,pathlib
r=json.loads(pathlib.Path('dist/publication/release.json').read_text())
assert r['draft']
for a in r['assets']:
    print(a['id'])
PY
    while read -r asset_id; do
        [[ "$asset_id" =~ ^[0-9]+$ ]]
        require_current_main
        gh api --method DELETE "repos/$repo/releases/assets/$asset_id" > /dev/null
    done < dist/publication/delete-assets.txt
    for name in trasc-server-android-0.6.40.apk launcher-sources.tar.gz release-build.json native-reuse.json; do
        require_current_main
        curl --fail --silent --show-error --retry 3 \
            -H "Authorization: Bearer ${GH_TOKEN:?}" -H 'Content-Type: application/octet-stream' \
            --data-binary "@dist/$name" "https://uploads.github.com/repos/$repo/releases/$release_id/assets?name=$name" > /dev/null
    done
    read_release "$release_id" dist/publication/release.json
    python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/publication')
r=json.loads((p/'release.json').read_text())
assert r['draft'] and r['tag_name']=='v0.6.40'
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.loads((p/'release-expected.json').read_text()), 'Uploaded release differs from qualified artifact'
PY
fi
require_current_main
gh api --method PATCH "repos/$repo/releases/$release_id" -F draft=false -F prerelease=false -f make_latest=true \
    -f "name=$title" -f "body=$(cat "$notes")" > /dev/null
read_release "$release_id" dist/publication/release.json
gh api "repos/$repo/releases/latest" > dist/publication/latest-release.json
python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/publication')
r=json.loads((p/'release.json').read_text())
assert not r['draft'] and not r['prerelease'] and r['tag_name']=='v0.6.40'
assert json.loads((p/'latest-release.json').read_text())['id']==r['id'], 'Release is not discoverable as latest'
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
assert actual==json.loads((p/'release-expected.json').read_text())
PY

require_current_main
if ! gh release view preview >/dev/null 2>&1; then
    gh release create preview --prerelease --latest=false --target "$GITHUB_SHA" \
        --title 'TRASC Android 0.6.40 compatibility preview' --notes-file docs/preview-notes.md
fi
gh api --method PATCH "repos/$repo/git/refs/tags/preview" -f "sha=$GITHUB_SHA" -F force=true > /dev/null
gh release upload preview dist/trasc-server-android-preview.apk dist/launcher-sources.tar.gz \
    dist/preview-build.json dist/native-reuse.json --clobber
require_current_main
gh release edit preview --prerelease=true --latest=false --title 'TRASC Android 0.6.40 compatibility preview' \
    --notes-file docs/preview-notes.md
gh api "repos/$repo/releases/tags/preview" > dist/publication/preview-release.json
gh api "repos/$repo/git/ref/tags/preview" > dist/publication/preview-tag.json
gh api "repos/$repo/releases/latest" > dist/publication/latest-release.json
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path('dist/publication')
r=json.loads((p/'preview-release.json').read_text())
assert not r['draft'] and r['prerelease'] and r['tag_name']=='preview'
actual={a['name']:{'size':a['size'],'digest':a['digest']} for a in r['assets']}
for name,expected in json.loads((p/'preview-expected.json').read_text()).items():
    assert actual[name]==expected, 'Preview asset differs: '+name
obj=json.loads((p/'preview-tag.json').read_text())['object']
assert obj['type']=='commit' and obj['sha']==os.environ['GITHUB_SHA']
assert json.loads((p/'latest-release.json').read_text())['tag_name']=='v0.6.40', 'Preview displaced latest release'
print('Published verified 0.6.40 latest release and matching compatibility preview from current main.')
PY
