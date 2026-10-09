# TRASC Android 0.6.18 / code 67

Repairs TAKP client startup by using the exact legacy `eqhost.txt` sections
`[Registration Servers]` and `[Login Servers]`, including their spaces.
Prepared clients from 0.6.16/0.6.17 receive a header-only repair on the next
launch. Their registration/login endpoints are preserved, and original files
are saved in `client/prefix/trasc-takp-login-originals`.

Install this APK as an update, then select **Start TAKP**. Existing prepared
clients need no reimport, prefix reset or repeated Prepare. Explicit Wine game
crashes now close the embedded display and retain the failure cause in launcher
status and exported logs.

The 0.6.17 import correction remains: Windows TAKP 2.1c's `spells_en.txt` is
accepted and preserved during Prepare and Export & sync. The pinned server
validates that original file's checksum. Server exports stay separate as
`spells_us.txt`; legacy ZIPs containing only that name remain accepted.

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
signing certificate and all 21 verified native launcher components from 0.6.17.
Existing Custom and Traditional profile files stay in their own locations.
The server, runtimes and renderer remain unchanged.

Android login needs to be retested with this startup repair. Gameplay, graphics,
input, zoning and bot behavior also require device testing. TAKP uses its EQW input wrapper;
RoF2 DLL hooks, launcher skin activation, Spire editing and PEQ era presets are
unavailable in the TAKP profile. Use the in-game UI menu for TAKP skins.

See the [TAKP setup and test guide](https://github.com/Russianranger/trasc-server-android/blob/codex/takp-world/docs/takp-world-0616.md)
for the source pins, setup order and device checks.
