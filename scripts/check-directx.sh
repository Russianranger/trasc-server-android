#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
task_dir="$PWD/runtime-work/directx-test"
mkdir -p "$task_dir/classes" "$task_dir/output"
archive="$task_dir/directx_Jun2010_redist.exe"
if [ ! -f "$archive" ]; then
    curl --fail --location --retry 3 -o "$archive" https://download.microsoft.com/download/8/4/A/84A35BF1-DAFE-4AE8-82AF-AD2AE20B6B14/directx_Jun2010_redist.exe
fi
echo "053f76dcbb28802e23341b6a787e3b0791c0fa5c8d4d011b1044172dbf89c73b  $archive" | sha256sum --check
bash scripts/build-cabextract.sh host
javac -d "$task_dir/classes" tests/java/android/system/Os.java \
    app/src/main/java/io/github/russianranger/trasc/TarExtractor.java \
    app/src/main/java/io/github/russianranger/trasc/DirectXInstaller.java \
    tests/java/io/github/russianranger/trasc/DirectXHostTest.java
java -cp "$task_dir/classes" io.github.russianranger.trasc.DirectXHostTest "$archive" \
    "$PWD/runtime-work/native/cabextract-host/cabextract" "$task_dir/output/directx"
