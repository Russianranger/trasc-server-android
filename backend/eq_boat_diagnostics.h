// Opt-in, read-only RoF2 boat observations after the game's normal mouse read.
// No hooks, coordinate writes, collision overrides or passenger attachment changes.
#pragma once
#include "eq_camera_mouse.h"
#include <cmath>

namespace trasc_boats {
static const char marker[] = "TRASC_EQ_BOATS_V1";
using trasc_camera::read;
inline DWORD u32(const BYTE *p) { DWORD v; memcpy(&v,p,4); return v; }
inline float f32(const BYTE *p) { float v; memcpy(&v,p,4); return v; }
inline DWORD address(const void *p) { return static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(p)); }
struct Spawn {
    DWORD pointer, id, vehicle, mount, actor, race, flags, cache;
    float y,x,z,heading,dy,dx,dz,floor,cachedFloor;
    bool flagsKnown; BYTE passenger,wet;
    char name[65];
};
struct Sample { DWORD state,zone; Spawn player,target,vehicle; bool targetValid,vehicleValid; };
inline bool supported(const BYTE *image) {
    DWORD getter=0,predicate=0;
    // Verified against the exact executable. Launcher additionally hashes the full file.
    return trasc_camera::supported(image)
        && read(image+0x4cfce0,getter) && getter==0x0150818b
        && read(image+0x5d7240,predicate) && predicate==address(image+0x19e530);
}
inline bool spawn(const BYTE *image,DWORD pointer,Spawn &s) {
    BYTE data[0x1084]={};
    s=Spawn{};
    if(!pointer || !read(reinterpret_cast<const BYTE *>(pointer),data)
       || u32(data)!=address(image+0x5d71f0)) return false;
    s.pointer=pointer;s.id=u32(data+0x148);s.vehicle=u32(data+0x150);s.mount=u32(data+0x154);
    s.actor=u32(data+0x101c);s.race=u32(data+0xeb4);s.cache=u32(data+0x1060);
    s.y=f32(data+0x64);s.x=f32(data+0x68);s.z=f32(data+0x6c);s.heading=f32(data+0x80);
    s.dy=f32(data+0x70);s.dx=f32(data+0x74);s.dz=f32(data+0x78);
    s.floor=f32(data+0x28);s.cachedFloor=f32(data+0x1070);s.passenger=data[0x18c];s.wet=data[0xa1];
    memcpy(s.name,data+0xa4,64);s.name[64]=0;
    for(unsigned i=0;i<64&&s.name[i];++i)if(static_cast<unsigned char>(s.name[i])<32)s.name[i]='?';
    DWORD info=u32(data+0x234);
    s.flagsKnown=info && read(reinterpret_cast<const BYTE *>(info)+0x2c,s.flags);
    return std::isfinite(s.x)&&std::isfinite(s.y)&&std::isfinite(s.z)&&std::isfinite(s.heading);
}
inline bool boat(const Spawn &s) {
    if(s.flagsKnown&&(s.flags&1)) return true;
    // Include known ships even if the runtime race flags are unexpectedly absent.
    switch(s.race) {
        case 72:case 73:case 114:case 141:case 404:case 502:case 533:
        case 544:case 545:case 546:case 550:case 551:case 552:case 691:case 692:case 693:case 699:return true;
        default:return false;
    }
}
inline bool inspect(const BYTE *image,Sample &s) {
    s=Sample{};DWORD game=0,player=0,target=0,again=0;
    if(!read(image+0xa67ccc,game)||!game
       ||!read(reinterpret_cast<const BYTE *>(game)+0x5c8,s.state)||s.state!=5
       ||!read(image+0x9d2630,player)||!spawn(image,player,s.player))return false;
    read(image+0x9e0858,s.zone);
    if(read(image+0x9d2648,target)&&target!=player)
        s.targetValid=spawn(image,target,s.target)&&boat(s.target);
    if(s.player.vehicle&&s.player.vehicle!=player)
        s.vehicleValid=spawn(image,s.player.vehicle,s.vehicle)&&boat(s.vehicle);
    // Discard a snapshot if zoning replaced the local player during observation.
    return read(image+0x9d2630,again)&&again==player;
}
inline void report(const Sample &s,bool valid,DWORD now) {
    char line[1200];
    snprintf(line,sizeof(line),
        "ticks=%lu boats=v1 valid=%u zone=%lu state=%lu player=%lu pos_yxz=%.3f,%.3f,%.3f heading=%.3f speed_yxz=%.4f,%.4f,%.4f floor=%.3f cached_floor=%.3f cache=%lu wet=%u passenger=%u mount=%08lx vehicle_ptr=%08lx vehicle_valid=%u vehicle_id=%lu vehicle_yxz=%.3f,%.3f,%.3f vehicle_heading=%.3f vehicle_flags=%lu target_valid=%u target_id=%lu target_name=%s target_race=%lu target_flags_known=%u target_flags=%lu target_actor=%08lx target_yxz=%.3f,%.3f,%.3f target_heading=%.3f\r\n",
        now,valid,s.zone,s.state,s.player.id,s.player.y,s.player.x,s.player.z,s.player.heading,
        s.player.dy,s.player.dx,s.player.dz,s.player.floor,s.player.cachedFloor,s.player.cache,
        s.player.wet,s.player.passenger,s.player.mount,s.player.vehicle,s.vehicleValid,s.vehicle.id,
        s.vehicle.y,s.vehicle.x,s.vehicle.z,s.vehicle.heading,s.vehicle.flags,s.targetValid,s.target.id,
        s.targetValid?s.target.name:"-",s.target.race,s.target.flagsKnown,s.target.flags,s.target.actor,
        s.target.y,s.target.x,s.target.z,s.target.heading);
    trasc_camera::logLine("Z:\\logs\\client-boats.log",line);
}
inline void afterRead(HRESULT result,DWORD size,void *data) {
    if(FAILED(result)||size!=sizeof(DIMOUSESTATE2))return;
    const BYTE *image=reinterpret_cast<const BYTE *>(GetModuleHandleW(NULL));
    if(data!=image+0xa67884)return;
    static const bool enabled=[](){char v[12]={};const BYTE *image=reinterpret_cast<const BYTE *>(GetModuleHandleW(NULL));
        return GetEnvironmentVariableA(marker,v,sizeof(v))==7&&!strcmp(v,"profile")
            &&GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"wine_get_version")&&supported(image);}();
    if(!enabled)return;
    static volatile LONG busy=0;static DWORD last=0;static unsigned reports=0;
    if(InterlockedCompareExchange(&busy,1,0))return;
    DWORD now=GetTickCount();
    if(reports<512&&(!reports||now-last>=500)){
        Sample s={};bool valid=inspect(image,s);
        // Sample a selected/attached boat twice a second; otherwise a heartbeat.
        if(!reports||s.targetValid||s.vehicleValid||now-last>=5000){last=now;++reports;report(s,valid,now);}
    }
    InterlockedExchange(&busy,0);
}
}
extern "C" void trasc_boat_after_read(HRESULT result,DWORD size,void *data) {
    DWORD error=GetLastError();trasc_boats::afterRead(result,size,data);SetLastError(error);
}
