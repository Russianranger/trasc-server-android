# TRASC 0.6.21 / code 70 — TAKP mouse-look toggle

**Preparation status: build qualification, publication and delivered artifact verification are pending.** This document records intended behavior and the verified reuse baseline; it does not record a completed 0.6.21 release.

## Device evidence and scope

The user confirms that the Accurate / Legacy math accuracy CPU profile resolves the invisible NPC models on the AYN Thor. New screenshots show normal skeleton and ghost models, and brief visual glitches settled. Keep that selected CPU profile. This establishes successful rendering in the tested session without proving the precise numerical fault in the translated game.

New TAKP launch settings default to Accurate in the launcher and runner; explicit saved CPU choices remain intact. Custom and Traditional retain Balanced as their default. Current logs confirm `X87DOUBLE=1`, `FASTNAN=0`, `FASTROUND=0` and `SYNC_ROUNDING=1`; the correcting member of that group has not been isolated.

Version 0.6.21 adds a TAKP-only **Look off / Look on** button beside the embedded client's gear button and an optional **Toggle mouse look** controller action (`MouseLookToggle`). The gear menu also offers **Enable mouse look**. Look starts off, stays transient and owns its held right-button state separately from physical/controller holds. Enabling look lets the right stick and touch drags steer at the existing 15% TAKP relative-motion gain; look touch does not also send left clicks.

Menus, keyboard/controller settings, focus/lifecycle transitions and input capture or controller changes disable the latch. Releasing the latch leaves independently held right-button inputs under their existing owners. No saved controller maps or default bindings change. Custom and Traditional retain their existing input.

The grouped launcher controls, spell filename handling, server logging and prior startup repairs remain included. No client DLL, server or renderer change is planned. Additional bot gameplay requests are being assessed; this release does not implement that additional work.

## Verified native baseline

The workflow reuses all 21 native launcher components from the verified 0.6.20 build and preserves the existing preview signing certificate. GitHub metadata independently confirms these immutable baseline assets:

| Baseline file | Bytes | Release asset | SHA-256 |
| --- | ---: | --- | --- |
| 0.6.20 APK | 18758916 | `626984091` | `391a145377731a5819ee280a320269a0664dc28e29e4d43dbf5e94d5bc491034` |
| 0.6.20 source archive | 198471916 | `626984090` | `c4c61cff60aa4c73222ceb7c2964e1462c68892dc5d1511804bdfd9e6f533deb` |

Package remains `io.github.russianranger.trasc.preview`; intended version is `0.6.21`, code `70`. The existing update certificate SHA-256 is `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.

See [0.6.20 release verification](release-status-0620.md) for its completed CI and artifact evidence. That qualification remains historical baseline evidence, not a completed 0.6.21 check.

## Required release verification

Before delivery, run the full Python/browser and management/native input checks, actual DirectX extraction, Android assembly/lint, signing/native reuse checks and ARM64 server qualification. Verify the actual APK version/package, signing certificate, downloaded and published hashes, packaged backend/UI/native bytes, source archive and preview tag against the built commit. Record the resulting source SHA, PR, workflow run, asset IDs and digests after those checks pass.

The mouse-look tests must cover dedicated latch ownership, independent right-button holds, look touch without left clicks, ordinary pointer recovery, lifecycle/focus/capture release and optional controller action handling. No physical-device acceptance of the new toggle is claimed yet.

## Device handoff after qualification

1. Camp out and stop the client/runtime, then install the qualified 0.6.21 APK as an update.
2. Keep Accurate selected, then start the existing TAKP runtime, server and client.
3. Enable **Look on** and steer with the right stick and touch without holding LB. Disable it and check ordinary pointer/menu input.
4. Open the gear menu, keyboard and mappings, then test background/resume. Confirm that the toggle returns off and menus are clickable. Optionally bind **Toggle mouse look** to a controller button.
5. Camp and export fresh logs if input or rendering regresses. Confirm that NPC models remain visible with Accurate selected.

No client reimport, prefix reset, repeated Prepare, server rebuild or database reinitialization is required. The new toggle, camera feel, zoning and playerbot gameplay still need device testing.
