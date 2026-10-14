# TRASC Android preview 0.6.30 · code 79

The Thor logs identify the actual TAKP window as exact `Client1`, while the
previous recovery helper accepted only `EqW-TAKP`. Version0.6.30 accepts both
exact titles with the existing process-class, visibility, pointer-path,
physical Look and absent-native-focus ownership guards.

Actual ARM qualification also reproduced a capture gap after restoring
focus: Wine's cached cursor could stay at center while the physical pointer
escaped, turning twelve fresh +1 packets into78. V4 now receives a tiny
private per-launch success notification and submits the same owned capture
rectangle once after a verified focus repair. It adds no frame warps, input
drain, axis conversion, registry change or runtime replacement.

The actual MSVC V4 helper and shared code passed native qualification:
24 exact signed segments (including centered restore),32 focus refusals,
9 event-reader refusals and three once-only repair/refresh sequences.
This is controlled runtime qualification; physical Thor camera acceptance
remains pending. APK/profile/signing/public download gates must also pass.

Camp and stop clients/servers normally, install in place without uninstalling,
then reopen TAKP. The official V3 helper upgrades with its exact backup
preserved, along with earlier originals. No Prepare/reimport, server rebuild,
database import or prefix/runtime reset is required. Keep the Yaulp deployment.

Test short Thor right-stick reversals in both axes, neutral and Look off/on;
background/resume and repeat. Camp/stop, wait stopped, export fresh logs.
Correlate V2 focus_repair/event_written with V4 focus_clip_refresh and actual
signed native/game input. NPC visibility, Traditional StoneUI and other
backup/bot/model/object-reuse acceptance remain separate. See
`docs/takp-camera-client1-0630.md` and `docs/device-camera-0629.md`.
