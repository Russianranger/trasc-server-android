#!/usr/bin/env bash
# Publish the user-authorized named beta only after the main build's release gates.
set -euo pipefail
version=$(sed -n "s/.*versionName '\([^']*\)'.*/\1/p" app/build.gradle)
if [[ "$version" != '0.6' ]]; then exit 0; fi
if [[ "${GITHUB_REF:?}" != 'refs/heads/main' || "${GITHUB_EVENT_NAME:?}" == 'pull_request' ]]; then
    echo 'Beta publication requires the verified main build.' >&2
    exit 1
fi
if gh release view v0.6 --json isDraft,targetCommitish > dist/existing-beta-06.json 2>/dev/null; then
    # Published named releases are immutable. Later main builds keep using preview.
    if [[ "$(python3 -c 'import json; print(json.load(open("dist/existing-beta-06.json"))["isDraft"])')" == 'False' ]]; then
        echo 'Beta 0.6 is already published; retaining its existing tag and assets.'
        exit 0
    fi
    python3 - <<'PY'
import json,os
assert json.load(open('dist/existing-beta-06.json'))['targetCommitish']==os.environ['GITHUB_SHA'], 'Existing draft belongs to a different commit'
PY
else
    rm -f dist/existing-beta-06.json
fi
python3 - <<'PY'
import hashlib,json,os,pathlib,shutil
folder=pathlib.Path('dist')
manifest=json.loads((folder/'preview-build.json').read_text())
apk=folder/'trasc-server-android-preview.apk'
source=folder/'dist/launcher-sources.tar.gz'
digest=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
assert manifest['commit']==os.environ['GITHUB_SHA']
assert manifest['version']=='0.6' and manifest['application_id']=='io.github.russianranger.trasc.preview'
assert manifest['signing_certificate_sha256']==pathlib.Path('docs/preview-signing.sha256').read_text().strip()
assert manifest['sha256']==digest(apk)
named=folder/'trasc-server-android-beta-0.6.apk'
shutil.copyfile(apk,named)
manifest.update(file=named.name,release='Beta version 0.6',version_code=49,bytes=named.stat().st_size,
                source_archive_sha256=digest(source),build_run=int(os.environ['GITHUB_RUN_ID']))
(folder/'beta-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
if [[ ! -f dist/existing-beta-06.json ]]; then
    gh release create v0.6 --draft --target "$GITHUB_SHA" --title 'Beta version 0.6' --notes-file docs/beta-06-release.md
fi
gh release upload v0.6 dist/trasc-server-android-beta-0.6.apk dist/dist/launcher-sources.tar.gz dist/beta-build.json --clobber
gh release edit v0.6 --draft=false --prerelease=false --latest --notes-file docs/beta-06-release.md
