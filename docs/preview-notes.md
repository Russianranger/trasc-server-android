# 0.5.3 — Keep boat diagnostics recording

- Boat diagnostics continue through long waits, retaining the latest two bounded log segments instead of stopping after 512 samples.
- Older diagnostic DLLs are detected so the launcher can prompt for a rebuild.
- The reported ship remains targetable but can be walked through. This release fixes capture of that failure; it does not repair boat collision.

Install over the existing app after stopping the client/server/runtime. Start the existing runtime and compile/deploy dinput8.dll once with this app and the existing SDK/source. Enable Boat investigation, keep the temporary ship selected while trying to board for 20–30 seconds, then stop and Export Logs immediately. No server rebuild, runtime reinstall or client reimport is needed.

[Evidence, corrected spawn command and testing steps](https://github.com/Russianranger/trasc-server-android/blob/main/docs/boat-capture-053.md).
