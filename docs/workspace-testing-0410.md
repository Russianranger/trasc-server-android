# Testing the 0.4.10 workspace

## Update and normal play

Stop ROF2 and the runtime, then install the preview APK over the existing app. Open the runtime again. Keep your existing Turnip 26, Balanced, exact 0.4.2 NPC compatibility, native helpers and fullscreen settings. Start ROF2 is now at the top of Client; expand a section only when you need its settings. The scenery and fonts work offline.

At character selection, watch the labels before entering the world. Check Skin Like Wood and Minor Healing for both sound and particles, then stop/relaunch once. This release preserves the existing game prefix and shader caches; it does not claim a new fix for cold-start name corruption. If that returns, export Logs promptly.

## Reversible spell compatibility

With the client stopped, expand **Spell compatibility**. An already-applied eight-ID test stays enabled after upgrading. Otherwise, enable compatibility explicitly. Export & sync and Prepare run the real server exporter against the active database, then omit IDs >=45000 only from the client spell table. All four generated files overwrite the installed client's root and Resources folders; the exported ZIP contains the same installed data.

Expect eight omitted IDs on the September 9 database and fifteen on the September 14 database. The report lists the affected names. Test again after an export to confirm the mode persists. **Restore full spell files** disables filtering and restores the latest complete generation to both locations; retain compatibility for normal play while the complete table causes sound/particle problems.

This bridge preserves server definitions but does not make the excluded abilities usable: Dire Charm, the seven custom/tome Edict of Command entries, and on September 14, Sunrise Hills Key Echo plus six top-rank Drakkin breaths. Full ID remapping remains a separate future migration.

## Source client add-ons

1. Import/update your source, stop the client, and open **Client add-ons from source**.
2. Choose **Compare files**. Missing, different and matching rows refer to the source's `Release-NMS-Client/ClientFiles` overlay.
3. Lock a file you want to keep unchanged. Try **Copy all missing** and confirm the locked row remains unchanged. Unlock and copy one row when wanted.
4. **Copy all unlocked changes** also replaces differing files. Previous bytes are backed up; locks persist across source updates. Compare again after either source or client changes.

Generated spell/skill/base data uses Export & sync rather than add-on copying. The launcher protects those files and the game executable in the add-on list.

## Preserve players across database updates

1. Stop the server. In **Database → Player & account data**, choose **Export player snapshot** and save the ZIP outside the app. Keep a full database backup as well.
2. Import the desired new database. Replacement also saves an automatic local player snapshot before dropping the old database.
3. Import the saved player ZIP, or list local snapshots and review the correct pre-update snapshot. Check account/character counts and the table/schema report.
4. Select the replacement checkbox and restore. This replaces the complete player/account dataset in the snapshot; it does not merge individual accounts. All rows are validated in staging tables before the table swap. A fresh full database recovery backup is saved first.
5. Start the server and verify login, character identity/level, inventory, currency, bank, spells, progression and any bots/companions you use. Confirm the newer world content is still present.

If schema review blocks restoration, retain the ZIP and recovery database and send the report. New custom tables outside the source's player-table catalog need a coverage review; content IDs that upstream changes may require their own migration. Player ZIPs contain account information and should remain private.

## Build dinput8.dll in the app

This is an experimental device path. The real upstream project requires Microsoft-specific naked function hooks; Clang cannot compile it unchanged. The app therefore uses the original MSVC compiler through its existing Wine/Box64 runtime, in a separate compiler prefix.

**No Windows PC available:** use the [Thor-only preparation instructions](toolchain-without-windows.md). The ZIP can be prepared in your existing Termux/Ubuntu environment and imported into the current APK; your work computer needs no downloads or extra tools. Automatic in-app downloading is not yet implemented.

Alternatively, one-time preparation on a Windows PC:

1. In Visual Studio Installer, install **MSVC v142 — VS 2019 C++ x64/x86 build tools (14.29)** and a **Windows 10 SDK**. They can be added to Visual Studio 2022.
2. Download `tools/pack-client-sdk.ps1` from this repository. In PowerShell, run it from its folder:

   ```powershell
   .\pack-client-sdk.ps1 -Output "$PWD\trasc-msvc-sdk-x86.zip"
   ```

3. Transfer that ZIP to the Android device. Microsoft tools are supplied by your own installation, not bundled in the APK.

In the app:

1. Open the server runtime, but stop the server and ROF2. Finish any source/database operations.
2. Import source containing `Release-NMS-Client/eqgame_dll/eqgame_dll.vcxproj`.
3. Expand **Build dinput8.dll on this device**. Install the client Wine runtime only if it is missing, then import the Microsoft toolchain ZIP and check status.
4. Choose **Compile dinput8.dll**. Follow `client-compiler.log` in Logs. The first build initializes a separate compiler prefix. **Stop client** cancels compilation; workspace changes are blocked during the build.
5. Check the successful staged DLL status. Compilation alone does not replace the installed DLL. To try it, unlock `dinput8.dll` in the add-on list if needed, then choose **Deploy built DLL**. The previous DLL is backed up.
6. Launch ROF2 and check the add-on's hooks/features as well as names, NPC models and spell effects. Export Logs if compiling or loading fails.

CI validates the unchanged upstream source with the original compiler on Windows. Running that compiler through Android's Wine/Box64 and loading the new DLL in ROF2 still need device acceptance.
