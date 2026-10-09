# Client compatibility release 0.6.12 / code 61

Published October 9, 2026 UTC, following the October 8 Thor observations.

- APK: `trasc-server-android-preview.apk`
- SHA-256: `8d78ced6130185881f2963efffa814020f7bcaf31a278a225fd4f9a15ea80bfc`
- Package: `io.github.russianranger.trasc.preview`
- Signing certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`
- Candidate: `19c6801c48c0bb1307f2923a6667d24e37ae7583`
- [Client-only Actions run](https://github.com/Russianranger/trasc-server-android/actions/runs/37869147746): all three jobs passed (`apk`, `camera-proxy`, `preview`).
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview).

The actual downloaded APK binary manifest, SHA-256, embedded signing certificate,
camera proxy and source receipt, and seven updated backend/UI assets were checked.
All nineteen prior native payload files were independently compared byte for byte
with the verified 0.6.11 APK. CI also verified the APK signature with `apksigner`.
Android compilation/lint, management/profile browser checks, host management checks,
Windows system DirectInput forwarding/camera gates, adapter recovery tests and
rendering-inventory/configuration tests passed. These checks do not establish
physical Thor appearance or camera behavior.

## Included behavior

Traditional exposes optional **Recenter only during camera look (experimental)**,
using a separate bundled camera-only DirectInput proxy. Its journal preserves and
restores an original imported DLL or its original absence after stopping, including
interrupted-launch recovery. The Custom loading, particle, boat and gameplay hooks
remain disabled. See [camera acceptance and restore](client-camera-0612.md).

**Name / sky compatibility (experimental, Turnip)** adds only
`d3d9.strictConstantCopies = True` to the existing DXVK configuration. It is a
candidate correction for malformed selection-screen labels and a black sky,
requiring Thor acceptance. Disabling it restores the previous configuration.
The new bounded read-only rendering evidence helps compare imported settings and
assets. See [evidence, acceptance and recovery](traditional-name-sky-0612.md).

Existing gear actions **Apply StoneUI viewport**, **Restore full viewport** and
**Return to Launcher** are retained. The separate StoneUI update blends the native
chat drag bar into parchment, makes Main/Other Chat titles black, and removes
oversized hotbar recesses while preserving the native twelve keys and fitted frames.
Class symbols, the larger book, fitted spell holders, window movement and saved
character geometry remain. Replacing matching skin assets requires no new layout
merge; import the matching class ZIP, keeping Load Default UI unchecked.

## Preservation and focused acceptance

Update the APK in place. Keep the compiled Traditional server, imported RoF2
client, Wine prefix, runtime, DirectX model helpers, controller bindings and
existing character preferences. This workflow built the launcher and camera
adapter only; it reused server/runtime/native components. Server compilation,
client startup repairs and original StoneUI archive qualification were not repeated.

Keep the known working Turnip 26.0.0 / Balanced / NPC compatibility / model-helper
choices and 1280x720. Enable the two optional controls and relaunch. Observe the
existing character-selection labels and sky for 30 seconds, then enter the world
and check camera rotation past a full circle, free pointer after releasing look,
chat dragging, title color, hotbar frames and ordinary controls. Camp normally and
reopen once to check persistence. If a problem remains, export fresh logs promptly
and capture the selection view and affected window. Disable either option while
stopped to revert it; the camera adapter restores its original DLL automatically.
