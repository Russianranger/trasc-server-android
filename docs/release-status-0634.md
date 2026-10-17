# Published 0.6.34 — session file-picker handoff

Source `cff8beba3448c77808ca132815b648a0a4b2d230`, qualified tree
`db6f791db10adc313104fdab617831aba7797a0a`.
[Release CI 38998882560](https://github.com/Russianranger/trasc-server-android/actions/runs/38998882560)
passed and published version 0.6.34/code 83. APK 18,970,464 bytes, SHA256
`7d787bc90c7c53a73f60c1eb1f79820cbb310d90db8149c5e929512d7971f307`.

The user's 0.6.33 report records two admission failures before archive writing,
with session state idle. The immediate profile-lease check can mistake launcher
resume/poll overlap for active transfers. The new session gate reserves
admission, drains existing requests for up to five seconds without holding the
runtime monitor, and releases pending state on timeout/interruption. Actual
transfers/pickers/client displays remain guarded; no lease counter is reset.
Storage cleanup keeps its immediate gate. See [session-handoff-0634.md](session-handoff-0634.md).

Local production-gate tests cover overlapping resume/poll leases, admission and
switch exclusion, actual-transfer timeout without lease loss, interruption,
retry and preserving another owner's reservation. The old immediate behavior
fails the same overlap regression. Exact-source CI passed 569 Python tests/zero
skips, JVM/C, all 16 browser scripts, Android assembly/lint/signing, exact native
reuse and accepted helper proofs. Production 600,661-record and 4,294,967,313-byte
export/restore roundtrips both passed with a 48 MiB heap and independent hashes.

Native assets/libraries are reused from the independently hashed 0.6.33 APK.
App ID, certificate, installed profiles, clients, prefixes and archive format
are preserved. Older backups remain readable; v3 all-profile backups require
0.6.32+ to restore. Install over the existing app and retry Files → Export all
profiles. No server rebuild, client import or prefix repair is required.
Physical Thor SAF/provider/lifecycle and large restore acceptance remain pending.

The final receipt commit only updates documentation; the release source above
is the qualified code. The skip-CI receipt avoids rebuilding unchanged server
and native components for documentation-only PR publication.

Independent public download matched the qualified manifest and GitHub asset
SHA256. ZIP integrity passed. All 52 UI files and backend engine match the
qualified source; DEX contains the session gate and v3 implementation. Relative
to the downloaded 0.6.33 APK, 151 asset/library entries are identical; only the
engine version and UI footer assets differ. The source-archive digest matches
the build manifest and GitHub asset record; the whole source TAR was not
independently downloaded/re-audited. See [release-proof-0634.json](release-proof-0634.json).
