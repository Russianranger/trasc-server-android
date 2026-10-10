// TRASC TAKP Wine cursor repair v1; called inside EQW's existing look gate.
// Wine 10's NtUserSetCursorPos skips its X11 warp when the cached cursor is
// already at the requested point. EQW's game-input and window-message threads
// can disagree with Xvnc at that instant. A one-pixel in-process intermediate
// point forces the final warp; Wine's own warp serial suppresses those events.
#pragma once

namespace trasc_takp_camera {
static const char marker[] = "TRASC_TAKP_WINE_RECENTER_V1";

template<class Setter> bool center(int x, int y, int left, int right, bool wine, Setter set) {
    // Work in final screen coordinates, after EQW's scaling/offset conversion.
    // A tiny/minimized window receives only the original SetCursorPos call.
    if (wine && right - left > 1 && x >= left && x < right) {
        const int intermediate = x < right - 1 ? x + 1 : x - 1;
        set(intermediate, y);
    }
    return set(x, y) != 0;
}
}
