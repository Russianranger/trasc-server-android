# TRASC Android 0.6.16 / code 65

TAKP World joins TRASC Custom and Traditional EQEmu in the world selector.
Each world has independent server files, database, client and Wine prefix.
The Monk and Necromancer launcher themes remain available across all worlds.

In TAKP Setup, install the server runtime, **Download TAKP world files**,
**Initialize fresh TAKP database**, and **Create local TAKP account**. Builds
compile the pinned Servertakp fork with playerbots and stage nine ARM64 binaries
before deployment. The matching queststakp and Mapstakp forks, Al’Kabor database
and eleven bot migrations use separate TAKP setup paths.

In Client, import your complete Windows TAKP client ZIP, install this profile’s
client runtime and DirectX helpers, then **Prepare client**. The launcher
installs the supplied, verified eqgame, EQW and D3D8 patches, writes the local
TAKP login endpoint on UDP 6000, and syncs spells_us.txt and SkillCaps.txt.
Launch uses Windows eqgame.exe; eqmac.exe remains its checksum resource.
Proprietary game assets must come from your own complete client ZIP.

Install this APK as an update. This build preserves the existing preview
signing certificate and all 21 verified native launcher components from 0.6.15.
Existing Custom and Traditional profile files stay in their own locations.

This is the first TAKP integration preview. Android gameplay, graphics, input,
zoning and bot behavior require device testing. TAKP uses its EQW input wrapper;
RoF2 DLL hooks, launcher skin activation, Spire editing and PEQ era presets are
unavailable in the TAKP profile. Use the in-game UI menu for TAKP skins.

See the [TAKP setup and test guide](https://github.com/Russianranger/trasc-server-android/blob/codex/takp-world/docs/takp-world-0616.md)
for the source pins, setup order and device checks.
