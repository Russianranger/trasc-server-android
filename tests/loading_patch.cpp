#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_client_loading.h"
#include <assert.h>
#include <stdlib.h>

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
static bool __fastcall fixtureLoad(void *self, void *, const char *a, const char *b) {
    assert(self == reinterpret_cast<void *>(0x1234));
    assert(!strcmp(a,"spells") && !strcmp(b,"associations"));
    return true;
}
int main() {
    using namespace trasc_loading;
    BYTE *image = static_cast<BYTE *>(VirtualAlloc(NULL,0x12c3000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    assert(image && !validateCalls(image));
    for(DWORD rva:numberCalls) {
        image[rva]=0xe8;
        *reinterpret_cast<DWORD *>(image+rva+1)=0x4089a0-rva-5;
    }
    assert(validateCalls(image));
    image[numberCalls[1]]=0x90;
    assert(!patchCalls(image,number)); // Partial/changed layouts must not mutate.
    assert(*reinterpret_cast<DWORD *>(image+numberCalls[0]+1)==0x4089a0-numberCalls[0]-5);
    image[numberCalls[1]]=0xe8;
    // An open, executable x86 fixture calls through the same CALL instruction.
    const BYTE args[]={0xff,0x74,0x24,0x08,0xff,0x74,0x24,0x08};
    const BYTE finish[]={0x83,0xc4,0x08,0xc3};
    memcpy(image+numberCalls[0]-sizeof(args),args,sizeof(args));
    memcpy(image+numberCalls[0]+5,finish,sizeof(finish));
    originalNumber=reference;
    assert(patchCalls(image,number));
    auto caller=reinterpret_cast<NumberReader>(image+numberCalls[0]-sizeof(args));
    const char *text="-42^next"; assert(caller(&text,'^')==-42 && !strcmp(text,"next"));
    text=" 12^next"; assert(caller(&text,'^')==12 && !strcmp(text,"next"));
    assert(fastCount==1 && fallbackCount==1);
    assert(!patchCalls(image,number)); // Never stack/reapply patches.
    originalLoad=reinterpret_cast<SpellLoader>(fixtureLoad);
    SpellLoader timed=reinterpret_cast<SpellLoader>(load);
    assert(timed(reinterpret_cast<void *>(0x1234),"spells","associations"));
    VirtualFree(image,0,MEM_RELEASE);
    puts("PASS: executable x86 call replacement, fallback, layout rejection and loader ABI");
}
