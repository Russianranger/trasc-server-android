# 0.6.28 native TAKP focus recovery — APK qualification pending

Source candidate 0.6.28/code77 addresses the native PointerRoot focus mismatch
identified in the physical 0.6.27 logs. It retains the V3 EQW helper, the input
bridge and all existing native launcher components, runtimes and prefix
settings. A separate native companion changes only missing focus during a
guarded right-mouse gesture over the exact visible TAKP game window.

[Exact ARM runtime run 38500575431](https://github.com/Russianranger/trasc-server-android/actions/runs/38500575431)
passed at source `d0bd98e387727a7eae14a728eea4541c05610674`. The original
runtime, input bridge, patched wineserver and observer were reused. The open
PE32 fixture reproduced the stale Windows foreground/cached clip with actual
PointerRoot focus, escaped physical pointer and wrong fresh negative reversal.
The new companion then restored actual focus/confinement and all ten signed
segments through polled and buffered DirectInput, zero idle drift, menu release,
six refusal guards and None-focus recovery after resume. This is controlled
qualification, not proprietary-game/Android/PRoot/GPU or physical Thor success.

Qualified ARM64 focus companion: 72,232 bytes, SHA-256
`90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865`.
Its exact build and runtime receipts are bundled alongside the unchanged
observer. Actual focus/observer logs completed normally at 4,982/50,083 bytes,
with zero drops or X errors. The original fixture files and prior receipts
remain intact; source fingerprints are checked by the APK gate.

Release assembly/signing/profile/publication gates must pass before this
candidate becomes a published APK.
Physical camera usability is still unaccepted. Read
[takp-camera-focus-0628.md](takp-camera-focus-0628.md) for scope and the short
Thor test; [device-camera-0627.md](device-camera-0627.md) records the measured
failure. Keep the working TAKP server and Yaulp deployment; no source build,
database import, client reimport, runtime replacement or prefix reset is needed.
