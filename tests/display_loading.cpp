#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_display_loading.h"
#include <assert.h>
#include <initializer_list>
using namespace trasc_display;
static BYTE *image;
static int objects[5];
static unsigned seenWait, modelCalls;
static bool failure;
static BYTE *entry(unsigned i) { return image+0x1000000+i*64; }
// Execute the actual relocated CALL through an isolated x86 ABI harness.
static void stub(unsigned i,unsigned args,bool callerCleansStack) {
    BYTE *p=entry(i);
    for(unsigned j=0;j<args;++j) { BYTE push[]={0xff,0x74,0x24,static_cast<BYTE>(args*4)}; memcpy(p,push,4);p+=4; }
    DWORD target=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(image+calls[i].rva+5))+*reinterpret_cast<DWORD *>(image+calls[i].rva+1);
    *p=0xe8;DWORD displacement=target-static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(p+5));memcpy(p+1,&displacement,4);p+=5;
    if(callerCleansStack && args) { *p++=0x83;*p++=0xc4;*p++=static_cast<BYTE>(args*4); }
    if(!callerCleansStack && args) { *p++=0xc2;*p++=static_cast<BYTE>(args*4);*p=0; } else *p=0xc3;
}
template<class F> F caller(unsigned i) { return reinterpret_cast<F>(entry(i)); }
static void jump(DWORD rva,const void *target) { image[rva]=0xe9;trasc_loading::writeCall(image,rva,target); }
static bool __cdecl parseFixture(void *a,void *b) { assert(a==objects+1 && b==objects+2);return !failure; }
static bool __fastcall compositeFixture(void *self,void *,void *a,void *b,void *c) {
    assert(self==objects && a==objects+1 && b==objects+2 && c==objects+3);return !failure;
}
static bool __fastcall passFixture(void *self,void *) { assert(self==objects);return !failure; }
static bool __fastcall dataFixture(void *self,void *,void *a) { assert(self==objects && a==objects+1);return !failure; }
static bool __fastcall readFixture(void *self,void *,void *a,void *b,void *c,void *d) {
    assert(self==objects && a==objects+1 && b==objects+2 && c==objects+3 && d==objects+4);
    assert(caller<ParseFile>(3)(a,b)==!failure);
    assert(caller<Composite>(4)(self,a,b,c)==!failure);
    for(unsigned i=5;i<9;++i) assert(caller<Pass>(i)(self)==!failure);
    return !failure;
}
static void __fastcall uiFixture(void *self,void *,void *a,void *b,void *c,void *d) {
    assert(active() && !models);
    assert(caller<ReadXml>(2)(self,a,b,c,d)==!failure);
    assert(caller<DataLoad>(9)(self,a)==!failure);
    assert(caller<Pass>(10)(self)==!failure);
}
static void __cdecl modelFixture(void *p) { assert(p==objects+1); ++modelCalls; }
static void WINAPI sleepFixture(DWORD ms) { seenWait=ms; }
static void executeSleepInstruction(const SleepOperand &site) {
    BYTE *p=image+0x1100000, *begin=p;
    bool reg=site.first==0x8b;
    BYTE r=site.second==0x2d?5:7;
    if(reg) *p++=static_cast<BYTE>(0x50+r); // Preserve EBP/EDI.
    if(!reg) { *p++=0x6a;*p++=1; }
    memcpy(p,image+site.rva,6);p+=6; // Execute the patched FF15 or MOV instruction.
    if(reg) { *p++=0x6a;*p++=1;*p++=0xff;*p++=static_cast<BYTE>(0xd0+r);*p++=static_cast<BYTE>(0x58+r); }
    *p++=0xc3;FlushInstructionCache(GetCurrentProcess(),begin,p-begin);
    reinterpret_cast<void (__cdecl *)()>(begin)();
}
static void __fastcall globalFixture(void *self,void *) {
    assert(self==objects && active() && models);
    for(unsigned i=12;i<sizeof(calls)/sizeof(calls[0]);++i) caller<ModelLoad>(i)(objects+1);
    for(const SleepOperand &site:sleepOperands) {
        auto slot=reinterpret_cast<SleepFunction *>(*reinterpret_cast<DWORD *>(image+site.rva+2));
        executeSleepInstruction(site); assert(seenWait==(reducePauses?0u:1u));
        (*slot)(7); assert(seenWait==7); // Never reduce other waits.
    }
}
static void prepare() {
    image=static_cast<BYTE *>(VirtualAlloc(NULL,0x12c3000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));assert(image);
    assert(!validate(image));
    for(const StageCall &site:calls) { image[site.rva]=0xe8; *reinterpret_cast<DWORD *>(image+site.rva+1)=site.target-site.rva-5; }
    for(const SleepOperand &site:sleepOperands) {
        image[site.rva]=site.first; image[site.rva+1]=site.second;
        *reinterpret_cast<DWORD *>(image+site.rva+2)=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(image+0x5c01b4));
    }
    for(const SleepSite &site:sleepSites) { BYTE code[]={0x6a,1,0xff,site.target};memcpy(image+site.rva,code,4); }
    *reinterpret_cast<SleepFunction *>(image+0x5c01b4)=reinterpret_cast<SleepFunction>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"Sleep"));
    jump(0x470c60,reinterpret_cast<const void *>(uiFixture));jump(0x451540,reinterpret_cast<const void *>(readFixture));
    jump(0x49e120,reinterpret_cast<const void *>(parseFixture));jump(0x450f60,reinterpret_cast<const void *>(compositeFixture));
    for(DWORD rva : {0x4504d0u,0x44e6d0u,0x4479b0u,0x450ab0u,0x493440u}) jump(rva,reinterpret_cast<const void *>(passFixture));
    jump(0x493d40,reinterpret_cast<const void *>(dataFixture));jump(0x91c20,reinterpret_cast<const void *>(globalFixture));
    jump(0x89500,reinterpret_cast<const void *>(modelFixture));assert(validate(image));
}
int main() {
    static_assert(sizeof(void *)==4,"Real x86 ABI required");
    const bool modes[]={false,true};
    for(bool fast:modes) {
        prepare();
        image[sleepSites[0].rva+1]=2;
        assert(!patch(image,fast));assert(trasc_loading::callMatches(image,calls[0].rva,calls[0].target));
        image[sleepSites[0].rva+1]=1;
        for(const SleepOperand &site:sleepOperands) {
            image[site.rva]^=1;assert(!patch(image,fast));image[site.rva]^=1;
        }
        for(const StageCall &site:calls) {
            image[site.rva]^=1;assert(!patch(image,fast));image[site.rva]^=1;
        }
        assert(patch(image,fast));assert(!patch(image,fast));
        assert(*reinterpret_cast<SleepFunction *>(image+0x5c01b4)==originalSleep); // Import table untouched.
        for(unsigned i=0;i<sizeof(calls)/sizeof(calls[0]);++i) {
            unsigned args=i<=2?4:i==3?2:i==4?3:(i==9 || i>=12)?1:0;
            stub(i,args,i==3 || i>=12);
        }
        originalSleep=sleepFixture;
        for(bool fail:modes) {
            failure=fail;
            caller<UiLoad>(fail?1:0)(objects,objects+1,objects+2,objects+3,objects+4);
            assert(ownerThread==0 && !models && stats[XML_READ].calls==1 && stats[XML_READ].failures==static_cast<unsigned>(fail));
            assert(stats[UI_RESOLVE].calls==1 && stats[XML_MAIN_FILE].calls==1);
        }
        caller<GlobalLoad>(11)(objects);
        assert(ownerThread==0 && !models && stats[MODEL_LOAD].calls==18 && stats[MODEL_WAIT].calls==18);
        assert(requestedWaitMs==72 && yieldedWaits==(fast?9u:0u));
        waitModel(1);assert(seenWait==1); // Out of scope retains original wait.
        models=true;InterlockedExchange(&ownerThread,static_cast<LONG>(GetCurrentThreadId()+1));
        waitModel(1);assert(seenWait==1);InterlockedExchange(&ownerThread,0);models=false;
        VirtualFree(image,0,MEM_RELEASE);
    }
    assert(modelCalls==36);
    // Component measurement only: the game/device's actual wait count is logged separately.
    for(bool fast:modes) {
        originalSleep=Sleep;reducePauses=fast;Scope scope(true);
        LONGLONG start=clockTicks(); for(int i=0;i<128;++i) waitModel(1);
        printf("model_wait_fixture mode=%s calls=128 elapsed_us=%llu\n",fast?"yield":"original",micros(clockTicks()-start));
    }
    puts("PASS: UI/model x86 ABIs, success/failure passthrough, exact-site rejection, original import preserved, scoped waits and opt-out");
}
