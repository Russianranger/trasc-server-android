# Released 0.6.26 — Thor camera acceptance remains

TRASC Android **0.6.26/code75** was qualified and published on October 13, 2026
UTC. [Run 38350483443](https://github.com/Russianranger/trasc-server-android/actions/runs/38350483443) passed all five jobs:
APK, TAKP production, Custom native, Traditional native and preview publication.
All 553 Python tests passed with no skips, alongside JVM, controller, DirectX
preservation and browser fixtures; Android assembly, lint and signing passed.

[Download the verified APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?v=0.6.26)
as an Android update. Size: **18,901,782 bytes**. SHA-256:
`7bb7a902c5695a430e396ddd035703b4cce278c11896b371a98363090290fa85`.

Two independent reads verified the public APK's binary manifest, original signing
certificate identity, 119 exact backend/UI/SDK assets, qualified V3 helper and all
21 native components. Signature validity was checked by release CI, and actual
public APK bytes match its build manifest. The public source archive contains
all 544 files of the qualified Git tree plus exact preserved 0.6.24 sources.
All four public assets and their hashes were independently checked. The rolling
bare APK URL briefly served cached 0.6.25 bytes; it subsequently returned the
new bytes. The versioned link above avoids that stale response.

Qualified source `72f482c58986d4b9d62f7d7e264cf5eadb4c80c1`, tree `6ace7009cb7b5aa891ad66d5583b34429384928c`;
[PR #33](https://github.com/Russianranger/trasc-server-android/pull/33) merged as `6ebe155ed8ae02c0b8eeff90d716a448c5509fb0`
with that exact tree. Preview remains on the qualified source commit.
This documentation receipt does not require another APK build. Full metadata,
native proof, public-asset identities and scope are in
[release-proof-0626.json](release-proof-0626.json).

## Camera repair and preservation

The fresh 0.6.25 trace came from the **Thor right stick**. It showed REL input
and young consumed events, but an escaped cursor despite Wine's cached one-pixel
capture rectangle. V3 retries the same owned rectangle only when escape is
observed, at most once per 250 ms, retaining physical-button, foreground and
lifecycle guards. It does not warp the cursor or change sensitivity or renderer.

[Native run 38349508008](https://github.com/Russianranger/trasc-server-android/actions/runs/38349508008)
passed the MSVC x86 build and real Wine10 lost-grab recovery, six exact signed
small reversals and zero idle drift. Exact helper/source/proof are bundled.
Helper SHA-256:
`875056a62d2df3c7434bf05d23d73186d6565d2bd5a14f2f53a58fa7d015bab3`.

On stopped-client relaunch, a known managed helper upgrades automatically and
retains its exact prior bytes as
`client/prefix/trasc-takp-camera-originals/eqw.0624.dll`, with earlier originals
also retained. Changed/custom helpers and corrupt or linked backups refuse
replacement. No server recipe/source pin, database, character/bot storage,
runtime, native Android input, renderer/settings, source-update or backup system
changed. See [takp-camera-0626.md](takp-camera-0626.md) for evidence and limits.

## Physical acceptance

The user confirmed the existing 0.6.25 TAKP server starts and the saved character
loads before source changes. Reviewed source update, compilation and deployment
succeeded; cleric idle Yaulp stopped. The physical log compiled only
`player_bot.cpp.o` and linked `zone`: 55 seconds with two jobs, deployment
21 seconds and subsequent server-start operation six seconds, excluding client
login/world entry.

Retain that working server. This camera release needs **only an in-place APK
update and TAKP client restart**. No server compilation, database initialization,
client reimport or Wine-prefix reset is needed. Keep renderer/CPU/inversion and
sensitivity fixed; test short right-stick reversals on both axes and diagonals,
neutral drift, Look off/on, inventory/chat, background/resume and a zone change.
Stop the client after a short test and export logs promptly. Retain
`eqw-camera-diagnostics.log`, V3 helper identity and any
`clip_repair count=... ok=...` rows, plus the exact direction sequence.
No repair rows can be normal during healthy capture.

Actual Thor camera acceptance remains pending. NPC visibility and Traditional
StoneUI remain separate unresolved issues. All-profile external checkpoint,
saved bots/characters across all profiles, classic skeleton appearance/restore
and physical repeat no-work build/object receipts still need confirmation.
Use [device-acceptance-0625.md](device-acceptance-0625.md) and
[source-updates-0625.md](source-updates-0625.md) for the retained preservation
procedure; 0.6.26 supersedes their APK and camera-helper identities only.
