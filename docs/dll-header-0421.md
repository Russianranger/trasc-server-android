# 0.4.21: deploy the display-loading header before DLL compilation

## Failure and cause

The Thor screenshot reports `[Errno 2] No such file or directory: '/opt/trasc/eq_display_loading.h'` when compiling the DLL with 0.4.20. The supplied `logs-1377593214237903447.zip` retains the previous successful 0.4.19 DLL build/deployment; it does not contain a successful display-adapter build. The failed attempt does not replace the installed or staged DLL.

Gradle packages every `backend/*.py` and `backend/*.h` asset, so `eq_display_loading.h` was present in the APK. However, `RuntimeManager.start()` maintains an explicit list of backend files to copy into the app-private `backend` directory. That list omitted the new header. The compiler mounts that directory at `/opt/trasc`, and `client_mouse.prepare_sources()` reads the header before invoking the Microsoft compiler. Reinstalling the SDK or client runtime cannot repair this omitted copy step.

0.4.21/code38 adds the missing header to the startup deployment list. Starting the existing runtime after the APK update copies it automatically. No DLL adapter, camera, spell-loading, model-loading, graphics or particle behavior changes in this correction.

## Regression coverage and verification

The new `test_android_runtime_deploys_all_dll_adapter_headers` checks the Android runtime's asset-copy list against the adapter headers required by the actual DLL preparation code, and checks that each deployed backend asset exists. This covers the APK-to-runtime boundary that hosted builds using `backend/` directly missed.

Before the fix, the regression test fails with exactly `eq_display_loading.h` missing; after the fix, all 136 Python tests pass. APK compilation, preserved signing and the existing seven release jobs must still succeed before using the new preview. Publication and device retry are not claimed by this initial implementation note.

## Thor retry

1. Stop the client and server runtime, then install 0.4.21 over the existing Preview app.
2. Start the server runtime, leaving the game server stopped. Keep the existing SDK, source, client, prefixes and installed runtimes.
3. Open **Client → Build dinput8.dll on this device → Compile dinput8.dll**. Wait for a new successful build, then select **Deploy staged DLL**. Do not deploy the old staged output after a failed build.
4. Resume [the 0.4.20 loading comparison and separate particle test](loading-0420.md). Keep Faster spell loading enabled. The new build record should include `TRASC_EQ_DISPLAY_V1` and the `eq_display_loading.h` hash alongside the existing camera/loading adapters.
5. Export Logs after the comparison, or immediately if compilation still fails.

No source pull, SDK reimport, runtime download, server rebuild, client reimport or Mac tools are needed. Particle cause and the model-wait option's actual Thor benefit remain open; camp remains parked.
