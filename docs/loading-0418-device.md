# 0.4.18 device result: controller works; pre-screen spell loading dominates

The user confirms that controller mouse look now works. They report that the visible loading screen reaches character select faster, but the preceding wait after connecting still feels longer. Bundle `logs-3542532455672139460.zip` contains a normal/profile run, a fast-parser run, and retained game landmarks from the previous build. No new product code or APK is part of this review.

## Measured phases

These are client log landmarks, starting at `Server selected`; they do not measure any unlogged time between the physical button press and that event. `Activating Load Screen` identifies screen activation in the game, not the exact first frame seen on the Thor. Character select means `Initializing character select UI`.

| Run | Server selected | Screen activation | Character UI | Before screen | After screen | Total |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Earlier 0.4.17 | 10:59:41 | 11:00:40 | 11:00:55 | 59s | 15s | 74s |
| 0.4.18, optimization off | 12:35:15 | 12:36:13 | 12:36:27 | 58s | 14s | 72s |
| 0.4.18, optimization on | 12:46:23 | 12:47:18 | 12:47:30 | 55s | 12s | 67s |

Sources in the bundle: `logs/client-game.previous.2.log`, `logs/client-game.previous.log`, and `client/current/Logs/dbg.txt`. World access is granted four seconds after server selection in all three. These retained samples do not show a pre-screen regression. They do show that the largest remaining wait precedes the loading screen. One run per configuration, in this order, does not isolate cache, scheduling or other run-to-run effects.

The new `client-loading.previous.log` and `client-loading.log` establish:

| Mode | Spell-loader time | Fast integer fields | Original-reader fallbacks |
| --- | ---: | ---: | ---: |
| Profile/original parser | 42,302ms | 0 | 0 |
| Fast parser | 41,405ms | 8,960,166 | 0 |

Both calls return success. The parser is installed and used, but the measured whole-loader difference is only897ms (about2.1%). Do not repeat the microbenchmark's761ms/92ms ratio as an EQ improvement, or attribute the full five-second total-load difference to integer parsing. The 41–42s is now measured inside the spell-loader wrapper, not merely inferred from adjacent log messages.

## Controller and runtime confirmation

Deployed DLL SHA256 `8686b2f3055436289c6f76edcdb4f43df7b5ebea18fb99c669cb4af249260222`,1,701,888 bytes, includes camera V2 and loading V1. Both sessions request camera recentering and load the native DLL. The previous/current camera logs record701/415 successful warps and return to the menu gate afterwards. Combine this with the user's report as device confirmation of the controller fix. Preserve this adapter and the earlier source-DLL reconnect fix.

During the fast-run spell pause, eqgame's main thread uses about99.6–99.8% of one CPU, sampled on CPU7. The profile run similarly uses about99.4–99.9%. Available-core affinity is enabled; do not reintroduce forced single-core restrictions. These are process CPU samples, not instruction-level profiling.

Native Surface uses MIT-SHM. Seven consecutive five-second windows at12:46:36–12:47:06 report zero new frames and299–300 unchanged responses each, with Android thermal status0. The idle capture behavior is working; repeated full-frame copying is not implicated in this pause. Thermal status0 alone does not rule out all clock/scheduling variation.

## Next loading work

Read-only inspection of the already supplied exact executable identifies the following stages within the measured virtual loader, RVA0x673f0:

- CALL at RVA0x6740e invokes the main text loader at RVA0x1c1c30. That loader reads spell lines, allocates/constructs records, builds lookup data, and invokes association loading at RVA0x3d50b0 from CALL RVA0x1c1e9c.
- CALLs at RVA0x6741e and0x6742a invoke the file checksum reader at RVA0x408d90 for the two input files.
- CALL at RVA0x6743a invokes post-load mapping at RVA0x67300.

The existing log wraps all of this; it cannot say which substage owns the remaining41s. The next targeted development should time these exact call boundaries, with layout checks and bounded logging, and separate line-reading/record construction if the main text pass dominates. Then optimize the measured slow stage while preserving resulting data and checksums. No substage is yet a proven bottleneck. Avoid another speculative integer-only replacement, skipping validation, discarding spell records, or caching without verified invalidation.

The current verified release remains0.4.18 at `16e989b12263b5f3df619fa74b04911914c5f7dc`. No user rebuild, reimport or extra Mac tools are needed for this review. Camp remains parked. This evidence/handoff update is documentation only with `[skip ci]`; no subagents were used.
