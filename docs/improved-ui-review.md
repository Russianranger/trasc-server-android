# Improved UI review branch

This work belongs to `improved-ui`, based on main `5f10025c82aa1479963917aa4264c999a1af897e` (published 0.6.42). It is a review candidate, not a release. The user will decide whether to merge and publish it. Do not merge, move release tags, or replace preview/Latest artifacts as part of this review.

## Navigation

The persistent top bar keeps six controls: runtime Start/Stop, server Start/Stop and client Start/Stop. Server Restart is under **Manage → Server**. The profile and launcher-theme selectors stay together.

| Area | Destinations |
| --- | --- |
| Play | Adaptive setup/open-runtime/start-server/launch-client/return-to-game action; setup/update links and common shortcuts |
| Manage | Setup, Server, Updates & builds, Backups & files |
| Customize | Gameplay, Content editor (Spire), Companions, Appearance, Database |
| Settings | Client & controls, Repairs, Logs |

LB/RB cycle the four main areas, remembering their last subpage. D-pad navigates, A accepts, and B closes the nearest expanded card/disclosure or returns to area navigation. Existing control IDs, native guards, confirmation flows and form values are retained. Profile-specific features remain restricted to their original world.

## First setup

**Manage → Setup** starts with a checklist derived from the selected profile's actual state. The user can choose a new setup, existing files, or session restoration. Restoring a complete backup does not require installing a runtime first. The existing import tools are in a disclosure below the guide; each checklist action opens the correct tool without starting an import.

The eight steps cover profile selection, runtime installation, server configuration/build, database/account, required content, client preparation, compatibility review and session launch. The selected setup path is retained separately for each profile; completion is always recomputed from installed evidence. A stopped runtime makes unknown components “Needs review,” rather than declaring their files absent. Traditional/TAKP use their qualified deployment status. The guide does not initialize or replace existing databases, automatically download content, or override launch warnings.

Play uses the existing action handlers. It never updates, builds, deploys or replaces content as part of launching. The user can still use the six top controls independently.

## Settings

Normal client settings appear first. **Recommended configuration** contains the existing profile-aware compatibility settings; **Experiments & diagnostics** contains comparison controls. The compatibility summary identifies differences without rewriting saved choices. Existing defaults remain in force, including TAKP's qualified accurate CPU profile and the RoF2 balanced profile. Optional experiments are not silently enabled.

Search in **Settings → Client & controls** finds tools across all areas, including aliases such as FPS, controller, quests, 4 GB, spellbook and Spire. Search only opens controls; it does not apply them. Models and skins are under **Customize → Appearance**.

## Server update checklist

Use **Manage → Updates & builds → Check installed files** after reviewing/applying source changes, building, deploying and synchronizing content. Checking is an explicit queued operation with cancellation, not a recurring full-disk scan.

- Imported source is fingerprinted locally. This does not establish that a remote branch has no newer commits; use the separate source-update review.
- Staged and deployed binaries are compared with their receipts and current imported source. A successful build and a deployed build remain separate states.
- Custom quests, Perl plugins and Lua modules compare live files with imported source, showing new/missing, changed, matching, runtime-only, unreadable and confirmed local conflict counts. Changes without a previous sync baseline are explicitly flagged for inspection. The comparison does not overwrite local edits or delete runtime-only files.
- Maps and independent content repositories are reviewed against per-file fingerprints recorded by future explicit imports, never inferred current from a server revision. Legacy imports without verifiable evidence require review. TAKP quest/map Review links open a dedicated component importer; replacing installed content requires explicit confirmation and retains a backup.
- Map imports prepare a complete directory before activation. Cancelling preparation leaves the active maps unchanged. Each successful replacement retains the complete previous directory under a unique `backups/maps-before-import/<token>` path, with interrupted activation recovery.
- Support files are compared when a source/destination mapping is known.
- Legends of Norrath links to its existing active-data/service verification, rather than claiming that an old import receipt proves service readiness.
- Client data compares the installed files with the recorded export. Matching export files can establish local setup preparation, but do not certify that the database has had no newer edits or migrations.
- Database migration acceptance remains an explicit review of the database/update/startup results. The checklist does not start the database or run migrations.

Results are snapshots. They are invalidated after tracked mutation/recovery jobs, imports, source/build changes, runtime closure or profile changes. Read-only remote preview receipts do not invalidate otherwise unchanged local results. Check again after external/manual edits. No aggregate “everything is current” claim is made while any component needs review.

## Review on the Thor

1. Install the branch test APK over the existing 0.6.42 app only after CI verifies the established signing certificate. No data reset, runtime reinstall, server rebuild or DLL rebuild is required to inspect this UI.
2. Confirm all six top controls are present. Find Restart under Manage → Server.
3. Navigate all four areas with LB/RB and their subpages with D-pad/A/B. Confirm the controller can leave nested import and settings disclosures.
4. Open Setup on an existing world. Confirm it detects prior work and does not demand database replacement. Inspect restoration and offline-import paths without activating them.
5. Search for controller, 4 GB, spellbook, quests and Spire. Confirm results open the appropriate tools, with the expected profile restrictions.
6. Check that saved graphics, controls, warning preferences, themes and all three isolated worlds retain their values. Inspect Recommended and Experiments; merely opening them must not change a setting.
7. Run the update checklist. Inspect its source/staged/deployed identities and every review-required row. Use a Review link; no copy/deploy should occur until the existing action is explicitly selected.
8. After a normal reviewed update or synchronization, recheck. Confirm changed build/content results are refreshed and local modifications are still presented for review.
9. Launch the existing client. Compatibility mismatches must still offer Continue/Cancel and the per-profile Don't warn again preference.
10. Confirm ordinary editing, backups, restore, storage cleanup and logs remain reachable. APK installation and browser fixtures do not establish physical gameplay acceptance.

## Branch verification and artifact policy

`.github/workflows/improved-ui.yml` triggers only on pushes to `improved-ui`, uses read-only repository permissions, and has no release or tag-writing job. It runs backend/host/browser regressions and builds a test APK using the pinned native payload from 0.6.42. The existing signing identity is required; a missing key stops the build instead of generating an incompatible signer. The APK, source archive, hashes and verification receipts are Actions artifacts only.

New browser coverage exercises four-area navigation, retained six controls, disclosure/controller behavior, settings preservation/search, resumed setup, manual update checks, stale-result invalidation, cross-profile result rejection and narrow/wide layouts. New backend coverage verifies live-file comparisons, import evidence, changed source/binaries, missing/invalid receipts, cancellation and profile boundaries. Physical Android acceptance remains the user's next review step.

Recovery checkpoint (2026-10-19 UTC): preserved 50 unpublished files from the prior local `improved-ui` checkout in an isolated checkout based on the verified main SHA above. No unpublished local commits or stashes were found. Syntax/whitespace checks and the navigation, readiness and preferences browser suites pass. Full backend/browser and Android qualification is in progress; earlier local test claims are not treated as fresh verification. CI installs MariaDB/Lua dependencies and verifies the actual APK. No production publication is authorized.

## Recovery qualification additions

- Runtime, server and client failures now have explicit Error badges, and retry clears the matching operation failure.
- Eight setup steps include a per-profile remembered setup path and live completion count. No saved completion checkbox can override file evidence.
- Update rows distinguish missing files, out-of-date builds, modified files and manual review. Custom script conflicts reuse the last synchronization manifest; untracked differences are explicitly disclosed.
- Compatibility review reuses the existing read-only client launch preflight with the selected native DLL option. It does not change the Continue/Cancel dialog or warning suppression. Traditional and TAKP retain their own manual client review.
- Review → Apply → Verify routes into existing component tools. The separate Verify button rescans all components; a failed component retains its own review state without erasing unrelated results. Installed-map replacement requires confirmation and keeps the complete previous directory.
- The Android version name is `0.6.42-improved-ui-test`, retaining versionCode 91 and the established application/signing identity so the review APK can replace 0.6.42 without a reset.
- Broad native rebuild PR jobs exclude this branch because its dedicated workflow verifies the exact reused 0.6.42 native payload. Production workflows are unchanged for main.

Local recovery qualification: the 850-test baseline Python suite passed with 30 environment-dependent skips; all native/Java host checks passed. All 25 browser suites passed after correcting the era test's reload wait. The update checklist suite has 20 cases, including four added recovery regressions. The final branch workflow reruns the complete suite, builds/lints Android, verifies the signing certificate and native/asset preservation, and uploads test artifacts.
