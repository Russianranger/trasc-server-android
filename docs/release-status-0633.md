# Published 0.6.33 — scalable all-profile backups

[PR #39](https://github.com/Russianranger/trasc-server-android/pull/39) merged.
Source `de3d2a5`; [qualified release run 38847312963](https://github.com/Russianranger/trasc-server-android/actions/runs/38847312963) passed.
APK 18,970,100 bytes, SHA256 `34a55129b0e46a09f2659abee8141fa664c3d059474a2b45475fcc8d11ab54f4`.
Install as an update without uninstalling; keep existing profile data.

The user's 0.6.31 report hit the combined 200,000-entry preflight limit. The new
production all-profile writer/reader uses v3: two ZIP members and sequential
records, with bounded buffers and a disk finalization journal. No per-file ZIP
central directory or whole-installation heap inventory remains. File digest
contexts are reused; hot path validation uses literal checks to avoid repeated
regex allocation. Files, prefixes, databases, runtimes, sources, builds, logs
and settings are retained within the same existing component/exclusion policy.
Existing checkpoint/quiesce, cancellation, SAF failure cleanup, staged identity
validation, sync, atomic activation and crash recovery remain in place.

Final exact-source CI passed 569 Python tests/zero skips, management JVM/C,
all 16 browser scripts, Android assembly/lint/signing, exact native reuse and
qualified TAKP helper proofs. Production export AND restore stress passed at a
48 MiB heap: 600,661 actual filesystem records with 200,001 real fixture client
files per world, and a 4,294,967,313-byte file with independent source/restored
SHA256. The legacy writer rejects the same many-file installation at its old
limit. Small tests also cover bytes, guest links/modes, partial-world preservation,
legacy read compatibility, staged activation, corruption, duplicate/traversal/
alias paths, link ancestors, cancellation, provider failure and journal cleanup.
Separate full-runtime/database integration checks also passed.

Independent public APK download matched the manifest, version 0.6.33/code 82,
qualified source and preserved certificate. ZIP integrity passed; all 52 UI
source assets and backend engine matched local qualified sources, and DEX
contains the streaming implementation. Only engine version and UI help/footer
assets differ from actual 0.6.31: 151 remaining assets/libraries match exactly.
The public source-archive digest matches the qualified manifest and GitHub asset
record. This is not a claim of downloading/re-auditing that entire source TAR.

New v3 all-profile backups require 0.6.32+ to restore. Existing single-profile
and v2 backups remain readable. Limits remain explicit: 2 million records,
256 GiB regular contents, 512 MiB metadata, 16 KiB text fields, depth 256.
See [session-stream-0632.md](session-stream-0632.md) and
[release-proof-0633.json](release-proof-0633.json).

Device next: camp/stop the client, install in place, Files → Export all profiles,
choose adequate storage with >4 GB support (for example exFAT), and wait for
success. Reopen runtime afterward. Retain the ZIP and collect fresh logs.
Physical Thor large export/restore/provider/lifecycle acceptance remains pending.
Use a separate test installation/device for a replacement restore test. No
server rebuild, client import or Wine-prefix reset is needed for this update.
