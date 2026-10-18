# TRASC Android 0.6.39 — Legends of Norrath and quest deployment

[Download the Android APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.39/trasc-server-android-0.6.39.apk)

Install over your existing TRASC app. The application identity, signing certificate and native components are preserved. These Setup actions belong to **TRASC Custom**; Traditional and TAKP keep their own content.

**Legends of Norrath Data** accepts the imported client, an Android-selected client/LegendsOfNorrath/data folder, or a nested ZIP from device or external storage. It discovers card data, validates the server's required data files, and resolves the destination from the active server configuration, rules and working directory. A SHA-256 preview shows the differences before copying the contents directly into the resolved `lon_data` location. The importer streams files with progress, byte counts and cancellation; changed files have protected recovery copies. It requires the server and client to be stopped before deployment.

**Quest & Plugin Sync** compares the selected source checkout's quest scripts, Perl plugins and Lua modules against their configured runtime destinations using SHA-256. **Scan for Changes** is read-only and displays New, Changed, Matching, Runtime Only, Errors and local conflicts, with separate group counts. Expand the file list to filter/sort, inspect sizes and modification dates, and review text diffs. Choose new files, changed files or both; replacing changed files and locally modified files requires explicit approval. Synchronization preserves runtime-only files, verifies copied hashes and records source revision, results and backups in a durable deployment manifest. Interrupted transfers are recovered with rollback before further deployment.

The tile shows the current source commit, the last successful synchronization and its date. **Refresh Source** uses the launcher's existing source update flow; synchronization itself does not download another revision. The post-sync report checks actual October 9 and October 16 source witnesses and distinguishes deployed scripts from server-code/database features or additional setup. It does not reimport `release-peq.zip`, change player data, perform migrations, rebuild server binaries or patch the client executable.

Also fixes the greyed-out **Apply 4 GB patch** action for a supported executable that already has Large Address Aware enabled: it becomes **Verify 4 GB patch** and verifies the existing flag without changing the executable. Controls report when the selected world runtime, stopped client or an idle transfer is required. Apply/Restore and the official NTCore download remain separate actions.

## Device checklist

1. Open the Custom runtime and stop the server and client. In **Setup → Quest & Plugin Sync**, select **Scan for Changes** and review the actual counts, configured paths, source commit and changed/conflict file list. Synchronize the selected changes after approving the preview.
2. In **Setup → Legends of Norrath Data**, select your RoF2 client folder, its `LegendsOfNorrath`/`data` folder, or the client ZIP. Scan, review the destination and differences, then choose **Import / repair card data**. Verify the report's copied files and bytes.
3. Start the server, then select **Verify data & card service**. It reports card-data validity separately from a confirmed fresh live service start, failed startup, disabled rule or pending restart, with actual log evidence. If disabled, review `Custom:LoNEnabled` in the existing rule controls; import/verify does not change this database rule. If pending, stop/start the server and verify again. Physical Android/server initialization remains a device acceptance step; a valid file-copy report alone does not establish it.
4. In **Client → Custom client · 4 GB patch**, use **Apply 4 GB patch** or **Verify 4 GB patch**, depending on the executable's current state. An already enabled flag does not require downloading or running the Windows patcher.
5. Confirm your existing Custom world/player data and Traditional/TAKP profiles still open normally. Keep your normal exported backup before making content changes.

Automated backend, JVM/native host, browser, Android compile/lint and APK/signing verification evidence is recorded in the release workflow. The existing database sorting, protected `eqhost.txt` settings, controller menu navigation and backup/export flows remain included.
