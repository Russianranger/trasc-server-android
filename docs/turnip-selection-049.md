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
builds upstream Mesa 26.0.0 using the same Debian runtime ABI, with pinned
glslang 15.1.0 and CMake 3.31.6 build tools. Debian bookworm's glslang12.0 is
too old for Mesa26's shaders, and its CMake3.25 cannot configure glslang15.1.
No new runtime LLVM dependency is introduced.

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

Published from2276f3497e1062c37aae31a5c4308a50f8cd57ad after all six jobs passed
in [run35148927421](https://github.com/Russianranger/trasc-server-android/actions/runs/35148927421).
The public APK/source/build manifest match the verified candidate. Exact
artifact hashes are recorded in HANDOFF.md. Physical-device acceptance is pending.

## Device follow-up: 2026-09-16

The user reports corrupt names on the first launch, correct names after fully
exiting/relaunching the client, continued success after exiting/reopening the
app, and correct names on the fallback driver too. Performance feels better
on26.0.0. No video accompanies these two bundles: visual correctness is the
user's observation, while the loaded drivers/cache activity below are verified
from the logs. This supersedes the pending initial device comparison above.

| Bundle / session | Start UTC | Loaded Mesa | Wine prefix | Until game launch request | DXVK state cache |
| --- | --- | --- | --- | --- | --- |
| logs-4784291699000747576(1).zip / previous | 21:23:13 | 26.0.0 | update,43.958s | 47.792s | absent, created, then22 entries |
| same / current | 21:33:38 | 26.0.0 | reuse,5.627s | 8.329s |22, later37 entries |
| logs-8112434176634700339.zip / previous | 21:48:26 | 26.0.0 | reuse,5.425s | 8.049s |37 entries |
| same / current | 21:51:43 | 24.3.4 | reuse,5.430s | 8.038s |7, later35 entries |

`client-state[.previous].json`, `client-vulkan[.previous].log`, and
`eqgame_d3d9[.previous].log` agree on the versions. Both drivers use Adreno740,
not a software fallback. The first26 log explicitly reports no state cache
file and creation of one; subsequent runs read it. Counts reflect successive
D3D device initializations, not numbers of compiled shaders or a complete
inventory of Mesa's cache. No cache-hit or per-shader compilation trace was
captured, and the logs cannot identify the exact frame when names recovered.

[DXVK2.5.3's documentation](https://github.com/doitsujin/dxvk/blob/v2.5.3/README.md#state-cache)
explains that its state cache allows shader recompilation ahead of time on
later runs and generally reduces stutter. That does not establish malformed
geometry as normal compilation behavior or prove causation here. TRASC's
`cache_paths()` keeps separate DXVK and Mesa cache directories for24.3.4 and
26.0.0; the newer driver's cache is not copied into the fallback's. The shared
Wine prefix also changed from update to reuse. Cache warm-up, persistent
client/prefix state or timing remain hypotheses; no specific cause is proven.

All four sessions retain Balanced, exact0.4.2 NPC compatibility, native
dinput8/model helpers, DXVK2.5.3 and1280x720 fullscreen. Both installed spell
tables remain40,914 rows, max43,019, SHA256
`034b5635049a9ef6e549f3f7d5b32f265a386d82a3fd3e8286b04d44b58a5e77`.
No data re-export or helper replacement occurred. Nonzero audio samples are
present, but audio logs alone cannot attribute them to a particular spell.

The first26 session has a late `virtual_setup_exception stack overflow` at
Wine timestamp273462.841, address0x7b03ade5. The game log ends around21:31:39UTC
after a graphics-device reinitialization, following camping and character
selection. Android presentation records then show a sustained lack of new
frames until Stop. This is consistent with the client stalling after that
exception. No call stack identifies its origin, and it occurs well after the
initial name screen; it is not proof of the name bug's cause. The three later
sessions have no stack-overflow/device-lost/compiler-failure report, though
gamma-ramp, MIDI, and Wine shutdown warnings remain. The missing
SkinMeshCBS1_VSB.fxo effect warning appears in both failing and reportedly
working sessions, so its presence alone does not explain the name issue.

Presentation samples report thermal_status0 and power_save=false in all four
sessions. These are Android reports, not proof of unchanged clocks. Wine FPS
traces include menus, loading, play and device resets; the later26 run only
reaches character selection, whereas the fallback enters the world. Do not
turn their whole-session averages into a driver speed-up percentage. The
in-app display target remains30FPS even when Wine reports higher present rates.

Keep26.0.0 selected and preserve caches/prefix. One full device reboot followed
by ordinary play, camping and relaunch is the next useful stability check.
If names corrupt or the client hangs again, export logs promptly (at most one
subsequent launch, because only one previous session is retained). Avoid
clearing known-working state merely to prove a hypothesis. No new APK or app
behavior change accompanies this evidence update.
