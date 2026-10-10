# TRASC 0.6.21 / code 70 — TAKP mouse-look toggle

**Published and independently verified.** TAKP now has a transient **Look off / Look on** button beside the embedded client's gear button, a gear-menu **Enable mouse look** action and an optional **Toggle mouse look** controller binding.

The latest Thor screenshots and user report confirm that **Accurate / Legacy math accuracy** resolves invisible NPC models in the tested session; brief initial glitches settled. New TAKP settings default to Accurate, while explicit saved choices remain intact. Custom and Traditional retain Balanced. The correcting member of the four Accurate math flags has not been isolated.

## Published build

- [PR #27](https://github.com/Russianranger/trasc-server-android/pull/27), merged at `cf13e95c192868ae1a8d497360086d7dbef57808`.
- Built source: `ce600b3f66302b42b54ed8bc39b8cc2983f42804`.
- [Build and ARM64 server qualification](https://github.com/Russianranger/trasc-server-android/actions/runs/38026942332).
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview); its tag points to the built source.
- Package: `io.github.russianranger.trasc.preview`; version `0.6.21`; code `70`.
- Update certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.

| Published file | Bytes | Release asset | SHA-256 |
| --- | ---: | --- | --- |
| `trasc-server-android-preview.apk` | 18762924 | `627090614` | `0047f5091b92b7417efc738ed056f221bb6c1d2cf9d63d4f3da00e7966c00b55` |
| `launcher-sources.tar.gz` | 208096155 | `627090617` | `76124578972ccf56159ad963fd52c48922fb42c29ef4618725802c6568375077` |
| `native-reuse.json` | 4817 | `627090613` | `502c4302f48af028b6e612ef1998fe90f5bf9c0d28224392f3219342fce59778` |
| `preview-build.json` | 765 | `627090611` | `756d0dbb516441eab7661c7dfc1ddee722e9c16f17bc914da4740acbcdce1ad4` |

Release ZIP artifact: `11660926823`, 226743613 bytes, SHA-256 `0c46815e908b5c6fbe26bea149b602a3c28ae343131f2d4f2d8607960e8a067c`.
ARM64 evidence artifact: `11660667377`, 859929 bytes, SHA-256 `33a01298fc05367182dc89c3c09c6d52428b924f0c9fc33d74a28ad9291f2c88`.

## Resulting behavior

Look starts off and is not saved. Its dedicated right-button input owner is separate from physical/controller holds. Enabling look lets the right stick, touch drags and external mouse steer at the existing 15% TAKP relative-motion gain. Look-mode touch does not also click the left button. Disable look to use the ordinary pointer and in-game menus.

Opening launcher gear, keyboard or mappings, losing focus, pausing/exiting, runtime or relative-input disconnects, controller capture/rebinding/device or layer changes, Escape and Enter release the latch. Native in-game windows are not automatically detected. Releasing the latch preserves independently held right-button inputs. External mouse capture is released when look is disabled. The optional controller action responds to a fresh physical press, not repeats or synthetic layer reconciliation.

Enabling requires a live client, active game input and a ready relative-input channel. Relative send failure clears look before pointer fallback. Existing controller maps and default bindings remain intact; Custom and Traditional retain their existing input.

New TAKP settings select Accurate in both launcher and runner. The confirmed math flags are `X87DOUBLE=1`, `FASTNAN=0`, `FASTROUND=0` and `SYNC_ROUNDING=1`; an explicitly saved Balanced choice is retained until changed by the user.

The grouped controls, spell filename handling, logging and prior startup repairs remain included. All 21 native launcher components are byte-identical to verified 0.6.20. Server pins, deployed binaries, database, client assets, DLLs, renderer and Wine prefix remain in place.

## Verification

All three main CI jobs passed: APK `114139668467`, ARM64 server `114139668326` and preview `114141249503`. Checks passed **409 Python tests without skips**, **13 browser programs**, **12 JVM programs**, **four native fixtures**, real Microsoft DirectX extraction, Android assembly/lint, signing, helper provenance and all 21 native reuse checks. The storage-cleanup and ferry workflows also passed; the separate general Android-preview workflow was intentionally skipped.

New tests cover Accurate defaults and saved-choice preservation, dedicated latch ownership, independent right-button holds, touch without left clicks, pointer recovery, lifecycle/focus/capture release, relative-send failure, physical controller edges, repeats, neutral rearming and layer transitions. Toolbar checks continue to cover 54 world/theme/viewport combinations.

Native ARM64 Bookworm qualification passed all **13 checks**, including nine production binaries and ELF dependencies, complete pinned source/content, four seed parts and eleven bot migrations, existing-database refusal, salted accounts, local services, Qeynos map/Lua startup, all 156 Paineel NPC creation events, two unfiltered client exports, clean shutdown and Custom workspace preservation.

The production Mac translator/encryption checks use the literal 224-byte client spawn layout. Bulk packets for 1, 56 and 100 NPCs were independently decoded and validated, at 78, 1021 and 1700 wire bytes respectively. All 156 individual `NewSpawn` packets passed, totaling 12791 encrypted bytes. This establishes server build/content/encoding qualification; the user's device test separately establishes visible NPC models.

Downloaded release and ARM64 ZIP sizes and SHA-256 digests match GitHub artifact metadata. The four extracted release files match the published asset IDs, sizes and digests. The actual Android manifest and APK v2 signature/content digest were independently verified. All 39 packaged backend modules, 49 UI files, 21 native components, three pinned TAKP helper DLLs and provenance match the reviewed build. All 21 changed source files and 105 archived source files checked match the built commit. The preserved native source archive matches 0.6.20 SHA-256 `c4c61cff60aa4c73222ceb7c2964e1462c68892dc5d1511804bdfd9e6f533deb`. The APK DEX contains the new toggle action, labels and dedicated input owner.

The published source archive records the preparation document at the built commit; this post-verification report records the completed checks without changing the packaged code.

## Bots proposal

The [Bots manager design](bot-manager-design.md) proposes one tab across all three worlds: select the owner character, draft a named roster with valid race/class/gender choices, generate bots offline, then preview/install summon/group socials and explicitly chosen free hotbar bindings.

TAKP supports minimal owner-linked creation and automatically groups spawned bots. Custom and Traditional require a versioned server-owned creation utility to preserve their creation rules, appearance, hooks and default items; invite commands need their own target/pause qualification. Social edits require literal command preservation, file backups and occupied-slot guards. RoF2 slot/hotbar formats are researched; TAKP's exact character-file format still needs a real client round trip. This release includes the proposal only, not the Bots tab, creation utility or social installer.

## Device handoff

1. Camp out, stop the client/runtime, then install 0.6.21 as an APK update.
2. Keep Accurate selected and start the existing TAKP runtime, server and client.
3. Enable **Look on**, then steer with the right stick and touch without holding LB. Disable it and check ordinary pointer and in-game UI input.
4. Open launcher gear, keyboard and mappings; background/resume; confirm look returns off. Optionally bind **Toggle mouse look** to a controller button and check external-mouse capture/release.
5. Confirm NPC models remain visible. Camp and export fresh logs if input or rendering regresses.

No reimport, prefix reset, repeated Prepare, server rebuild or database reinitialization is required. The new mouse-look toggle and camera feel still require Thor acceptance; zoning and playerbot gameplay remain separate device checks.
