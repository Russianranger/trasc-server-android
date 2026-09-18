// Exact-client loading measurements and optional model-load scheduler yields.
// No assets/validation are skipped. All original loading functions still run.
#pragma once
#include "eq_client_loading.h"

namespace trasc_display {
static const char marker[] = "TRASC_EQ_DISPLAY_V1";
typedef void (__thiscall *UiLoad)(void *, void *, void *, void *, void *);
typedef bool (__thiscall *ReadXml)(void *, void *, void *, void *, void *);
typedef bool (__cdecl *ParseFile)(void *, void *);
typedef bool (__thiscall *Composite)(void *, void *, void *, void *);
typedef bool (__thiscall *Pass)(void *);
typedef bool (__thiscall *DataLoad)(void *, void *);
typedef void (__thiscall *GlobalLoad)(void *);
typedef void (__cdecl *ModelLoad)(void *);
typedef void (WINAPI *SleepFunction)(DWORD);
static UiLoad originalUi;
static ReadXml originalRead;
static ParseFile originalParse;
static Composite originalComposite;
static DataLoad originalData;
static GlobalLoad originalGlobal;
static ModelLoad originalModel;
static Pass originalPass[5];
static SleepFunction originalSleep;
static bool reducePauses = false;
static volatile LONG ownerThread = 0;
static bool models = false;
static unsigned sequence = 0;
enum { XML_READ, XML_MAIN_FILE, XML_COMPOSITE, XML_PASS_4504D0, XML_PASS_44E6D0,
    XML_PASS_4479B0, XML_PASS_450AB0, UI_DATA, UI_RESOLVE, MODEL_LOAD, MODEL_WAIT, STAGE_COUNT };
static const char *names[] = {"xml_read", "xml_main_file", "xml_composite", "xml_pass_4504d0",
    "xml_pass_44e6d0", "xml_pass_4479b0", "xml_pass_450ab0", "ui_data", "ui_resolve", "model_load", "model_wait"};
struct Stat { LONGLONG ticks; unsigned calls, failures; };
static Stat stats[STAGE_COUNT] = {};
static LONGLONG frequency = 0;
static unsigned requestedWaitMs = 0, yieldedWaits = 0;
inline bool active() { return static_cast<DWORD>(InterlockedCompareExchange(&ownerThread,0,0)) == GetCurrentThreadId(); }
inline LONGLONG clockTicks() { LARGE_INTEGER value; QueryPerformanceCounter(&value); return value.QuadPart; }
inline unsigned long long micros(LONGLONG ticks) { return frequency > 0 ? static_cast<unsigned long long>(ticks)*1000000/frequency : 0; }
struct Measure {
    int index; LONGLONG start; bool enabled;
    explicit Measure(int i) : index(i), start(0), enabled(active()) { if(enabled) start=clockTicks(); }
    void finish(bool success=true) {
        if(!enabled) return;
        stats[index].ticks += clockTicks()-start;
        ++stats[index].calls; if(!success) ++stats[index].failures;
        enabled=false;
    }
    ~Measure() { finish(); }
};
struct Scope {
    bool owns; LONGLONG start;
    explicit Scope(bool modelScope) : owns(!InterlockedCompareExchange(&ownerThread,static_cast<LONG>(GetCurrentThreadId()),0)), start(0) {
        if(!owns) return;
        models=modelScope; ++sequence; memset(stats,0,sizeof(stats)); requestedWaitMs=yieldedWaits=0;
        start=clockTicks();
    }
    ~Scope() {
        if(!owns) return;
        LONGLONG elapsed=clockTicks()-start; DWORD lastError=GetLastError();
        char line[320];
        snprintf(line,sizeof(line),"ticks=%lu display_scope=%s sequence=%u elapsed_us=%llu reduce_pauses=%d requested_wait_ms=%u yielded_waits=%u\r\n",
            GetTickCount(),models?"global_models":"ui",sequence,micros(elapsed),reducePauses,requestedWaitMs,yieldedWaits);
        trasc_camera::logLine("Z:\\logs\\client-loading.log",line);
        for(int i=0;i<STAGE_COUNT;++i) if(stats[i].calls) {
            snprintf(line,sizeof(line),"display_stage=%s sequence=%u inclusive_us=%llu calls=%u failures=%u\r\n",
                names[i],sequence,micros(stats[i].ticks),stats[i].calls,stats[i].failures);
            trasc_camera::logLine("Z:\\logs\\client-loading.log",line);
        }
        models=false; InterlockedExchange(&ownerThread,0); SetLastError(lastError);
    }
};
static void __fastcall uiLoad(void *self,void *,void *a,void *b,void *c,void *d) {
    Scope scope(false); originalUi(self,a,b,c,d);
}
static bool __fastcall readXml(void *self,void *,void *a,void *b,void *c,void *d) {
    Measure m(XML_READ); bool result=originalRead(self,a,b,c,d); m.finish(result); return result;
}
static bool __cdecl parseFile(void *a,void *b) {
    Measure m(XML_MAIN_FILE); bool result=originalParse(a,b); m.finish(result); return result;
}
static bool __fastcall composite(void *self,void *,void *a,void *b,void *c) {
    Measure m(XML_COMPOSITE); bool result=originalComposite(self,a,b,c); m.finish(result); return result;
}
template<int Index,int Stage> static bool __fastcall pass(void *self,void *) {
    Measure m(Stage); bool result=originalPass[Index](self); m.finish(result); return result;
}
static bool __fastcall dataLoad(void *self,void *,void *document) {
    Measure m(UI_DATA); bool result=originalData(self,document); m.finish(result); return result;
}
static void __fastcall globalLoad(void *self,void *) { Scope scope(true); originalGlobal(self); }
static void __cdecl modelLoad(void *request) { Measure m(MODEL_LOAD); originalModel(request); }
static void WINAPI waitModel(DWORD milliseconds) {
    if(!active() || !models) { originalSleep(milliseconds); return; }
    Measure m(MODEL_WAIT); requestedWaitMs+=milliseconds;
    bool yield=reducePauses && milliseconds==1;
    if(yield) ++yieldedWaits;
    originalSleep(yield?0:milliseconds); // Still yields; never changes a polling/timeout loop.
}
// Only the six call operands and three register loads in the verified global
// model loader point here. The game's import table and other Sleep calls stay intact.
static SleepFunction routedSleep = waitModel;
using trasc_loading::StageCall;
static const StageCall calls[] = {
    {0x96228,0x470c60,reinterpret_cast<const void *>(uiLoad)},
    {0x96471,0x470c60,reinterpret_cast<const void *>(uiLoad)},
    {0x470cc0,0x451540,reinterpret_cast<const void *>(readXml)},
    {0x45175c,0x49e120,reinterpret_cast<const void *>(parseFile)},
    {0x4517a2,0x450f60,reinterpret_cast<const void *>(composite)},
    {0x4517ad,0x4504d0,reinterpret_cast<const void *>(pass<0,XML_PASS_4504D0>)},
    {0x4517b8,0x44e6d0,reinterpret_cast<const void *>(pass<1,XML_PASS_44E6D0>)},
    {0x4517c3,0x4479b0,reinterpret_cast<const void *>(pass<2,XML_PASS_4479B0>)},
    {0x4517ce,0x450ab0,reinterpret_cast<const void *>(pass<3,XML_PASS_450AB0>)},
    {0x470d22,0x493d40,reinterpret_cast<const void *>(dataLoad)},
    {0x470d38,0x493440,reinterpret_cast<const void *>(pass<4,UI_RESOLVE>)},
    {0x11c513,0x91c20,reinterpret_cast<const void *>(globalLoad)},
    {0x920d0,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x922a0,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x9251a,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x925aa,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x926ee,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92837,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x928cd,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x9298e,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92a85,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92b1b,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92bce,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92c4a,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92e0a,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92e9a,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x92fa0,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x931cc,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x932c0,0x89500,reinterpret_cast<const void *>(modelLoad)},
    {0x9361e,0x89500,reinterpret_cast<const void *>(modelLoad)}
};
struct SleepOperand { DWORD rva; BYTE first,second; };
static const SleepOperand sleepOperands[] = {
    {0x920da,0xff,0x15},{0x922aa,0xff,0x15},{0x9242e,0x8b,0x2d},
    {0x9283c,0x8b,0x3d},{0x92a8a,0x8b,0x3d},{0x92faa,0xff,0x15},
    {0x931d6,0xff,0x15},{0x932ca,0xff,0x15},{0x93628,0xff,0x15}
};
struct SleepSite { DWORD rva; BYTE target; };
static const SleepSite sleepSites[] = {
    {0x920d8,0x15},{0x922a8,0x15},{0x92522,0xd5},{0x925b2,0xd5},{0x926f6,0xd5},
    {0x92845,0xd7},{0x928d5,0xd7},{0x92996,0xd7},{0x92a93,0xd7},{0x92b23,0xd7},
    {0x92bd6,0xd7},{0x92c52,0xd7},{0x92e12,0xd5},{0x92ea2,0xd5},
    {0x92fa8,0x15},{0x931d4,0x15},{0x932c8,0x15},{0x93626,0x15}
};
inline bool validate(const BYTE *image) {
    for(const StageCall &site:calls) if(!trasc_loading::callMatches(image,site.rva,site.target)) return false;
    for(const SleepOperand &site:sleepOperands) {
        WORD opcode=0; DWORD address=0;
        if(!trasc_camera::read(image+site.rva,opcode) || opcode!=(site.first | (site.second<<8))
            || !trasc_camera::read(image+site.rva+2,address)
            || address!=reinterpret_cast<ULONG_PTR>(image+0x5c01b4)) return false;
    }
    for(const SleepSite &site:sleepSites) {
        DWORD instruction=0;
        if(!trasc_camera::read(image+site.rva,instruction) || instruction!=(0x00ff016au | (static_cast<DWORD>(site.target)<<24))) return false;
    }
    return true;
}
inline bool patch(BYTE *image,bool fast) {
    LARGE_INTEGER freq;
    if(!validate(image) || !QueryPerformanceFrequency(&freq) || freq.QuadPart<=0) return false;
    SleepFunction sleeper=NULL;
    if(!trasc_camera::read(image+0x5c01b4,sleeper) || sleeper!=reinterpret_cast<SleepFunction>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"Sleep"))) return false;
    BYTE *start=image+0x920d0; SIZE_T size=0x470d38+5-0x920d0;
    DWORD protection=0,ignored=0;
    if(!VirtualProtect(start,size,PAGE_EXECUTE_READWRITE,&protection)) return false;
    frequency=freq.QuadPart; originalSleep=sleeper; reducePauses=fast;
    originalUi=reinterpret_cast<UiLoad>(image+0x470c60);
    originalRead=reinterpret_cast<ReadXml>(image+0x451540);
    originalParse=reinterpret_cast<ParseFile>(image+0x49e120);
    originalComposite=reinterpret_cast<Composite>(image+0x450f60);
    const DWORD passRvas[]={0x4504d0,0x44e6d0,0x4479b0,0x450ab0,0x493440};
    for(unsigned i=0;i<5;++i) originalPass[i]=reinterpret_cast<Pass>(image+passRvas[i]);
    originalData=reinterpret_cast<DataLoad>(image+0x493d40);
    originalGlobal=reinterpret_cast<GlobalLoad>(image+0x91c20);
    originalModel=reinterpret_cast<ModelLoad>(image+0x89500);
    for(const StageCall &site:calls) trasc_loading::writeCall(image,site.rva,site.replacement);
    DWORD address=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(&routedSleep));
    for(const SleepOperand &site:sleepOperands) memcpy(image+site.rva+2,&address,sizeof(address));
    FlushInstructionCache(GetCurrentProcess(),start,size);
    VirtualProtect(start,size,protection,&ignored);
    return true;
}
inline void install() {
    static bool attempted=false; if(attempted) return; attempted=true;
    char mode[16]={}; GetEnvironmentVariableA(marker,mode,sizeof(mode));
    bool fast=!strcmp(mode,"yield"); if(!fast && strcmp(mode,"profile")) return;
    BYTE *image=reinterpret_cast<BYTE *>(GetModuleHandleW(NULL));
    if(!GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"wine_get_version") || !trasc_camera::supported(image)) return;
    bool installed=patch(image,fast);
    trasc_camera::logLine("Z:\\logs\\client-loading.log",!installed
        ? "display_adapter=v1 status=layout_or_protection_mismatch\r\n" : fast
        ? "display_adapter=v1 mode=yield status=installed\r\n" : "display_adapter=v1 mode=profile status=installed\r\n");
}
}
