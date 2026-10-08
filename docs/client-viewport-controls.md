# In-game viewport controls

The shared Custom and Traditional client gear menu offers two native RoF2 chat
commands. Enter the game before using them. Each action closes the gear menu,
cancels an unsent chat draft, types the command and presses Enter automatically.
Wait for typing to finish and check the game’s response.

| Gear action | Native command | Result |
| --- | --- | --- |
| Apply StoneUI viewport | `/viewport 179 0 920 480` | Insets the world view for the StoneUI 1280×720 layout. |
| Restore full viewport | `/viewport 0 0 1280 720` at 1280×720 | Restores the world view to the whole client frame. |

Apply StoneUI viewport requires the active launch resolution to be 1280×720.
Restore full viewport reads the active launch resolution: at 800×600, for
example, it sends `/viewport 0 0 800 600`. It restores a full frame rather than an
arbitrary earlier custom rectangle. UI window positions and chat preferences
are not changed by the launcher. RoF2 can save its resulting viewport settings
when camping normally.

To test on Thor, keep the existing server, runtime, Wine prefix, client and
DirectX helpers. Launch Traditional at 1280×720 with StoneUI selected, enter the
world, and choose Gear → Apply StoneUI viewport. Check that the world sits to the
right of the dock and above the bottom chat/hotbar area. Choose Gear → Restore
full viewport and check that the world fills the client frame while UI windows
remain in place. Apply again if desired, camp normally and reopen to verify the
native saved result. If either command fails, capture its native chat response,
a screenshot, the saved character INI and exported client logs.

Opening the gear menu, losing focus or leaving the client cancels pending command
typing and releases its held keys. Return to Launcher retains its existing name
and behavior.

Host command tests check the exact submitted text, final Enter, pacing and
cancellation at every stroke. The client runtime integration also replays both
viewport schedules through the real Windows WM_CHAR input probe. Neither check
substitutes for RoF2 appearance and persistence acceptance on Thor.
