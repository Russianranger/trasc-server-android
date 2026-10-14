# Published 0.6.29 — read-only TAKP window diagnostics

0.6.29/code78 was published on October14, 2026 at03:32:36 UTC
(October13 at22:32:36 Chicago). This is a diagnostic update for the still
unusable Thor right-stick camera. The 0.6.28 helper ran but made zero repair
requests because the actual game window failed pointer-path discovery.
The missing title/type/length/class/visibility/layout facts require the new
device log. Existing focus recovery and camera behavior remain unchanged.

[Download the signed APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?v=0.6.29):
18,952,880 bytes, SHA-256:
`e81e6afe2ac639a292d7c048cc7575a9cbd1af6a19f2cfe4a934f2c723e40fcf`.

All five release jobs passed in
[run38505887209](https://github.com/Russianranger/trasc-server-android/actions/runs/38505887209):
566 Python tests with zero skips, management/JVM/C/browser/controller,
APK assembly/lint/signing and all three server profiles.
Independent actual public audit cryptographically verified v2 signing with
the existing certificate and no errors/warnings, all132 APK source assets,
all598 archived Git files, all public asset hashes and exact inspector CI bytes.
All21 native launcher components and old focus/observer/V3/TAKP assets match
the actual0.6.28 APK.

Native read-only qualification passed
[run38505023364](https://github.com/Russianranger/trasc-server-android/actions/runs/38505023364)
at source `50ae39a550a6597a294f92502693e28b625ef993`.
Fourteen property/layout cases preserved actual focus/pointer/buttons and
completed bounded logs normally with zero drops/X errors (max15,928 bytes).
Invalid CLI and SIGTERM checks passed. Inspector ELF72,232 bytes, SHA-256
`e1df07509f870d35f8feea87e64f20101597bd14dbc5ed0632335906b312d21c`.
Four build and twelve fixture hashes matched. This qualifies collection,
not physical camera repair or proprietary-game window identity.

Qualified release source/tag `aff675a1564c1bfee850dc5400de2b4cbed410bb`,
tree `b7995938db2dfc8324c3e966d0b3651c98021bcf`;
[PR36](https://github.com/Russianranger/trasc-server-android/pull/36) merged as
`4032f5922e07f9278706b947c02b03dfee0d8148` with the exact qualified tree.
Preview retains the qualified source; main adds documentation receipts only.
See [release-proof-0629.json](release-proof-0629.json) for exact public asset
IDs, signature, qualification, source and preservation receipts.

Camp and stop clients/servers normally. Install in place without uninstalling,
then reopen TAKP and retain the working Yaulp deployment, data, clients,
prefixes, runtimes and settings. No server rebuild/import/reset is needed.
Enter the saved character within five minutes of launch, enable Look and
reproduce Thor right-stick motion for ten seconds, turn Look off, camp/stop
normally, wait for stopped status and export a fresh bundle.
See [takp-window-0629.md](takp-window-0629.md).

Physical camera acceptance remains failed/pending. NPC visibility, Traditional
StoneUI, post-camp expired session key and backup/bot/model/object-reuse checks
remain separate.
