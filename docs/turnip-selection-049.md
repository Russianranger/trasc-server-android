# 0.4.9: selectable Turnip drivers

The user cannot switch the working ARM64EC Winlator environment to Box64.
The earlier source-based suggestion does not apply to that installed build;
it is withdrawn. The user requests a different Turnip driver or driver selection.

## Scope

Client -> Graphics -> Turnip + DXVK now exposes **Turnip driver**:

- **24.3.4 (current / fallback)** is the default and preserves the previous driver configuration.
- **26.0.0 (comparison)** is an additional upstream Mesa build for TRASC's
  existing ARM64 glibc/KGSL/X11 runtime. It is not the exact Winlator R5 build.

The selected version is saved with launch options and appears in session
status. Stop the client to enable selection, then relaunch. Both drivers are
packaged in the APK, so a runtime download, client reimport, prefix repair,
or export is unnecessary. No automatic fallback disguises a failed driver.
An error points to 24.3.4 or VirGL for recovery.

Winlator-style Android/bionic driver ZIPs are not directly compatible with the
glibc Vulkan loader inside TRASC's Linux runtime. This release provides two
compatible choices; it does **not** implement arbitrary ZIP import or change
to an Android-native rendering path. It does not claim to fix character names
until the physical-device comparison succeeds.

DXVK 2.5.3, Wine/Box64, NPC compatibility, audio and spell data are unchanged.
Keep the successful eight-ID spell exclusion enabled. No server changes are
needed. 26.0.0 gets separate Mesa and DXVK cache directories; switching back
retains the baseline cache. A new driver may take longer on its first launch.

## Build and evidence

The baseline recipe remains in `vulkan/Dockerfile`. `vulkan/Dockerfile.26`
builds upstream Mesa 26.0.0 using the same Debian runtime ABI, with a pinned
glslang 15.1.0 build because Debian bookworm's 12.0 compiler is too old for
Mesa 26's shaders. No new runtime LLVM dependency is introduced.

- [Mesa 26.0.0 official release checksum](https://docs.mesa3d.org/relnotes/26.0.0.html):
  `2a44e98e64d5c36cec64633de2d0ec7eff64703ee25b35364ba8fcaa84f33f72`.
- Khronos glslang 15.1.0 official source archive SHA256:
  `4bdcd8cdb330313f0d4deed7be527b0ac1c115ff272e492853a6e98add61b4bc`.
- Both Mesa sources, glslang source and exact recipes accompany the APK in
  `launcher-sources.tar.gz` -> `vulkan-sources.tar.gz`.

The bundle manifest pins both driver filenames/hashes and rejects missing,
changed, non-ARM64 or unexpected files. The request accepts only the two
bundled versions. The ICD points directly to the selected file. On the device,
the preflight must report Qualcomm/Turnip hardware, Vulkan >=1.3, three
presented frames, and the selected Mesa `driverVersion`; software fallback and
a different loaded Mesa version are rejected. Logs retain requested version,
selected file/hash, and separately observed driver version/info.

CI has no Qualcomm GPU. It independently loads each real ARM64 driver in the
unchanged client runtime to catch dependency failures, then retains the exact
missing-KGSL negative control for each. Existing real PE32/DXVK tests use
explicit CI-only Lavapipe as before; these do not validate Mesa26 rendering on
the Thor. Unit tests cover switching/reverting ICD/cache paths, invalid choices,
changed driver bytes and observed-version mismatch. Browser coverage checks
selection, request propagation, saved restoration, running-state lock and
VirGL applicability. Existing graphics/audio/input/model gates remain strict.

## Device comparison

1. Stop the client and runtime; update in place to 0.4.9, then start the runtime/server.
2. Keep Turnip + DXVK, Balanced CPU, exact0.4.2 NPC compatibility, native helpers,
   1280x720 fullscreen, and the successful spell exclusion. Leave verbose logs off.
3. Select **Turnip driver -> 26.0.0** and launch. Watch the character-selection
   name/class/zone labels for 30 seconds. If stable, enter the same area and
   inspect NPC models; confirm Skin Like Wood and Minor Healing still work.
4. Stop and export Logs before launching another session. If loading or FPS
   needs comparison, include a second run with the same driver to warm its cache.
5. If labels or models regress, stop, select **24.3.4**, and relaunch. Export a
   separate log after that comparison. Keep the better driver selected.

Build/publication status and exact artifact hashes are recorded in HANDOFF.md.
