# Published ARM64 camera-path qualification

The optional workflow `.github/workflows/takp-camera-runtime.yml` distinguishes
the published Bookworm/Box64/TigerVNC input path from the successful native-host
Wine fixture. It does not rebuild the client runtime, production input bridge,
EQW helper, Android launcher, server binaries or player database.

## Immutable inputs

The workflow fetches public release **asset IDs**, checks their identities and
then checks downloaded bytes. A changed rolling tag cannot silently substitute
a later runtime or APK. If an old asset has been deleted, qualification stops.

| Input | Asset ID | Bytes | SHA-256 |
|---|---:|---:|---|
| Published client runtime | 617421976 | 353710680 | `2f130c07683e50bc606af111d5c35c4f503c1427772c1f9b0f45e1e4b75c76c4` |
| Runtime manifest | 617422429 | 356 | `f61bf0e4719815ba8b67dff437af8944f0b11173d3b63572bcca51985c3cd0ea` |
| Actual 0.6.26 / code 75 APK | 635995342 | 18901782 | `7bb7a902c5695a430e396ddd035703b4cce278c11896b371a98363090290fa85` |

The runtime manifest identifies client-1.0, Wine 10.0 WoW64, Box64 0.4.4 and
source commit `270b0bbb485e80397148112ebca66a5d98c0f69e`. The archive is imported
unchanged into a native `ubuntu-24.04-arm` Docker environment. Actual package
versions, including TigerVNC, are retained in `runtime-packages.log`.

The APK's exact ARM64 `x11-frame-bridge --input` handles the fixture's TRASCIN1
socket, including its production packet parser and per-packet XFlush. Its
SHA-256 must match the embedded presentation receipt. The actual patched
wineserver is overlaid at `/opt/wine/bin/wineserver`; its hash must be
`09933d17ab07fe9c79245b22c9b8f4ff3fbc42d237595bb693271d168c8cb7d3`.
Only the open PE32 consumer and a separate read-only ARM64 observation tool are
compiled. The observer is compiled in Bookworm so its glibc ABI matches the
preserved runtime.

## Controlled prefix comparison

Each case creates a new disposable Wine prefix. The wrapper executes the open
fixture as `eqgame.exe`, so Wine's per-app values and Box64's production
accurate-profile overrides apply to that process name. Global and app values
are queried and recorded after initialization. No existing player prefix is
opened or edited.

| Case | Global GrabPointer | Per-eqgame.exe GrabPointer | Expected observation |
|---|---|---|---|
| Default | Absent | Absent | Full signed-input fixture passes |
| Global disabled | N | Absent | Accepted cached clip with escaped physical pointer |
| Global enabled | Y | Absent | Full signed-input fixture passes |
| App disables global | Y | N | Accepted cached clip with escaped physical pointer |
| App enables global | N | Y | Full signed-input fixture passes |

The disabled cases count as successful controls only when recorded native
focus, visibility and held Look remain active, Wine reports the one-pixel
clip, and XQueryPointer proves physical escape during the raw-look fixture.
A bootstrap, protocol, missing-library or unrelated failure does not satisfy
that control. All cases are attempted before a combined pass/fail result is
written.

The observer records XI2 client version, master/source device IDs, device
valuator modes, cooked/raw values, focus/PID ancestors and current pointer.
Its sampling is bounded to 128 KiB and five minutes; core MotionNotify may be
absent while Wine owns the grab and is not treated as proof that input stopped.
The begin row's monotonic and epoch clock anchors support correlation with
producer and game traces. It requests XI2 2.2, whose raw-event behavior includes
delivery while another client owns a grab.

## Evidence and limits

`takp-published-arm64-camera-proof-0627` contains the combined receipt and all
case logs, registry observations, native X events and DirectInput results.
`takp-bookworm-arm64-xinput-observer-0627` contains the observer ELF and its
exact source/build receipt. `takp-native-host-cursor-receipt-0627` reissues the
existing x86-host proof after adding optional observation support; it is the
receipt to bundle for the unchanged EQW helper's source-fingerprint checks.

The expected download is about 373 MB plus the small test-toolchain image. A
single ARM job runs five fresh prefixes; allow roughly 10–25 minutes, depending
on runner and package/download speed. That estimate is not a measured result.
The job has a 45-minute limit. The native-host fixture runs independently.

This isolates the published runtime and native input bridge. The fixture is
800×600 with an open consumer, while the Thor session is 1280×720 and uses the
actual client, Android, PRoot, physical stick and GPU. CI cannot establish
physical reversal acceptance. If default and enabled controls pass here while
Thor still fails, preserve its actual global/per-app registry values and use
device-side producer/XInput/DirectInput traces before selecting another fix.
