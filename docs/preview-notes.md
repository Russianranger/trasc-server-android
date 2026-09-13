This is the first TRASC Server Android preview for ARM64 devices, targeting the AYN Thor.

1. Install `trasc-server-android-preview.apk`.
2. In Setup, download the runtime or import `runtime-arm64.tar.gz` from the **ARM64 runtime v1** release.
3. Import your server from GitHub or ZIP, import maps separately, and select the full database seed from the discovered files.
4. Build on-device, deploy the successful build, then start the server.

The APK is a development build. Physical Android runtime, compilation, zone persistence and Winlator connectivity still need device acceptance testing. Automated build checks are not a claim that these have passed on the Thor.

Updates to this preview may require reinstalling if GitHub's ephemeral debug signing key changes. **Export your database and edited files before uninstalling.** Do not clear app storage to update the runtime.

See the repository README and `docs/device-tests.md` for setup, scope and the test sequence. Client integration remains a later phase; the app exports the four database-generated client files for your current Winlator client.
