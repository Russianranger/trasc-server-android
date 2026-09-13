TRASC Server Android **0.1.1** fixes database initialization on the AYN Thor.

The reported import stopped before reading SQL because MariaDB could not resolve `localhost`. The app now repairs the runtime's local hosts file on startup and initializes MariaDB without requiring DNS. Database credentials and local-only networking are retained.

Gameplay controls also resolve the default ruleset by name, including this seed's ID 1, and apply inherited values before overrides. This fixes the post-import `Unknown ruleset` error without changing the imported database's rule IDs.

**Updating an existing installation:**

1. In Setup, select **Shut down runtime**, then close the app.
2. Install `trasc-server-android-preview.apk` over the existing app. Do not uninstall or clear storage.
3. Open the runtime, select `Release-NMS-Server/database/release-peq.zip!release-peq.sql` from the discovered database files, and retry the import.

Source, maps, database files, settings and build cache are retained. This fix is in the APK; runtime 1.1 remains compatible and does not need another download.

Publication now requires reproducing the original hostname failure and successfully importing the complete database from server commit `18141ae0c9a11813733f08fa77db986951b853d6` with networking disabled and an empty hosts file. The checks also cover database restart, gameplay reads, authentication, SQL and backup/restore.

**New installations:**

1. Install `trasc-server-android-preview.apk`.
2. In Setup, download the runtime or import `runtime-arm64.tar.gz` from the **ARM64 runtime 1.1** release.
3. Import your server from GitHub or ZIP, import maps separately, and select the full database seed from the discovered files.
4. Build on-device, deploy the successful build, then start the server.

The APK is a development build. Physical Android runtime, compilation, zone persistence and Winlator connectivity still need device acceptance testing. Automated build checks are not a claim that these have passed on the Thor.

Main builds cache the preview signing key so later APKs can normally be installed over this one. If that cache is lost, a changed debug key can require reinstalling. **Export your database and edited files before uninstalling.** Do not clear app storage to update the runtime. `preview-build.json` identifies the exact source commit and APK checksum.

See the repository README and `docs/device-tests.md` for setup, scope and the test sequence. Client integration remains a later phase; the app exports the four database-generated client files for your current Winlator client.
