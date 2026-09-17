# 0.4.15 input follow-up and crash evidence

The Thor 0.4.14 bundle logs-7101954634475225843 confirms shared-memory capture: memfd SysV IPC, MIT-SHM, about 0.95 ms median capture time, 16,511 idle capture skips and 15,621 duplicate transfer skips in the latest session. This is capture-stage evidence, not proof of improved battery life or equivalent-scene FPS.

The user reports gear #tim fails while manual typing succeeds; controller look remains bounded; stack overflow follows character select → server select → reconnect; the app also disappeared during server stop. No stack-overflow trace or Android crash report is present in this bundle. dbg.txt reaches normal quit and login UI initialization. Do not label reconnect or shutdown crashes fixed by this update.

Changes:
- Gear command uses paced key-down/up events, Escape to cancel an existing draft, slash then Backspace to open an empty command line, explicit Shift+# and tim, then Enter. No Ctrl+A assumption. All pending strokes cancel on menu/focus/lifecycle changes; held modifiers release. The shared Java schedule is replayed through the real VNC/Wine Windows text receiver in CI.
- Optional Client → Graphics, audio & launch options → Recenter mouse for camera look. Off by default. The app-specific Wine DirectInput MouseWarpOverride is force when enabled, default when disabled, set before the next game process creates input devices. Wine owns recentering and its warp bookkeeping. This is a device comparison, not a proven EQ fix; turn it off/relaunch if inventory pointing snaps to center. Tests add buffered GetDeviceData alongside polled GetDeviceState and check actual client-area recentering after movement beyond desktop width. Helper connection/delta counts distinguish readiness from received input.
- Logs export adds the app's five most recent Android process-exit records, with at most 256 KiB of trace per record. Native tombstone protobufs are base64; ANR traces are text. A bounded latest Java uncaught-exception report is retained before Android's normal handler. These are local diagnostics, no additional permission or upload.
- Management WebView renderer exit now records the event and offers a native reopen button instead of accepting Android's default application termination. Late worker replies/submission after activity destruction are guarded. Notification stop requests share one owned executor, ignore duplicate concurrent requests, attempt both client and server stops independently, record failures and keep the foreground service if a runtime remains alive. This fixes identified lifecycle/resource handling gaps, not an established cause of the reported crash.
- Server shutdown now logs request/completion phases so interrupted saves can be located.

Source basis: [Wine 10 DirectInput mouse](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/dinput/mouse.c), [per-application registry lookup](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/dinput/device.c), [Android process exit information](https://developer.android.com/reference/android/app/ApplicationExitInfo), [WebView renderer exit](https://developer.android.com/reference/android/webkit/WebViewClient#onRenderProcessGone(android.webkit.WebView,%20android.webkit.RenderProcessGoneDetail)).

Device checks after installing in place:
1. In-world with no chat draft to keep, use gear #tim and check the game response.
2. Stop client, enable recentering, relaunch, compare held-right-click and toggled mouse look plus inventory pointing. Disable/relaunch if unsuitable. No runtime reinstall or DLL rebuild is needed.
3. Reproduce character select → server select → reconnect once with the existing Wine diagnostic option enabled for that short attempt, then export Logs. Turn verbose diagnostics off afterward. Restart the client rather than re-entering the same process as a temporary workaround.
4. Export Logs after updating; Android may still retain the previous app-exit record. If the stop failure recurs, reopen the app and export promptly.

Pending device acceptance: EQ chat handling, held/toggled mouse look and inventory pointing; stack-overflow and shutdown root causes. No Thor acceptance or crash fix is claimed by the CI results. Keep the working installed runtimes.

Initial source bb6685d passed all application gates, including six direct/PRoot software, DXVK and VirGL input passes. Review then corrected the WebView recovery order: clear the activity reference before releasing controller state, and only destroy the failed WebView. Input-release callbacks must not evaluate JavaScript on the failed renderer. The static footer is also corrected to0.4.15. The initial APK is superseded; deliver only the subsequent verified candidate. All original gates remain required.

## Verified and published

Final implementation **09e5e0b5334073c25a7fdca4a39240add0fc66e1**, version **0.4.15/code32**, [run35283326055](https://github.com/Russianranger/trasc-server-android/actions/runs/35283326055). All seven jobs passed: Microsoft DLL, database, WineD3D, Vulkan, APK, full client runtime and publication.125 Python tests, JVM/C input/cancellation/archive tests, browser flows, Android lint/signing and all existing direct/PRoot software/DXVK/VirGL rendering/model/audio/shutdown/restart gates passed. Six real Windows receivers received exact #tim; both buffered and polled DirectInput continued past the one-pixel clip; forced recentering returned to the client-area center. These are open Windows fixtures, not the proprietary EQ chat implementation or physical Thor acceptance.

Final DXVK evidence artifact10523503987 (ZIP SHA25663625596708ab39cacb2499792e75adc3042b8e18d02865f68d863d5c880c575) reports recentering true directly and through PRoot. Direct/clipped polled dx6320; PRoot dx6400. Buffered counters7960/7920 include the subsequent1600-pixel unclipped recentering phase, so do not compare them to the report's6400-pixel initial phase as simultaneous counters. The input helper records200 actual relative events per consumer. No repeat-capture/power benchmark was run in this follow-up.

Final APK artifact10523427357 ZIP SHA2568366b05823aa5a2691a51a6cbb9047327d0c5c69c9b9f320ceecc34d79024bea. Independent verification checked the complete APK v2 signed digest, RSA signature, preserved certificate, package/version, all33 packaged Python/UI assets, both ARM64 presentation binaries, helper manifest hash, memfd PRoot binary marker and corresponding presentation sources/recipe. The final version label is0.4.15. APK and source archive are under ignored runtime-work; the superseded initial APK is explicitly named superseded.

- APK: 10,513,934 bytes, SHA256 `f1f39f02ae6e192bd0e29c6ad11018efe18368f60b0c5fe9a8b4e22e14330d05`.
- Corresponding native sources: 114,558,369 bytes, SHA256 `fb6a0784df644d91366c0f7fdf48feec98e20930f739f2e561d5df8da3bc5571`.
- Signing certificate SHA256 `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; package `io.github.russianranger.trasc.preview`.

Publication succeeded at23:06UTC on September17. Public preview points to the final tested commit; release asset sizes/digests match the independently verified Actions candidate. This comparison uses public metadata, not a second APK download. The previous upload outage also cleared: client-runtime-v1 now has both archives and its manifest, published in order on the first attempt. The existing Thor runtime should still be retained; no reinstall is needed.

- Public runtime payload353,710,627 bytes; SHA2563e55a6046672af9ddc94580ccc14e63af9a387b39c3cdcf4bef855edd5b865c7.
- Public runtime sources51,203,144 bytes; SHA2569dab9064dbac5cf7ebfc6fe0932abb7ddc6a3158dd47d34b7a4ffbb7c910ccd4.
- Public runtime manifest356 bytes; GitHub digest4af58f9f211260a67208f77a6137ce6c30d15fea9279d8f58eef50e16b72a321.

Next: update in place after stopping client/runtime, test #tim, then enable mouse recentering and relaunch for the camera/inventory comparison. Export Logs after updating: Android may retain the earlier app-exit record. For the reconnect overflow, use the existing Wine diagnostic option for one short reproduction and export, then turn verbose logging off. Until diagnosed, restart the client before re-entering the server. Do not change database/camp settings, rebuild the DLL, clear the prefix/caches or install Mac tooling for this update.
