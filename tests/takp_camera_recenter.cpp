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

// Wine can report a successful ClipCursor and the requested cached rectangle
// while X focus has prevented the actual pointer grab. Keep those states
// independent, so success alone cannot make the recovery checks pass.
struct CaptureCursor {
    Rect current = {0,0,800,600};
    int x=443,y=253;
    bool capture_available=false,fail_set=false;
    unsigned reads=0;
    std::vector<Rect> calls;
    bool get(Rect& rect) { ++reads;rect=current;return true; }
    bool set(const Rect& rect) {
        calls.push_back(rect);
        if(fail_set)return false;
        current=rect;
        if(capture_available){x=rect.left;y=rect.top;}
        return true;
    }
};

static void verified_capture_recovery_tests() {
    const Rect bounds={0,0,800,600},center={400,300,401,301};
    {
        CaptureCursor c;trasc_takp_camera::LookClip look;
        const auto original=c.current;
        auto get=[&](Rect& r){return c.get(r);};auto set=[&](const Rect& r){return c.set(r);};
        auto hold=[&](bool known,unsigned long now){
            return look.hold_verified_since(look.generation(),400,300,bounds,known,c.x,c.y,now,get,set);
        };
        // Initial API success establishes ownership, but not physical capture.
        assert(hold(true,1000)&&look.held()&&same(c.current,center));
        assert(c.x==443&&c.y==253&&c.calls.size()==1&&look.repair_count()==0);
        assert(hold(true,1249)&&c.calls.size()==1); // acquisition starts the cooldown
        assert(hold(true,1250)&&c.calls.size()==2&&look.repair_count()==1&&look.repair_ok());
        assert(same(c.calls.back(),center)&&c.x==443&&c.y==253); // still no X focus
        assert(hold(true,1499)&&c.calls.size()==2);
        // When X capture becomes possible later, the same cached clip is retried.
        c.capture_available=true;
        assert(hold(true,1500)&&c.calls.size()==3&&look.repair_count()==2&&look.repair_ok());
        assert(c.x==400&&c.y==300&&same(c.current,center));
        for(unsigned long now=1501;now<3000;now+=16)assert(hold(true,now));
        assert(c.calls.size()==3); // healthy capture never becomes frame-by-frame traffic
        c.x=401;c.y=300;
        assert(hold(false,3000)&&c.calls.size()==3); // a failed cursor query is not escape evidence
        assert(hold(true,3000)&&c.calls.size()==4&&look.repair_count()==3);
        c.x=400;c.y=301;
        assert(hold(true,3249)&&c.calls.size()==4);
        assert(hold(true,3250)&&c.calls.size()==5&&look.repair_count()==4);
        assert(look.release(get,set)&&same(c.current,original)&&!look.held());
    }
    {
        CaptureCursor c;trasc_takp_camera::LookClip look;
        const auto original=c.current;
        auto get=[&](Rect& r){return c.get(r);};auto set=[&](const Rect& r){return c.set(r);};
        auto hold=[&](unsigned long now){
            return look.hold_verified_since(look.generation(),400,300,bounds,true,c.x,c.y,now,get,set);
        };
        assert(hold(2000));
        c.fail_set=true;
        // Return true for the still-owned logical clip even if repair fails:
        // a false return makes the caller fall back to SetCursorPos warps.
        assert(hold(2250)&&look.held()&&same(c.current,center));
        assert(c.calls.size()==2&&look.repair_count()==1&&!look.repair_ok());
        assert(hold(2499)&&c.calls.size()==2&&!look.repair_ok());
        c.fail_set=false;c.capture_available=true;
        assert(hold(2500)&&c.calls.size()==3&&look.repair_count()==2&&look.repair_ok());
        const auto generation=look.generation();
        assert(look.release(get,set)&&same(c.current,original));
        const auto calls=c.calls.size();const auto reads=c.reads;const auto repairs=look.repair_count();
        assert(!look.hold_verified_since(generation,400,300,bounds,true,443,253,3000,get,set));
        assert(!look.held()&&c.calls.size()==calls&&c.reads==reads&&look.repair_count()==repairs);
    }
    {
        CaptureCursor c;trasc_takp_camera::LookClip look;
        auto get=[&](Rect& r){return c.get(r);};auto set=[&](const Rect& r){return c.set(r);};
        auto hold=[&](unsigned long now){
            return look.hold_verified_since(look.generation(),400,300,bounds,true,c.x,c.y,now,get,set);
        };
        assert(hold(1000));
        // A different clip owner is a new acquisition, never a refresh using
        // the original rectangle from before that owner's change.
        const Rect external={10,20,700,500};c.current=external;
        assert(hold(2000)&&c.calls.size()==2&&look.repair_count()==0);
        assert(hold(2249)&&c.calls.size()==2);
        assert(hold(2250)&&c.calls.size()==3&&look.repair_count()==1);
        assert(look.release(get,set)&&same(c.current,external));
        assert(hold(3000));
        c.current={30,40,650,450};const auto changed=c.current;
        const auto calls=c.calls.size();
        assert(look.release(get,set)&&same(c.current,changed)&&c.calls.size()==calls);
    }
    {
        CaptureCursor c;trasc_takp_camera::LookClip look;
        auto get=[&](Rect& r){return c.get(r);};auto set=[&](const Rect& r){return c.set(r);};
        auto hold=[&](unsigned long now){
            return look.hold_verified_since(look.generation(),400,300,bounds,true,c.x,c.y,now,get,set);
        };
        // GetTickCount wraps at 32 bits even when this portable host's
        // unsigned long is 64 bits. Exactly 250 ms must still trigger once.
        assert(hold(0xfffffff0UL)&&c.calls.size()==1);
        assert(hold(0x000000e9UL)&&c.calls.size()==1);
        assert(hold(0x000000eaUL)&&c.calls.size()==2&&look.repair_count()==1);
        assert(hold(0x000001e3UL)&&c.calls.size()==2);
        assert(hold(0x000001e4UL)&&c.calls.size()==3&&look.repair_count()==2);
    }
}

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
    // A physical button/focus release between input query and clip acquisition
    // must reject that stale hold, even if the game look flag has not updated.
    auto generation=look.generation();count=c.calls.size();
    assert(look.release(get,set));assert(!look.hold_since(generation,720,400,bounds,get,set));
    assert(!look.held()&&c.calls.size()==count);
    assert(look.hold_since(look.generation(),720,400,bounds,get,set));
    generation=look.generation();assert(look.release(get,set));count=c.calls.size();
    assert(!look.hold_since(generation,720,400,bounds,get,set));assert(!look.held()&&c.calls.size()==count);
    verified_capture_recovery_tests();
    puts("PASS: Wine raw-look bounds, physical escape recovery, bounded retries, wrap-safe timing, prior clip restore and lifecycle ownership");
}
