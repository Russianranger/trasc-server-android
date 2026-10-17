# Session preparation after returning from the file picker

The 0.6.33 device report `logs-4597651028510037813.zip` records two
`save_export` failures at 2026-10-17 01:25:42Z and 03:21:53Z. Both are thrown by
`WorldProfiles.beginMaintenance` before the archive writer runs. The report
shows `session_busy=false`, `session_phase=idle` and no client running. This is
an admission failure, not proof that a transfer from an older build is alive.

The old gate required exactly one profile lease at the instant the SAF callback
started. Launcher `onResume`, status polls and other requests can already have
leases at that time, even though the picker has handed its own lease to the
transfer. That race reproduces the same failure without an ongoing transfer.

0.6.34 reserves session state, closes profile admission, and allows admitted
requests up to five seconds to release their leases. It does not hold the
RuntimeManager monitor while waiting: already-admitted log/status operations
may need that monitor to finish. The original caller's single lease remains
held through the entire transfer. New operations and profile switching remain
blocked. Genuine long operations, another picker or a client display still
cause a bounded refusal. No counter is forcibly reset. A failed or interrupted
reservation restores admission and idle session state; transfer finally blocks
retain their existing descriptor, partial-document and lease cleanup.

Storage cleanup keeps its immediate non-waiting gate, since its callers already
hold the runtime/client monitors. No archive format or payload code changed.
No persistent transfer lock is introduced or cleared; these gates are in memory.

`SessionGateHostTest` uses the production WorldProfiles gate and concurrent
leases to cover SAF/onResume/poll overlap, blocked new entry/switching, retry
after cleanup, real transfer timeout without lease loss, interruption cleanup,
and refusal that must not clear another owner's maintenance reservation.
Full management/archive regressions and release CI must pass before publication.
Physical device export/provider/lifecycle and restore acceptance remain pending.
