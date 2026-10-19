# TRASC Android — Beta 0.7.0

[Download Beta 0.7.0 APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.7.0-beta/trasc-server-android-beta-0.7.0.apk)

This beta brings the improved launcher UI and revised themes to `main`. Install over your current TRASC app; the application ID and signing certificate are preserved and Android versionCode increases to 92. Existing profiles, runtimes, client options and world/player data do not need to be reset or reimported.

- **Cleaner navigation:** Play, Manage, Customize and Settings organize the existing tools. Six top controls retain Runtime, Server and Client Start/Stop; Restart Server lives under Manage → Server. Advanced controls remain available in context and through searchable preferences.
- **Resumable setup:** an eight-step checklist detects completed requirements from installation evidence, preserves each profile's setup path and links to the next relevant action.
- **Update checklist:** review source/binaries, database readiness and profile-supported content, then use the existing Review → Apply → Verify tools. Missing, outdated, modified and review-required results remain distinct. Local quest/plugin edits require review; copying, backups and rollback retain existing protections. Database migrations are not applied automatically.
- **1999 theme:** four new low-polygon game-style scenes evoke original EverQuest gameplay, with bronze frames and parchment colors. These generated scenes are interpretations, not historical screenshots.
- **Necromancer theme:** realistic textured bones replace the straight panel borders and inset outlines, including navigation and setup/update tiles.

Custom RoF2, Traditional and TAKP flows remain supported. The 0.6.42 client/server mismatch behavior remains a nonblocking warning with Continue/Cancel, per-profile suppression and an option to re-enable warnings. Existing Legends of Norrath imports, quest synchronization, native patch/compiler tools and profile backups remain included.

The release workflow runs the complete backend/host/browser suite, builds and lints the signed APK, verifies every bundled UI file and backend Python module, and checks native payload/signing preservation. Native components are reused unchanged from checksum-pinned 0.6.42. Matching launcher code and corresponding native sources, build hashes and verification receipts accompany the APK.

## AYN Thor checks

1. Install over the existing app without clearing data; confirm all three profiles and saved client options remain.
2. Exercise all six runtime controls and server Restart. Verify running, stopped, starting and error statuses.
3. Reopen Setup with an established installation; completed requirements should be detected without reinstalling anything.
4. Review the update checklist before and after a normal content update. Check local modifications, previews and the result after verification; use a disposable backup for restore tests.
5. Select 1999 and visit Setup, Gameplay, Bots and Updates to inspect all four scenes. Reopen the app and switch profiles to check persistence.
6. Select Necromancer and inspect bone-framed tiles, navigation, controller focus and scrolling on both Thor screens.
7. If testing a client/server mismatch, verify Continue/Cancel and warning suppression remain available.

Physical AYN Thor acceptance remains a device check. This is a GitHub prerelease; stable 0.6.42 and the existing preview remain available.
