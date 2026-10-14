# TRASC Android preview 0.6.27 · code 76

This is a diagnostic update for the still-unusable TAKP right-stick camera.
The existing V3 helper remains unchanged. It automatically records bounded,
read-only capture settings, native X focus/pointer/raw events, and the actual
Android pointer packets with queue/send timestamps. File I/O runs off the input
writer. No focus changes, pointer warps, injected movements or registry changes
are performed by the observers.

The exact published ARM64 Box64/Wine/TigerVNC runtime passed signed motion and
reversals in controlled qualification. Disabled-capture controls reproduced
successful ClipCursor calls with an escaped pointer. This narrows the device
investigation; it does not establish the user's setting or a physical fix.

Install as an update and restart only the TAKP client. Keep the working server
and Yaulp deployment. After a short right-stick reversal test, stop the client
and export logs. Server source/database/characters/bots, client assets, Wine
prefixes, runtimes, settings and all-profile backup remain in place. No new
server update/build/deployment, client import or prefix reset is required.

Camera acceptance remains open. NPC visibility and Traditional StoneUI remain
separate issues. See docs/takp-input-0627.md for qualification and test scope.
