# 0.4.5: preserve useful evidence after the rejected CPU comparison

## Device findings

Inputs: logs-2366861782211882706.zip and logs-369691760030245216.zip, with 06:51:09 and 06:53:03 September 16 videos. Extracted under ../analysis-044/a and b. Three distinct sessions are preserved: Balanced → Accurate → Balanced, all with exact `compatibility_042`, verified Adreno 740/Turnip24.3.4/DXVK2.5.3, native D3DX30/35, 1280×720 fullscreen, sound diagnostics on and general verbose diagnostics off. Final warm launch requests took 10.320s (Accurate) and 7.461s (Balanced); these are separate runs, not controlled benchmarks.

The user confirms music, sit/stand and swinging effects in both profiles, silent spells, unchanged corrupted names and worse Legacy math FPS. Reject the 0.4.4 CPU hypothesis for these observed defects; keep Balanced and the confirmed 0.4.2 NPC settings. Do not repeat the failed 0.4.3 direct-mapping experiment.

Both short videos were sampled at 0/5/10 seconds. The selection label has readable yellow name/class/zone text plus repeated/extruded yellow geometry. The in-world NPC labels appear readable in the supplied samples. This remains a rendering problem, not typed character-name input. The second video shows game sound at 100 and music at 0. Startup INI inventory shows SoundVolume20; that is a pre-launch snapshot and does not invalidate the visible in-game adjustment.

The final Balanced audio stream reaches 11,178,336 submitted frames / 11,176,416 played, 776,115 nonzero samples, three underruns. Accurate reaches 9,862,400 submitted frames and 966,549 nonzero samples, 50 underruns. Underruns stabilize after early loading; these runs do not establish a causal CPU comparison. The bridge continues advancing through silent periods. Retained sound traces show repeated filling/mixing of the same secondary buffer, without retained DirectSound/wave/MMDevice warnings/errors. They do not identify an individual spell inside Miles' mix.

The new inventory finds 1777 loose WAVs, 3136 unique WAV references, 1644 resolved loose and 1492 unresolved loose. The first 256 headers include 241 mono PCM16/22050, 10 PCM16/48000, 3 PCM16/44100 and 2 float32/22050. This sample does not identify the spell WAV formats. The old report neither indexes PFS archives nor names the spell-specific results; unresolved loose references cannot establish missing assets. `sounds.eff` and `spelleffects.eff` absence is not proof of a broken ROF2 installation.

## Corrected diagnostics, unchanged playback/rendering

0.4.4 generated 24–31MB of Wine text per session, rotating away all startup DirectSound evidence. The new `client-wine.sound.json` retains bounded first/last lifecycle samples and counts per function independently of the existing two 8MiB text segments. Known high-rate mixer/lock/padding calls are counted and omitted from this summary. It updates every five seconds and at EOF; the next launch retains `.previous.json`. Limits: 96 event types, three first and three last samples/type, 512 characters/sample. Write failure is reported without aborting the client. No file/API payload tracing, arbitrary file paths, raw PCM, credentials or chat are added.

With Sound diagnostics enabled, read-only `client-sound-assets.json` format2 checks up to64 root `snd<number>.pfs` archives, their filename table and selected casting/spell WAV header prefixes. It matches filenames by the PFS CRC including the NUL byte, not directory order. Known casting/effect names plus bounded spell-prefixed sound-table references are reported with loose/packed location and format. It counts references found only in packed archives and explicitly reports incomplete scans. The reader has an aggregate8MiB read budget, 512MiB archive-size limit,8193-entry directory limit,512KiB filename-table limit,64KiB compressed/inflated-block limits, and strict offsets, inflate sizes/EOF, CRC/name ambiguity and safe basename checks. No files are extracted or replaced. Header inspection returns formats only, not samples. Other resource presence checks now include spellsnew.edd/.eff, spells_us.txt and eqgraphicsdx9.dll.

UI guidance recommends Balanced and records the failed Legacy math comparison. Saved settings remain user-controlled. No renderer/driver, native bridge, client DLL, runtime image, prefix, server, app identity or signing change. This is explicitly a diagnostic release, not a spell/name fix.

## Validation and next step

71 backend tests pass locally, including independently computed fixed PFS CRC fixtures with reordered entries, actual zlib/WAV header parsing, read-only preservation, unreadable/budget/malformed-block handling and lifecycle evidence surviving repeated log rotation and split final lines. Existing rendering, CPU-profile, archive, privacy and audio tests remain. Full Android/runtime CI and release verification are required before publication.

Follow [preview-notes.md](preview-notes.md): one short Balanced/Turnip spell run with diagnostics, export immediately, then a short VirGL character-selection comparison and export. Return to Turnip and quiet logging. No further speculative global flags are recommended. Root causes remain unresolved until this evidence or a real reproducer establishes them.

## Primary references

- [EQEmu PFS reader](https://github.com/EQEmu/zone-utilities/blob/b361e63dd067e8959f5bf2341579f481d2374fd5/src/common/pfs.cpp) and [CRC](https://github.com/EQEmu/zone-utilities/blob/b361e63dd067e8959f5bf2341579f481d2374fd5/src/common/pfs_crc.cpp): format, special filename-table CRC and CRC association. The new Python reader is a bounded metadata implementation, not a bundled extractor.
- [WillEQ's Titanium audio catalog](https://github.com/wcassis/willeq/blob/7a8162a932d8eae81f1b5cc2f7d7a0210f268225/docs/reference/eq_audio_assets_catalog.md): known classic casting/effect filenames and packed archives. This does not establish which resources the user's modified ROF2 invokes.
