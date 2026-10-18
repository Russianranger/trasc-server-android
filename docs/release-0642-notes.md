# TRASC Android 0.6.42 — Client launch repair and optional compatibility warnings

[Download the Android APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.42/trasc-server-android-0.6.42.apk)

Fixes the 0.6.41 startup regression reporting `No module named 'client_spellbook'`. The backend modules are now copied into the client runner as well as the server runtime, and the compatibility check cannot prevent launch because a report is unavailable.

A detected client/server compatibility mismatch now offers **Continue** or **Cancel** before starting the client. **Don't warn again** saves the choice for that profile. You can turn compatibility warnings back on in Client settings. Choosing Continue starts the configured client without changing its executable, DLL or server data.

Install this APK over your current app. No database reimport, runtime reset or DLL rebuild is required just to install this launcher repair. The existing optional 1,440-slot executable repair, protected original and explicit restore remain available for the matching October Triptych server. If you choose to repair an actual mismatch, follow the [compatibility instructions](client-world-entry-0641.md); the warning itself performs no patch or migration.

The release preserves the application identity and signing certificate, the qualified 0.6.36 native payload, all three profiles, player data, quests, LoN data, imports/exports and backups.

## Device checklist

1. Install the update and start your existing client. The missing-module startup failure should no longer occur.
2. If a mismatch warning appears, choose Cancel once; then start again and choose Continue. Confirm the client starts.
3. Select Don't warn again and Continue. Launch once more to confirm the warning stays suppressed for that profile, then re-enable it in Client settings and confirm it returns for an unresolved mismatch.
4. Test character-select world entry and camp/relog. Export logs if the transition still stops; successful world entry on the Thor remains a separate physical acceptance check.
5. Confirm Traditional/TAKP and existing transfer/backup tools retain their settings and behavior.

Automated backend, browser, JVM/native host, real Microsoft current-source DLL compilation, Android compile/lint, signing and public-download checks must pass before publication. Qualification and physical Thor retest are pending until recorded in the release proof.
