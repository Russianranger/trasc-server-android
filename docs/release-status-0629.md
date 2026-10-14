# 0.6.29 window discovery diagnostics — APK qualification pending

Candidate 0.6.29/code78 records the real TAKP X window layout because 0.6.28
never recognized its target on Thor and made zero focus-repair attempts.
This preserves the qualified focus helper, V3 cursor helper, existing observer,
all existing native launcher components and input/camera settings. It adds
read-only bounded diagnostics and final child-state refresh only.

Native ARM runtime qualification passed
[run 38505023364](https://github.com/Russianranger/trasc-server-android/actions/runs/38505023364)
at source `50ae39a550a6597a294f92502693e28b625ef993`. Actual bounded logs from
14 property/layout cases completed normally with zero drops/X errors and
unchanged focus/pointer/buttons. Max log15,928 bytes; invalid CLI and SIGTERM
checks passed. Inspector ELF72,232 bytes, SHA-256:
`e1df07509f870d35f8feea87e64f20101597bd14dbc5ed0632335906b312d21c`.
All four build and twelve fixture fingerprints match. Original focus/observer/
input/runtime bytes remain. This qualifies collection, not camera repair.

APK assembly/signing, all profile gates, publication and independent public
verification are pending. Physical camera
acceptance remains failed. See [takp-window-0629.md](takp-window-0629.md).
