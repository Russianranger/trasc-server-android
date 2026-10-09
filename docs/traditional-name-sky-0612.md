# Traditional character labels and black selection sky

## Device evidence, October 8, 2026

The supplied `Screenshot_20261008-194454.png` shows the **character-selection**
screen, with readable yellow `Levaon [1 Magician]` / `Felwithe` text plus repeated,
extruded yellow geometry. The upper sky is black while the horizon backdrop,
trees, selected character and ordinary screen labels render. The supplied
in-world merchant image is indoors; it does not establish whether every outdoor
zone's sky is affected. This is rendered name geometry, not corrupted typed
character names or a server player-name change.

`logs-6872074258588036253.zip` records a Traditional 0.6.11 session beginning
2026-10-09 00:43:42 UTC. Its actual loaded graphics path is Turnip 26.0.0 on
Adreno 740, DXVK 2.5.3, 1280x720 fullscreen, native-surface presentation.
The game uses Box64 0.4.4 commit `2f130fab1`, Wine's experimental WoW64 path,
Balanced CPU settings and the exact `compatibility_042` NPC profile. This run
does **not** use FEX. Native D3DX model helpers are enabled; DirectInput is
Wine's built-in implementation. The existing Wine prefix is reused in 6.029s;
DXVK reads six state-cache entries. No runtime or prefix replacement is needed.

Verified component digests from launch state:

| Component | SHA-256 |
| --- | --- |
| Turnip 26.0.0 | `3c00117f6d5d01235ccb1457c6d58e799159a4d343401e6ba16ce6c46586ac95` |
| DXVK D3D9 | `3d6b529dc4f7f55639aad580e81b2939ab1489cdbb9f1550dce74e41656bbf5b` |
| Native D3DX9_30 | `5edeed79f2359527a55b8189cfa8b9b121cd608d44eead905a0f3436938ad532` |
| Native D3DX9_35 | `2198022938156b790e9cfb0f7997494b66a11a1ad49b395be58251d635b66b26` |

`dbg.txt` initializes the sky system at 00:44:45 without a recorded sky-load
failure. It reports a missing/failing `RenderEffects/SPL/SkinMeshCBS1_VSB.fxo`.
That same warning also existed in earlier reportedly working TRASC runs, so
replacing that shader without further evidence is not warranted. DXVK logs an
inverted/flat gamma-ramp error; that does not by itself explain the selective
geometry corruption. This export lacks the actual rendering INI values and
imported executable, graphics-DLL and sky-asset hashes needed for a direct
installation comparison.

## Previous TRASC outcome

The historical TRASC fix record is narrower than a permanent name repair.
The [Turnip device follow-up](turnip-selection-049.md#device-follow-up-2026-09-16)
records names becoming correct after fully exiting/relaunching the client and
remaining correct across later launches. That observation suggested warm state;
it did not prove a shader-cache cause. Earlier direct-buffer-mapping and Accurate
CPU-math experiments **failed actual device acceptance**. Their synthetic tests
did not reproduce this exact game defect. Those failed tests are not repeated
or presented as the remedy for Traditional.

## Isolated shader-constant comparison

**Name / sky compatibility (experimental)** is an opt-in Turnip/DXVK option,
off by default. It appends exactly:

```ini
d3d9.strictConstantCopies = True
```

The pinned [DXVK 2.5.3 option documentation](https://github.com/doitsujin/dxvk/blob/v2.5.3/dxvk.conf)
describes copying all shader-defined constants to the uniform buffer when
relative addressing is used. The pinned [shader compiler](https://github.com/doitsujin/dxvk/blob/v2.5.3/src/dxso/dxso_compiler.cpp)
implements this separately from direct buffer mapping. The option defaults off
in [D3D9 option construction](https://github.com/doitsujin/dxvk/blob/v2.5.3/src/d3d9/d3d9_options.cpp).

Incorrect shader-constant state is a plausible shared path for the malformed
3D labels and sky rendering. The logs do not prove this is their cause. This
comparison preserves all existing NPC flags, CPU profile, selected driver,
cache paths, imported files, model helpers and personal INI values. It is a
candidate correction requiring Thor acceptance, not an established repair.

The launcher records the enabled flag and exact requested DXVK configuration.
DXVK's own effective-configuration log is the loaded-setting evidence. Turning
the checkbox off before the next launch returns to the previous configuration;
there are no persisted client-INI or asset changes to restore.

## Focused acceptance and recovery

The already supplied run is the failing baseline. Do not repeat it before
testing the new option.

1. Stop the game normally. Update the APK in place and select Traditional.
2. Keep Turnip 26.0.0, 1280x720, Balanced, existing NPC compatibility and model
   helpers unchanged. Enable **Name / sky compatibility (experimental, Turnip)**.
3. Enter the existing character-selection screen. Watch the name/class/zone
   label through animation or Rotate for 30 seconds; check the sky above the
   horizon. Capture the same view if either remains wrong. No new character
   creation is required.
4. Enter the world to check models and movement. Camp normally and inspect the
   selection label again; then close/reopen the game once and inspect it again.
5. Export Logs promptly, keeping the new current and previous-session evidence.
   If graphics regress, stop the game, disable the option and reopen. Preserve
   the logs from the enabled run before additional launches rotate them.

The new read-only `render_assets` launch report records selected numeric/boolean
rendering options from `eqclient.ini` and `defaults.ini`, their content hashes,
and bounded hashes/metadata for the executable, graphics DLL and selected sky
and shader paths. It exports no arbitrary INI values, names, chat, or asset
bytes. Missing paths in this limited inventory do not prove missing resources:
the client may resolve packed assets or another search path.

Current hypothesis order is shared translated geometry/shader state, an
unobserved imported sky/rendering setting, then missing/incompatible sky data.
The new inventory distinguishes the latter two from actual graphics state
without resetting preferences. If the option fails, compare its effective
DXVK setting and exact client/graphics hashes before choosing a different
rendering change. Do not clear caches, reimport the client, repair the prefix,
rebuild the server or repeat the old direct-mapping/math comparisons.

## Automated validation

Focused tests verify that enabling the comparison changes only one DXVK flag,
disabling it restores the exact existing configuration, and all previous NPC
modes retain their values. Rendering-inventory tests check exact hashes,
case-insensitive paths, preference/file preservation, private-value exclusion,
duplicate-setting ambiguity, symlink rejection, UTF-16 handling and read limits.
These validate configuration and evidence collection; they do not reproduce
the proprietary character-selection screen or establish physical-device gain.
