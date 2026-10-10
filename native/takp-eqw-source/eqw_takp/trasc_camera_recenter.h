// TRASC TAKP Wine camera v2. Restrict the cursor only during EQW's existing
// look gate, enabling Wine's clipped XI2/raw relative-input path. Repeated
// SetCursorPos warps can turn late game-window MotionNotify into false deltas.
#pragma once

namespace trasc_takp_camera {
static const char marker[] = "TRASC_TAKP_WINE_RAW_LOOK_V2";

struct Rect { int left, top, right, bottom; };
inline bool same(const Rect& a, const Rect& b) {
    return a.left == b.left && a.top == b.top && a.right == b.right && a.bottom == b.bottom;
}

// The caller serializes this state across the game-input and window threads.
class LookClip {
    bool held_ = false;
    unsigned long generation_ = 0;
    Rect original_ = {}, clip_ = {};
public:
    bool held() const { return held_; }
    unsigned long generation() const { return generation_; }
    // Capture only if no lifecycle release overtook the caller's input query.
    template<class Getter, class Setter>
    bool hold_since(unsigned long generation, int x, int y, const Rect& bounds, Getter get, Setter set) {
        return generation == generation_ && hold(x, y, bounds, get, set);
    }
    template<class Getter, class Setter>
    bool hold(int x, int y, const Rect& bounds, Getter get, Setter set) {
        if (x < bounds.left || x >= bounds.right || y < bounds.top || y >= bounds.bottom ||
            bounds.right - bounds.left < 2 || bounds.bottom - bounds.top < 2) return false;
        const Rect next = {x, y, x + 1, y + 1};
        Rect current;
        if (!get(current)) return false;
        if (held_ && !same(current, clip_)) held_ = false; // another owner changed the clip
        if (held_ && same(next, clip_)) return true; // no frame-by-frame warp or ClipCursor
        if (!set(next)) return false;
        if (!held_) original_ = current;
        clip_ = next;
        held_ = true;
        return true;
    }
    template<class Getter, class Setter> bool release(Getter get, Setter set) {
        ++generation_; // stamp even an already-released clip / paused look
        if (!held_) return true;
        Rect current;
        if (!get(current)) return false; // retry rather than forget the saved rectangle
        if (same(current, clip_) && !set(original_)) return false;
        // Never overwrite a rectangle changed by another window/application.
        held_ = false;
        return true;
    }
};

// Retained only as the v1 comparison in the open native fixture.
template<class Setter> bool legacy_center(int x, int y, int left, int right, Setter set) {
    if (right - left > 1 && x >= left && x < right) set(x < right - 1 ? x + 1 : x - 1, y);
    return set(x, y) != 0;
}
}
