# Traditional deployment and quests helpers — 0.6.8

Traditional now deploys the nine verified ARM64 binaries from the existing staged build, validates the complete PEQ/local-login schema, retains a database backup before migrations, and writes its own configuration. Start generates shared memory and launches the local login server, world, chat, query service and dynamic zones. Generated client exports and preparation use the deployed Traditional binaries. Custom retains its existing paths, server and client behavior.

## Quests and helpers

The Quests import keeps zone/global scripts, `plugins/` and `lua_modules/` together under `server/quests`. The two helper cards show the imported quest repository/revision, detected path and actual script count. They no longer download separate copies by default. Missing, empty or unsafe folders are reported. Existing separately imported `server/plugins` and `server/lua_modules` remain fallback paths; deployment chooses the detected usable paths.

If Quests was imported using an older launcher, that importer omitted its helper directories. To consolidate them, choose the same quest repository/ref, check **Replace this entire component**, and import Quests once. The previous tree remains under `backups/content`. Reimporting is unnecessary when the desired helpers already exist; the checklist reports which paths are in use. The advanced component selector remains available for unusual standalone distributions.

## Device acceptance

1. Stop the client and server runtime. Install 0.6.8 over the existing app without uninstalling or clearing storage.
2. Select **Traditional EQEmu** and **Start runtime**. Keep the successfully compiled build; no source/server rebuild or runtime refresh is required for this launcher update.
3. Confirm the complete PEQ database, quests and server assets are imported. The assets need RoF2 patches and the full login opcode set. Check the Perl/Lua detection cards. If either helper is absent, import the complete Quests repository as described above.
4. Open **Builds → Deploy successful build**. Missing prerequisites are listed in the build/checklist status. Deployment backs up the database, checks/applies the pinned server's migrations, then activates verified binaries and the profile-local configuration. Do not replace your database seed just to install this update.
5. Import maps if missing. Their default is `Russianranger/eqemu-maps`.
6. In **Client → Import your ROF2 client**, choose a separate clean RoF2 ZIP. Install this profile's client runtime and DirectX model helpers if needed. Traditional uses Wine's built-in DirectInput; Custom DLL modifications stay disabled in this profile.
7. Use **Prepare client for this server** to set the local login endpoint and generate/sync `spells_us.txt`, `dbstr_us.txt`, `SkillCaps.txt` and `BaseData.txt`. Existing files are backed up by the established client preparation flow. UI ZIP import remains available in either profile.
8. **Start server**, wait for server/zone readiness in Logs, then launch the client. New local login accounts are created automatically from the username/password entered on first login. Select **Traditional EQEmu on Android**, create a character and try world entry, camping and relogin. This acceptance test does not apply an era preset.
9. Export logs from Traditional if deployment, preparation, login or world entry fails. Stop this profile, switch back to Custom, and confirm the existing world/client still start.

Binary rollback restores only a verified previous Traditional deployment. It does not undo schema migrations; database backups remain separately available. Interrupted activation is recovered on runtime startup.

Physical Thor first login and zoning remain device acceptance. Automated qualification uses a disposable Traditional profile and synthetic test credentials; it is separate from the user's saved database and characters.
