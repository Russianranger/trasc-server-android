# 0.4.19: equivalent spell checksums and stage timings

The user authorized the next loading optimization after confirming that camera/controller input works. Preserve camera V2 unchanged. [The 0.4.18 device comparison](loading-0418-device.md) measures42.302s/41.405s inside spell loading with the integer optimization off/on. It does not yet identify the cost of individual substages.

## Concrete source finding

In the actual imported add-on, `MQ2DetourAPI.cpp` implements `memcheck0` and `memcheck1` by walking the complete `ourdetours` linked list for every byte hashed. This also happens for ordinary heap-backed spell records and input-file data with no overlapping patch. Read-only inspection of the supplied executable links the record checksum at RVA0xaca30 to the first routine, and the two file-checksum calls to the second. The resulting work is proportional to bytes times registered patches, even for disjoint data.

The optional optimization first checks the complete buffer range against the patch list once under the existing registry lock. If disjoint, it computes the same table-based CRC using the original table, seed and final-complement behavior. If any patch overlaps, or the range is unsupported/overflows, the entire original implementation runs. There is no cached overlap decision, removed validation, substituted checksum or changed input byte. List changes are seen on the next call. The optimized helper alone uses compiler optimization; the upstream Microsoft v142 `/Od`, runtime and packing recipe remain.

This applies only during the supported client's spell-record and spell-file checksum calls on its loading thread, with **Faster spell loading (experimental)** enabled. It is inactive in other loading stages, gameplay, other threads, unsupported executables and profile/off mode. The existing integer fast path remains. A block-reader prototype was evaluated but removed from this pass after the checksum source finding; file I/O and Unicode/line handling remain original.

## Implementation and observability

The loader adapter marker is `TRASC_EQ_LOAD_V2`. The launcher requires the exact existing executable SHA256 and new DLL marker. A0.4.18 DLL continues to provide its confirmed camera support, but the new loading experiment reports that recompiling is required. Legacy loading environment variables are cleared.

The build overlays `MQ2DetourAPI.cpp` alongside the existing startup/input overlays. The exact original bodies of both checksum functions are hashed and checked before adding the fast path; changed imported implementations fail with a review message. Imported source stays untouched. No proprietary client executable is published or edited on disk.

Twelve original CALL opcodes/targets and the loader vtable slot must match before any patch. Write permissions are obtained before mutation. New wrappers retain the original x86 ABI and results, adding bounded `client-loading.log` measurements for:

- Main text/association stage, with aggregate original line-reading, record-construction and per-record-checksum time/counts.
- Association loading separately; its time is included in the main stage, so do not sum those two.
- Each input-file checksum and post-load mapping.
- Whole spell-loader time, integer fast/fallback counts, checksum fast/fallback counts and processed checksum bytes.

Per-call timer totals are millisecond-resolution diagnostics and include some measurement overhead. Both modes use the same instrumentation. Timings do not establish a device gain until the next off/on comparison.

## Verification and device comparison

Differential tests compile the actual retained upstream checksum function bodies and the production overlay, preserving their license. Cases cover keyed/unkeyed values, disjoint/overlapping and adjacent ranges, competing overlaps, disabled nodes, list mutation, invalid range rejection and disabled mode. The same-source host fixture processes 4,096 records of 1,256 bytes against120 patches in1,108ms versus22ms, with identical checksum2089226240. This is a component benchmark, not a predicted EQ or Thor loading time.

The open executable x86 fixture exercises the complete patched loader and all wrapper signatures, opt-out, result preservation, scope cleanup and layout rejection. The user executable is used only for local static layout verification. The first Windows run caught a test-only `cdecl` macro collision and a missing initializer-list dependency; the fixture now uses a distinct identifier and an explicit mode array. The complete fixture and actual add-on compilation then passed Microsoft v142. No release gate was removed.

The ARM64 Wine/Box64 fixture also passed. Using the actual original and overlaid checksum bodies, the same 4,096-record / 5,144,576-byte workload with 120 registered patches took **3,850 ms original versus 46 ms optimized**, with checksum `2089226240` in both modes. The test also verified keyed seeds, overlapping-buffer fallback, changing patch lists and boundary cases. This is an isolated component result on the hosted Neoverse-N2 runner, not a Thor or whole-game loading result. The full patched-loader fixture passed through Wine as well.

Update the APK in place with client/runtime stopped, then compile and deploy dinput8.dll once using the already imported SDK/source. Compare two fresh client launches to the same character screen, Faster spell loading off then on. Export Logs; verify camera/inventory, character-select reconnect and normal spells. No Mac tools, runtime reinstall, server rebuild or client reimport. Camp remains parked.

## Published build

Version **0.4.19 / code 36**, commit `2233d068303ab543237403cce6e5b0e1ad041ac5`, passed all seven jobs in [run 35350753552](https://github.com/Russianranger/trasc-server-android/actions/runs/35350753552). This includes 133 Python tests, native/JVM/browser checks, Windows add-on compilation, Android lint/signing, database/session roundtrips and all existing direct/PRoot Software/DXVK/VirGL graphics, audio and input tests. The updated phone options were reviewed. Downloaded DXVK evidence retains free menus and camera movement after recentering.

The APK is 10,527,178 bytes, SHA256 `7a89702bf09301acbb5383de2c372ebb2667249a163368b9dacbcb50dee674f1`. Independent APK v2 signature/content verification passed, with the existing signing certificate, expected package/version and all 38 bundled source/UI assets. The corresponding source archive is 114,558,335 bytes, SHA256 `ea022aec8f5a721ce55c66bd8a5c09211fad22e62968711e36c7a452907dc99f`. The published preview tag and asset digests match the verified candidate.
