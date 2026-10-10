# TRASC Android 0.6.21 / code 70

TAKP gains a compact **Look off / Look on** toggle beside the embedded client's
gear button. Look starts off and is transient. When enabled, the right stick
and touch drags steer the camera through a dedicated held right-button state;
look-mode touch does not also send a left click. **Toggle mouse look** is an
optional controller action, with no changes to saved bindings or defaults.
The gear menu also offers **Enable mouse look**.

Opening a menu, keyboard or controller mappings, losing focus, pausing/leaving
the client or losing input capture disables the toggle. Controller disconnect,
rebind, removal or layer changes also release it. Physical/controller right
mouse-button holds remain independently owned when look is toggled off.
Custom and Traditional retain their existing input. The new toggle still
needs an AYN Thor test.

The latest Thor test confirms that **Accurate / Legacy math accuracy CPU**
resolves the invisible NPC models. Screenshots show normal skeleton and ghost
models; brief visual glitches settled. Keep the confirmed Accurate setting
for TAKP. This device result establishes model visibility without proving the
precise numerical fault inside the translated game. This release does not
change the server, renderer or client DLLs.

The 0.6.19 TAKP camera sensitivity remains included: relative motion uses a
0.15 gain while the right mouse button is held, including the new look toggle.
Signed fractional motion is retained. A configured 700-pixel/second controller
rate becomes 105 pixels/second during camera look; ordinary pointer movement
and the other worlds keep their rates. Compare look motion and menus on-device.

The grouped launcher controls remain available on every tab across all worlds
and themes. Seven buttons align in one row on landscape/wide screens, with
compact grouped rows on narrow phones. Stacked labels, matching heights and
Runtime, Server and Client headings/dividers distinguish the controls. Stop
client remains available while the server is busy.

Install as an APK update. Keep the existing Accurate CPU choice, client, Wine
prefix, database and deployed server build; no reimport, reset, repeated
Prepare or server rebuild is needed. All 21 native launcher components are
reused from verified 0.6.20 with the existing preview signing certificate.
The 0.6.18 login header repair and explicit Wine crash reporting remain included.

Windows TAKP 2.1c's original `spells_en.txt` stays preserved during Prepare and
Export & sync. Server exports retain the separate `spells_us.txt` and
`SkillCaps.txt` names. Legacy ZIPs containing only `spells_us.txt` remain accepted.

TAKP World sits beside TRASC Custom and Traditional EQEmu. Each world owns its
server runtime, database, client and Wine prefix. Default, Monk and Necromancer
launcher themes remain available across all three worlds.

For a fresh TAKP installation, install the server runtime, **Download TAKP world
files**, **Initialize fresh TAKP database**, and **Create local TAKP account**.
Builds compile the pinned Servertakp fork with its existing playerbots and stage
nine ARM64 binaries. The matching quests, maps, four-part Al’Kabor seed and eleven
bot migrations use separate TAKP setup paths. Additional bot gameplay work is
assessment only and is not implemented by this release.

For a new client, import the complete Windows TAKP ZIP, install this world's
client runtime and DirectX helpers, then **Prepare client**. Preparation installs
the verified eqgame, EQW and D3D8 patches, writes the local UDP 6000 login endpoint
and copies the two server exports without changing `spells_en.txt`. Launch uses
Windows `eqgame.exe`; `eqmac.exe` remains its checksum resource.

The publication workflow requires full Python/browser, management/native input,
DirectX, Android assembly/lint, signing/native reuse and ARM64 server checks.
ARM64 qualification includes nine server binaries, all 156 Paineel NPC creation
events and native bulk/individual spawn encoding. The release verification
report records the completed checks and independently verified artifact hashes.

Keep Accurate selected, test Look on with the right stick and touch, then switch
Look off and test menu clicks. Open the gear/keyboard and resume from the
background to check that look is released. Camp and export fresh logs for any
input or rendering regression. Zoning and playerbot gameplay remain separate
device acceptance work. TAKP uses EQW; RoF2 DLL hooks, launcher skin activation,
Spire editing and PEQ era presets remain unavailable in this world.

See the [TAKP setup and test guide](https://github.com/Russianranger/trasc-server-android/blob/main/docs/takp-world-0616.md),
[0.6.21 release verification](https://github.com/Russianranger/trasc-server-android/blob/main/docs/release-status-0621.md)
and [proposed Bots tab](https://github.com/Russianranger/trasc-server-android/blob/main/docs/bot-manager-design.md).
