# TRASC Android 0.6.41 — Custom client world-entry compatibility

[Download the Android APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.41/trasc-server-android-0.6.41.apk)

Adds a protected **1,440-slot RoF2 executable repair** for the October 16 Triptych server. That server sends an expanded player profile that an older executable cannot parse, causing a freeze after character select. The previous 4 GB/LAA action only changed memory addressing; this separate spellbook repair supplies the missing executable changes. Supported inputs and already-patched output are verified; unknown executables remain unchanged. The original is backed up for explicit restoration.

Open **Client → Custom client · 1,440-slot spellbook compatibility** to check, apply/verify or restore. The report separates selected source from a verified deployed server build and reports DLL freshness. After applying, use **Compile dinput8.dll → Deploy staged DLL** from the selected current source; the October update requires the matching DLL as well. The compiler now honors the project's C source setting for the new LoN audio decoder. [Diagnosis and exact repair steps](client-world-entry-0641.md).

The user's 0.6.40 logs confirm that both Setup deployments completed and the LoN card service initialized with 6,027 readable cards. This repair preserves those files, all three profiles, player data, imports/exports and backups. No database reimport or migration is performed. Install over the current app with the preserved application identity and signing certificate.

## Device checklist

1. Keep the Custom runtime open with server and client stopped. Check compatibility, apply the supported 1,440-slot patch and approve its visible confirmation. Verify the reported protected backup and successful checksum.
2. Compile and deploy a new current-source `dinput8.dll`; check compatibility again. Keep native dinput8 enabled.
3. Start server/client, enter the world, confirm inventory/spells/casting, and camp/relog once. Export logs if the transition still stops.
4. Confirm the already synchronized quests and initialized LoN service remain available. Traditional/TAKP should retain their own client setup.

Automated backend, browser, JVM/native host, Android compile/lint and signing qualification results are recorded by the release workflow. Physical repaired-world-entry acceptance remains pending the Thor retest.
