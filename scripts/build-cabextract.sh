#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
target="${1:-android}"
native="$repo_root/runtime-work/native"
mkdir -p "$native"
archive="$native/cabextract-1.11.tar.gz"
if [ ! -f "$archive" ]; then curl --fail --location --retry 3 https://www.cabextract.org.uk/cabextract-1.11.tar.gz -o "$archive"; fi
echo "b5546db1155e4c718ff3d4b278573604f30dd64c3c5bfd4657cd089b823a3ac6  $archive" | sha256sum --check
build="$native/cabextract-$target"
mkdir -p "$build"
tar --no-same-owner -xzf "$archive" --strip-components=1 -C "$build"
cd "$build"
if [ "$target" = android ]; then
    ndk_path="${ANDROID_NDK_HOME:-${ANDROID_HOME:?Set ANDROID_HOME}/ndk/27.2.12479018}"
    llvm="$ndk_path/toolchains/llvm/prebuilt/linux-x86_64/bin"
    export CC="$llvm/aarch64-linux-android26-clang" AR="$llvm/llvm-ar" RANLIB="$llvm/llvm-ranlib"
    export CFLAGS="-O2 -fPIE" LDFLAGS="-pie -Wl,-z,max-page-size=16384"
    ./configure --host=aarch64-linux-android --quiet
else
    ./configure --quiet
fi
make -j2
if [ "$target" = android ]; then
    output="$repo_root/app/src/main/jniLibs/arm64-v8a/libcabextract.so"
    mkdir -p "$(dirname "$output")"
    cp cabextract "$output"
    "$llvm/llvm-strip" "$output"
    "$llvm/llvm-readelf" -h -l -d "$output"
fi
