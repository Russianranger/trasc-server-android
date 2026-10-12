# Reviewed source updates and incremental builds

The **Updates** section is below the original source/build setup in **Builds**, in Custom, Traditional and TAKP. Its four steps remain separate: check a source update, apply the reviewed changes, build updated source, then deploy the verified binaries. None runs automatically from status polling. Your deployed server, database, maps, runtime quests, imported client, Wine prefix and personal settings remain in place.

## What is incremental

Current server imports are immutable archive snapshots rather than Git working trees. The update check downloads an exact GitHub source snapshot; it is not a partial network `git pull`. Applying compares files and changes only added, removed or differing inputs. Unchanged file inodes and timestamps are retained so Ninja can reuse their compiled objects.

A compatible build recompiles inputs affected by the change and relinks dependent targets. A header, compiler, dependency or CMake option change can affect many targets or require a fresh cache. Deployment still switches a complete verified binary set atomically, retaining the previous set. It never mixes a new zone binary with an unverified set of older dependencies.

TAKP and Traditional update to the exact app-qualified source revisions. Custom uses its saved GitHub repository and the branch, tag or commit entered in **Update to branch, tag or commit**; the check resolves it to an immutable commit. An original ZIP without recorded GitHub provenance cannot be safely attributed to an upstream tree, so incremental source review refuses rather than overwriting local work. Original full source import remains available.

## Use on Thor

1. Stop the client and server, leave the server runtime open, and save an external session checkpoint. If checkpoint export stopped the runtime, choose **Start runtime** again. Open **Builds**. The current verified deployed server should remain startable even if its imported source needs updating.
2. In **Updates**, choose **Refresh update status**. Check the imported/target/deployed revisions and cache message. For Custom, choose the desired branch/ref. For TAKP and Traditional, the qualified target is selected by the app.
3. **Check source update** downloads and validates the candidate, then displays counts and file paths. It does not replace the current source, build or deploy. Local edits are listed and block application. Preserve/reconcile them before checking again; changing the target invalidates the review.
4. **Apply reviewed source update** applies the reviewed immutable delta. Changed/deleted originals and source metadata remain under `sources/update-backups/<review token>`. Unchanged source and compiler output remain intact. A stale review, changed candidate, unsupported source or insufficient space refuses before activation.
5. Use one **Parallel compiler job** initially. Choose **Build updated source** when a compatible cache is available. Compilation verifies its inputs, runtime and outputs before promoting the successful staged binary set. Failed or cancelled compilation preserves the previous stage and deployed server.
6. If status explicitly requires it, choose **Build with fresh cache**. This is an explicit alternative; the original cache is retained. **Older Custom builds require this once**, because their historical receipts did not record enough compiler/runtime provenance to authenticate reuse. Subsequent builds create the required receipts. Known released TAKP and Traditional receipts support adoption of their compatible historical caches. A missing cache naturally requires an initial build.
7. After successful staging, **Deploy updated binaries**. A previous successful stage from a different source revision cannot be relabeled as an updated build. Keep the previous binaries and matching database checkpoint for recovery; binary rollback does not undo any server database migration.

The original **Replace imported source** and **Build imported source** controls remain available. Prefer Updates for an existing installation. TAKP's original source replacement button follows the pinned world-file setup operation instead of requesting an obsolete frontend pin.

## TAKP failure repaired

The October 12 device logs show setup checked the existing `25bf70ac` source against the new `03e934d0` pin without fetching anything. The reported incomplete-ZIP message was therefore caused by reusing the old source. Both official archives are complete. Setup now uses the same verified update transaction when source is outdated and requalifies the resulting exact tree.

The real source delta is two changes (`zone/player_bot.cpp`, `tests/player-bots/run.py`) and two additions (the Yaulp regression and policy document). The seed is unchanged. Updating/building/deploying this source enables the cleric Yaulp policy while preserving existing bots, characters and settings.

A second defect made old deployed build receipts depend on the new imported-source and Python adapter identity. Deployed verification now accepts only known released identities with matching original source/runtime/recipe records and verified binary bytes, independently of the latest source. New stages remain strict. This repairs the code path that disabled **Start server** after an app update. The uploaded bundle lacks the deployed receipt, so physical confirmation remains a Thor acceptance step.

## Qualification and boundaries

`source-update-archive-proof-0625.json` records the actual official archive upgrade, exact inventory, preserved stamps and protected fixtures. `source-update-cmake-proof-0625.json` records real C++/CMake/Ninja fixtures for all profiles: only the changed object compiled, the next build reported no work, and failed compilation preserved a running deployed executable.

The coordinated production TAKP job also bootstraps the exact released older app/server, adopts its real ARM64 build cache, tests startup after upgrading the app, applies the actual Yaulp delta, verifies failed-build preservation, checks the changed object set, then requires a true no-op rebuild before the usual server/database/native integration. Use the release receipt for its final result. Small fixtures alone do not establish the production or device result.

Source activation and Custom stage promotion use durable journals. Recovery validates all retained files, metadata, destinations and ancestor types before writing any live file. Backups, rename parents, receipt replacements and deletions are flushed before committed cleanup. Unknown edits and unsafe recovery data refuse rather than discarding user files. These tests do not substitute for physical storage/power-loss acceptance.

Production qualification passed in run `38204284306`: one of 375 TAKP objects recompiled, 374 retained, followed by a true no-op rebuild and unchanged nine binary hashes. See `release-proof-0625.json` for exact receipts and scope.
