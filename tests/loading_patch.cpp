#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_client_loading.h"
#include <assert.h>
#include <stdlib.h>
using namespace trasc_loading;
static BYTE *fixtureImage;
static bool expectFast;
static unsigned mapped;
static int object;

static int __cdecl reference(const char **p, int delimiter) {
    char field[512]; unsigned n=0;
    while (**p && **p != delimiter && **p != '\r' && **p != '\n') {
        if(n<511) field[n++]=**p;
        ++*p;
    }
    field[n]=0;
    if(**p==delimiter) ++*p;
    return atoi(field);
}
static BYTE *entry(DWORD rva) {
    if (rva==numberCalls[0]) return fixtureImage+0x1000000;
    for(unsigned i=0;i<sizeof(stageCalls)/sizeof(stageCalls[0]);++i)
        if(stageCalls[i].rva==rva) return fixtureImage+0x1000000+(i+1)*64;
    assert(false); return NULL;
}
template<class F> F caller(DWORD rva, unsigned) {
    return reinterpret_cast<F>(entry(rva));
}
static int __fastcall fixtureNext(void *self, void *) { assert(self==&object); return 5; }
static void *__cdecl fixtureRecord(const char *line) {
    assert(!strcmp(line,"42^row")); assert(!trasc_spell_checksum_fast()); return &object;
}
static DWORD __fastcall fixtureRecordChecksum(void *self, void *) {
    assert(self==&object && trasc_spell_checksum_fast()==expectFast); return 0x12345678;
}
static DWORD __cdecl fixtureChecksum(const char *path) {
    assert((!strcmp(path,"spells") || !strcmp(path,"associations")) && trasc_spell_checksum_fast()==expectFast);
    return 0x87654321;
}
static void __fastcall fixtureMap(void *self, void *) { assert(self==&object); ++mapped; }
static int __fastcall fixtureAssociations(void *self, void *, const char *path, int flags) {
    assert(self==&object && !strcmp(path,"associations") && flags==0);
    assert(activeLines==&associationLines);
    assert(caller<NextLine>(0x3d4e66,0)(self)==5);
    return 17;
}
static bool __fastcall fixtureText(void *self, void *, const char *a, const char *b, void *table) {
    assert(self==&object && !strcmp(a,"spells") && !strcmp(b,"associations") && table==&object);
    assert(activeLines==&spellLines);
    assert(caller<NextLine>(0x1c1d5d,0)(self)==5);
    void *entry=caller<RecordLoader>(0x1c1dbe,1)("42^row"); assert(entry==&object);
    assert(caller<RecordChecksum>(0x1c1dd3,0)(entry)==0x12345678);
    assert(caller<NextLine>(0x1c1e6b,0)(self)==5);
    assert(caller<Associations>(0x1c1e9c,2)(self,b,0)==17);
    assert(activeLines==&spellLines);
    return true;
}
static bool __fastcall fixtureLoad(void *self, void *, const char *a, const char *b) {
    assert(self==&object && !strcmp(a,"spells") && !strcmp(b,"associations"));
    assert(profiling());
    assert(caller<TextLoader>(0x6740e,3)(self,a,b,self));
    assert(caller<Checksum>(0x6741e,1)(a)==0x87654321);
    assert(caller<Checksum>(0x6742a,1)(b)==0x87654321);
    caller<MapLoader>(0x6743a,0)(self);
    return true;
}
static void jump(DWORD rva, const void *function) {
    fixtureImage[rva]=0xe9;writeCall(fixtureImage,rva,function);
}
static void stub(DWORD rva, unsigned args, bool callerCleansStack) {
    BYTE *p=entry(rva);
    for(unsigned i=0;i<args;++i) {
        const BYTE push[]={0xff,0x74,0x24,static_cast<BYTE>(args*4)};
        memcpy(p,push,4);p+=4;
    }
    DWORD target=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(fixtureImage+rva+5))
        + *reinterpret_cast<DWORD *>(fixtureImage+rva+1);
    *p=0xe8;
    DWORD displacement=target-static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(p+5));
    memcpy(p+1,&displacement,4);p+=5;
    if(callerCleansStack && args) { *p++=0x83;*p++=0xc4;*p++=static_cast<BYTE>(args*4); }
    if(!callerCleansStack && args) { *p++=0xc2;*p++=static_cast<BYTE>(args*4);*p=0; }
    else *p=0xc3;
}
static void prepare() {
    fixtureImage=static_cast<BYTE *>(VirtualAlloc(NULL,0x12c3000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    assert(fixtureImage && !validateLayout(fixtureImage));
    for(DWORD rva:numberCalls) {
        fixtureImage[rva]=0xe8; *reinterpret_cast<DWORD *>(fixtureImage+rva+1)=0x4089a0-rva-5;
    }
    for(const StageCall &site:stageCalls) {
        fixtureImage[site.rva]=0xe8;*reinterpret_cast<DWORD *>(fixtureImage+site.rva+1)=site.target-site.rva-5;
        unsigned args=0;bool callerCleansStack=false;
        if(site.rva==0x6740e) args=3;
        if(site.rva==0x1c1e9c) args=2;
        if(site.rva==0x6741e || site.rva==0x6742a || site.rva==0x1c1dbe) { args=1;callerCleansStack=true; }
        stub(site.rva,args,callerCleansStack);
    }
    stub(numberCalls[0],2,true);
    *reinterpret_cast<DWORD *>(fixtureImage+0x5c6144)=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(fixtureImage+0x673f0));
    jump(0x673f0,reinterpret_cast<const void *>(fixtureLoad));
    jump(0x1c1c30,reinterpret_cast<const void *>(fixtureText));
    jump(0x3d50b0,reinterpret_cast<const void *>(fixtureAssociations));
    jump(0x67300,reinterpret_cast<const void *>(fixtureMap));
    jump(0xafaf0,reinterpret_cast<const void *>(fixtureRecord));
    jump(0xaca30,reinterpret_cast<const void *>(fixtureRecordChecksum));
    jump(0x408d90,reinterpret_cast<const void *>(fixtureChecksum));
    jump(0x408860,reinterpret_cast<const void *>(fixtureNext));
    jump(0x4089a0,reinterpret_cast<const void *>(reference));
    assert(validateLayout(fixtureImage));
}
int main() {
    static_assert(sizeof(void *)==4,"This fixture exercises the real x86 ABI");
    const bool modes[] = {false, true};
    for(bool fast : modes) {
        expectFast=fast;prepare();
        fixtureImage[stageCalls[1].rva]=0x90;
        assert(!patchLayout(fixtureImage,fast));
        assert(callMatches(fixtureImage,stageCalls[0].rva,stageCalls[0].target));
        assert(callMatches(fixtureImage,numberCalls[0],0x4089a0));
        fixtureImage[stageCalls[1].rva]=0xe8;
        assert(patchLayout(fixtureImage,fast));
        assert(!patchLayout(fixtureImage,fast));
        stub(numberCalls[0],2,true);
        for(const StageCall &site:stageCalls) {
            unsigned args=0;bool callerCleansStack=false;
            if(site.rva==0x6740e) args=3;
            if(site.rva==0x1c1e9c) args=2;
            if(site.rva==0x6741e || site.rva==0x6742a || site.rva==0x1c1dbe) { args=1;callerCleansStack=true; }
            stub(site.rva,args,callerCleansStack);
            DWORD displacement=*reinterpret_cast<DWORD *>(fixtureImage+site.rva+1);
            assert(reinterpret_cast<ULONG_PTR>(fixtureImage+site.rva+5)+displacement==reinterpret_cast<ULONG_PTR>(site.replacement));
        }
        fastCount=fallbackCount=0;
        auto numberCall=caller<NumberReader>(numberCalls[0],2);
        const char *p="-42^next";assert(numberCall(&p,'^')==-42 && !strcmp(p,"next"));
        p=" 12^next";assert(numberCall(&p,'^')==12 && !strcmp(p,"next"));
        assert(fastCount==(fast?1u:0u) && fallbackCount==(fast?1u:0u));
        assert(!trasc_spell_checksum_fast());
        auto full=*reinterpret_cast<SpellLoader *>(fixtureImage+0x5c6144);
        assert(full(&object,"spells","associations"));
        assert(profileThread==0 && checksumDepth==0 && !activeLines && !trasc_spell_checksum_fast());
        assert(spellLines.records==1 && spellLines.recordChecksums==1 && spellLines.lines==2 && associationLines.lines==1);
        // Another thread cannot inherit the checksum scope.
        checksumDepth=1;InterlockedExchange(&profileThread,static_cast<LONG>(GetCurrentThreadId()+1));
        assert(!trasc_spell_checksum_fast());
        checksumDepth=0;InterlockedExchange(&profileThread,0);
        VirtualFree(fixtureImage,0,MEM_RELEASE);
    }
    assert(mapped==2);
    puts("PASS: complete patched x86 loader, all stage ABIs, unchanged results, scope cleanup, opt-out and layout rejection");
}
