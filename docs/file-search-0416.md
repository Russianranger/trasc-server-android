# 0.4.16 file search and complete folder browsing

The Thor client directory exceeded the Files browser's silent 2,000-entry limit. The browser could not reach later filenames, preventing export of the installed DLL needed for the reconnect investigation.

The Files tab now offers case-insensitive substring search across every name in the open folder. Filtering happens in the backend before pagination, so files after the old cutoff remain searchable. Search matches file and folder names literally; it does not descend into subfolders. Open folder/Up still navigate normally, and search results retain Select → Export file.

The browser displays 200 entries per page with a visible result count and Previous/Next controls. Empty results are explicit. Changing a folder or search clears the old selection, and responses from an earlier request cannot replace the current list. Backend paging validates arguments and preserves existing symlink and managed-filename exclusions. Existing API consumers retain their default 2,000-entry page size.

Device use after updating in place:
1. Open Files. Enter `client/current` in Folder path, then Open folder.
2. Enter `dinput8.dll` under Search names in this folder and tap Search (or keyboard Enter).
3. Select the matching file and tap Export file.
4. Open `client/toolchain`, search `sdk.json`, and export that small file too.

No runtime reinstall, compiler rebuild, database changes, prefix repair or Mac tools are needed. Mouse recentering must stay off; the separate reconnect investigation still needs the installed DLL. This update changes only file browsing and the app version.

Local validation: 129 Python tests, including actual folders beyond 2,000 entries, complete pagination without duplicates, case-insensitive/literal search, scoped results, empty/shrinking directories, and invalid argument/path rejection. Existing native/JVM archive, logging, input and command tests pass. Browser tests cover large-folder paging, search/export of the requested DLL and SDK metadata, empty results, clearing, and delayed-response protection, with portrait/landscape screenshots. All required Android/signing and existing runtime gates subsequently passed.


## Verified APK

Implementation `b04db7ba0f20fce535251a7e65cadc58a007fc1e`, version **0.4.16/code33**, [run35289099016](https://github.com/Russianranger/trasc-server-android/actions/runs/35289099016). Android compilation/lint/signing and all129 Python tests passed. The browser suite passed large-folder paging, both requested exports, empty search, clearing and stale-response protection. Portrait and landscape screenshots in UI artifact10525957307 were reviewed; its ZIP SHA256 is `31e4330aadf042fa1f4d1fbe295429d9279b67322672f825b7e08e63eafc3ee8`.

APK artifact10525014414 ZIP SHA256 `b5254bbf8b84945ae217a1f91e283493d3e04f5ffb534f567cae093f5a89d7c7`. Independent verification checked the full APK v2 signed-content digest/RSA signature, preserved signing certificate, package/version, all33 bundled Python/UI assets, file-search controls, ARM64 binaries/helper manifest and corresponding presentation source files/build recipe.

- APK: **10,514,646 bytes**, SHA256 `461a8268765ead949c7f3222a6626325aa2decb5cfa7d51566a38c370c21d814`.
- Corresponding native sources: **114,558,412 bytes**, SHA256 `6a508bc5c2b03eb2590afaad08bb60d42c7cd5b1c37ff2084e557cc838c9e53e`.
- Preserved certificate SHA256 `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; package `io.github.russianranger.trasc.preview`.

Local verified files and verification records are under ignored `runtime-work/`, named for0.4.16. Physical Thor search/export acceptance remains the next device check.


## Published September 18, 2026

Run35289099016 completed successfully with all seven jobs: database, Microsoft DLL, WineD3D, Vulkan, APK, full client runtime and preview publication. All existing direct/PRoot software/DXVK/VirGL graphics/model/input/audio/shutdown/restart gates remain intact and passed. Runtime assets uploaded successfully on their first attempts; keep the already-working installed runtime. Public `preview` points to tested implementation `b04db7ba0f20fce535251a7e65cadc58a007fc1e`. Public APK/source asset sizes and SHA256 digests match the independently verified Actions candidate. This final public check compares metadata; it is not a second APK download.

Stop client/runtime, update in place with0.4.16, then open the runtime and use Files search to export the installed DLL and SDK metadata. Continue the reconnect investigation only after examining those exact files.
