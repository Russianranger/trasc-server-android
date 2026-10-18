# Database sorting and discoverable release — 0.6.36

User requested Setup database deployment sorting by descending size and modification time across all three profiles, followed by an easily discoverable APK release from main.

Baseline main: 0edd846410ad3d8e10974651fca7ac0862620a16. The preceding 0.6.35-beta APK existed as a prerelease, while GitHub /releases/latest still returned v0.6.2. Version 0.6.36/code85 is published as a normal release and explicitly marked Latest, with a versioned APK and a direct download link at the top of its notes and README. The preview compatibility channel is updated to identical APK bytes.

The shared database selector adds Recommended, Size descending, and Modified descending. Selection is preserved across reordering, filtering and rescanning. Numeric comparisons use deterministic identifier ties; missing dates sort after known dates. The existing candidate catalog limits and import validations remain in effect. Sorting does not rearrange the ordered five-part seed import sequence.

Metadata uses filesystem modification times for SQL/SQL.GZ and ZIP member local date/time for SQL stored in ZIP archives. ZIP metadata has no timezone, so it is interpreted in the runtime's local timezone; malformed dates have no timestamp. PEQ bundle modification time is the latest known component date, excluding the wrapper manifest. Discovery does not extract SQL data merely to sort it.

TAKP previously hid the shared database selector. The catalog/sorting card is now available there for review, with generic import blocked and explicit guidance to use the matching pinned TAKP initialization workflow.

The APK retains the application identity, pinned signing certificate and native payload of 0.6.35. Native components and their source attribution are read from immutable, checksum-verified v0.6.35-beta release assets. The publisher uses a draft release ID returned directly by the creation API, preventing the prior immediate release-list propagation race. It verifies current main, APK/source hashes, release state, Latest pointer and preview parity before finishing.

## Device check

Install over the existing app, open the selected profile runtime, and use Setup → Select database / Database files → Find database files. Check largest-first and newest-first with known files. Confirm the selected database remains selected while sorting and searching. Repeat in Custom, Traditional and TAKP; TAKP keeps its Initialize fresh TAKP database deployment action.

Published: workflow 39138297822 passed on its first attempt. All 599 Python tests with zero skips, JVM/C/DirectX checks and 19 browser scripts passed, followed by assembly/lint, pinned signing, native payload identity and TAKP helper verification. The public APK was independently downloaded and matched its published SHA256. GitHub /releases/latest now resolves to non-draft/non-prerelease v0.6.36 and preview APK bytes are identical. See release-proof-0636.json. Physical device acceptance is pending.
