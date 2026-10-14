# 0.6.28 native TAKP focus recovery — qualification pending

Source candidate 0.6.28/code77 addresses the native PointerRoot focus mismatch
identified in the physical 0.6.27 logs. It retains the V3 EQW helper, the input
bridge and all existing native launcher components, runtimes and prefix
settings. A separate native companion changes only missing focus during a
guarded right-mouse gesture over the exact visible TAKP game window.

Runtime recovery/refusal qualification and release assembly/signing/profile/
publication gates must pass before this candidate becomes a published APK.
Physical camera usability is still unaccepted. Read
[takp-camera-focus-0628.md](takp-camera-focus-0628.md) for scope and the short
Thor test; [device-camera-0627.md](device-camera-0627.md) records the measured
failure. Keep the working TAKP server and Yaulp deployment; no source build,
database import, client reimport, runtime replacement or prefix reset is needed.
