TRASC Server Android **0.4.8 — reversible spell exclusion test**

The Winlator comparison also has silent spells, according to the user. This build adds the authorized, explicit test of the eight high spell IDs. It does not claim that spell effects or names are fixed until tested on the device.

1. Stop the embedded client. Install 0.4.8 over the existing app and open the server runtime. No runtime download, client reimport, prefix repair or repeated export is needed.
2. In **Client → Spell effects comparison**, press **Apply spell exclusion test**. Wait for **Test active · 8 IDs excluded · 40914 rows in each folder** for the currently captured table. This changes only `spells_us.txt` in the imported client's root and Resources, with original-file backups. It validates that the files match and that exactly IDs 50000–50007 are excluded; unexpected data stops the test without replacement.
3. Keep **Turnip + DXVK / Balanced / NPC compatibility (0.4.2 exact) / native dinput8 / native model helpers / 1280×720 fullscreen**. Enable **Sound diagnostics**, leave general verbose diagnostics off, start the server if needed, and launch ROF2.
4. Inspect the character-selection name, then cast **Skin Like Wood** and **Minor Healing**. Record particles and sound separately. Do not use the eight excluded high-ID abilities during this comparison.
5. Stop the client and **Export Logs** before restoring. Then press **Restore full spell files** and wait for confirmation that both originals were restored and verified. Turn Sound diagnostics off for normal play.

Normal **Export & sync client data** and **Prepare** still copy the complete database export. Export, Prepare and client replacement are blocked while this comparison is active. The server database, generated exports, other client files and graphics/audio settings remain unchanged. An interrupted change blocks launch until Restore; cancellation or a replacement error restores both originals. Restore refuses to overwrite unrelated intervening edits or use a damaged backup.

The comparison journal and report are retained in `backups/client-spell-test` and `logs/client-spell-test.json`. Every test launch independently verifies both installed spell files and records their hashes/counts in `client-state.json`, including when general sound diagnostics is off. Original backups are retained after Restore. No additional client asset upload is requested.

---

**Latest device follow-up:** all four requested client files have been supplied and [inspected](client-assets-047.md). Both spell animations have effect and sound references; the actual add-on also contains spell lookups bounded below ID 45,001, strengthening the remaining high-ID compatibility hypothesis. A single backed-up client-only comparison is proposed, pending the user's lifting of the filtering pause. No new APK or verified fix yet. Keep **Load the imported native dinput8.dll** enabled; do not repeat the failed bypass, export or reinstall. No additional file upload is currently requested.

TRASC Server Android **0.4.7 — automatic local client data sync**

**Server → Export & sync client data** generates `spells_us.txt`, `dbstr_us.txt`, `SkillCaps.txt` and `BaseData.txt`, then overwrites every file in **both the imported local client's root and its nested Resources folder**. Existing capitalization is respected, and each original is backed up. The ZIP also contains both sets of files.

Spell filtering is paused at the user's request. All generated data is copied byte-for-byte, including high spell IDs. This also replaces a previously filtered 0.4.6 table with a fresh complete export. The exact table installed during earlier device tests was not captured; this test checks whether synchronizing the files restores effects before pursuing filtering.

1. Stop the client and server runtime. Install 0.4.7 over the existing app, then open the server runtime using the top control.
2. On **Server**, press **Export & sync client data**. Wait for the completion message confirming that both local folders were overwritten. Save the ZIP wherever you prefer, or cancel the ZIP picker: the local copy has already completed. **No manual extraction or additional Prepare step is needed.**
3. Start the server and launch with your existing **Turnip + DXVK / Balanced / NPC compatibility (recommended or 0.4.2 exact) / 1280×720 / Fullscreen** settings. Enable **Sound diagnostics** for this short test; keep general verbose diagnostics off.
4. Cast **Skin Like Wood** and **Minor Healing**, checking particles and sound separately. Check NPC models and the character-selection name. Stop the client, export Logs, then turn Sound diagnostics off for normal play.

Export copies only those four data files; existing login/display settings, native add-on, runtime, prefix and server database remain intact. **Prepare client for this server** still performs one backed-up transaction that also sets the login address and display settings. Export is blocked while the embedded client is running, and launch waits for a pending export to finish. Without an imported local client, export generates only the ZIP and says so.

Backups: `backups/client-setup/<timestamp>-<id>/`, with a manifest of original paths. Cancellation or copy failure restores files already replaced. `logs/client-data-sync.json` records the completed copy, export hashes and backup path; `logs/client-spell-export.json` explicitly records `filter_applied: false`. Opt-in sound diagnostics remains read-only. Its compatibility counts describe a hypothetical filter, not removed installed rows.

This update implements automatic synchronization. Recovery of spell effects and the unresolved name glitch still require the device test above.

---

TRASC Server Android **0.4.4** restores the confirmed NPC rendering settings and improves the next sound/name investigation.

- **NPC compatibility (recommended)** again uses the exact 0.4.2 settings. Existing `compatibility` selections recover automatically; the explicitly named 0.4.2 option remains identical. The failed 0.4.3 experiment is labeled **Direct mapping (0.4.3 comparison)**.
- The working 0.4.3 Android audio bridge is retained. User testing confirms music; missing spell effects are still unresolved.
- **Legacy math accuracy (test)** is a reversible CPU comparison that preserves double-precision x87 intermediates and x86 rounding behavior. It may cost performance; the actual ROF2 name/sound result is unverified.
- **Sound diagnostics (short tests)** traces Windows sound calls without enabling the much heavier general Wine exception traces. Logs remain bounded. Each client launch also records selected sound settings, sound-library presence, loose WAV counts/header formats and unresolved sound references. A file may be packed, so an unresolved loose reference does not automatically mean it is missing.
- Fullscreen/gear controls, TL icon, runtime controls, signing identity and installed files remain intact.

**Two short Thor tests:**
1. Stop the client/runtime and install 0.4.4 over the existing app. No runtime download, prefix repair, reimport or server rebuild.
2. Select **NPC compatibility (recommended)**, **Balanced** CPU, Game audio on and **Sound diagnostics** on. Keep Turnip/1280×720/Fullscreen/Automatic/available cores/native helpers. Leave general Verbose Wine diagnostics off.
3. Watch the character-selection name for 20–30 seconds, then check the same NPCs. In game, turn **Music Volume to 0** and **Sound Volume to 100** to isolate effects. Cast **Skin Like Wood** several times, and test one UI/combat sound. Note whether all effects or only spells are silent. Stop and export Logs immediately.
4. Change only CPU profile to **Legacy math accuracy (test)**. Repeat the same name/NPC/spell test and export a second log bundle. Compare correctness and FPS. Return to Balanced if it makes no difference or slows play.
5. If effects remain silent, try the game's **Sound Realism at 0** once, and report whether that changes anything. This is a separate attenuation test, not a claimed fix. Restore preferred music/realism settings afterward and turn Sound diagnostics off for normal play.

Send the two short videos/logs labeled **Balanced** and **Legacy math accuracy**. The new evidence should distinguish missing/disabled sound resources, Windows 3D buffer failures, and CPU translation behavior. Audible spell effects and the real ROF2 label remain device acceptance items.

[Evidence and implementation](audio-and-labels-044.md).

---

TRASC Server Android **0.4.3** addresses audio startup and the animated character-name regression.

- **Audio startup:** align Android's write buffer with Wine's queue and lower the startup threshold on Android 12+. This removes a concrete stall when Android waits for more frames than Wine can supply. New bounded diagnostics record actual buffer sizes, playback progress, nonzero samples and underruns.
- **NPC + name compatibility:** retains strict shader math and sampler handling, but restores live dynamic vertex-buffer updates for animated labels. The exact **NPC compatibility (0.4.2)** mode remains available if the model issue returns; **Standard** also remains available.
- The user confirmed that 0.4.2 NPC compatibility fixes models on the Thor. The audio/name changes still require a device check. Older MIDI music synthesis remains pending.
- Fullscreen 1280×720, gear controls, the TL icon, top runtime controls, imported files and installed runtimes are retained.

**Test on Thor:**
1. Stop the client and server runtime; install 0.4.3 over the existing app. No runtime download, prefix repair, reimport or rebuild is needed.
2. Start runtime from the top bar, then Server → Start server. Keep Turnip + DXVK /1280×720 /Fullscreen /Balanced CPU /Automatic runtime /available cores and native helpers. Keep verbose logging and shadows off. Select **NPC + name compatibility** and enable **Game audio**. Your last exported run was Standard, so explicitly select the new compatibility option.
3. At character selection, watch the yellow character-name/class/zone labels for 30 seconds while the character animates. Then enter the world and check the same NPCs that previously flickered. Note FPS.
4. Raise Android media volume and the game's sound sliders; test a spell, combat or other known sound effect. Test again after a complete client stop/relaunch. A silent MIDI music track alone does not test this audio path.
5. Stop the client and export Logs immediately. Send a short video and state whether sound, names and NPC models are correct. If models regress, compare **NPC compatibility (0.4.2)** after a relaunch and export both sessions. If audio is still silent, the new log records whether PCM arrives and whether Android's playback head advances; avoid prefix repair before collecting it.

[Implementation and evidence](audio-and-labels-043.md).

---

TRASC Server Android **0.4.2** adds **Android game audio**, an **NPC rendering comparison**, top runtime controls and a fantasy **TL** launcher icon.

- **Start runtime / Stop runtime** and status stay near the top across all tabs. Stop uses the existing clean server/database shutdown.
- **Game audio** is enabled by default and routes Wine PCM/DirectSound playback to Android media output. Use the device volume buttons. Legacy MIDI music synthesis is still pending.
- **NPC rendering → NPC compatibility** enables stricter legacy shader and buffer handling for Turnip. **Standard (0.4.1 behavior)** remains available. The exact NPC flicker is not yet confirmed fixed on the Thor.
- The 1280×720 fullscreen display and gear menu are retained, along with the installed runtime, client files, Wine prefix, DirectX helpers and server data.

**Test on Thor:**
1. Stop the client and server runtime; install this APK over the existing app. No runtime download, prefix repair, reimport or server rebuild is needed.
2. Use the new top controls to Start runtime, then Server → Start server. In Client keep Turnip + DXVK, 1280×720, Fullscreen game, Balanced CPU, Automatic runtime, available cores and native helpers. Leave verbose logging and shadows off. Enable Game audio and select NPC compatibility.
3. Check a UI click, spell or combat sound with Android media volume raised and the game's sound sliders enabled. Try speakers and headphones. A silent MIDI zone track alone does not test PCM effects.
4. Revisit Guard Sunblaze for 30–60 seconds; watch hair, arms, legs and armor while turning. Note FPS. Stop the client, select Standard and repeat the same route to compare. Return to Compatibility if it improves the NPCs.
5. Stop/relaunch once to check sound again; test gear Keyboard/Esc and Back/Return. Stop the client, then export Logs immediately so both runs and audio counters are retained. Include a short video and say which NPC mode each run used. If audio causes a launch problem, disable Game audio before relaunching and preserve the failed logs.

Physical-device audio and the NPC comparison remain the acceptance test. [Implementation and evidence](audio-and-npc-042.md).

---

TRASC Server Android **0.4.1** adds **1280×720 fullscreen** and a compact in-game controls menu.

- The Android display fills the screen in landscape. System bars hide during play and can be revealed with an edge swipe. The permanent toolbar is replaced by a translucent gear at the top right.
- Gear opens **Back to Client**, **Keyboard**, **Esc** and session status over the game. Tap the gear, outside the panel or Android Back to collapse it. Opening controls releases held game input; closing them returns input to the game. Keyboard Type and Send + Enter remain available.
- Choose **1280x720** and enable **Fullscreen game** in Client. Launch applies the game resolution and removes its window border. Only display INI keys change, with original and previous byte-exact copies under `client/prefix/trasc-display-originals`. Disable Fullscreen game for the previous windowed behavior. Existing saved resolution is retained until changed.
- A bundled, verified Wine 10 server gives translated processes time to finish native cleanup after Windows exit. It retains bounded forced termination and normal exit codes; the installed runtime image and prefix are preserved.
- Turnip and the successful CPU-affinity path remain in place. The display delivery target remains 30 updates/sec for this resolution/UI pass. Diagnostic logs now include Android thermal status, battery-saver state, focus, menu visibility and view dimensions.

**Device test:** stop both runtimes and update in place. Start the server, select **Turnip + DXVK / 1280x720 / Fullscreen game / Balanced / Automatic / Allow available cores**. Keep native DLL/model helpers enabled and shadows/verbose logging off. Launch ROF2, verify the game fills the screen without a title bar, and check taps near each corner. Open/collapse the gear, test Keyboard and Esc, then Back to Client and Return to client. Repeat the same route after relaunching and export logs after the second run. Include the DXVK FPS seen in each run. If fullscreen fails, stop, export logs and disable Fullscreen game before relaunching. No Prepare, runtime download, prefix repair, client reimport or server rebuild is needed.

0.4.0 device logs verify real Turnip Adreno 740 rendering and normal game exits in both sessions. Loading was faster on the second run; the existing 30/s display cap hides possible differences in game FPS above that. Thermal throttling is not established. See `docs/client-performance.md` for the measured comparison.

---

TRASC Server Android **0.4.0** adds **Turnip + DXVK (experimental)** and addresses the observed game CPU restriction.

- Turnip's Qualcomm driver, Vulkan presentation probe and DXVK D3D9 module are bundled with the APK. The first launch checks actual hardware and presentation. If the check fails, select VirGL and export logs.
- CPU affinity → Allow available cores removes the game's observed CPU 0 restriction within Android's currently allowed cores. Choose Let the game choose to restore previous behavior on the next launch. No client INI edits.
- The new path still copies frames into the existing in-app display. It is not yet Winlator's direct presentation path; physical-device rendering and performance need testing.
- DXVK shows FPS and device identity inside the game. WineD3D's graphics-threading option does not apply to this renderer. Existing native dinput8, model helpers, controls, prefix and server data are retained.

**Device test:** stop both runtimes and update in place. Choose **Turnip + DXVK / 800×600 / Balanced CPU / Automatic runtime / Allow available cores**, with native DLL/model helpers on and verbose diagnostics and shadows off. Launch twice to separate one-time setup/shader compilation from a warm comparison. Check menus, character models, world movement and the DXVK FPS/device HUD; export logs after the second run. If launch or graphics fail, stop, return to VirGL and export the failure logs before further launches. No runtime download, client reimport, prefix repair or server rebuild is required. Hardware success and better FPS are not assumed before the Thor test.

---

TRASC Server Android **0.3.10** adds **Single + OpenGL worker (experimental)** to Graphics threading.

- Wine stays single-threaded while Mesa 22.3 batches GL commands on its native worker (`mesa_glthread=true`). Existing Multithreaded and Single thread explicitly keep this worker off. Switching modes does not repair or change the prefix.
- Exported state distinguishes requested batching from a worker actually observed in the current Wine launch. `client-threads.log` samples bounded thread CPU ticks, last CPU and available CPU masks every ten seconds. It does not log command lines, environments or unrelated processes, and does not change CPU affinity or Android policy.
- Preserve a bounded copy of ROF2's previous `dbg.txt` as `client-game.previous.log` before a new client launch, and preserve `client-state.previous.json`. Current startup diagnostics stay in their original location. This fixes the missing first-run loading evidence in the latest comparison.
- Latest 0.3.9 movement samples: Wine median approximately 6.0 presents/s with Multithreaded and 7.7 with Single thread. Android bitmap delivery generally tracked these rates; decode/apply was about 1–1.5 ms per update. These are separate scene samples, not identical-path benchmarks. The previous run's game startup log was not retained, so its asset/UI durations cannot be reconstructed precisely.

**Device comparison:** stop both runtimes and update in place. Keep **VirGL / 800×600 / Balanced CPU / Automatic runtime**, native DLL/model helpers on, shadows and verbose diagnostics off. First use **Single thread** for 30–60 seconds of movement in the same scene; stop, select **Single + OpenGL worker**, and repeat the route. Export logs after the second run. Return to Single thread if batching is worse or affects graphics. The first launch after the APK update can refresh the Wine prefix once; a repeat launch avoids comparing that one-time setup with a warm launch. No runtime download, client reimport or server rebuild is needed. Turnip/DXVK is still not included, and Thor FPS improvement from this option requires device testing.

---

TRASC Server Android **0.3.9** adds a graphics-threading comparison and measures the remaining frame-rate bottleneck.

- Display decoding and CopyRect reuse bounded buffers, reducing repeated allocations while preserving the current graphics path.
- **Graphics threading → Multithreaded** retains Wine's previous default. **Single thread** uses Wine 10's supported per-launch setting to remove the graphics command queue. Compare both; single threading is not assumed to be faster. No prefix registry changes or runtime reimport.
- The client bar shows **Wine** presentations per second and **Display** new bitmap draws per second separately. Wine uses its aggregate fps channel, about one line per 1.5 seconds, with the first incomplete interval discarded. A dash means no recent sample. Display measurements include transfer/decoding/Canvas submission timings in `client-presentation.log`, sampled every five seconds and bounded with rotation. Canvas submission is not a GPU timing; neither counter measures physical monitor refresh.
- Device 0.3.8 evidence: acceleration actually enabled, repeat startup 18.138 → 8.175 seconds, global assets 102 → 46 seconds, game UI 48 → 35 seconds. Graphics remained correct; frame rate is still unacceptable. These are separate user runs, not a controlled benchmark.

**Device comparison:** stop both runtimes and update in place. Keep **VirGL / 800×600 / Balanced CPU / Automatic runtime**, native DLL/model helpers on and verbose diagnostics off. Leave shadows off. First check **Multithreaded** in the same scene for 30–60 seconds, then stop the client, select **Single thread**, and repeat. Export logs after the second run; both current and previous sessions are retained. Note each Wine/Display counter while turning or moving. If single threading regresses, return to Multithreaded. The first APK launch may refresh the Wine prefix once. No server rebuild, client move, prefix repair or runtime download is required. Turnip/DXVK is not included yet; actual device FPS improvement from this release remains unverified.

---

TRASC Server Android **0.3.8** enables a verified PRoot syscall accelerator for the client.

- **Runtime mode → Automatic** runs an isolated file/socket/child-process check and requires actual accelerator activation before starting Wine. An unsupported or failed check selects Compatibility. A hung check aborts startup and offers the manual Compatibility path.
- **Runtime mode → Compatibility** uses the previous tracing mode. CPU profile and graphics selection remain independent.
- Client files already live in app-private internal storage. `D:` is a Wine mapping to those files, not an SD card or shared-storage mount; no file migration or drive-letter workaround is needed.
- Exported state records storage mapping and actual acceleration evidence. `client-runtime-probe.log` records the preflight; `client-proot.log` records the current launcher/session, with one previous log retained.
- Existing prefix reuse, graphics fixes, native DLLs and controller settings are retained. Server runtime mode is unchanged.

**Device test:** stop both runtimes, update in place, and retain all installed files. Use **VirGL / Balanced / Automatic**, 800×600, native DLL/model helpers on and verbose diagnostics off. After the first post-update launch, stop and launch again; enter the same zone and export Logs. If launch or behavior regresses, use **Runtime mode → Compatibility** and repeat with the other settings unchanged. No runtime download or server rebuild is needed. Device FPS remains unverified.

TRASC Server Android **0.3.7** adds a Balanced CPU profile and reuses verified Wine prefixes to reduce repeated startup work.

- **CPU profile → Balanced** uses larger Box64 translation blocks and default flag handling, retains x86 memory-order barriers, and reports the actual CPU count instead of the bundled 64-core Wine override. **Compatibility** restores the previous CPU settings. Neither option changes the graphics fixes.
- A completed Wine prefix is reused on later launches. Runtime/graphics-module changes, missing system files or interrupted checks trigger a full update. The first launch after installing 0.3.7 still performs one update; compare the **second** launch as well.
- Exported client state includes startup-stage durations, CPU settings and inherited CPU affinity. Selected ROF2 launch options are remembered and included in session backups.
- Turnip is not installed by this update. A direct Turnip/DXVK path is a separate implementation milestone; see [performance findings and integration plan](client-performance.md).

**Device test:** stop both runtimes, update the APK in place, and retain the installed client/runtime/prefix/model helpers. Start the server. Select **Android GPU / VirGL**, **Balanced**, **800×600**, native dinput8 and model helpers enabled, diagnostics off. Launch, visit the same character/zone, stop the client, and repeat once. Export Logs after the second attempt. If behavior regresses, select Compatibility and repeat at the same resolution. No runtime download or server rebuild is required. This build does not claim a measured Android FPS improvement before device testing.

TRASC Server Android **0.3.6** corrects texture storage and legacy Wine shaders in the experimental Android GPU path.

- DXT1/3/5 artwork now uses consistent RGBA host storage. Uploads preserve texture subregions, mip levels, alpha and sRGB; other compressed formats keep their own paths.
- The APK includes a matching Wine 10 graphics module with the GLSL 1.20 specular/fog variable correction. It applies at launch to the installed runtime; no client/runtime reimport or prefix repair is needed.
- GPU startup now samples compressed texture pixels instead of accepting a plain color clear alone. CI additionally exercises OpenGL 2.1 and compares unpatched/patched Wine with our own shader fixture.

**Device test:** stop both runtimes, install this APK over the existing preview, and reopen the app. Start the server, choose **Client → Graphics → Android GPU / VirGL (experimental)** at **800×600**, retain native dinput8/model helpers and leave verbose logging off. Check menu backgrounds, loading artwork, character/model textures, then enter the same zone and check movement. Export Logs afterward. Software remains the recovery option. Actual Adreno rendering and performance still require your device test.

TRASC Server Android **0.3.5** adds an experimental Android GPU path for the next performance test.

The 0.3.4 device pass confirms working models, animations and movement. Its logs show zero HMD/model failures and global asset initialization in 1m58s. Rendering still uses CPU llvmpipe, which remains a major performance limit.

- **Client → Graphics → Android GPU / VirGL (experimental)** forwards WineD3D rendering through the packaged native Android GLES helper. Software remains the default and recovery option.
- Verify a mapped GLX drawable and rendered pixel before Wine starts. Record actual guest and Android driver identity in exported logs/state.
- Own the GPU helper for the client session, stop it during cleanup and backups, report driver failures, and bound its diagnostic logs.
- Retain `eqgame.exe patchme`, native/system DirectInput, installed Microsoft model helpers, quiet logging and existing runtime/prefix/controller data.

**Device test:** stop both runtimes and update this APK in place. Keep the existing runtime and prefix; no server build, download, helper reinstall, Prepare or reimport is needed. Start the server, choose **Android GPU / VirGL (experimental)** at **800×600**, keep native dinput8/model helpers enabled and verbose diagnostics off, then launch ROF2. Check models, animation and movement in the same zone. Export Logs after the test. If GPU setup or graphics fails, stop the client and select **Software** for comparison.

ARM64 tests exercise real Windows Direct3D9 output, native animated models and held movement input over the GLES bridge, including PRoot. The CI host uses a software GLES driver; physical Adreno compatibility and playable ROF2 performance require this device test. GPU mode adds no Termux dependency and retains the embedded display. CPU translation and display transfer costs remain.

Previous updates follow for reference.

TRASC Server Android **0.3.4** adds DirectX model helper installation for the invisible-character problem after the first successful world entry.

- Install the two Microsoft x86 D3DX libraries used by ROF2 from the official June 2010 redistributable. Choose **Install DirectX model helpers**, or select the matching offline `directx_Jun2010_redist.exe`.
- Verify the entire download before extraction, stage and verify both Windows DLLs, preserve the previous helper installation, and remove only the app's temporary installer copy. Existing client, Wine prefix and server data are retained.
- **Use installed DirectX model helpers** enables native-first loading for d3dx9_30/35. Wine's original prefix files are retained in `client/prefix/trasc-directx-originals`. Disable the option for a built-in Wine comparison. Actual native model-library loading appears separately from DirectInput.
- Keep normal logging, `eqgame.exe patchme` and native/system DirectInput forwarding. The Linux runtime images are unchanged.

**Device test:** stop both runtimes, install this APK in place, then open **Client → Install DirectX model helpers**. Keep the existing client runtime and prefix. Start the server and launch at **800×600**, with native dinput8 and model helpers enabled, verbose diagnostics off. Check models at character selection, enter Greater Faydark, try movement, then export Logs. No client reimport, server rebuild or prefix repair is needed.

The last session reached the game world and camped normally. It still reported 573 model initialization failures while using Wine's built-in D3DX functions; the relevant animation/skinning APIs return E_NOTIMPL in Wine10. This change targets that compatibility gap. Rendering still uses CPU llvmpipe; it does not enable the Thor GPU or promise playable FPS. Successful device model rendering remains to be confirmed.

Previous updates follow for reference.

TRASC Server Android **0.3.3** removes the diagnostic logging flood found in the first successful embedded ROF2 launch.

- Normal launches retain Wine errors and DLL-load confirmation while disabling verbose exception/module traces and repetitive fixme messages. The reported session wrote 1,059,025,481 bytes / 9,258,244 lines; global asset initialization took 53 minutes 11 seconds.
- **Verbose Wine diagnostics (slower)** is off by default. Enable it only for a requested diagnostic comparison. The launch status and exported state record the selected mode.
- Wine output is drained independently and rotated into two segments of at most 8 MiB each. One previous session is kept, capped at 8 MiB with startup/final excerpts; this also trims old 0.3.2 traces on the next launch. Load evidence and fatal errors are captured before rotation.
- Keep `eqgame.exe patchme`, native-first/system-fallback DirectInput, the existing prefix and conservative CPU translation settings.

**Stop both runtimes, install this APK over Preview 0.3.2, start the server, and Launch ROF2 at the same 800x600 with native dinput8 on and verbose diagnostics off.** No runtime download, prefix repair, Prepare, server rebuild or client/database reimport is required. Export Logs and report time to character selection and responsiveness there. The previous run reached character selection; playable frame rates and world entry are still unverified. Graphics still use CPU llvmpipe: this update does not enable the Thor GPU.

Previous updates follow for reference.

TRASC Server Android **0.3.2** fixes the system DirectInput load behind the imported native client DLL.

- Use native-first, built-in fallback (`dinput8=n,b`): load your imported DLL, then allow its absolute system DLL request to reach Wine's implementation.
- Report native DLL and system DirectInput loading separately, based on actual Wine traces.
- Include the game's startup diagnostics and the add-on's `dinput8.log` in native log viewing/export. Client settings, binaries and character chat logs are excluded.
- Record session start/end times and stop reasons; retain exception traces.
- Test an open PE32 proxy that forwards to system DirectInput and creates keyboard/mouse devices. A negative control reproduces failure under the old native-only override.

**Update in place, keep your current prefix/runtime/client, start the server, and Launch ROF2 with the native DLL option enabled.** No prefix repair, runtime redownload, server rebuild or reimport is needed. Export Logs after the attempt. The earlier kernel32 failure is cleared in the latest device run; actual ROF2 login/world entry still require device verification.

Previous updates follow for reference.

TRASC Server Android **0.3.1** adds recovery and diagnostics for the reported ROF2 black screen.

- Verify Wine's 32-bit core files and run its 32-bit command interpreter before ROF2.
- Report fatal Windows loader/dependency errors visibly, with separate prefix logs.
- **Repair Wine prefix** preserves the previous prefix in `client/prefix-backups/`, then initializes a fresh Windows environment. Game files, controller bindings and server data are retained.
- Keep the required `eqgame.exe patchme` launch command and native dinput8 override.
- Verify the installed runtime through pinned PRoot, including a large legacy PE32 test program.

Stop runtimes and install over Preview 0.3.0. No server rebuild, database/client import or runtime redownload is needed. For this device pass: **Stop client → Repair Wine prefix → wait for the Wine desktop → Stop client → start server → Launch ROF2**. Export Logs afterwards.

The fatal error in the device bundle is `could not load kernel32.dll, status c0000135`. Fresh-prefix infrastructure tests cannot establish the exact cause on Android; this pass provides a preserved-prefix recovery path and verifies 32-bit Wine before attempting the modified client. Actual ROF2 login/world entry remain unverified. Software graphics only; sound and hardware acceleration remain later work.

TRASC Server Android **0.3.0** starts the embedded ROF2 client milestone. The user confirmed session backup/restore and input on 0.2.1.

- Download the separate client runtime in Client, with an offline archive option.
- Try Wine desktop, launch the imported ROF2 client, return to the display or stop it.
- Saved controllers, touch and physical keyboard/mouse feed the native display. Its Keyboard dialog supports Type and Send + Enter.
- Prepare client data/login/windowed resolution with original-file backups.
- Require matching PE32 DLL architecture and report native dinput8 loading only from Wine's actual trace.

This is an experimental software-graphics compatibility pass. ROF2/device/plugin behavior is not yet verified; sound, hardware acceleration and performance tuning remain later work. [Device sequence](https://github.com/Russianranger/trasc-server-android/blob/main/docs/client-runtime.md).

The following server/export fixes remain included:

Install this APK over **TRASC Server Preview 0.1.2, 0.2.0 or 0.2.1**. It uses the same application ID and pinned signing certificate. Stop the client and server runtime before updating. Your existing runtime 1.1, source, maps, database and binaries are retained; this APK update needs no server recompile.

- **Session export/import:** accept valid Debian `:arm64` filenames while retaining path traversal and drive-prefix checks.
- **Logs:** native Android listing, viewing and ZIP export work with the runtime closed, including after a failed session backup. Both log export buttons work without the localhost control service.
- **Recovery:** backup failures are recorded in `app.log` and explain whether the runtime is stopped. No game processes restart automatically.
- **Regression checks:** exact reported filename, full published-runtime backup/restore, native log bundles without Python, and the failed-backup/closed-runtime UI flow.

All 0.2.0 management features remain included:

- **Gameplay:** all database/source rules in searchable, collapsible categories; types and established bounds checked with field names in errors; save only modified rules.
- **Setup:** apply the legacy Nektulos map/nav pair with original-file backups, and revert it.
- **Server:** create and export a complete session ZIP. It stops the session cleanly and includes runtime, database, SQL snapshot, binaries, maps, logs, sources/builds, configuration, backups and imported client.
- **Setup:** restore that ZIP into a fresh app without downloading a runtime or recompiling. Checksums, modes and symlinks are verified/restored before activation. Existing sessions have a recovery generation.
- **Client:** ZIP import, private temporary-ZIP cleanup, DLL inventory, saved controller-to-keyboard/mouse bindings and a focused input diagnostic. The separate client runtime adds an experimental launch/display/DLL-loading path.
- **Continuity:** implementation decisions, validation and remaining work are recorded in `docs/HANDOFF.md`.

For the current device pass, use the comparison sequence at the top of these notes. Export Logs after the attempt.

Backups contain accounts, credentials and client files and are not encrypted. Save them privately outside the app. Only the private temporary copy of an imported session/client ZIP is removed; the selected source document remains intact.

**Older 0.1.0/0.1.1 installations:** their signing key was lost before 0.1.2, so this Preview application installs alongside them. Their data is not transferred automatically. Export the database, source/maps archives and edited files, stop the old runtime, and import into Preview. Do not uninstall the old app until migration is verified. Only run one runtime at a time because the ports are shared.

`preview-build.json` identifies the exact commit, APK checksum, application ID and signing certificate. Publication requires backend/JVM tests, ARM64 database integration, the Windows/DLL/Direct3D/input probe, full client-runtime archive roundtrip, APK compilation and lint. New Android management workflows still require the user's device acceptance tests.
