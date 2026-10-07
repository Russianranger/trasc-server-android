# Apply an installed UI skin in 0.6.10

The Thor client starts successfully on 0.6.9. The supplied character settings
still save `UISkin=Default`, while the exported `UIErrors.txt` contains only its
creation timestamp. Neither file identifies a native XML rejection. The new
launcher action saves an installed skin directly for the selected character
and optionally applies its included layout. Native RoF2 loading and appearance
still need the device test below.

The action is available separately in TRASC Custom and Traditional. It requires
an imported client and an existing `UI_<character>_<server>.ini` created by the
game. Stop the client before applying or restoring settings. Keep the server
runtime open so the launcher can perform the operation.

Saving a skin changes the selected character's `[Main] UISkin`. Applying an
included layout also merges its supported window positions, dimensions,
visibility and viewport settings. Chat filters, colors and other preferences
are retained. The previous INI is backed up byte for byte. Restore previous UI
settings returns that saved configuration and retains the configuration it
replaces as a new backup.

## Thor test with StoneUI 0.1.1

1. Stop the client and server runtimes, install 0.6.10 in place, then freshly
   **Start runtime** in Traditional. Keep the existing compiled server, client,
   Wine prefix and DirectX helpers.
2. In the Client tab's UI skin card, confirm `stoneui_rof2_720_v011` is installed.
   If needed, import `StoneUI-RoF2-0.1.1-activation.zip` with the optional skin
   folder name blank. Enable Replace matching skins only when replacing that
   same installed skin. Existing default UI resources remain installed.
3. Select `UI_Rusuty_Traditional.ini` and `stoneui_rof2_720_v011`. Select
   **Apply included window layout**, then choose **Apply skin for next launch**. If the checkbox is
   unavailable, the installed skin has no matching layout text file; import the
   activation ZIP above before applying the layout.
4. Launch ROF2 at 1280 x 720. Leave **Load Default UI** unchecked at character
   selection. Check the stone dock, spell gems, hotbar, chat and status panels.
5. Camp and exit normally, then reopen the client to check persistence. The
   launcher shows the saved skin for the character settings; normal game exit
   is needed before relying on that saved value.
6. If the client falls back, immediately export Logs before another UI reload
   or restart and retain the chat response/screenshot. Root-level
   `client/current/UIErrors.txt` is now included when present. **Restore previous
   UI settings** is available while the client is stopped.

In-game `/loadskin <skin> 0` requests the XML layout; `1` retains saved window
positions. These are still available for native UI loading. The launcher does
not modify the skin XML, replace the renderer or change the Wine translator.

The in-client gear menu now labels its exit action **Return to Launcher** in
both TRASC Custom and Traditional.
