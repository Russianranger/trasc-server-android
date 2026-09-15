#!/usr/bin/env bash
# Exercise the GLES forwarding path with real Wine/D3D/model/input probes on ARM64.
set -euo pipefail
cd "$(dirname "$0")/.."
task_dir="$PWD/runtime-work/client-virgl"
mkdir -p "$task_dir/tmp" "$task_dir/logs" "$task_dir/client"
cp runtime-work/client-test/client/eqgame.exe runtime-work/client-test/client/dinput8.dll runtime-work/client-test/client/models.exe runtime-work/client-test/client/textures.exe "$task_dir/client/"
LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe runtime-work/native/virgl-host/out/vtest/virgl_test_server \
    --use-egl-surfaceless --use-gles --multi-clients --socket-path "$task_dir/tmp/.virgl_test" > "$task_dir/logs/client-gpu.log" 2>&1 &
graphics_pid=$!
trap 'kill "$graphics_pid" 2>/dev/null || true; wait "$graphics_pid" 2>/dev/null || true' EXIT
for i in $(seq 1 100); do test -S "$task_dir/tmp/.virgl_test" && break; sleep .1; done
test -S "$task_dir/tmp/.virgl_test"
docker run --rm --network none \
    -e TRASC_TEST_RENDERER=virgl \
    -e MESA_GL_VERSION_OVERRIDE=2.1 -e MESA_GLSL_VERSION_OVERRIDE=120 \
    -v "$PWD/backend-assets/wined3d.dll:/opt/wine/lib/wine/i386-windows/wined3d.dll:ro" \
    -v "$PWD/backend/wineserver:/opt/wine/bin/wineserver:ro" \
    -v "$PWD/backend:/opt/trasc-client:ro" -v "$PWD/tests:/tests:ro" \
    -v "$task_dir/client:/client" -v "$task_dir/logs:/logs" -v "$task_dir/tmp:/tmp" \
    -v "$PWD/runtime-work/directx-test/output/directx:/directx:ro" \
    trasc-client:1 python3 /tests/integration_client.py
# The negative control uses the identical published runtime without our DLL
# overlay. Restricting test GL to 2.1 reproduces the actual Thor capability path.
for variant in original patched; do
    expected=42
    overlay=()
    if [ "$variant" = patched ]; then
        expected=0
        overlay=(-v "$PWD/backend-assets/wined3d.dll:/opt/wine/lib/wine/i386-windows/wined3d.dll:ro")
    fi
    mkdir -p "$task_dir/logs/$variant"
    docker run --rm --network none "${overlay[@]}" \
        -e MESA_GL_VERSION_OVERRIDE=2.1 -e MESA_GLSL_VERSION_OVERRIDE=120 \
        -v "$PWD/backend/wineserver:/opt/wine/bin/wineserver:ro" \
        -v "$PWD/backend:/opt/trasc-client:ro" -v "$PWD/tests:/tests:ro" \
        -v "$task_dir/client:/client" -v "$task_dir/logs/$variant:/logs" -v "$task_dir/tmp:/tmp" \
        -v "$PWD/runtime-work/directx-test/output/directx:/directx:ro" \
        trasc-client:1 python3 /tests/legacy_shader.py "$expected"
done
