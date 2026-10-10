# TRASC 0.6.22 / code 71 — Bots manager and TAKP cursor repair

Published and independently verified from source commit `25fb54cf86d9b4b15b121bc199b44375a6810e74`, [qualification run 38039299622](https://github.com/Russianranger/trasc-server-android/actions/runs/38039299622), and [PR 28](https://github.com/Russianranger/trasc-server-android/pull/28).

The release adds the Bots tab across all three worlds, normal server-owned offline creation for the two pinned modern servers, native TAKP records, backed-up social/hotbar installation and restore, Wine-only EQW recentering, draggable per-world controls, and Look tile visibility.

APK SHA-256: `6e4606d94db9d667033e37465b914159a3612face88f77810b119bdcf3ff1411`.
Source archive SHA-256: `314c2e8a161f3f5428b75c7052fd1fd337ccfee96419ebc214470bf0916ba13d`.
The existing preview update certificate remains `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.

The final workflow passed 482 Python tests, including 22 real MariaDB cases, browser regression flows, 13 JVM fixtures, 5 native fixtures, Android build/lint, signing and packaged-helper verification. Both ARM64 modern servers passed real creation, native stats/items/quest hooks, owner inventory/bank preservation, fresh database restart and native reload, durable retries, and 17 unchanged-row refusal/rollback cases each. Traditional's exact native 9055 schema repair passed after a real full backup without rewriting version numbers. Its full deployment-receipt gate is separately unit-tested. Production TAKP build, migrations, accounts, startup and exports passed.

The delivered APK's signature, version/code, exact packaged backend/UI bytes, all 83 reviewed source changes, 169 selected archived source files, and 21 reused native payload files were independently verified. The four published release asset IDs and SHA-256 values match the downloaded workflow artifact and build manifest.

The exact published 0.6.21 native payload is retained: baseline APK SHA-256 `0047f5091b92b7417efc738ed056f221bb6c1d2cf9d63d4f3da00e7966c00b55`; preserved native source archive SHA-256 `76124578972ccf56159ad963fd52c48922fb42c29ef4618725802c6568375077`.

The EQW repair was built from upstream `3b4d43562c9dacc89349185684bb0bf0b01f9d06`, preserving its MIT notice and patch sources. DLL SHA-256 `b739dfe64b7f69be2ffebf13a1cf794bcfd9e37fe143a75134ca6359e60ef584` passed the real Wine 10/Xvnc cursor fixture and Windows build in [run 38029612146](https://github.com/Russianranger/trasc-server-android/actions/runs/38029612146). The previous managed DLL is backed up and upgraded on launch.

Device acceptance remains for actual TAKP camera feel on Thor, proprietary client INI load/save roundtrips and summon/target/invite timing. These checks are distinct from the passed open-fixture and server/database qualifications.

See [Bots instructions](bot-manager-0622.md), [camera diagnosis and device checks](takp-camera-0622.md) and [preview notes](preview-notes.md). Existing installations can update without reimporting the client. Modern profiles need their current server rebuilt and deployed before offline generation.
