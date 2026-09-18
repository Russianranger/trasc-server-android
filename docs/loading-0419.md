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

The open executable x86 fixture exercises the complete patched loader and all wrapper signatures, opt-out, result preservation, scope cleanup and layout rejection. The user executable is used only for local static layout verification. Windows compiler and ARM64 Wine/runtime checks run before publication; final release evidence will be added when complete.

Update the APK in place with client/runtime stopped, then compile and deploy dinput8.dll once using the already imported SDK/source. Compare two fresh client launches to the same character screen, Faster spell loading off then on. Export Logs; verify camera/inventory, character-select reconnect and normal spells. No Mac tools, runtime reinstall, server rebuild or client reimport. Camp remains parked.
