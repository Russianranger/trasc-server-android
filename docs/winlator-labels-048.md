# Character-selection labels work in Winlator (2026-09-16)

The user explicitly confirms that names work in Winlator. The new clip,
`Winlator Ludashi_2026-09-16 14_43_44.mp4`, is 10.83 seconds long. Sampled
frames show readable yellow `Yehaos [1 Dru]` and `Greater Faydark` labels
through character animation. This supplies the previously missing comparison
at character selection; the earlier Winlator clip only showed in-world play.

Both supplied settings images were readable from the uploaded files despite
the initial image-path errors in the conversation. Do not request them again.

## Observed configuration

| Component | Working Winlator shortcut, from screenshots | TRASC 0.4.8 |
| --- | --- | --- |
| DXVK | 2.4.1-fix | 2.5.3 |
| Vulkan driver | Mesa Turnip v26.0.0 - R5, Vulkan 1.4.330 | Mesa Turnip 24.3.4, ARM64 glibc/KGSL |
| Vulkan version setting | 1.3 | ICD advertises 1.3; probe requires Vulkan >=1.3 |
| DX wrapper | DXVK+VKD3D; VKD3D version None | DXVK for the D3D9 client |
| Wine | Not shown | 10.0 WoW64 |
| CPU translator | Version and preset not shown | Box64 0.4.4, pinned commit 2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a |

Other visible Winlator settings: OpenGL driver freedreno, 154/154 Vulkan
extensions enabled, Rendering Mode None, GPU Name Device, Frame Rate 0,
and Max Frame Latency switched off. The clipped Bilinear field does not
identify additional settings. VKD3D Feature Level 12_1 is displayed but
VKD3D is disabled; it does not establish the game's D3D9 configuration.

These are selected settings, not verified loaded DLL versions. No Winlator
runtime log, installed-file hashes, Wine version, Box64 version/preset, or
container architecture accompanies the new clip. The user reports using the
same client files/server; byte identity between installations has not been
independently checked.

## What this narrows down

The labels can render correctly on this device with the Winlator setup.
This shifts the investigation toward differences in the client runtime,
graphics stack, or configuration. It does not identify a single faulty
component or prove that changing only Turnip or DXVK will fix the app.
The earlier name failure on both our Turnip/DXVK and VirGL/WineD3D paths
also keeps their shared Wine/Box64/client configuration relevant.

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

Request the working Winlator **Wine version**, **Box64 version and preset**,
and container type if shown (WoW64, ARM64EC, or other). Container/runtime and
advanced/preset screenshots are sufficient. This allows the next comparison
to target a concrete difference shared by the failing rendering paths.
Do not request another broad renderer/CPU/native-DLL OFF test.

Keep 0.4.8 with the successful eight-ID spell exclusion, native dinput8/model
helpers, Balanced CPU, and exact 0.4.2 NPC compatibility. The spell issue is
separate and has a confirmed device workaround. This investigation changes
documentation only; no new APK or verified name fix is claimed. A future
runtime comparison must preserve the baseline, backups, signing identity,
and existing gates, and distinguish CI API checks from actual game evidence.

Repository version sources: `scripts/build-vulkan.sh`, `vulkan/Dockerfile`,
`scripts/build-client-runtime.sh`, `backend/client_vulkan.py`,
`backend/client_runner.py`, and `docs/client-runtime.md` at 1f50b67.
