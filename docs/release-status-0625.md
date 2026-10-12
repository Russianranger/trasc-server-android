# 0.6.25 qualification and continuation

Status: implementation complete; coordinated production/Android qualification is pending. Latest independently verified published release remains **0.6.24/code73** until the new release proof is recorded. Do not describe this draft as published.

Recovered current main: `0742d1367a3cf5bf26b69231c7df9e97bc25d6d1`; published source `02a1af7aa8d7a808aafcf4421971a15e9110a8cc`, PR30/nativePR2 merged and run38103647834 successful. Workspace maintenance removed the prior scratch checkout; a clean clone recovered its committed source and handoff. No previous unpublished changes or active build were assumed. The new branch is `codex/source-updates-skele-0625`.

The attached screenshot/log ZIP were read from their scratch copies. Logs confirm stale source reuse in TAKP setup, before fetching, and no fresh camera diagnostics. Exact official old/new source archives qualified. Existing deployed-receipt invalidation is proven in code/regressions and consistent with the disabled Start button; the bundle does not contain the actual deployed receipt.

Completed: transactional source deltas and reviewed Updates GUI for all three profiles; compatible incremental builds and strict staged deployment; explicitly preserved old caches/fresh-build fallback; released TAKP/Traditional deployed receipts remain startable; stale TAKP setup refresh; optional reversible MIT EqSkelePatcher classic-model port with bounded archive validation and retained originals/caches; corrected frontend TAKP source pin and version footer.

Local qualification: 551 Python tests completed successfully, 22 database fixtures skipped pending MariaDB CI; JVM/native management checks passed. Actual official archive upgrade and all-profile real C++/CMake/Ninja fixture proofs are in the accompanying source-update JSON files. Reversible archive-format/transaction tests passed. Read-only preservation review found no remaining blocker after fixes. Local browser download was unavailable; all actual browser fixtures must run in the coordinated pipeline.

Planned single pipeline reuses exact 0.6.24 signing/native payload, bootstraps old TAKP source/app and verifies real ARM64 incremental cache/startup/update/no-op behavior, runs both modern native integrations, browser/Android/lint/signature checks, and publishes only after successful qualification. Independent published byte verification is required before merge/final handoff. No new helper/server source build job is needed outside that coordinated pipeline; existing EQW helper remains unchanged.

Read `source-updates-0625.md`, `takp-skeletons-0625.md` and `device-acceptance-0625.md`. Preserve existing databases, servers, imports, prefixes, runtimes, settings and receipts. Camera reversal, physical skeleton appearance/texture compatibility, TAKP NPC visibility and Traditional StoneUI remain open device concerns; no speculative fix is claimed.
