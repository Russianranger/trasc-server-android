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

Local validation: 129 Python tests, including actual folders beyond 2,000 entries, complete pagination without duplicates, case-insensitive/literal search, scoped results, empty/shrinking directories, and invalid argument/path rejection. Existing native/JVM archive, logging, input and command tests pass. Browser tests cover large-folder paging, search/export of the requested DLL and SDK metadata, empty results, clearing, and delayed-response protection, with portrait/landscape screenshots. Full Android/signing and existing runtime gates remain required before publication.
