# Published 0.6.27 — TAKP input diagnostics

Published 2026-10-14 at 00:41:48 UTC (October 13, 19:41:48 Chicago).
Package 0.6.27/code76 adds bounded read-only capture settings, native X events
and Android sent-packet observations for the still-unusable Thor right-stick
camera. This is a diagnostic update; physical camera acceptance remains open.

[Download the verified APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?v=0.6.27) —
18,923,551 bytes, SHA-256:
`603776458fb2d245262bb36febdec5380557270cc39f5bc476267e21095f5595`.
Install as an Android update without uninstalling. The working server needs
no source update, compilation, deployment, database import or prefix reset.

[Release run 38490628425](https://github.com/Russianranger/trasc-server-android/actions/runs/38490628425)
passed all five jobs, including 559 Python tests with zero skips, management/
JVM/C checks, APK assembly/lint/signing and all three server-profile gates.
Qualified source `8086fc2bc5a13a4c385bdf7910f7d941310da233`, tree `e685e2f149ac3358d842744cd3647e3f1b69e3f2`.
[PR #34](https://github.com/Russianranger/trasc-server-android/pull/34) merged as
`bca4328715625a11f64071c42217d8155d0c4017` with the exact qualified tree. The preview tag remains on
the qualified source; this documentation receipt does not rebuild its payload.

Independent public downloads verified the APK's v2 signature with Google's
apksig 8.8.2 (no errors/warnings, preserved signing certificate), all 124
bundled source assets, all 566 archived Git files and all four asset digests.
All 21 existing native launcher components and the V3 EQW helper are byte-equal
to the actual published 0.6.26 APK. The new ARM64 observer, its source/build
receipt and five-case runtime evidence match. Exact receipts are in
[release-proof-0627.json](release-proof-0627.json).

The exact published ARM64 runtime and native-host qualification passed
[run 38489151047](https://github.com/Russianranger/trasc-server-android/actions/runs/38489151047)
at source `3511ce6260ccef33478983d79356a205b8b43c5d`. Default/enabled capture delivers signed
reversals; disabled controls reproduce accepted cached clipping with an
escaped physical pointer. These controls do not identify the user's setting.
The observer collected bounded XI2, device, focus and pointer evidence under
held capture in all cases. This fixture is not physical Thor acceptance.
See [takp-input-0627.md](takp-input-0627.md) for the short device test and logs.

Keep the working TAKP server/Yaulp, databases/characters/bots, client assets,
Wine prefixes, installed runtimes and settings. This measurement does not
change the camera delivery implementation. NPC visibility and Traditional
StoneUI remain separate. Full all-profile reopening, external backup/model
restore and physical no-work/object-retention measurements remain separate
acceptance gates.
