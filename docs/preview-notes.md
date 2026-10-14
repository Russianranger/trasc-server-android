# TRASC Android preview 0.6.30 · code 79

Published and independently verified October 14, 2026. All five release jobs
passed, including 569 Python tests with zero skips, all three production
profiles, APK signing/lint and exact native payload checks. The actual public
APK signature, source archive and qualified helper bytes were independently
verified. See `docs/release-status-0630.md` and `docs/release-proof-0630.json`.

The Thor logs identify the game window as exact `Client1`; the previous
recovery helper accepted only `EqW-TAKP`. Version 0.6.30 accepts both exact
titles with the existing process-class, visibility, pointer-path, physical
Look and absent-native-focus guards.

Actual ARM qualification also reproduced capture loss after focus restoration:
Wine's logical cursor could stay centered while the physical pointer escaped,
turning twelve fresh +1 packets into 78. V4 reads a private per-launch success
notification and submits the same owned capture rectangle once after verified
focus repair. It adds no frame warps, input drain, axis conversion, registry
change or runtime replacement.

The actual MSVC V4 helper and matching shared code passed 24 exact signed
segments, including centered restore, 32 focus refusals, nine reader refusals
and three once-only repair/refresh sequences. This is controlled runtime
qualification; **physical Thor camera acceptance remains pending**.

Camp and stop clients/servers normally, install in place without uninstalling,
then reopen TAKP with the working Yaulp deployment. The known official V3
helper upgrades with its exact backup and earlier originals preserved. No
Prepare/reimport, server rebuild, database import or prefix/runtime reset is
required. Existing profiles, data, client assets, runtimes and settings remain.

Within the first five minutes, test short Thor right-stick reversals in both
axes, neutral and Look off/on; background/resume and repeat. Camp/stop, wait
stopped, then export fresh logs. Correlate V2 `focus_repair/event_written`
with V4 `focus_clip_refresh` and actual signed native/game input.
NPC visibility, Traditional StoneUI and backup/bot/model/physical object-reuse
acceptance remain separate. See `docs/takp-camera-client1-0630.md`.
