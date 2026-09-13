#!/usr/bin/env bash
set -euo pipefail
key_path="${TRASC_PREVIEW_KEYSTORE:?Set the explicit preview keystore path}"
if [ ! -f "$key_path" ]; then
    if [ -f docs/preview-signing.sha256 ]; then
        echo 'Preview signing key was not restored. Stop publication; recover the key instead of generating an incompatible update.' >&2
        exit 1
    fi
    mkdir -p "$(dirname "$key_path")"
    keytool -genkeypair -keystore "$key_path" -storepass android -keypass android \
        -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \
        -dname 'CN=TRASC Android Preview,O=Russianranger,C=US'
fi
chmod 600 "$key_path"
mkdir -p dist
keytool -exportcert -keystore "$key_path" -storepass android -alias androiddebugkey \
    | sha256sum | cut -d ' ' -f1 > dist/preview-signing.sha256
if [ -f docs/preview-signing.sha256 ]; then
    diff -u docs/preview-signing.sha256 dist/preview-signing.sha256
fi
