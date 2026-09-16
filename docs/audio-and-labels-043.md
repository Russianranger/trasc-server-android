# 0.4.3: audio start watermarks and live label geometry

## Device evidence

The user confirms NPC compatibility in 0.4.2 fixes models. The September 16 03:40:20 video shows the selected character's yellow name/class/zone label twisting and duplicating; this is rendered text geometry, not Android keyboard entry. The 03:44:09 video belongs to the compatibility session and the 03:47:43 video to the Standard session. The latter is the last saved launch choice. FPS differs between these recordings (roughly 20–30 and 50–60 in the visible HUD), but they are not identical-route benchmarks and no speedup is asserted.

In logs-3726963507059387515(1).zip, both client-audio logs show focus granted and nonzero Android media volume. Each session accepted only 480 frames on one stream and 1920 on another, all silence, with no bridge error. Native libasound and Wine DirectSound load. Therefore the listener is reached; a missing socket or denied audio focus does not explain the observed silence. 0.4.2 did not log the Android buffer size or playback head, so the exact device watermark cannot be reconstructed.

## Audio correction

AudioTrack allocation can be larger than the ALSA producer ring. Android's default start watermark is its allocation size; Wine stops writing when its own ring is full until the playback head advances. Those two limits can deadlock. AudioBufferPolicy now bounds the effective write buffer to the producer ring and sets the start watermark to one frame on API 31+. On older supported Android, the effective buffer limit supplies the watermark. An impossible returned threshold fails explicitly rather than pretending playback succeeded. Reset, start and a detected routing-size change reapply the policy. No clock is fabricated, PCM dropped or silence added to fake progress. The actual AudioTrack head still drives ALSA.

Bounded five-second progress records include written/played frames, signal counts, underruns and play state; setup records requested, allocated, effective and startup sizes. First nonzero data is recorded once per reset. No raw PCM or microphone data is collected. The old code's larger-watermark behavior is reproduced by a JVM sink model; it stalls at1920 frames. The same test requires progress with the production buffer policy at 480/1920/3840 frames, both old/new Android API behavior, repeated underruns and an invalid hardware-limit rejection. This validates buffer accounting and call policy; only Thor testing confirms audible output.

## Label correction

Pinned DXVK 2.5.3 documents that DEFAULT dynamic buffers can be updated while locked, and some games continue drawing that way. Forcing `d3d9.allowDirectBufferMapping=False` changes that behavior: staging copies can go stale when the application writes through a retained pointer between draws. Compatibility now keeps `d3d9.floatEmulation=Strict` and `d3d9.forceSamplerTypeSpecConstants=True` while restoring `d3d9.allowDirectBufferMapping=True`. EverQuest's built-in cached-dynamic-buffer profile is unchanged. `compatibility_042` preserves the exact prior three settings for recovery/comparison.

The open PE32 fixture repeatedly changes colored label geometry through a retained vertex pointer, reading rendered pixels after each draw. The DXVK suite requires the old staged mode to reproduce stale pixels (exit 42 with an explicit marker) and the corrected mode to render each update (exit 0). This is a concrete rendering regression control, not a claim to have executed the proprietary ROF2 character screen in CI. Original shader/model/input/fullscreen/exit/audio checks remain strict. No automatic retry or acceptance of SIGKILL is introduced.

## Sources

- [Android AudioTrack playback/start threshold](https://developer.android.com/reference/android/media/AudioTrack#play()) and [buffer sizing](https://developer.android.com/reference/android/media/AudioTrack#setBufferSizeInFrames(int)).
- [DXVK 2.5.3 dynamic-buffer mapping behavior](https://github.com/doitsujin/dxvk/blob/v2.5.3/src/d3d9/d3d9_common_buffer.cpp) and [lock/upload/draw implementation](https://github.com/doitsujin/dxvk/blob/v2.5.3/src/d3d9/d3d9_device.cpp).

**Published and verified:** version 0.4.3/code20, source `5dfcae27403df33f26f928f9a56d7ce3457e3cea`, after all six jobs passed in [run 35080301081](https://github.com/Russianranger/trasc-server-android/actions/runs/35080301081). Public downloads match the tested APK/source artifacts and preserved signing identity. The new PE32 pixel comparison passes both directly and through PRoot: old staging produces the required stale-pixel negative control; restored direct mapping renders every update. Original runtime/model/input/audio/restart gates also pass. The concrete API/source defects are covered by regressions, while audible Thor output and the exact ROF2 name/model result still require device acceptance. No runtime image, app ID, imported assets or prefix change.
