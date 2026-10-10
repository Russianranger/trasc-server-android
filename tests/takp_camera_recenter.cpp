#include "../native/takp_camera_recenter.h"
#include <cassert>
#include <cstdio>
#include <vector>
using trasc_takp_camera::Rect;
using trasc_takp_camera::same;
struct Cursor {
    Rect current = {0,0,1920,1080};
    bool fail_get=false,fail_set=false;
    std::vector<Rect> calls;
    bool get(Rect& rect) { if(fail_get)return false;rect=current;return true; }
    bool set(const Rect& rect) { calls.push_back(rect);if(fail_set)return false;current=rect;return true; }
};
int main() {
    Cursor c;trasc_takp_camera::LookClip look;
    const Rect bounds={80,40,1360,760},saved=c.current;
    auto get=[&](Rect& r){return c.get(r);};auto set=[&](const Rect& r){return c.set(r);};
    assert(look.hold(720,400,bounds,get,set));
    assert(same(c.current,{720,400,721,401}) && look.held());
    for(int i=0;i<200;i++)assert(look.hold(720,400,bounds,get,set));
    assert(c.calls.size()==1); // idle frames must never produce nudge/warp traffic
    assert(look.hold(700,390,bounds,get,set) && c.calls.size()==2);
    assert(look.release(get,set) && same(c.current,saved) && !look.held());
    assert(look.release(get,set) && c.calls.size()==3); // idempotent lifecycle release
    c.current={10,20,1000,700};const Rect restricted=c.current;
    assert(look.hold(720,400,bounds,get,set));assert(look.release(get,set));assert(same(c.current,restricted));
    assert(!look.hold(79,400,bounds,get,set));assert(!look.hold(720,760,bounds,get,set));
    assert(!look.hold(1,1,{1,1,2,2},get,set));
    c.fail_get=true;assert(!look.hold(720,400,bounds,get,set)&&!look.held());c.fail_get=false;
    c.fail_set=true;assert(!look.hold(720,400,bounds,get,set)&&!look.held());c.fail_set=false;
    assert(look.hold(720,400,bounds,get,set));c.fail_get=true;assert(!look.release(get,set)&&look.held());c.fail_get=false;
    c.fail_set=true;assert(!look.release(get,set)&&look.held());c.fail_set=false;
    assert(look.release(get,set)&&same(c.current,restricted));
    assert(look.hold(720,400,bounds,get,set));c.current={20,30,900,600};const auto external=c.current;
    auto count=c.calls.size();assert(look.release(get,set)&&same(c.current,external)&&c.calls.size()==count);
    // A lost clip can be reacquired, retaining the new owner's rectangle for restore.
    assert(look.hold(720,400,bounds,get,set));c.current={25,35,850,650};const auto changed=c.current;
    assert(look.hold(720,400,bounds,get,set));assert(look.release(get,set)&&same(c.current,changed));
    puts("PASS: Wine raw-look clip bounds, no repeated cursor warp, prior rectangle restore, focus/release retries and external clip ownership");
}
