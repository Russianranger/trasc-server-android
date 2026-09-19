# 0.5.2 — Easier merchant stock and boat diagnostics

- Spire: open a merchant NPC or inventory, search items by name/ID and select an item to sell. Merchant ID and a free slot are filled in for linked inventories; existing preview, backup and change history remain in place.
- Add another item directly from a merchant stock record. Shared-inventory warning and occupied-slot checks prevent accidental assumptions or overwrites.
- Boat investigation: optional bounded client diagnostics record selected ships and passenger state to investigate deck collision and sliding. This build does not claim a boat repair yet.
- Existing RoF2 spell compatibility, particles, loading, controller and graphics settings are preserved.

Install over the existing app. Merchant changes need no DLL/server rebuild or runtime reinstall. For boat diagnostics, compile/deploy dinput8.dll once with this APK, select the new Boat investigation option, target one ship and test boarding/riding for 1–2 minutes; stop and Export Logs.

[Scope, evidence and testing checklist](https://github.com/Russianranger/trasc-server-android/blob/main/docs/boat-investigation-052.md).
