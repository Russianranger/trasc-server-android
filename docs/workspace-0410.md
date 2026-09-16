# Client workspace 0.4.10

## Spell compatibility

The existing format1 journal and operation names are retained so applied0.4.8/0.4.9 tests become persistent opt-ins. Filtering uses the existing conservative exclusive45000 boundary, not a growing hardcoded denylist. Complete original bytes remain in dated generations, with bounded ID/name reports. Future Export/Prepare run the real server/bin/export_client_files against the active database, filter only generated client spells, update all four files in root and Resources and write the corresponding ZIP. No server spell IDs or references change. Restore selects the latest successful full generation and turns the mode off. Interrupted spell replacement blocks launch and can restore both copies. Standard export exceptions roll back all client writes; the spell journal recovers a process death between its two copies.

## Client overlay

Only the imported source's ClientFiles overlay is compared. Case-insensitive paths match Windows behavior; ambiguous casing, symlinks, traversal and stale comparisons fail. Locks persist in client/addon-locks.json. Bulk modes skip locked and managed data; individual copying rejects them. Existing files are backed up by the existing client transaction. Database-generated data and eqgame.exe cannot be installed by this overlay path.

## Player/account snapshots

Data-only ZIP format `trasc-players-1` contains a manifest and hex/NULL TSV streams, never executable SQL. Coverage includes the upstream GetPlayerTables catalog, four omitted custom character tables, login_accounts, related instance/group/raid state, companions and shared tasks. The imported source can extend GetPlayerTables. New unrelated/custom tables outside that catalog require a coverage review; item/spell/content ID migrations still require a dedicated migration.

Export requires a stopped server. Text is serialized as UTF8, binary/bit data as raw bytes; nullable values and zero IDs are preserved. Database replacement saves an automatic local snapshot before dropping the old database. Restore replaces player rows as a complete snapshot, not an account-by-account merge. It does not install old table definitions. Added defaulted columns use the current schema; removed populated columns, missing tables, cross-boundary foreign keys or triggers need review. All rows are loaded under strict SQL mode into LIKE copies of current tables, checked for counts/checksums, then swapped by one multi-table RENAME. Player-only foreign keys are rebuilt and validated against the staging graph before the swap; parcel relationships and cascade rules remain enforced afterward. Cleanup disables checks only for obsolete staging/previous tables in its own short-lived SQL connection. Current world content is retained. Full recovery SQL is saved first; restore journals identify staging/previous tables if interrupted. Snapshots include account credentials; keep them private. A saved snapshot cannot guarantee compatibility with arbitrary future schema/content changes.

## Client DLL compiler

The real build project is eqgame_dll/eqgame_dll.vcxproj, not the small unrelated dinput8.vcxproj wrapper. It targets Win32, MSVC v142, static runtime, one-byte struct packing, disabled optimization and frame-pointer omission. The implementation reads its source/definition/include lists and refuses unrecognized ABI/compiler setting changes. The first Clang16 approach was rejected by the actual-source CI gate: Clang cannot compile upstream naked member functions and several MSVC-only reference constructs. Do not disable or rewrite those hooks just to get a build.

The implementation instead runs the original Microsoft v14214.29 Hostx64/x86 compiler and linker inside the existing Wine10/Box64 runtime. The imported toolchain contains compiler EXEs/DLLs plus matched headers/libraries and Windows10 SDK, packed using tools/pack-client-sdk.ps1 on a licensed VS installation. Microsoft files are never bundled or redistributed. A separate client/compiler-prefix is used; the game prefix, model helpers, graphics options and shader caches are preserved. Wine handles Windows path/case semantics. Output remains staged until explicit, backed-up deployment. PE32 x86 and hash validation precede staging. The compiler lease blocks server workspace writes during compilation. Stop client cancels compilation.

Windows CI compiles pinned actual upstream source using the same original Microsoft toolset and production recipe. This verifies source/compiler compatibility but not execution under Wine/Box64 on the Android device or live ROF2 hooks. Device acceptance remains required. No ARM compiler packages or compiler-runtime download are needed beyond the existing client runtime. Subsequent builds run on-device with the imported toolchain.

## Theme provenance

Background: built-in image generation; prompt: original panoramic fantasy adventure landscape, ancient stone citadel in emerald forest, misty mountains, river and path, golden sunset, painterly book-cover style, no text/logos/UI; quiet dark lower half for readable controls. Generated PNG retained in scratch, encoded as app/src/main/assets/ui/fantasy-landscape.webp without compositing. Two additional built-in generations use the same style: an ancient candlelit stone library with an astronomical globe and starry mountain doorway (`fantasy-library.webp`), and an enchanted forest bridge, elven ruins, waterfalls and amber lanterns (`fantasy-forest.webp`). Each tab selects a backdrop and scenic position. All three final assets are in app/src/main/assets/ui. Fonts Cinzel and Crimson Pro come from google/fonts (SIL OFL licenses bundled). No runtime image/font network requests.

## Validation

Release must pass existing native graphics, database, JVM, browser, APK/lint and signing gates, plus actual-source client DLL compile and player migration integration. Preserve stable signing identity and runtime caches. Complete final CI/artifact evidence in HANDOFF after the candidate passes.
