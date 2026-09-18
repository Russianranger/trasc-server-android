// Optional exact-client first-person particle permission repair.
// Calls the original actor setter after the original camera update; no view switch.
#pragma once
#include "eq_camera_mouse.h"
#include <wchar.h>

namespace trasc_particles {
static const char marker[] = "TRASC_EQ_PARTICLES_V1";
enum Mode { OFF, PROFILE, REPAIR };
typedef void (__thiscall *Update)(void *, void *);
typedef void (__thiscall *SetPermission)(void *, bool);
typedef bool (__thiscall *GetPermission)(void *);
static Update originalUpdate = NULL;
static BYTE *gameImage = NULL;
static HMODULE graphicsModule = NULL;
static Mode mode = OFF;
static volatile LONG installed = 0, updateThread = 0, inspecting = 0;
static DWORD attemptedPlayer = 0, attemptedActor = 0;
static bool attempted = false;
static unsigned attempts = 0, reports = 0;
static const DWORD updateSlot = 0x5d0f88, updateRva = 0x397160;
static const BYTE updatePrefix[] = {0x56,0x57,0x8b,0x7c,0x24,0x0c,0x83,0xbf,0x1c,0x10,0,0,0};
static const BYTE setterCode[] = {0x8a,0x44,0x24,0x04,0x88,0x41,0x5c,0xc2,0x04,0};
static const BYTE getterCode[] = {0x8a,0x41,0x5c,0xc3};
enum Status { OUTSIDE_WORLD, OTHER_VIEW, NO_ACTOR, BAD_GRAPHICS, BAD_ACTOR,
    ATTACHED_ACTOR, VISIBLE, PERMITTED, MISSING, REPAIRED, REPAIR_FAILED, ATTEMPT_LIMIT };
static const char *statusNames[] = {"outside_world","other_view","no_actor","unsupported_graphics",
    "unsupported_actor","attached_actor","visible","permitted","missing_permission",
    "repaired","repair_failed","attempt_limit"};
struct Sample { DWORD player, actor, table, parent; BYTE hidden, before, after; Status status; };
static Sample lastSample = {};
static bool haveSample = false;
using trasc_camera::read;

template<size_t N> bool matches(const BYTE *address, const BYTE (&expected)[N]) {
    BYTE actual[N] = {};
    return read(address, actual) && !memcmp(actual, expected, N);
}
inline DWORD field(const BYTE *data, unsigned offset) { DWORD v; memcpy(&v,data+offset,4); return v; }
inline DWORD pointer(const void *p) { return static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(p)); }
inline bool graphicsSupported(const BYTE *image) {
    IMAGE_DOS_HEADER dos = {}; IMAGE_NT_HEADERS32 nt = {};
    if(!image || !read(image,dos) || dos.e_magic!=IMAGE_DOS_SIGNATURE || dos.e_lfanew<64
       || dos.e_lfanew>1048576 || !read(image+dos.e_lfanew,nt)) return false;
    if(nt.Signature!=IMAGE_NT_SIGNATURE || nt.FileHeader.Machine!=IMAGE_FILE_MACHINE_I386
       || nt.FileHeader.TimeDateStamp!=0x518de5b6 || nt.OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC
       || nt.OptionalHeader.SizeOfImage!=0x1e6000) return false;
    DWORD mask=0;
    return read(image+0x174ba4,mask) && mask==1
        && matches(image+0x3b1a0,setterCode) && matches(image+0x3b190,getterCode);
}
inline bool sameClientDirectory(HMODULE module) {
    wchar_t exe[1024] = {}, dll[1024] = {};
    DWORD a=GetModuleFileNameW(NULL,exe,1024), b=GetModuleFileNameW(module,dll,1024);
    if(!a || !b || a>=1024 || b>=1024) return false;
    wchar_t *ea=wcsrchr(exe,L'\\'), *da=wcsrchr(dll,L'\\');
    if(!ea || !da) return false;
    *ea=0; *da=0;
    return _wcsicmp(exe,dll)==0;
}
inline void report(const Sample &s) {
    if(haveSample && s.player==lastSample.player && s.actor==lastSample.actor
       && s.table==lastSample.table && s.parent==lastSample.parent && s.hidden==lastSample.hidden
       && s.before==lastSample.before && s.after==lastSample.after && s.status==lastSample.status) return;
    lastSample=s; haveSample=true;
    if(reports>=512) return;
    ++reports;
    char line[384];
    snprintf(line,sizeof(line),"ticks=%lu particles=v1 mode=%s thread=%lu status=%s player=%08lx actor=%08lx vtable=%08lx parent=%08lx hidden=%u before=%u after=%u attempts=%u\r\n",
        GetTickCount(),mode==REPAIR?"repair":"profile",GetCurrentThreadId(),statusNames[s.status],
        s.player,s.actor,s.table,s.parent,s.hidden,s.before,s.after,attempts);
    trasc_camera::logLine("Z:\\logs\\client-particles.log",line);
}
inline Sample inspect(BYTE *image, BYTE *graphics, void *camera, void *updatedPlayer, bool entering) {
    Sample s = {}; s.status=OUTSIDE_WORLD;
    DWORD game=0,state=0,view=~0u,firstCamera=0;
    if(!read(image+0xa67ccc,game) || !game
       || !read(reinterpret_cast<BYTE *>(game)+0x5c8,state) || state!=5) {
        attempted=false; attemptedActor=attemptedPlayer=0; return s;
    }
    s.status=OTHER_VIEW;
    if(!read(image+0x91fd9c,view) || view!=0 || !read(image+0x9e0d64,firstCamera)
       || firstCamera!=pointer(camera) || !read(image+0x9d2630,s.player) || !s.player
       || s.player!=pointer(updatedPlayer)) {
        attempted=false; attemptedActor=attemptedPlayer=0; return s;
    }
    s.status=NO_ACTOR;
    if(!read(reinterpret_cast<BYTE *>(s.player)+0x101c,s.actor) || !s.actor) {
        attempted=false; attemptedActor=attemptedPlayer=0; return s;
    }
    if(entering || attemptedPlayer!=s.player || attemptedActor!=s.actor) {
        attempted=false; attemptedPlayer=s.player; attemptedActor=s.actor;
    }
    s.status=BAD_GRAPHICS;
    if(!graphicsSupported(graphics)) return s;
    BYTE actor[0x140] = {};
    s.status=BAD_ACTOR;
    if(!read(reinterpret_cast<BYTE *>(s.actor),actor)) return s;
    s.table=field(actor,0); s.parent=field(actor,0x24);
    // Only the verified hierarchical layouts use visibility flags at +0x13c.
    if(s.table!=pointer(graphics+0x137074) && s.table!=pointer(graphics+0x1373b4)) return s;
    DWORD setter=0,getter=0,invisible=0;
    if(!read(reinterpret_cast<BYTE *>(s.table)+0x23c,setter)
       || !read(reinterpret_cast<BYTE *>(s.table)+0x240,getter)
       || !read(reinterpret_cast<BYTE *>(s.table)+0x38,invisible)
       || setter!=pointer(graphics+0x3b1a0) || getter!=pointer(graphics+0x3b190)
       || invisible!=pointer(graphics+0x46f20) || actor[0x5c]>1) return s;
    s.hidden=(field(actor,0x13c)&1)!=0; s.before=s.after=actor[0x5c];
    // The particle renderer resolves the root owner. Never change an attachment.
    if(s.parent) { s.status=ATTACHED_ACTOR; return s; }
    if(!s.hidden) { s.status=VISIBLE; return s; }
    if(s.before) { s.status=PERMITTED; return s; }
    s.status=MISSING;
    if(mode!=REPAIR) return s;
    // At most one attempt per observed player/actor or camera-entry episode.
    // A failing setter or another mod resetting it cannot cause a busy retry loop.
    if(attempted || attempts>=128) { s.status=ATTEMPT_LIMIT; return s; }
    DWORD current=0,local=0;
    if(!read(reinterpret_cast<BYTE *>(s.player)+0x101c,current) || current!=s.actor
       || !read(image+0x9d2630,local) || local!=s.player
       || !read(image+0x91fd9c,view) || view!=0) { s.status=OTHER_VIEW; return s; }
    MEMORY_BASIC_INFORMATION memory = {};
    if(!VirtualQuery(reinterpret_cast<BYTE *>(s.actor)+0x5c,&memory,sizeof(memory))
       || memory.State!=MEM_COMMIT || (memory.Protect&(PAGE_GUARD|PAGE_NOACCESS))
       || !(memory.Protect&(PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY))) {
        s.status=BAD_ACTOR; return s;
    }
    attempted=true; ++attempts;
    reinterpret_cast<SetPermission>(setter)(reinterpret_cast<void *>(s.actor),true);
    s.after=reinterpret_cast<GetPermission>(getter)(reinterpret_cast<void *>(s.actor))?1:0;
    s.status=s.after?REPAIRED:REPAIR_FAILED;
    return s;
}
static void __fastcall update(void *camera,void *,void *player) {
    BYTE entering=0;
    DWORD entryError=GetLastError(); read(static_cast<BYTE *>(camera)+0x4c,entering); SetLastError(entryError);
    originalUpdate(camera,player); // Same object/argument, on the game's own update thread.
    DWORD error=GetLastError();
    LONG thread=static_cast<LONG>(GetCurrentThreadId());
    LONG owner=InterlockedCompareExchange(&updateThread,thread,0);
    if((!owner || owner==thread) && !InterlockedCompareExchange(&inspecting,1,0)) {
        if(!graphicsModule) {
            HMODULE candidate=GetModuleHandleW(L"EQGraphicsDX9.dll");
            if(candidate && sameClientDirectory(candidate)) {
                // Keep this verified module alive as long as the callback exists.
                GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_PIN,L"EQGraphicsDX9.dll",&graphicsModule);
            }
        }
        report(inspect(gameImage,reinterpret_cast<BYTE *>(graphicsModule),camera,player,entering!=0));
        InterlockedExchange(&inspecting,0);
    }
    SetLastError(error);
}
inline bool patch(BYTE *image,Mode requested) {
    if(requested==OFF || !trasc_camera::supported(image) || !matches(image+updateRva,updatePrefix)) return false;
    DWORD target=0;
    if(!read(image+updateSlot,target) || target!=pointer(image+updateRva)) return false;
    DWORD protection=0;
    if(!VirtualProtect(image+updateSlot,sizeof(void *),PAGE_READWRITE,&protection)) return false;
    gameImage=image; originalUpdate=reinterpret_cast<Update>(target); mode=requested;
    void *old=InterlockedCompareExchangePointer(reinterpret_cast<PVOID volatile *>(image+updateSlot),
        reinterpret_cast<PVOID>(update),reinterpret_cast<PVOID>(target));
    DWORD ignored=0;
    bool restored=VirtualProtect(image+updateSlot,sizeof(void *),protection,&ignored)!=FALSE;
    if(!restored) {
        InterlockedCompareExchangePointer(reinterpret_cast<PVOID volatile *>(image+updateSlot),
            reinterpret_cast<PVOID>(target),reinterpret_cast<PVOID>(update));
        VirtualProtect(image+updateSlot,sizeof(void *),protection,&ignored);
    }
    return old==reinterpret_cast<PVOID>(target) && restored;
}
inline void install() {
    if(InterlockedCompareExchange(&installed,1,0)) return;
    DWORD error=GetLastError(); char value[16] = {};
    if(GetEnvironmentVariableA(marker,value,sizeof(value))>=sizeof(value)) value[0]=0;
    Mode requested=!strcmp(value,"repair")?REPAIR:!strcmp(value,"profile")?PROFILE:OFF;
    if(requested!=OFF) {
        bool wine=GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"wine_get_version")!=NULL;
        bool ok=wine && patch(reinterpret_cast<BYTE *>(GetModuleHandleW(NULL)),requested);
        char line[128]; snprintf(line,sizeof(line),"particles=v1 install=%s mode=%s\r\n",ok?"ready":"rejected",value);
        trasc_camera::logLine("Z:\\logs\\client-particles.log",line);
    }
    SetLastError(error);
}
}
