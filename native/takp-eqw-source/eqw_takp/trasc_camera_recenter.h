// TRASC TAKP Wine camera v3. Restrict the cursor only during EQW's existing
// look gate. Wine can acknowledge its cached rectangle without a physical X
// grab; retry that same rectangle only when an observed cursor escapes it.
// Repeated SetCursorPos warps can turn late MotionNotify into false deltas.
#pragma once

namespace trasc_takp_camera {
static const char marker[] = "TRASC_TAKP_WINE_RAW_LOOK_V3";

struct Rect { int left, top, right, bottom; };
inline bool same(const Rect& a, const Rect& b) {
    return a.left == b.left && a.top == b.top && a.right == b.right && a.bottom == b.bottom;
}

// The caller serializes this state across the game-input and window threads.
class LookClip {
    bool held_ = false;
    unsigned long generation_ = 0;
    unsigned long capture_serial_ = 0, repair_count_ = 0;
    unsigned long last_repair_tick_ = 0;
    bool repair_clock_started_ = false, repair_ok_ = true;
    Rect original_ = {}, clip_ = {};
public:
    bool held() const { return held_; }
    unsigned long generation() const { return generation_; }
    unsigned long repair_count() const { return repair_count_; }
    bool repair_ok() const { return repair_ok_; }
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
        ++capture_serial_;
        return true;
    }
    // GetClipCursor is only Wine's logical rectangle. GetCursorPos may expose
    // an escaped X cursor after a refused/lost grab. Re-submit the SAME owned
    // rectangle, which queues Wine's physical-grab request even if unchanged.
    // Initial application is asynchronous: allow 250 ms before retrying and
    // throttle failed attempts too. Never fall back to a warp on retry failure.
    template<class Getter, class Setter>
    bool hold_verified_since(unsigned long generation, int x, int y, const Rect& bounds,
                             bool cursor_known, int cursor_x, int cursor_y, unsigned long now,
                             Getter get, Setter set) {
        if (generation != generation_) return false;
        const unsigned long serial = capture_serial_;
        if (!hold(x, y, bounds, get, set)) return false;
        if (!repair_clock_started_ || serial != capture_serial_) {
            last_repair_tick_ = now;
            repair_clock_started_ = true;
            return true;
        }
        if (!cursor_known || (cursor_x >= clip_.left && cursor_x < clip_.right &&
                              cursor_y >= clip_.top && cursor_y < clip_.bottom)) return true;
        // GetTickCount is a 32-bit counter even where unsigned long is wider.
        if (static_cast<unsigned int>(now - last_repair_tick_) < 250U) return true;
        last_repair_tick_ = now;
        ++repair_count_;
        repair_ok_ = set(clip_);
        return true; // retain logical ownership/original even if retry failed
    }
    template<class Getter, class Setter> bool release(Getter get, Setter set) {
        ++generation_; // stamp even an already-released clip / paused look
        if (!held_) return true;
        Rect current;
        if (!get(current)) return false; // retry rather than forget the saved rectangle
        if (same(current, clip_) && !set(original_)) return false;
        // Never overwrite a rectangle changed by another window/application.
        held_ = false;
        repair_clock_started_ = false;
        return true;
    }
};

// Retained only as the v1 comparison in the open native fixture.
template<class Setter> bool legacy_center(int x, int y, int left, int right, Setter set) {
    if (right - left > 1 && x >= left && x < right) set(x < right - 1 ? x + 1 : x - 1, y);
    return set(x, y) != 0;
}
}
