# First device acceptance run

Use a copy of your world/database initially. Record the APK commit from GitHub Actions, Android version, available storage and the runtime version. These are tests to perform, not results already achieved.

| Order | Test | Pass condition |
| --- | --- | --- |
| 1 | Install APK, download runtime, open runtime | Runtime Ready; no PRoot/permission errors in runtime.log |
| 2 | Repeat runtime installation from the offline release archive | Same Runtime Ready state without needing Termux |
| 3 | Import your fork from its GitHub link | Correct commit shown; database candidates include nested release-peq seed |
| 4 | Import the same complete source ZIP offline | Source detected; live server files retained |
| 5 | Import maps by link, then a ZIP containing a Nektulos correction | Expected base/nav/water paths; replaced file under backups/maps-before-import |
| 6 | Choose and import full database | Database Ready; real account/rule/launcher tables queryable |
| 7 | Compile with two jobs, deploy | All eight ARM64 binaries built; no missing libraries when launched |
| 8 | Start world and zone processes | Login, world, UCS, query server and launcher stay alive; zone logs show successful connections |
| 9 | Export four client data files | Nonempty spells_us/dbstr_us/SkillCaps/BaseData files in ZIP; client reads them |
| 10 | Connect existing Winlator ROF2 client | Account login, character select and entry into a mapped zone |
| 11 | Change XP rule, worker count, state saving | Values persist in selected SQL ruleset; restart applies settings |
| 12 | Modify a zone, stop, then restart | Zone state actually survives when saving is enabled; no forced-kill warning |
| 13 | Back up database; make a test SQL edit; restore | Original data returns; prior database backup retained |
| 14 | Move/copy an individual map and export it | Exact expected destination and byte contents; active-server edits blocked |
| 15 | Pull an update, rebuild, deploy and rollback | Source and binaries change as expected; live quests/maps retained; DB rollback handled separately |
| 16 | Screen off / app background for 15 minutes | Foreground service remains; server responds; device temperature acceptable |
| 17 | Shutdown runtime, reopen app | Clean MariaDB shutdown; existing data available; server starts only when requested |
| 18 | Offline source, maps and database imports | All three complete with network disabled after runtime installation |

If a step fails, export Logs and include the step number and visible error. In 0.2.1 all log viewing and both log bundle buttons remain accessible without the Python backend, including `app.log` for native failures. Do not uninstall or clear storage as a troubleshooting step before exporting backups.

## Version 0.2.1 export regression pass

1. Update the existing Preview installation in place. Keep the runtime closed. Open Logs, view operation.log/runtime.log and any nested server log; export a bundle using Android's save picker. Confirm the ZIP contains the logs and status.json with native.alive=false.
2. Use Server's Export logs button while the runtime remains closed. It must also save a bundle without a localhost connection error or starting the runtime.
3. Create a complete session backup. It should cleanly stop server/database and save a ZIP without rejecting `runtime/var/lib/dpkg/info/binutils-common:arm64.conffiles`. Save it outside the app. Log viewing/export must still work after completion.
4. Restore the externally saved session using the 0.2.0 acceptance sequence below. Confirm restored runtime opens and the existing world works without a build/import.
5. If any archive operation fails, capture the on-screen message and export Logs; check `app.log` and `runtime.log`. An error after clean shutdown should say the runtime is stopped and logs remain available. Do not deliberately fill the working device's storage to simulate failure.

## Version 0.2.0 acceptance pass

The user has already confirmed compilation, database import and connection with the existing external client. Do not rebuild or reimport the server just to test this APK update. Keep the existing world until the backup roundtrip is verified.

1. Stop the runtime, update Preview in place and reopen it. Confirm the existing source, map readiness, binaries and database.
2. Open Gameplay and load rules. Expand Character/Zone/Custom; search XP and StateSavingOnShutdown. Confirm the tiny FinalRaidExpMultiplier is retained. Set RaidExpMultiplier to 1.1: Save must identify this field and persist nothing. Restore its original value, change a harmless rule, save and reload to verify it. Check the selected ruleset and inherited rule markers.
3. Stop the server. Apply legacy Nektulos maps, apply a second time, then Revert. Verify the original pair survives, and water files stay unchanged. Apply again if that is the geometry you want. Start to inspect NPC elevation/pathing.
4. Create a complete session backup and save the ZIP through Android's document picker. Confirm runtime/server/database stop, the external ZIP exists, and separate components plus the manifest/index are visible. A SQL snapshot should be inside backups/.
5. Restore into a fresh compatible test app/device where available; runtime download and server build should be unnecessary. Alternatively, after securing the external backup, restore into the existing Preview instance with replacement selected. Its former session is retained as one recovery generation. Do not uninstall/clear the only working app to create a test instance.
6. Open the restored runtime; review login IP; check database character/rules, maps, source, deployed binaries, logs and controller profile. Connect using the existing Winlator client. Confirm the world/character persists across stop/start.
7. Supply a corrupt/truncated session ZIP: restoration must fail before replacing the current directories. Check an interrupted/low-storage import similarly only in a disposable test instance.

Client tests are deferred in this pass. When ready: import a complete client ZIP, verify the source ZIP remains while incoming's temporary copy is removed, verify DLL presence reporting, rebind buttons and both sticks, check mouse/keyboard holds in the input canvas and ensure capture/held keys release on tab changes, app backgrounding and controller disconnect. No game launch is expected yet.
