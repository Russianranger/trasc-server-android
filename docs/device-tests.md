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

If a step fails, export Logs and include the step number and visible error. If the runtime cannot open, select **Logs → runtime.log**; it remains accessible without the Python backend. Use the file export button if the backend cannot make a log bundle. Do not uninstall or clear storage as a troubleshooting step before exporting backups.
