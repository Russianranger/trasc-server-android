# 0.4.21: deploy the display-loading header before DLL compilation

**Device confirmation:** the subsequent `logs-7280042745619990780.zip` contains a successful Thor build and deployment with the display header/adapter. See [the device result](loading-0421-device.md). The retry instructions and pending-device statements below describe release-time status; the compile failure is now resolved.

## Failure and cause

The Thor screenshot reports `[Errno 2] No such file or directory: '/opt/trasc/eq_display_loading.h'` when compiling the DLL with 0.4.20. The supplied `logs-1377593214237903447.zip` retains the previous successful 0.4.19 DLL build/deployment; it does not contain a successful display-adapter build. The failed attempt does not replace the installed or staged DLL.

Gradle packages every `backend/*.py` and `backend/*.h` asset, so `eq_display_loading.h` was present in the APK. However, `RuntimeManager.start()` maintains an explicit list of backend files to copy into the app-private `backend` directory. That list omitted the new header. The compiler mounts that directory at `/opt/trasc`, and `client_mouse.prepare_sources()` reads the header before invoking the Microsoft compiler. Reinstalling the SDK or client runtime cannot repair this omitted copy step.

0.4.21/code38 adds the missing header to the startup deployment list. Starting the existing runtime after the APK update copies it automatically. No DLL adapter, camera, spell-loading, model-loading, graphics or particle behavior changes in this correction.

## Regression coverage and verification

The new `test_android_runtime_deploys_all_dll_adapter_headers` checks the Android runtime's asset-copy list against the adapter headers required by the actual DLL preparation code, and checks that each deployed backend asset exists. This covers the APK-to-runtime boundary that hosted builds using `backend/` directly missed.

Before the fix, the regression test fails with exactly `eq_display_loading.h` missing; after the fix, all 136 Python tests pass. Native/JVM checks also pass locally. [Release run 35372949456](https://github.com/Russianranger/trasc-server-android/actions/runs/35372949456) completed successfully on implementation `9700df77e1924b841c7f7e61740166123ad32609`: all seven jobs passed, including APK/lint/signing, Microsoft DLL, database and the full ARM64 Software/DXVK/VirGL/direct/PRoot/session checks. Physical Thor compilation still needs the retry below.

## Thor retry

1. Stop the client and server runtime, then install 0.4.21 over the existing Preview app.
2. Start the server runtime, leaving the game server stopped. Keep the existing SDK, source, client, prefixes and installed runtimes.
3. Open **Client → Build dinput8.dll on this device → Compile dinput8.dll**. Wait for a new successful build, then select **Deploy staged DLL**. Do not deploy the old staged output after a failed build.
4. Resume [the 0.4.20 loading comparison and separate particle test](loading-0420.md). Keep Faster spell loading enabled. The new build record should include `TRASC_EQ_DISPLAY_V1` and the `eq_display_loading.h` hash alongside the existing camera/loading adapters.
5. Export Logs after the comparison, or immediately if compilation still fails.

No source pull, SDK reimport, runtime download, server rebuild, client reimport or Mac tools are needed. Particle cause and the model-wait option's actual Thor benefit remain open; camp remains parked.

## Published artifact verification

The public preview tag and `preview-build.json` identify implementation `9700df77e1924b841c7f7e61740166123ad32609`, version 0.4.21/code38. The downloaded Actions candidate APK matches the public release asset size/SHA256 and build manifest. The APK manifest confirms the version, code and existing application ID. All 25 bundled Python/header assets match the source; `classes.dex` contains the corrected `eq_display_loading.h` deployment string. CI verified the preserved signing certificate; the candidate certificate record and release manifest agree with the repository certificate.

- APK: 10,531,871 bytes; SHA256 `0871b26ec39cf4d49bd8d761092ab46cea17b1f0aeb42b03a37dbe5157a04a2c`.
- Candidate artifact `10559601455`; ZIP SHA256 `6d60ee9ee5dc68413693f7516759587734313df2be9ea0ae0a01a486e6e815ec`.
- Native source archive: 114,558,423 bytes; SHA256 `f11522ca2fd62461762c62951e5a2eefb3c1bef722e7c3fc6a64459ebaaa6e3b`.
- Signing certificate: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.

Downloaded candidate, manifest and verification script/report are under ignored `runtime-work/0421`. This final evidence update is documentation only with `[skip ci]`. Device compile success, model-loading gain and particle behavior remain for the Thor retry; no gameplay fix is claimed.
