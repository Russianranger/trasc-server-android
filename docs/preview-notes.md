# TRASC Android 0.6.40 — Custom deployment confirmation repair

[Download the Android APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.40/trasc-server-android-0.6.40.apk)

Fixes the confirmation step for **Setup → Quest & Plugin Sync → Synchronize Files** and **Setup → Legends of Norrath Data → Import / repair card data**. Android WebView previously could cancel the JavaScript confirmation without showing a dialog, so the scan succeeded but no copy job was submitted. The deployment flow now presents a visible confirmation and makes cancellation clear. Existing overwrite and local-conflict approvals still apply.

The file inspector now says **Server file: Not deployed yet** when a particular source file has not been deployed; this does not mean the server runtime is absent. After confirming a deployment, wait for its copied-file/byte report, then scan again. Successfully deployed files with identical contents should be **Matching**.

SHA-256 comparisons and verification, protected backups, atomic replacement, interrupted-transfer recovery and preservation of runtime-only files remain enabled. The update keeps the existing Custom, Traditional and TAKP profiles, client 4 GB patch controls, Android storage imports and backup/export flows. It does not reimport the database, perform migrations or change player data. Install over your current app using the preserved application identity and signing certificate.

## Device checklist

1. Open the Custom runtime and stop the server and client. Scan quests or LoN data, review the preview and any overwrite/conflict approvals, then press the deployment action.
2. Confirm that the confirmation appears. Cancel once and verify that no files were copied. Repeat the action and approve it; wait for copying progress and the completion report.
3. Scan again. Files successfully copied from the same source should now be **Matching**. Runtime-only files should remain present.
4. After importing valid LoN data, start the server and use **Verify data & card service**. The report distinguishes valid files from a fresh confirmed live service, disabled rule, failed startup or pending restart. Synchronization does not enable the LoN database rule or rebuild server binaries.
5. Confirm that your existing world/player data and the Traditional/TAKP profiles still open normally.

Automated backend, browser, JVM/native host, Android compile/lint and APK/signing verification results are recorded in the release workflow. Physical AYN Thor confirmation and service-start acceptance remain device checks.
