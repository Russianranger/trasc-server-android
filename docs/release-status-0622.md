# TRASC 0.6.22 / code 71 — Bots manager and TAKP cursor repair

Preparation record. Publication and artifact verification are pending at this
source snapshot. The completed verification record will replace this paragraph
after qualification; this document does not yet claim a released APK.

The release adds a Bots tab across all three worlds, server-owned offline
creation for the two modern pins, native TAKP creation, social installation/
restore, Wine-only EQW recentering, draggable per-world controls and tile visibility.

The exact published 0.6.21 native payload is reused. APK SHA-256:
`0047f5091b92b7417efc738ed056f221bb6c1d2cf9d63d4f3da00e7966c00b55`.
Source archive SHA-256:
`76124578972ccf56159ad963fd52c48922fb42c29ef4618725802c6568375077`.
The existing preview update certificate remains
`ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.

The EQW repair is built from upstream commit
`3b4d43562c9dacc89349185684bb0bf0b01f9d06`, preserving its MIT notice and narrow
patch sources. The previous managed DLL is backed up and upgraded on launch.
Real Wine/Xvnc qualification and server/database fixtures are distinct from
actual client/Thor acceptance.

See [Bots instructions](bot-manager-0622.md) and
[preview notes](preview-notes.md) for setup and device acceptance.
