# TRASC Android 0.6.23 / code 72

TAKP's Bots tab now exports a combined **Spawn party** social and a separate
**Revive party** social for the selected owned companions. Select multiple
commands from 39 supported actions across Party, Behavior, Magic and Reports,
preview their exact named lines, then place each social in a free hotbar slot
or save it to socials only. Up to five names fit in one native social; larger
selections, up to 20, split into numbered buttons without dropping names. The
server's active/group limits still apply. No TAKP server rebuild is needed.

Revive requires a fallen inactive bot, an owner out of combat and at least 60
seconds since the recorded fall. It restores one HP and zero mana. Press
**Revive party**, then **Spawn party**. This is separate from resurrection of
a player corpse. Command descriptions retain target/class/combat restrictions.

Stop the client and server, leave the runtime open, refresh the roster and
select the owner and companions. **Preview buttons** discovers matching
character files; choose the actual file and preview again if there are several.
Existing occupied socials/hotbar slots and other settings are preserved. Each
file-changing installation makes an atomic, revision-checked backup. Old
0.6.22 per-bot backups and retry receipts remain supported.

The TAKP camera follow-up replaces repeated Wine recenter warps with clipping
only during mouse look, using Wine's raw relative-input path. The helper
restores the prior clipping rectangle on look release, lost focus, minimize
and close, including when game input is paused. Native Windows retains its
original behavior. The 15% TAKP gain, touch/controller mappings and transient
Look toggle remain. Physical Thor camera acceptance is still required.

Install as an APK update. The exact managed original or 0.6.22 EQW helper is
upgraded before Wine starts; existing original backups are retained and the
0.6.22 helper receives a separate backup. Changed/custom helpers are refused
with a clear error. Preserve imported game files, Wine prefixes, runtime,
profiles, renderer options, themes, controller mappings, character settings
and databases. No reimport, prefix reset or database reset is required. All
21 native launcher components are reused from verified 0.6.22, with the same
preview signing certificate.

The 0.6.22 Bots manager remains available across Custom, Traditional and TAKP.
Custom/Traditional generation requires their qualified modern server utility:
rebuild and deploy only if the installed server lacks it. Review storage and
complete its full backup before any required table conversion. Existing bot
records are preserved. Modern per-bot spawn/group export remains unchanged.

Drag the gear to move the gear and Look tile together. Saved per-world position,
Show mouse look tile, controller Toggle mouse look and Reset controls position
remain available. Keep the established Accurate / Legacy math accuracy setting
for the TAKP NPC-model comparison. TAKP NPC visibility and Traditional StoneUI
remain separate concerns; this update does not change their settings.

Publication requires Python/MariaDB, browser, native/JVM, DirectX, Android
assembly/lint, signing/reuse, TAKP ARM64 and modern offline-creation qualification.
The separate camera fixture measures polled and buffered DirectInput in real
Wine 10/Xvnc. Follow [Thor acceptance](docs/device-acceptance-0623.md),
[bot command details](docs/bot-commands-0623.md) and
[camera evidence](docs/takp-camera-0623.md). Open fixtures do not establish a
physical TAKP play-session result.
