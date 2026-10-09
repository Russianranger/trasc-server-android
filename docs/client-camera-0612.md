# Traditional camera recentering — 0.6.12

Traditional now exposes **Client → Graphics, audio & launch options → Recenter
only during camera look (experimental)**. It is off by default. Custom retains
its existing compiled add-on; Traditional uses a separate bundled camera-only
32-bit DirectInput proxy. No Microsoft SDK import or user compilation is needed.

The proxy forwards system DirectInput, including keyboard and mouse state, and
uses the existing verified RoF2 camera state gates. It does not include MQ2,
Custom spell loading, model-pause, particle, boat or gameplay hooks. Both the
launcher and proxy check the exact supported executable. Unsupported clients
keep normal input and report the unavailable adapter in launch state.

On an enabled launch the manager preserves an imported DirectInput DLL, its
filename casing and metadata, or records that no DLL existed. It installs the
verified bundled proxy beside the game and restores the exact original after
Wine stops. A persistent, locked journal and original bytes travel with the
client backup. Interrupted launches recover before the next launch, client-file
operation, session backup or profile change. Changed DLL/executable ownership
causes a conflict instead of overwriting the user's files.

## Focused Thor test

1. Stop the client normally and install 0.6.12 over the existing APK. Select
   Traditional, keeping the existing client, runtime, prefix and launch choices.
2. Enable **Recenter only during camera look (experimental)** and relaunch.
   Leave the Custom native-DLL/loading/particle/boat controls disabled.
3. Check a free pointer on login and character selection. Enter the existing
   character; turn continuously with right-click camera look past a full circle.
   Release right-click and check that the pointer can reach menus and inventory.
   Check ordinary controller movement, hotkeys and both mouse buttons.
4. Camp normally, return to the launcher and reopen once. Repeat camera look
   and a menu click; do not reset bindings or reimport the client.
5. To revert, stop the client, uncheck the camera option and relaunch. The
   previous DLL bytes or original absence are restored automatically.

Export Logs after a failure. Include the current launch state, native
`dinput8.log`, and `traditional-camera-recovery.log` if present. A managed
adapter request is not itself proof that physical camera motion works.

Automated checks cover system DirectInput forwarding, camera state gates,
executable/DLL validation, exact restoration and interrupted transactions.
Physical Thor acceptance remains separate.
