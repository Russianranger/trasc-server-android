#include "../native/takp_camera_focus_event.h"
#include "../native/takp_camera_recenter_v4.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>
using trasc_takp_focus_event::Sequence;
using trasc_takp_camera::Rect;
using trasc_takp_camera::same;
static const char token[]="0123456789abcdef0123456789abcdef";
static std::string event(const std::string& sequence,const char* key=token) {
    return std::string("TRASCFOCUS1 ")+key+" "+sequence+"\n";
}
struct Cursor {
    Rect current={0,0,1280,720};bool fail_get=false,fail_set=false;
    unsigned reads=0;std::vector<Rect> calls;
    bool get(Rect& value){++reads;if(fail_get)return false;value=current;return true;}
    bool set(const Rect& value){calls.push_back(value);if(fail_set)return false;current=value;return true;}
};
int main() {
    Sequence out=0;
    const auto first=event("1");
    assert(trasc_takp_focus_event::parse(first.data(),first.size(),token,out)&&out==1);
    auto maximum=event("18446744073709551615");
    assert(trasc_takp_focus_event::parse(maximum.data(),maximum.size(),token,out)&&out==~Sequence(0));
    const std::vector<std::string> invalid={"",first.substr(0,first.size()-1),first+"x",first+"\n",
        event("0"),event("01"),event("-1"),event("+1"),event("1 "),event("1\r"),
        event("18446744073709551616"),event("1", "ffffffffffffffffffffffffffffffff"),
        "TRASCFOCUS2 "+std::string(token)+" 1\n",std::string(97,'x'),
        "TRASCFOCUS1 "+std::string(token)+"\0 1\n"};
    for(const auto& value:invalid){out=77;assert(!trasc_takp_focus_event::parse(value.data(),value.size(),token,out)&&out==77);}
    auto embedded=first;embedded[45]='\0';assert(!trasc_takp_focus_event::parse(embedded.data(),embedded.size(),token,out));
    assert(!trasc_takp_focus_event::parse(first.data(),first.size(),nullptr,out));
    assert(!trasc_takp_focus_event::parse(first.data(),first.size(),"short",out));
    assert(!trasc_takp_focus_event::parse(first.data(),first.size(),"0123456789abcdef0123456789abcdeg",out));
    const auto uppercase=event("1","0123456789ABCDEF0123456789ABCDEF");
    assert(!trasc_takp_focus_event::parse(uppercase.data(),uppercase.size(),"0123456789ABCDEF0123456789ABCDEF",out));
    trasc_takp_focus_event::SequenceReader reader;
    assert(reader.accept(first.data(),first.size(),token,out)&&out==1);
    assert(!reader.accept(first.data(),first.size(),token,out));
    const auto next=event("4");assert(reader.accept(next.data(),next.size(),token,out)&&out==4);
    const auto stale=event("2");assert(!reader.accept(stale.data(),stale.size(),token,out)&&reader.sequence()==4);
    for(const auto& value:invalid)assert(!reader.accept(value.data(),value.size(),token,out)&&reader.sequence()==4);

    Cursor cursor;trasc_takp_camera::LookClip look;
    auto get=[&](Rect& rect){return cursor.get(rect);};auto set=[&](const Rect& rect){return cursor.set(rect);};
    const auto original=cursor.current;
    assert(!look.force_refresh_since(look.generation(),get,set)&&cursor.calls.empty()&&cursor.reads==0);
    assert(look.hold(640,360,{0,0,1280,720},get,set));const auto owned=cursor.current;
    const auto generation=look.generation();
    assert(look.force_refresh_since(generation,get,set)&&cursor.calls.size()==2&&same(cursor.calls.back(),owned));
    assert(look.focus_refresh_count()==1&&look.repair_count()==1&&look.repair_ok());
    cursor.fail_get=true;auto count=cursor.calls.size();
    assert(!look.force_refresh_since(generation,get,set)&&cursor.calls.size()==count&&look.focus_refresh_count()==1);
    cursor.fail_get=false;cursor.current={1,2,500,600};
    assert(!look.force_refresh_since(generation,get,set)&&cursor.calls.size()==count&&look.focus_refresh_count()==1);
    cursor.current=owned;cursor.fail_set=true;
    assert(!look.force_refresh_since(generation,get,set)&&look.held()&&!look.repair_ok());
    assert(look.focus_refresh_count()==2&&cursor.calls.size()==count+1&&same(cursor.calls.back(),owned));
    cursor.fail_set=false;assert(look.release(get,set)&&same(cursor.current,original));count=cursor.calls.size();
    assert(!look.force_refresh_since(generation,get,set)&&cursor.calls.size()==count);
    assert(look.hold(640,360,{0,0,1280,720},get,set));count=cursor.calls.size();
    assert(!look.force_refresh_since(generation,get,set)&&cursor.calls.size()==count);
    assert(look.release(get,set));
    // A new record consumed with Look off cannot refresh a later generation.
    const auto off_event=event("5");assert(reader.accept(off_event.data(),off_event.size(),token,out));
    assert(!look.force_refresh_since(look.generation(),get,set));
    assert(look.hold(640,360,{0,0,1280,720},get,set));count=cursor.calls.size();
    assert(!reader.accept(off_event.data(),off_event.size(),token,out)&&cursor.calls.size()==count);
    puts("PASS: bounded session event parsing, freshness, exact owned-clip refresh and lifecycle refusal");
}
