# TRASC Android 0.6.19 / code 68

Server Start/Stop/Restart and client Start/Stop now share a centered top toolbar
on every tab, in all three worlds and every launcher theme. Stop client stays
available while a server operation is busy.

TAKP relative camera movement uses a 0.15 gain while the right mouse button is
held. Signed fractional motion is retained, so slow movement still reaches the
client. A configured 700-pixel/second controller rate becomes 105 pixels/second
during camera look; menu movement and other worlds keep their previous rates.
This adjustment still needs a Thor test. Cursor-warp feedback has not been
established as the cause of the reported fast camera.

TAKP enables the server's existing Spawns/Netcode logging. Fresh logs record
actual spawn creations and coordinates, plus packet errors where reported.
Start the server after updating, visit the area where NPCs appeared absent,
then camp and export logs. These records provide evidence for the visibility
investigation; live NPC counts and nearby-distance snapshots are unavailable.
NPC visibility remains unresolved, and this release does not claim an NPC fix.

On 0.6.18, the user confirmed Android login, character creation, entry into
Paineel, four stable minutes in the world and camp. Both the executable and
original spell-file checksums were accepted by the server. A host probe using
the same database seed recorded 156 NPC creation events in Paineel with clean zone startup.
NPC visibility on the Thor remains unresolved.

Install this APK as an update, open the TAKP runtime, and start the server and
client. Keep the existing client, Wine prefix, database and server build; no
reimport, reset, repeated Prepare or server rebuild is needed. The 0.6.18 login
header repair and explicit Wine crash reporting remain included.

Windows TAKP 2.1c's original `spells_en.txt` is accepted and preserved during
Prepare and Export & sync. Server exports are `spells_us.txt` and `SkillCaps.txt`;
their filenames stay as exported, with no rename of the client's spell file.
Legacy ZIPs containing only `spells_us.txt` remain accepted.

TAKP World joins TRASC Custom and Traditional EQEmu in the world selector.
Each world has independent server files, database, client and Wine prefix.
The Monk and Necromancer launcher themes remain available across all worlds.

For a fresh TAKP setup, install the server runtime, **Download TAKP world files**,
**Initialize fresh TAKP database**, and **Create local TAKP account**. Builds
compile the pinned Servertakp fork with playerbots and stage nine ARM64 binaries
before deployment. The matching queststakp and Mapstakp forks, Al’Kabor database
and eleven bot migrations use separate TAKP setup paths.

For a new client installation, import your complete Windows TAKP client ZIP, install this profile’s
client runtime and DirectX helpers, then **Prepare client**. The launcher
installs the supplied, verified eqgame, EQW and D3D8 patches, writes the local
TAKP login endpoint on UDP 6000, and copies the server's spells_us.txt export
and SkillCaps.txt without changing the client's original spells_en.txt.
Launch uses Windows eqgame.exe; eqmac.exe remains its checksum resource.
Proprietary game assets must come from your own complete client ZIP.

Install this APK as an update. This build preserves the existing preview
signing certificate and all 21 verified native launcher components from 0.6.18.
Existing Custom and Traditional profile files stay in their own locations.
The pinned server binaries, runtimes and renderer remain unchanged.

Version 0.6.19 automation is pending until the build completes. Camera behavior,
NPC visibility, graphics/audio, zoning and bots require further device testing.
TAKP uses its EQW input wrapper;
RoF2 DLL hooks, launcher skin activation, Spire editing and PEQ era presets are
unavailable in the TAKP profile. Use the in-game UI menu for TAKP skins.

See the [TAKP setup and test guide](https://github.com/Russianranger/trasc-server-android/blob/codex/takp-world/docs/takp-world-0616.md)
for the source pins, setup order and device checks.
