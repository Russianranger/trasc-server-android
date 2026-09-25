# Beta version 0.6.2

This named release contains the exact signed APK tested and published as preview
0.6.2. Android version is **0.6.2/code51**. It keeps the existing app identity and
signing certificate and can be installed over Beta 0.6 or earlier previews.

## Included

- Client display startup repair for devices that deny hard links, reported on
  Galaxy Z Fold6 / Android 16. Both the RoF2/Wine desktop and DLL compiler displays
  use private authorization files without xauth's hard-link lock. The display
  server also avoids its separate hard-link PID lock. Authentication remains enabled.
- **Download Microsoft toolchain** under **Client → Build dinput8.dll on this device**,
  including license acceptance, verified downloads, progress/cancellation and import.
- The server/client runtime installation repair from Beta 0.6 remains included.

## Update and test

1. Stop the client and server runtime, then install the APK over the existing app.
   **Do not uninstall or clear storage.**
2. Start the runtime and server, then choose **Client → Start ROF2** with your current
   client and graphics settings.
3. If startup still fails, export Logs immediately after the attempt and retain the
   displayed error.

No runtime/client reimport, server rebuild or DLL rebuild is required for this
display repair. The toolchain download is optional for users who already have a
working compiler/DLL; its preparation needs at least 8 GiB free internal storage.

All nine signed-build/release checks passed, including ARM64 tests with hard links
denied and software/Vulkan/VirGL launch tests through PRoot. The Fold6 screenshot
did not include xauth stderr, so a physical-device retest is still needed to confirm
the reported failure is resolved. This is not a claim of complete Android 16
gameplay compatibility.

## Build identity

- Source commit: `2cd9d50c2de3b6c2607187702452fb87d0b954bd`
- [Verified build](https://github.com/Russianranger/trasc-server-android/actions/runs/36119436611)
- APK: `trasc-server-android-beta-0.6.2.apk`, **15,204,739 bytes**
- APK SHA256: `d9a4dce3e6657c8fdb9713cab1aeebf5cf65b8d87a678bad723353045652483b`
- Launcher source SHA256: `228c60708d8edae71be5ef0b575f5eca3b0ea926e85507eb93cb10f6aa46e3b4`

The corresponding launcher source archive and `beta-build.json` are attached.
Microsoft compiler/SDK payloads are downloaded from Microsoft by the app and are
not included in these release assets. Beta 0.6 and older releases remain available.
