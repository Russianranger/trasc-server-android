Runtime 1.1 fixes the missing `uuid/uuid.h` header reported by the first Thor compilation test. The image now includes `uuid-dev`, including the UUID development library used during linking.

Publication requires a complete ARM64 build of world, zone, loginserver, shared_memory, ucs, eqlaunch, queryserv and export_client_files from server commit `18141ae0c9a11813733f08fa77db986951b853d6`, using the same importer and build/staging code as the app. Dynamic library resolution is checked for all eight binaries. See `server-build-verification.json` for the result. This does not certify Android gameplay or zone persistence.

**Existing installations: no APK reinstall is needed.**

1. In Setup, select **Shut down runtime**.
2. Select **Download runtime**. This replaces the Linux runtime and opens it when installation finishes. The existing app supports this update.
3. In Builds, select **Build imported source** again. Successful object files in the existing build cache can be reused.

Your imported source, maps, database, build cache and backups are stored separately from the runtime and are retained. Do not uninstall the app or clear its storage.

For offline installation, download the new `runtime-arm64.tar.gz`, shut down the runtime, then select **Choose runtime .tar.gz**. The old offline archive does not contain this fix.
