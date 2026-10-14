# TRASC Android preview 0.6.29 · code 78

This is a diagnostic update for the unresolved TAKP camera. On the latest
Thor test, the 0.6.28 focus companion ran but made zero focus requests because
it did not recognize the actual game window in the pointer path. The next
correction requires the real window properties and layout; capture behavior
and its strict ownership checks are unchanged in this release.

A bounded read-only native inspector records short window title/class bytes,
property types/counts, visibility, geometry, parents, PIDs and pointer-path
relationships. It can identify matching candidates outside that path without
changing focus, pointer or properties. Final helper liveness also refreshes
after teardown. Existing V3, focus companion, observer, input transport,
runtimes, settings and all 21 native launcher components remain unchanged.

Actual ARM64 qualification passed 14 property/layout cases with unchanged
focus/pointer/buttons, normal bounded logs and zero drops/X errors. It qualifies
collection, not physical camera repair. All five APK/profile/publication gates
and independent public signature/source/asset verification passed. Exact
receipts are in docs/release-status-0629.md and release-proof-0629.json.

Camp and stop clients/servers normally; install as an Android update without
uninstalling, then reopen TAKP. Keep the working Yaulp deployment and data;
no server rebuild, database import, client reimport or prefix reset is needed.
Enter the saved character within five minutes of client launch, enable Look,
reproduce right-stick motion for ten seconds, turn Look off, stop normally
and export a fresh bundle including client-takp-windows.log.

Camera remains unaccepted. NPC visibility, Traditional StoneUI, the separate
expired post-camp session-key observation and backup/bot/model/object-reuse
checks remain separate. See docs/takp-window-0629.md and device-camera-0628.md.
