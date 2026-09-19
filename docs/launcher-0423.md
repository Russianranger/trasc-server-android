# 0.4.23 launcher layout and status wording

Requested from the September 18 Thor screenshots: close the Server runtime panel's sides, correct “start started,” and condense Gameplay and client launch options.

The runtime toolbar has a complete gold border, internal padding, rounded corners and an opaque background. Its sticky position leaves a small top gap; scroll/focus positioning accounts for its changing height in portrait and landscape.

The startup notice and activity title say “Starting server…” while the operation runs. Only a completed successful job produces “Server started. Verify zone readiness in server logs.” Stop uses “Stopping server”; backend errors remain visible.

All eleven launch dropdowns are grouped in a responsive grid (one column on narrow screens, two on landscape/tablet widths, three on wide screens). All ten checkboxes form a separate group with at least44px touch rows. Detailed option explanations and preparation/recovery help are collapsed by default. Every control ID, option value, default, saved-setting path and action is retained. Gameplay's ruleset/worker controls and zone checkbox are condensed; the full rule editor and validation remain available.

Version0.4.23/code40 retains the existing application ID and pinned signing certificate. Update in place after stopping the client/runtime, then reopen the installed runtime. No DLL/server rebuild, runtime reinstall, SDK/source refresh, client import or database change is needed.

The latest handoff also closes user-confirmed player/account migration and camping (CampTimerMs2900→30000), and records Spire content browsing, focused content editing and spell/string/AA editing as future planning only.

## Verification

Local validation:138 existing Python tests passed; JavaScript syntax and diff whitespace checks passed. An HTML inventory check confirms every existing control ID and attribute is retained without duplicate IDs. The local browser package has no Chromium executable; responsive screenshots and the existing browser flows will run in CI, along with the unchanged release gates. Publication remains pending.
