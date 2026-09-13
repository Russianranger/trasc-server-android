TRASC Server Android **0.1.2** fixes database initialization on the AYN Thor and establishes a preserved preview signing key.

The reported import stopped before reading SQL because MariaDB could not resolve `localhost`. The app now repairs the runtime's local hosts file on startup and initializes MariaDB without requiring DNS. Database credentials and local-only networking are retained.

Gameplay controls also resolve the default ruleset by name, including this seed's ID 1, and apply inherited values before overrides. This fixes the post-import `Unknown ruleset` error without changing the imported database's rule IDs.

**Moving from 0.1.0 or 0.1.1:**

The early workflow tried to cache a keystore path that did not exist, so the original signing key was lost. Android cannot accept an in-place update signed by a different key. Version 0.1.2 uses a new application ID and the label **TRASC Server Preview** to install alongside the old app without deleting its files. Earlier instructions to update 0.1.0 in place were incorrect.

1. In the old app, open **Files**, enter `incoming`, and select **Open folder**. Select and **Export file** for `source-download.zip` and `maps-download.zip`, saving them to Android Downloads. Export any edited server/map files separately. If a database has been imported successfully, export it using **Database → Back up & export** too.
2. Select **Setup → Shut down runtime** in the old app. Keep it installed.
3. Install the new APK and open **TRASC Server Preview**. Download runtime 1.1 or choose an existing offline runtime archive.
4. Import the exported source and maps ZIPs through Setup. GitHub download remains available as an alternative.
5. Select `Release-NMS-Server/database/release-peq.zip!release-peq.sql` and **Import selected database**. If migrating an existing world, import its database backup instead of the seed. Reapply any customized settings and edited files, then build and deploy in the new app.

The new app has separate storage. Source, maps, settings and build cache are not transferred automatically. Only run one app's runtime at a time because both use the same local ports. The old app remains intact while you verify the new one.

Updates within the new preview application ID will use the explicitly selected, preserved signing key. Publication verifies the APK certificate; a missing or changed key stops the build once its public certificate is pinned. No private signing key is committed or attached to releases.

Publication now requires reproducing the original hostname failure and successfully importing the complete database from server commit `18141ae0c9a11813733f08fa77db986951b853d6` with networking disabled and an empty hosts file. The checks also cover database restart, gameplay reads, authentication, SQL and backup/restore.

**New installations:**

1. Install `trasc-server-android-preview.apk`.
2. In Setup, download the runtime or import `runtime-arm64.tar.gz` from the **ARM64 runtime 1.1** release.
3. Import your server from GitHub or ZIP, import maps separately, and select the full database seed from the discovered files.
4. Build on-device, deploy the successful build, then start the server.

The APK is a development build. Physical Android runtime, compilation, zone persistence and Winlator connectivity still need device acceptance testing. Automated build checks are not a claim that these have passed on the Thor.

`preview-build.json` identifies the source commit, APK checksum, application ID and signing certificate. **Export your database and edited files before uninstalling any installation.** Do not clear app storage to update the runtime.

See the repository README and `docs/device-tests.md` for setup, scope and the test sequence. Client integration remains a later phase; the app exports the four database-generated client files for your current Winlator client.
