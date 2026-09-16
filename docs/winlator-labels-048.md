# Character-selection labels work in Winlator (2026-09-16)

The user explicitly confirms that names work in Winlator. The new clip,
`Winlator Ludashi_2026-09-16 14_43_44.mp4`, is 10.83 seconds long. Sampled
frames show readable yellow `Yehaos [1 Dru]` and `Greater Faydark` labels
through character animation. This supplies the previously missing comparison
at character selection; the earlier Winlator clip only showed in-world play.

All four supplied settings images were readable from the uploaded files despite
the initial image-path errors in the conversation. The follow-up files
`Screenshot_20260916-152130.png` and `Screenshot_20260916-152113.png` identify
the runtime and emulator. Do not request them again.

## Observed configuration

| Component | Working Winlator shortcut, from screenshots | TRASC 0.4.8 |
| --- | --- | --- |
| DXVK | 2.4.1-fix | 2.5.3 |
| Vulkan driver | Mesa Turnip v26.0.0 - R5, Vulkan 1.4.330 | Mesa Turnip 24.3.4, ARM64 glibc/KGSL |
| Vulkan version setting | 1.3 | ICD advertises 1.3; probe requires Vulkan >=1.3 |
| DX wrapper | DXVK+VKD3D; VKD3D version None | DXVK for the D3D9 client |
| Wine/Proton environment | Container-1, Proton 11.0-1 arm64ec | Wine 10.0 amd64 WoW64 |
| 32-bit CPU translator | FEXCore 2601, Performance preset | Box64 0.4.4, Balanced, pinned commit 2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a |

Other visible Winlator settings: OpenGL driver freedreno, 154/154 Vulkan
extensions enabled, Rendering Mode None, GPU Name Device, Frame Rate 0,
and Max Frame Latency switched off. The clipped Bilinear field does not
identify additional settings. VKD3D Feature Level 12_1 is displayed but
VKD3D is disabled; it does not establish the game's D3D9 configuration.
Follow-up images also show DDraw Wrapper none, PulseAudio-GN audio, and
Fullscreen Stretched off. Audio has a separate successful spell-data workaround;
the audio-driver difference does not by itself justify replacing our audio path.

These are selected settings, not verified loaded DLL versions. No Winlator
runtime log or installed-file hashes accompany the clip. The user reports using
the same client files/server; byte identity between installations has not been
independently checked. A Box64 version is not needed to identify the working
32-bit path: the screenshot explicitly selects FEXCore instead.

## What this narrows down

The labels can render correctly on this device with the Winlator setup.
This shifts the investigation toward differences in the client runtime,
graphics stack, or configuration. It does not identify a single faulty
component or prove that changing only Turnip or DXVK will fix the app.
The earlier name failure on both our Turnip/DXVK and VirGL/WineD3D paths
also keeps their shared Wine/Box64/client configuration relevant.

The newer screenshots reveal a different translation architecture, not just
different driver versions. FEX supports a Wine WoW64/ARM64EC backend
([official project overview](https://fex-emu.com/)). Our current build executes
amd64 Wine via the standalone Box64 loader. Substituting a FEX DLL into that
existing Wine installation does not reproduce the ARM64EC environment; a
matching Wine/Proton build and launcher/runtime integration would be required.
The screenshots make the translation path a concrete comparison target, but
do not prove a Box64 defect or guarantee that an FEX port fixes names.

The [Winlator101 DXVK collection](https://github.com/K11MCH1/Winlator101/releases/tag/dxvk_col)
describes 2.4.1-fix as potentially helping proprietary-driver compatibility;
it does not document an EverQuest name fix. Its release asset is
`dxvk-2.4.1-fix.wcp`, 8,924,613 bytes, published SHA256
`b011c06a50901916f20c93a42eedea8aa00ee14fb319a7777a12d0327f4df849`.
This is a possible source for further inspection, not proof of the user's
installed binary identity. Do not substitute stock 2.4.1 and describe it
as the same custom build. No archive from that collection was installed
or added to the app in this investigation.

## Next evidence and preserved baseline

The previous request for Wine/emulator/container details is now satisfied.
The next focused device comparison is available inside the working Winlator
shortcut, without a TRASC APK or runtime replacement:

1. Fully stop the Winlator client/container session.
2. In shortcut Compatibility, change only **32-bit Emulator: FEXCore -> Box64**
   if offered. Keep Proton 11.0-1 arm64ec, DXVK 2.4.1-fix, Turnip, files, and
   other settings unchanged. Record the Box64 version/preset shown without
   experimenting with those settings.
3. Relaunch to the same character-selection screen and watch the yellow
   name/class/zone labels for about 30 seconds. World entry is unnecessary.
4. Fully stop, restore **FEXCore 2601 / Performance**, and confirm names work again.

Verified in the [Ludashi source](https://github.com/StevenMXZ/Winlator-Ludashi/tree/2d45b7b620251abd10727f160462f9054e65b1db):
`app/src/main/res/values/arrays.xml` lists FEXCore and Box64; the shortcut
dialog enables emulator selection for ARM64EC; and
`GuestProgramLauncherComponent.java` selects `HODLL=libwow64fex.dll` versus
`HODLL=wowbox64.dll` while retaining the same native Wine command.
The UI's Box64 choice is therefore **WowBox64** in this container, which is
not identical to our standalone Box64 0.4.4 environment. This source revision
is not verified against the user's installed APK. If the alternative is
absent or does not launch, restore FEXCore and report that outcome; do not
change containers or install speculative components to force this test.

Corruption appearing only on WowBox64 and clearing again on FEXCore would
strongly implicate the 32-bit translation backend or its configuration.
Correct labels on both leave Wine/Proton version, standalone Box64 integration,
graphics versions, and per-client settings unresolved. Failure to launch does
not establish the name bug's cause. This is a new emulator comparison, not
a repeat of our failed Box64 math-preset/native-DLL/renderer tests.

Keep 0.4.8 with the successful eight-ID spell exclusion, native dinput8/model
helpers, Balanced CPU, and exact 0.4.2 NPC compatibility. The spell issue is
separate and has a confirmed device workaround. This investigation changes
documentation only; no new APK or verified name fix is claimed. A future
runtime comparison must preserve the baseline, backups, signing identity,
and existing gates, and distinguish CI API checks from actual game evidence.

Repository version sources: `scripts/build-vulkan.sh`, `vulkan/Dockerfile`,
`scripts/build-client-runtime.sh`, `backend/client_vulkan.py`,
`backend/client_runner.py`, and `docs/client-runtime.md` at 1f50b67.
