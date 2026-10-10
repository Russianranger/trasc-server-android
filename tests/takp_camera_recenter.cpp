#include "../native/takp_camera_recenter.h"
#include <cassert>
#include <cstdio>
#include <vector>
#include <utility>

// Model Wine's documented cached-position equality gate, while the real
// X server has accepted motion before the window-message thread consumes it.
struct Cursor {
    int cached_x=400,cached_y=300,server_x=400,server_y=300;
    std::vector<std::pair<int,int>> calls;
    int set(int x,int y) {
        calls.push_back({x,y});
        if(x!=cached_x || y!=cached_y){server_x=x;server_y=y;}
        cached_x=x;cached_y=y;return 1;
    }
};
int main() {
    Cursor before,after;
    const int deltas[]={20,20,20,-10,-10,-10,-10,-10,-10};
    for(unsigned i=0;i<sizeof(deltas)/sizeof(deltas[0]);i++) {
        before.server_x+=deltas[i];after.server_x+=deltas[i];
        if(i==3)assert(before.server_x-400>0); // the first reversed input still looks right
        assert(after.server_x-400==deltas[i]);
        before.set(400,300);
        trasc_takp_camera::center(400,300,0,800,true,[&](int x,int y){return after.set(x,y);});
        assert(after.server_x==400);
    }
    for(int dx : {-20,20})for(int dy : {-20,20}) {
        Cursor c;
        for(int i=0;i<20;i++) {
            c.server_x+=dx;c.server_y+=dy;
            assert(c.server_x-400==dx && c.server_y-300==dy);
            trasc_takp_camera::center(400,300,0,800,true,[&](int x,int y){return c.set(x,y);});
            assert(c.server_x==400 && c.server_y==300);
            dx=-dx;dy=-dy;
        }
    }
    std::vector<std::pair<int,int>> calls;
    auto set=[&](int x,int y){calls.push_back({x,y});return 1;};
    assert(trasc_takp_camera::center(400,300,0,800,false,set));
    assert(calls.size()==1 && calls[0]==std::make_pair(400,300)); // native Windows unchanged
    calls.clear();trasc_takp_camera::center(11,7,10,12,true,set);
    assert(calls.size()==2 && calls[0]==std::make_pair(10,7) && calls[1]==std::make_pair(11,7));
    calls.clear();trasc_takp_camera::center(10,7,10,11,true,set);assert(calls.size()==1);
    calls.clear();trasc_takp_camera::center(9,7,10,12,true,set);assert(calls.size()==1);
    int count=0;assert(!trasc_takp_camera::center(10,7,10,12,true,[&](int,int){return ++count==1?1:0;}));
    puts("PASS: TAKP Wine cached-center hysteresis reproduction, immediate reversal on both axes, native Windows passthrough, bounds and final-call failure");
}
