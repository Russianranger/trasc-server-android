# 0.4.23 launcher layout and status wording

Requested from the September 18 Thor screenshots: close the Server runtime panel's sides, correct “start started,” and condense Gameplay and client launch options.

The runtime toolbar has a complete gold border, internal padding, rounded corners and an opaque background. Its sticky position leaves a small top gap; scroll/focus positioning accounts for its changing height in portrait and landscape.

The startup notice and activity title say “Starting server…” while the operation runs. Only a completed successful job produces “Server started. Verify zone readiness in server logs.” Stop uses “Stopping server”; backend errors remain visible.

All eleven launch dropdowns are grouped in a responsive grid (one column on narrow screens, two on landscape/tablet widths, three on wide screens). All ten checkboxes form a separate group with at least44px touch rows. Detailed option explanations and preparation/recovery help are collapsed by default. Every control ID, option value, default, saved-setting path and action is retained. Gameplay's ruleset/worker controls and zone checkbox are condensed; the full rule editor and validation remain available.

Version0.4.23/code40 retains the existing application ID and pinned signing certificate. Update in place after stopping the client/runtime, then reopen the installed runtime. No DLL/server rebuild, runtime reinstall, SDK/source refresh, client import or database change is needed.

The latest handoff also closes user-confirmed player/account migration and camping (CampTimerMs2900→30000), and records Spire content browsing, focused content editing and spell/string/AA editing as future planning only.

## Verification

Implementation65bba40 on [draft PR1](https://github.com/Russianranger/trasc-server-android/pull/1), [run35408972837](https://github.com/Russianranger/trasc-server-android/actions/runs/35408972837):138 existing Python tests, host/JVM checks, browser management flows, Android build and lint passed. Database, real Microsoft add-on compilation, WineD3D and Vulkan jobs passed. The client-runtime job remains in progress at this checkpoint. Every existing control ID/attribute is retained without duplicates.

Reviewed phone412×915, Thor landscape854×480 and wide1280×720 screenshots. Runtime borders are enclosed, dropdowns follow the intended one/two/three-column layout, and checkbox labels fit. One early phone checkbox screenshot had incomplete paint; the later full-page capture shows every checkbox correctly. UI artifact10574100251 matches SHA256 `c92a33b92523832a908d149211b21f0fce87fdc05396738c343c072d5c6e301b`.

Automatic approval review blocked direct main publication because that target needs explicit user approval. The draft PR is reviewable;0.4.23 is not merged or published. Keep0.4.22 installed. After approval, retain every existing release gate and publish using main's preserved signing key; the branch's ordinary debug-signed APK is not an in-place update.
