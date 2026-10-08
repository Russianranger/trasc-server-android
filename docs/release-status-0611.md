# Verified 0.6.11 viewport launcher update

Published October 8, 2026 from `5f5a16788e78c8d4298b2b34eb5d50d36f281d07`.
The [APK-only Actions run](https://github.com/Russianranger/trasc-server-android/actions/runs/37857258669) passed Android compilation, lint, host management/command checks, signing verification and byte-for-byte native payload preservation. The separate launcher workflow reuses the verified 0.6.10 native assets; it does not compile the server or rebuild runtimes.

- APK: `trasc-server-android-preview.apk`
- Actual package: `io.github.russianranger.trasc.preview`
- Actual version: `0.6.11`, code `60`
- APK SHA-256: `5810b46eb34497ceda39c27568ff64ff1bcc74024b1b2021511167a12b8c1f20`
- Actual signing certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`
- All 19 native assets/libraries remain byte-identical to the published 0.6.10 APK.

Gear offers **Apply StoneUI viewport** (`/viewport 179 0 920 480` at 1280×720) and **Restore full viewport** (`/viewport 0 0 W H` for the active launch resolution). Both type through the existing paced native command path and press Enter. Return to Launcher retains its wording.

Install in place and retain the compiled Traditional server, imported RoF2 client, Wine prefix, runtime and DirectX helpers. [Thor viewport acceptance](client-viewport-controls.md) still requires an in-world device test. The restored viewport is the full frame, not an arbitrary earlier custom rectangle.

The separate StoneUI ZIP update adds parchment chat chrome, a larger dock book and 640×454 native spellbook, and properly fitted twelve-slot native spell-gem holders. It preserves native controls and class emblems. Static checks passed; actual native appearance and persistence remain to be verified on Thor.
