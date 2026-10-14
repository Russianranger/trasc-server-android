# TRASC Android preview 0.6.28 · code 77

The physical 0.6.27 logs identify missing native X focus: Android's signed stick
packets reach XI2 correctly, but Wine reports foreground while X remains on
PointerRoot. The escaped cursor offset then produces wrong-direction input.
This update restores missing focus only during held right mouse over the exact
visible TAKP game window. It preserves concrete foreign focus, menus, hidden
windows and existing prefix settings. The existing V3 helper then confines the
pointer. No warps, injected movement, runtime replacement or registry edits.

The exact published ARM64 Box64/Wine/TigerVNC path reproduced PointerRoot with
wrong fresh reversal input, then passed physical confinement, ten exact signed
motion segments through both DirectInput APIs, zero idle drift, menu release,
six refusal guards and resume recovery. These controlled results do not prove
camera usability on Thor. APK signing/profile/publication gates must also pass.

Install as an update and restart only the TAKP client. Keep the working server
and Yaulp deployment. After a short right-stick reversal test, stop the client
and export logs. Server source/database/characters/bots, client assets, Wine
prefixes, runtimes, settings and all-profile backup remain in place. No new
server update/build/deployment, client import or prefix reset is required.

Camera acceptance remains open. NPC visibility and Traditional StoneUI remain
separate issues. See docs/takp-camera-focus-0628.md for qualification and test scope.
