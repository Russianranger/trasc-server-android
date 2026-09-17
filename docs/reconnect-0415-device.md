# Thor 0.4.15 reconnect and mouse follow-up

Device evidence: `logs-1609566688878504148.zip`, exported September 17, 2026 at 23:30:56 UTC from 0.4.15. The user confirms gear `#tim` now works in EQ. Preserve that input sequence.

The experimental recenter setting failed on the real client. `client-prefix.previous.2.log` records per-application `MouseWarpOverride=force`. That session fails during graphics initialization: repeated `GetAdapterDisplayModeEx` failures, then an unhandled read at `FFFFFFFC`, instruction `7945046E`, Wine time 313737.184. Do not claim the generic Windows input fixture proved compatibility with EQ. Keep recentering off; no replacement is proven yet.

Both subsequent prefix logs record `MouseWarpOverride=default`. The latest verbose session reproduces character select → server select → Play. Its first stack-overflow exception is at Wine time 314473.439, `c00000fd`, instruction `7AE69EE4`. The loaded native `D:\\DINPUT8.dll` base is `7AE60000`, giving RVA `0x9EE4`. Only afterward does the exception handler exhaust the remaining stack and report `virtual_setup_exception` at `7b03ade5`. The final Wine error is therefore not the original fault address. The game log ends after graphics reinitialization succeeds at 23:28:43. This reconnect failure occurred with recentering disabled.

The source import log pins `Russianranger/Triptych-Triumvirate` commit `4c653ca2d16aaede33b7011d07254c520ac5f5df`. Its project SHA256 matches the device compiler report: `c62b7c14baa6e1b7fda58666842b8858f65d24190a15a89620305eba09cba037`. The device's staged DLL was 1,695,232 bytes, SHA256 `556ead4699b1af797eb2c676ef40dacc92ade932526ebe551f36382de7424c28`; the build record alone does not hash the currently installed DLL. An isolated Windows Actions build generates a link map and disassembly from the same source and production recipe. It does not publish an app or Microsoft tools.

The private input helper now records actual connected consumers with 462, 2,434 and 387 relative events. This confirms controller deltas reached XTest; it does not prove EQ consumed unbounded camera movement.

Android historical exit information recovered the earlier 21:44:32 crash. Its native tombstone contains Chromium's fatal message that a render-process crash was not handled by all associated WebViews, triggering application termination. This predates the 0.4.15 update and is the failure class addressed by the new `onRenderProcessGone` handler. There is no new Android process-crash record during these 0.4.15 tests. Renderer recovery still needs device acceptance.

Until the reconnect cause is resolved, stop/relaunch the client before entering the server again. Keep the server running and preserve the working runtime, prefix, database and client files. Turn verbose Wine diagnostics off for normal play after exporting evidence.

## Symbol-build result and required next evidence

Isolated branch `codex/dll-reconnect-diagnosis`, commit `25ae5b5b0c3280881505a77cbce2986c744ba0d8`, [successful run 35287847157](https://github.com/Russianranger/trasc-server-android/actions/runs/35287847157). Artifact `client-dll-diagnosis` / `10524759035`, ZIP SHA256 `67b47888203f79378ea0d5c5ea55227dcaeb49abb8dc5e960f7979f606236ee9`, was downloaded and verified. Local files are under ignored `runtime-work/reconnect-symbols/`. No application or runtime release was changed.

The runner used MSVC 14.29.30133 and Windows SDK 10.0.26100.0. Its DLL is 1,756,672 bytes, SHA256 `01f72f16770767c2624463a0132b62ffd376529c230d51529209ce338b763edd`. Windows checkout changes the project hash through CRLF conversion; normalizing those endings exactly reproduces the device's project hash. The actual binary layout nevertheless differs: RVA 0x9EE4 maps to an unpatched `InjectCustomZones_Trampoline` placeholder instruction reading address zero, inconsistent with the device's recorded stack write and registers. **Do not use this map to assign a function name to the device crash.** A matching source revision is insufficient without matching binary layout/toolchain.

The log bundle includes a staged-build record but no `client-dll-deploy.json` and no `client_dll_deploy` operation in the retained control log. This does not establish which DLL is installed; do not assume the newly compiled DLL was deployed or overwrite it speculatively.

Next ask the user to export the installed DLL from Files → folder `client/current` → select `DINPUT8.dll` (case as shown) → Export file, and the small `sdk.json` from `client/toolchain`. Only these files are needed, not the SDK archive or entire session. The Files browser and Android export bridge allow both paths. Compare the actual DLL hash, PE layout and disassembly to the staged record/map before choosing a source fix. Recenter must stay disabled. No safe unbounded-look replacement or reconnect fix has been established, and no new APK is claimed.
