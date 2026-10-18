# TRASC 0.6.35 beta — client connection and controller menus

Install over the existing TRASC preview app without uninstalling.

- Client → Login address edits **eqhost.txt**, independently for Custom, Traditional and TAKP. The default for a missing file is 127.0.0.1. Existing files are unchanged until you save; saving changes only the address and retains the port and remaining text. Prepare client preserves the file.
- The first changed host file is retained in a protected recovery folder. Restore original login file reverts it. The connection screen shows the current address, port and recovery availability.
- Custom → Client → 4 GB client patch enables Large Address Aware in the selected 32-bit eqgame.exe, as recommended by Triptych upstream for its enlarged spellbook. The protected original can be restored. Already patched clients are left intact. This increases the executable's address-space allowance; available memory still depends on the Wine/runtime environment.
- Controller menu navigation is enabled by default: LB/RB change visible tabs, D-pad moves focus, A opens a tile or activates a control, and B collapses a tile. A on a text field opens Android's keyboard. Gameplay and controller testing retain their mappings.

Open the selected server runtime to read or change the client connection or executable, and stop the game client before saving, patching or restoring. Existing protected recovery and session-backup behavior remains available.

The APK retains the existing application identity, signing certificate and verified native runtime components. No server rebuild, database import or Wine prefix repair is required to use these launcher features.

Physical AYN Thor acceptance of the new menus, keyboard and client customization remains pending. Host/browser regression and APK build evidence are recorded separately in the release workflow.
