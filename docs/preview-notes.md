# TRASC Android preview 0.6.26 · code 75

Repairs the TAKP mouse-look capture path identified by the 0.6.25 Thor right-stick trace. Wine could report a held clip while the cursor escaped it. The V3 EQW helper retries the same owned rectangle only when an escaped cursor is observed, at most once per 250 ms; it avoids repeated cursor warps and focus changes.

The real Wine 10/TigerVNC gate deliberately loses the physical grab while focus, RMB and the cached rectangle remain unchanged. It verifies old behavior stays escaped, one V3 retry restores capture, both DirectInput APIs receive separate signed small movements exactly, and idle drift remains zero. Native helper qualification passed run 38349508008. Actual Thor camera acceptance is still required; no physical camera success is claimed.

Install as an update. Stop/relaunch TAKP's client to upgrade the known managed helper automatically, retaining earlier originals and the exact 0.6.24/0.6.25 helper backup. Modified/custom helpers refuse automatic replacement. No server source update/rebuild, database initialization, client reimport or prefix reset is required. Retain the already working Yaulp server.

Preserves Builds → Updates in all three profiles, all-profile streaming backups, classic skeleton enable/restore, saved characters/bots, imported clients/Wine prefixes, installed runtimes, controller/renderer/theme settings and signing identity. Native launcher payload and other client helpers are reused. TAKP NPC visibility and Traditional StoneUI remain separately unresolved.

See [camera details and Thor test](https://github.com/Russianranger/trasc-server-android/blob/main/docs/takp-camera-0626.md), [release status](https://github.com/Russianranger/trasc-server-android/blob/main/docs/release-status-0626.md), and [retained preservation checks](https://github.com/Russianranger/trasc-server-android/blob/main/docs/device-acceptance-0625.md).
