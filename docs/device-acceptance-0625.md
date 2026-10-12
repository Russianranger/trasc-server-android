# AYN Thor acceptance: 0.6.25

Install only the independently verified APK/version recorded in `release-status-0625.md` and `release-proof-0625.json`. Install as an update without uninstalling; retain all profiles, databases, bots, source/build output, imported clients, Wine prefixes, controls, themes and settings. The footer and Android package now identify 0.6.25/code74.

## Existing TAKP server and source update

1. Open the TAKP runtime with client/server stopped. Before updating source, check **Start server** is available for your existing qualified deployment. Start it and enter with the existing character once; stop normally. If unavailable, export logs and include the deployed `server/bin/build-info.json` and deployment receipt, without deleting or recreating the database. The original log bundle did not include those receipts.
2. Export an all-profile checkpoint to SD/USB using **Server → Session backups → Create & export all profiles**. Keep it outside app-private storage. Export stops the runtimes; select **Start runtime** again before the next step.
3. **Builds → Updates → Refresh update status → Check source update**. Expect old `25bf70ac` to qualified `03e934d0`, two changed files/two additions. Review the list, then **Apply reviewed source update**. Current binaries must still start; source update does not deploy or initialize a database. A second check should show already-current source.
4. Choose one compiler job, connect power, **Build updated source**. Expect reuse when the old cache can be independently qualified; logs disclose any incompatible/missing cache. Use **Build with fresh cache** only if explicitly needed. Record build duration, changed-object output and cache message. Then **Deploy updated binaries** after successful qualification.
5. Spawn the existing cleric. Remain idle two minutes: no repeated automatic Yaulp maintenance. Test permitted melee, leaving melee range and healing priorities; camp/restart and confirm bots/settings are retained. No fresh database or bot recreation is needed.

## Updates in Custom and Traditional

Repeat the check/review/apply/build/deploy flow for each installed world. An already-current qualified revision should show no source delta. Verify your database/characters, runtime quests/maps, clients/prefixes and original server remain intact. Historical Custom caches require one explicit fresh build to establish compiler/runtime receipts; the old cache is retained. Future unchanged builds should report no work. Relevant dependencies can still cause additional recompilation.

On a spare imported-source copy, make a harmless local source edit, then check an update: application must refuse and retain the edit. A source target change invalidates the previous review. Client/server activity or another operation must block updating. A failed compile keeps the previous successful stage and deployment; do not deliberately damage the only live installation to test failure.

## Optional classic skeleton models

With the TAKP runtime open and client stopped, **TAKP → Client → Skeleton models → Check skeleton models**. Check **Use classic skeleton models**, then **Apply model choice**. Both required archives must validate; unsupported, corrupt or already modified assets refuse before activation. Originals and related texture caches are retained.

Launch the same client with renderer/camera settings unchanged. Compare familiar skeleton NPCs and summoned pets in more than one zone; record screenshots and any texture conflict. Stop the client, **Restore original skeleton models**, relaunch and compare again. Check the option is off, original appearance returns and unrelated models, client settings and controller mappings persist. Client import is blocked while the managed patch is enabled; restore first. The option must not appear in Custom or Traditional.

Existing all-profile/session backups include the patch receipt and originals. On a spare installation, restore a checkpoint made while enabled and confirm both the enabled state and subsequent original restoration. Interruption recovery must not leave one archive changed and the other original. This is an asset option, not a claim that TAKP NPC visibility is resolved.

## Camera and retained acceptance

This pass does not change camera delivery. The attached logs contain no fresh 0.6.24 diagnostic-helper launch or consumer trace. When testing camera, prepare the current helper, reproduce short left/right and up/down reversals using touch and right stick, stop the client, then **Logs → Export log bundle** within the first minute. Include `client/current/eqw-camera-diagnostics.log`; retain actual direction, input source and Look state.

Use the retained test steps in `device-acceptance-0624.md` with the current 0.6.25 APK for the full gear/Look, offline bot creation, command/social/hotbar persistence, storage conversion protections and large all-profile SAF import/export checklist. Those completed features remain preserved. TAKP NPC visibility and Traditional StoneUI remain separately tracked.

The linked 0.6.24 guide is historical: its older APK/code/footer and source-replacement/build instructions are superseded by the verified 0.6.25 release and the Updates workflow above. Reuse its retained gameplay/control/backup test procedures.
