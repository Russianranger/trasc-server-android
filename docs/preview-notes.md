# TRASC Android 0.6.13 / code 62

Traditional now offers reviewed Velious, Luclin and Planes of Power ruleset
presets, plus Return to default. The presets use 47 source-supported era values,
reversible startup-default overlays, and composite per-zone sets preserving
unrelated existing overrides. Preview before applying; stop the server and client,
then start the existing server again. Original default values and zone routing
are restored without rewinding character progress. A database backup precedes
changes, and stale previews and unsupported schemas are rejected.

The official TAKP database and engine, pinned Traditional EQEmu source, Daybreak
era documentation, EQEmuTools expansion switcher and supplied PEQ database were
researched. PEQ's sparse era tags and upstream mechanics limit historical fidelity;
these are compatible approximations, not a TAKP database replacement. Existing XP
curves/rates and over-cap characters are preserved. See
[research, exact behavior and focused acceptance](https://github.com/Russianranger/trasc-server-android/blob/main/docs/traditional-eras-0613.md).

Launcher theme choices **Default**, **Necromancer** and **Monk** persist across
reloads and both profiles. Default preserves the current appearance; class themes
have distinct palettes and original offline vector scenes. They do not change
StoneUI, client INIs, game models or server rules.

Update the APK in place. The existing compiled Traditional server, imported RoF2
client, Wine prefix, runtime, DirectX helpers, controller bindings and unrelated
preferences remain. This scoped build reuses all 21 existing native components
from verified 0.6.12, including the camera proxy; no server/runtime/native builds
are performed. Existing camera/name-sky options, viewport gear actions and
**Return to Launcher** remain. Physical Thor era acceptance remains a device test.
