# Published 0.6.31 — profile export and Wine-prefix browsing

PR #38 is merged. Qualified source `f165ec0`, tree `3e0a790e53a5b5ebb582ca9c82c523d29f591b56`.
APK: 18,960,032 bytes; SHA256 `132243827df0dcf2d275e9a01396111861b8a94a35a0d2b267be5727b9537105`.

Files now exposes **Export all profiles** through the same direct-to-destination
ZIP64 exporter as Server → Session backups. Both entry points share busy,
installation and transfer gating. Existing sequential runtime checkpoints,
SQL snapshots, progress/cancellation, fixed file buffers, memory/count/index
limits, destination-failure cleanup and verified restoration remain intact.

Missing lazily created backup/export/import collections return an empty native
listing without creating folders. Traditional/TAKP Old Wine prefixes displays
an explanatory message when no prefix backup exists. Unknown paths, symlinks,
protected live files and explicit reviewed deletion remain guarded. Empty or
failed listings clear stale per-page cleanup candidates.

[Release workflow](https://github.com/Russianranger/trasc-server-android/actions/runs/38815690385)
passed: 569 Python tests, zero skips; JVM/C; all 16 browser scripts; Android
assembly/lint/signing; exact 0.6.30 native reuse and qualified TAKP helpers.
All archive stress cases passed under a 96 MiB heap: 4,294,967,313-byte file
export/restore with independent checksums, 190,000 files, 87,000 long-name/link
records and a 58,256,144-byte index. Independent public APK audit matched the
manifest and qualified source; ZIP integrity passed; all 52 UI source assets
matched. Only four expected asset files changed; 149 remaining assets/libraries
match the actual published 0.6.30 APK byte-for-byte.

Install as an update without uninstalling. Stop/camp the client first. Use
Files → Export all profiles and a destination with sufficient capacity and
support for >4 GB files, such as exFAT. Reopen the runtime after export. Check
Old Wine prefixes separately in Traditional and TAKP; existing backups should
list, otherwise the empty-state explanation should appear. Physical large SAF
export/restore/provider/lifecycle acceptance remains pending. No server build,
client import or prefix repair is needed for this update.

See [release-proof-0631.json](release-proof-0631.json) for receipts and hashes.
