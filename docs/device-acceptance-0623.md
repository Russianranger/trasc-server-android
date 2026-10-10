# AYN Thor acceptance: 0.6.23 / code 72

Install the APK as an update, without uninstalling. Keep the existing client,
Wine prefix, runtime, database, controller mapping, renderer and settings.
Before testing character exports, save a complete session checkpoint with the
client and server stopped. These tests extend the 0.6.22 acceptance work; they
do not require recreating bots or rebuilding the working TAKP server.

## TAKP camera

Keep the same renderer, resolution, Accurate / Legacy math accuracy and look
sensitivity used for the reported veering. Start the existing TAKP client.

1. With Look off, move the pointer around menus and click a harmless window.
   The pointer must move freely. Turn Look on and face a visible landmark.
2. Use the right stick for small left → right → left movements, then right →
   left → right. Repeat up → down → up and down → up → down. Perform at least
   ten reversals per axis, including quick reversals. The camera must reverse
   promptly and must not turn on the other axis or keep moving after neutral.
3. Hold each direction for several seconds. The camera must keep turning
   without stopping at a screen edge. Repeat the reversal sequence using
   touch drags while Look is on and, if available, a physical mouse with RMB.
4. Release RMB / turn Look off. Open chat, the launcher gear menu and keyboard,
   then resume the game. Background/resume once. Each interruption must release
   capture, restore a free pointer and require deliberate look activation.
5. Drag the gear away from game windows; the Look tile moves with it. Hide and
   show the tile, test the controller Toggle mouse look action while hidden,
   reopen the client and verify the saved position/visibility. Use Reset
   controls position and verify that both controls return to their default.

If veering remains, export logs immediately. Record the input source, direction
that was intended versus observed, whether Look was latched or RMB held, and
whether it followed a menu, zoning, death or focus change. The open Wine fixture
cannot replace this physical-device result.

## Combined bot buttons and command export

1. Stop client and server, keep TAKP runtime open, open Bots and Refresh roster.
   Choose the owner character and select two to five existing owned bots.
2. In Commands to export select Spawn party, Revive party, Follow and Report
   party. Preview buttons. If multiple character settings files match, select
   the correct one and preview again. Expect four separate socials, each with
   one named native command per selected companion. Inspect all names/lines.
3. Choose distinct free hotbar positions or Socials only. Existing occupied
   positions must remain unavailable. Assign the same free position to two
   actions temporarily: installation must be disabled. Correct the placements
   and Install buttons.
4. Before launching the client, Restore previous character buttons → select the
   newest restorable backup → Restore selected backup. Confirm the former
   personal buttons return, then preview and install the desired actions again.
5. Start server/client and log into that owner. With available group slots and
   the owner leading the group, press Spawn party once. Each eligible selected
   bot should spawn and auto-group. Test Follow and Report party.
6. For companions already fallen, leave combat and wait more than 60 seconds
   after the recorded fall. Press Revive party once, then Spawn party once.
   Revival restores one HP and zero mana; it does not spawn or fully heal them.
   Alive/active companions or a premature revival may receive normal refusals.
7. Camp/exit normally and reopen. Confirm social names/lines, hotbar positions,
   original personal buttons, bot roster and character settings persist.
8. Change a harmless personal social in game and camp again. Stop client/server
   and refresh the preview. The older backup must refuse to overwrite this
   changed file. Preserve the edit and use the complete checkpoint if needed.

Optional boundary check: six selected companions produce two numbered socials
per action because a native social has five lines. The server's active/group
limit still applies; selecting more names does not bypass it.

For failures, report owner, selected bots/actions, previewed lines, in-game chat
response and whether the failure occurred at preview, install, activation,
normal save or restore. Include the exported log bundle privately.

## Continuing 0.6.22 acceptance

Custom and Traditional retain their existing offline generation and per-bot
spawn/group export. Rebuild and deploy their qualified world servers only if
their current deployment lacks the offline creation utility; preserve the
database and installed runtime. Use Review storage and its full-backup safeguard
before any required table conversion. Follow docs/bot-manager-0622.md.

Track TAKP NPC visibility and Traditional StoneUI separately. This update does
not resolve either concern or change their renderer/UI settings.
