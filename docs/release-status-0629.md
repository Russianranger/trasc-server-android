# 0.6.29 window discovery diagnostics — qualification pending

Candidate 0.6.29/code78 records the real TAKP X window layout because 0.6.28
never recognized its target on Thor and made zero focus-repair attempts.
This preserves the qualified focus helper, V3 cursor helper, existing observer,
all existing native launcher components and input/camera settings. It adds
read-only bounded diagnostics and final child-state refresh only.

Native inspector qualification, APK assembly/signing, all profile gates,
publication and independent public verification are pending. Physical camera
acceptance remains failed. See [takp-window-0629.md](takp-window-0629.md).
