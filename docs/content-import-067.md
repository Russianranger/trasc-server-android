# 0.6.7 content downloads and client UI ZIPs

## Traditional support components

Start the Traditional server runtime and open Setup. Perl plugins, Lua modules,
and Server assets each have their own editable GitHub repository, revision,
download button and ZIP picker. Quests retain their separate import controls.

| Component | Default repository | Selected files / destination |
| --- | --- | --- |
| Perl plugins | https://github.com/ProjectEQ/projecteqquests | `plugins/` → `server/plugins/` |
| Lua modules | https://github.com/ProjectEQ/projecteqquests | `lua_modules/` → `server/lua_modules/` |
| Server assets | https://github.com/EQEmu/EQEmu | Client patch configurations → `server/assets/patches/`; general, mail and login opcode files → `server/assets/opcodes/` |

ProjectEQ defaults to its repository default branch. To match your imported
quests exactly, copy that recorded commit into both module revision fields.
Assets default to `4aceae18b94ffaafc08e2b17bc41cd72c77f795d`, the same qualified
source revision as Traditional's server. The importer follows the official
[Spire installer layout](https://github.com/EQEmu/spire/blob/master/internal/eqemuserver/installer.go)
and excludes the source tree, database SQL and installation scripts.

First imports do not need the replacement checkbox. Replacing an existing
component requires its checkbox and retains the old directory under
`backups/content/`. Import status appears on each card and the Traditional
checklist. These are imported files; deployment/configuration and first login
remain the next Traditional milestone.

## Import a client UI ZIP in either world

1. Stop the embedded client. Select TRASC Custom or Traditional EQEmu and start
   that profile's server runtime. A RoF2 client must already be imported there.
2. Open Client → **Import a client UI skin** → **Choose UI ZIP**.
3. Choose a RoF2-compatible skin ZIP. It can contain loose XML/textures, a skin
   folder, or a `uifiles/` folder containing skins. For loose files, optionally
   enter a skin folder name before choosing the ZIP.
4. For an existing skin, select the replacement checkbox deliberately. Its old
   folder is retained under the profile's backups before activation.
5. Confirm the skin appears in the installed list. Start the client and use the
   displayed `/loadskin skin_name 1` command, or choose it in the game's UI menu.

Imports write only to `client/current/uifiles/<skin>` in the selected world.
The default skins are protected; importing a default-named ZIP under a new
explicit name is allowed. Executables, DLLs and client settings are excluded.
Archive paths, duplicate Windows-style names and links are rejected, and
interrupted replacement transactions recover on runtime startup. Importing a
skin does not certify that every XML element matches RoF2; test the skin in game.

Install 0.6.7 over the existing app with its data retained, then freshly start
the server runtime so it copies the new importer. This feature requires no
runtime redownload, server rebuild, client reimport or DLL rebuild.
