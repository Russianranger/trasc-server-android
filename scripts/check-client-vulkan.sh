#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Only CI gains Lavapipe. The shipped runtime and APK never select it as Turnip.
docker build -t trasc-vulkan-test:1 - <<'DOCKER'
FROM trasc-client:1
RUN apt-get update && apt-get install -y --no-install-recommends mesa-vulkan-drivers && apt-get clean && rm -rf /var/lib/apt/lists/*
DOCKER
mkdir -p runtime-work/client-vulkan/client runtime-work/client-vulkan/logs
cp runtime-work/client-test/client/{command-keys.txt,eqgame.exe,dinput8.dll,textures.exe,models.exe,audio.exe} runtime-work/client-vulkan/client/
# Check dependency loading separately so a missing library cannot masquerade as
# the intended rejection of a host with no Qualcomm KGSL device.
docker run --rm --network none -v "$PWD/backend:/opt/trasc-client:ro" trasc-client:1 python3 -c '
import ctypes,json,os,pathlib,subprocess,sys
sys.path.insert(0,"/opt/trasc-client")
import client_vulkan
p=pathlib.Path("/opt/trasc-client");client_vulkan.verify_bundle(p)
assert not pathlib.Path("/dev/kgsl-3d0").exists(), "This CI negative control requires a host without Qualcomm KGSL"
for version, filename in client_vulkan.DRIVERS.items():
    # Separate loader processes prevent symbols from one Mesa build masking
    # missing dependencies in the other. Use the unchanged published runtime.
    subprocess.run([sys.executable,"-c","import ctypes,sys; ctypes.CDLL(sys.argv[1])",str(p/filename)],check=True)
    icd=pathlib.Path("/tmp/turnip.json");icd.write_text(json.dumps({"file_format_version":"1.0.0","ICD":{"library_path":str(p/filename),"api_version":"1.3.0"}}))
    r=subprocess.run([str(p/"vulkan-probe")],env=dict(os.environ,VK_ICD_FILENAMES=str(icd),VK_DRIVER_FILES=str(icd),MESA_VK_WSI_DEBUG="sw"),capture_output=True,text=True,timeout=30)
    print(r.stderr,flush=True)
    assert r.returncode==1 and "Cannot open /dev/kgsl-3d0 for Turnip: No such file or directory" in r.stderr
    print("PASS: Turnip "+version+" dependencies load, unavailable Qualcomm hardware is rejected",flush=True)
' 2>&1 | tee runtime-work/client-vulkan/logs/turnip-unavailable.log
docker run --rm --network none \
    -e TRASC_TEST_RENDERER=turnip -e TRASC_TEST_ALLOW_SOFTWARE_VULKAN=1 \
    -e TRASC_TEST_VULKAN_ICD=/usr/share/vulkan/icd.d/lvp_icd.aarch64.json \
    -v "$PWD/backend-assets/wined3d.dll:/opt/wine/lib/wine/i386-windows/wined3d.dll:ro" \
    -v "$PWD/backend/wineserver:/opt/wine/bin/wineserver:ro" \
    -v "$PWD/backend:/opt/trasc-client:ro" -v "$PWD/tests:/tests:ro" \
    -v "$PWD/runtime-work/client-vulkan/client:/client" -v "$PWD/runtime-work/client-vulkan/logs:/logs" \
    -v "$PWD/runtime-work/directx-test/output/directx:/directx:ro" \
    trasc-vulkan-test:1 python3 /tests/integration_client.py
vulkan_test_container=$(docker create trasc-vulkan-test:1)
trap 'docker rm -f "$vulkan_test_container" >/dev/null 2>&1 || true' EXIT
docker export "$vulkan_test_container" -o runtime-work/vulkan-test-rootfs.tar
python3 scripts/pack-runtime.py runtime-work/vulkan-test-rootfs.tar runtime-work/vulkan-test-rootfs.tar.gz
TRASC_TEST_ROOTFS="$PWD/runtime-work/vulkan-test-rootfs.tar.gz" bash scripts/check-client-proot.sh turnip
