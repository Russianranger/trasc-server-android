# Physical TAKP mouse-look acceptance: 0.6.30 on AYN Thor

**PASS for the tested Thor right-stick configuration.** On October 14, 2026,
the user reports: “That worked!! It's perfect now.” The fresh device logs
support that usability result with an actual game focus repair, capture
refresh and correctly signed camera input. This closes the mouse-look failure
reported through 0.6.29 for this configuration.

The device explicitly reports TRASC 0.6.30, AYN Thor, Android SDK 33, TAKP,
1280×720, Turnip 26.0.0, DXVK 2.5.3, Native Surface, accurate CPU mode and
relative XTest input. Code 79 comes from the published release mapping;
the export contains the version string, not an explicit version-code field.

The bundle `logs-1420871679027905814.zip` is 783,177 bytes, SHA-256
`f3001e2135723deadfff8a0819a3241e68fadc52bb8ea07d95387a6049c62f9a`.
It was exported at **17:37:37.104783 UTC / 12:37:37.104783 Chicago** on
October 14. The ZIP CRC check passes. Full measurements, reconstruction
samples and 17 source-file hashes are in
[device-camera-evidence-0630.json](device-camera-evidence-0630.json).

## Actual recovery and game-input evidence

| Check | Physical result |
| --- | --- |
| Qualified helper | Official V3 upgraded to V4 EQW SHA `ae556d045a0b64586b1e4f0c0957a75c99626f9f149f8e95b7bb99ed7a738fc8`; the game loads native EQW and logs the V4 marker. |
| Scoped focus repair | V2 helper SHA `fcec1f6a4f0d1101efef56f58671b47944fd19219f0eeb3a4591a66607f5b364`: one attempt, one success, PointerRoot → Client1 window 20971521, physical RMB and depth-three pointer path, zero errors. |
| Verified event/capture refresh | Sequence 1 is written successfully, then the actual game logs `focus_clip_refresh seq=1 ok=1` **23 ms later**, with generation 272/272 and held/Look/physical/foreground/visible all valid. |
| Sampled physical capture | Twenty held window-inspector samples and 44 held XI2 samples show the pointer centered at 640,360 after recovery. |
| Signed native input | **125/125** XI2 samples within pointer-log coverage match signed Android input exactly; delivery is 0–5 ms. |
| Signed game input | **67** same-frame game consumers exactly match reconstructed signed packet sums, covering positive and negative movement on both axes. |
| Sampled neutral game behavior | **35** post-refresh zero-result consumers produce zero camera delta with unchanged accumulators. |
| Look release/reentry | Six successful clip releases, 127 Look-off buffer records and repeated native RMB periods are present. |

The game-buffer reconstruction uses consecutive nonzero held relative packets,
requires matching signed XY sum and nonzero-axis event count, and allows
0–8 ms delivery at each endpoint. Of 98 physically held nonempty buffer
samples within packet-log coverage, 97 have a unique reconstruction; 67
also have a same-frame logged game consumer within 0–2 ms. The remaining
buffer uniquely matches when a 14 ms first-endpoint delay is allowed and
is kept outside the conservative count. No opposite-sign result appears
in the 67 exact game matches.

The 1,434 recorded held relative packets include 39 neutral packets.
Recorded queue latency is 0–8 ms and queue drops are zero. The current
capture/consumer measurements support the user's report of immediate,
usable reversals rather than the old escaped-position camera behavior.

## Preservation and session evidence

The existing TAKP server starts from 17:32:34 to 17:32:41 UTC, seven seconds.
Saved character ID 4 enters Paineel at 17:33:54 and camps normally at
17:37:05, a 191-second session. The client returns to character select at
17:37:25 and logs `Quitting normally` at 17:37:28. Display shutdown is normal.

The Wine prefix explicitly reports `reuse`. Forty-eight selected stable
configuration/runtime fields match the previous launch, including renderer,
presentation, resolution, CPU settings, storage and installed runtime
component hashes. No new source update, build/deployment, database import or
reset is recorded. The helper reports no prefix-settings change. Registry
bytes differ across sessions, so this is reuse/configuration evidence rather
than a byte-identical prefix claim.

The upgrade receipt reports the original EQW backup path. Backup binaries
are absent from this bundle, so their exact physical bytes are not verified
by this test. Controlled upgrade/backup transaction qualification remains
in the [publication receipt](release-proof-0630.json).

## Measurement scope and separate checks

XI2 is sampled, and the pointer/window/camera diagnostic logs reach their
byte limits. The pointer logger has one unwritten selected diagnostic record,
the window inspector has two byte-limit drops, and the camera trace reaches
its inferred 128 KiB cap. These are separate from zero input-queue drops.
Forty-six later XI2 samples fall beyond pointer-log coverage and are not
classified as input mismatches.

One later noncentered native snapshot occurs two milliseconds after a brief
RMB press, beyond camera-trace coverage; clip activity cannot be established
for that transition. Look records do not identify whether the tile or a
physical button generated the changes. Background/resume is not separately
labeled. These limits do not reopen the user-accepted camera failure.

The focus helper ends with zero errors/drops. The XI2 observer's five X errors
occur only during RMB-up window teardown, the first 72.441 seconds after the
last RMB release; held gameplay samples have no X errors. The export still
reports Stopping/alive, so it is not a final fully stopped/server-shutdown
receipt.

Existing server start, source update/build/deployment and the cleric Yaulp
correction remain confirmed from prior user reports. This camera bundle does
not establish full inventory/saved-bot persistence, all-profile external
backup/restore, classic skeleton visual/exact restoration or physical
incremental/no-work build receipts. NPC visibility and Traditional StoneUI
remain separate unresolved checks.

The [release proof](release-proof-0630.json) preserves publication-time
camera-pending status. This later physical receipt supersedes that status
for the tested configuration. The qualified APK and preview source remain
unchanged; 0.6.30 is the working camera baseline.

