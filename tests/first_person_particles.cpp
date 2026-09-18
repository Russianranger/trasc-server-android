#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_first_person_particles.h"
#include <assert.h>
using namespace trasc_particles;
static BYTE *image, *graphics, *actor, *replacement;
static BYTE player[0x1200], otherPlayer[0x1200], camera[0x80], game[0x700];
static volatile LONG originals;
static bool createLate;
static void put(BYTE *p,DWORD n) { memcpy(p,&n,4); }
static void __fastcall referenceUpdate(void *self,void *,void *who) {
    assert(self==camera && who==player);
    InterlockedIncrement(&originals);
    camera[0x4c]=0;
    if(createLate) { put(player+0x101c,pointer(replacement)); createLate=false; }
    SetLastError(0x7788);
}
static void metadata(BYTE *p,DWORD stamp,DWORD size) {
    IMAGE_DOS_HEADER *dos=reinterpret_cast<IMAGE_DOS_HEADER *>(p);
    dos->e_magic=IMAGE_DOS_SIGNATURE; dos->e_lfanew=128;
    IMAGE_NT_HEADERS32 *nt=reinterpret_cast<IMAGE_NT_HEADERS32 *>(p+128);
    nt->Signature=IMAGE_NT_SIGNATURE; nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;
    nt->FileHeader.TimeDateStamp=stamp; nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    nt->OptionalHeader.SizeOfImage=size;
}
static BYTE *allocate(DWORD size) {
    BYTE *p=static_cast<BYTE *>(VirtualAlloc(NULL,size,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    assert(p); return p;
}
static void setupActor(BYTE *p) {
    memset(p,0,0x2000); put(p,pointer(graphics+0x137074)); put(p+0x13c,1);
}
static void runUpdate() {
    DWORD error=0x3344; SetLastError(error);
    Update fn=*reinterpret_cast<Update *>(image+updateSlot);
    fn(camera,player);
    assert(GetLastError()==0x7788);
}
static DWORD WINAPI otherThread(void *) { runUpdate(); return 0; }
int main() {
    static_assert(sizeof(void *)==4,"Actual x86 callback ABI required");
    image=allocate(0x12c3000); graphics=allocate(0x1e6000);
    actor=allocate(0x2000); replacement=allocate(0x2000);
    assert(!graphicsSupported(graphics));
    metadata(image,0x518de58f,0x12c3000); metadata(graphics,0x518de5b6,0x1e6000);
    memcpy(image+updateRva,updatePrefix,sizeof(updatePrefix)); put(image+updateSlot,pointer(image+updateRva));
    memcpy(graphics+0x3b1a0,setterCode,sizeof(setterCode)); memcpy(graphics+0x3b190,getterCode,sizeof(getterCode));
    put(graphics+0x174ba4,1);
    put(graphics+0x137074+0x23c,pointer(graphics+0x3b1a0));
    put(graphics+0x137074+0x240,pointer(graphics+0x3b190));
    put(graphics+0x137074+0x38,pointer(graphics+0x46f20));
    assert(graphicsSupported(graphics));
    assert(!patch(image,OFF)); assert(field(image,updateSlot)==pointer(image+updateRva));
    image[updateRva]^=1; assert(!patch(image,REPAIR)); image[updateRva]^=1;
    put(image+updateSlot,0); assert(!patch(image,REPAIR)); put(image+updateSlot,pointer(image+updateRva));
    assert(patch(image,PROFILE)); assert(!patch(image,REPAIR));
    // Once installed, run through the patched vtable and a same-signature x86
    // original callback. The real PE is covered separately by the private verifier.
    image[updateRva]=0xe9;
    put(image+updateRva+1,pointer(reinterpret_cast<void *>(referenceUpdate))-pointer(image+updateRva+5));
    FlushInstructionCache(GetCurrentProcess(),image+updateRva,5);
    graphicsModule=reinterpret_cast<HMODULE>(graphics);
    setupActor(actor); setupActor(replacement);
    put(image+0xa67ccc,pointer(game)); put(game+0x5c8,5);
    put(image+0x91fd9c,0); put(image+0x9e0d64,pointer(camera)); put(image+0x9d2630,pointer(player));
    put(player+0x101c,pointer(actor));
    runUpdate(); assert(originals==1 && !actor[0x5c] && lastSample.status==MISSING && !attempts);
    unsigned logged=reports; runUpdate(); assert(reports==logged); // No per-frame log spam.
    mode=REPAIR; runUpdate(); assert(actor[0x5c]==1 && attempts==1 && lastSample.status==REPAIRED);
    assert(lastSample.before==0 && lastSample.after==1 && (field(actor,0x13c)&1));
    runUpdate(); assert(attempts==1 && lastSample.status==PERMITTED);
    actor[0x5c]=0; runUpdate(); assert(!actor[0x5c] && attempts==1 && lastSample.status==ATTEMPT_LIMIT);
    camera[0x4c]=1; runUpdate(); assert(actor[0x5c]==1 && attempts==2); // New entry episode.

    put(player+0x101c,0); runUpdate(); assert(lastSample.status==NO_ACTOR);
    createLate=true; runUpdate(); assert(replacement[0x5c]==1 && lastSample.status==REPAIRED);
    assert(lastSample.actor==pointer(replacement)); // Checked after original callback creates actor.
    replacement[0x5c]=0; put(game+0x5c8,4); runUpdate(); assert(!replacement[0x5c] && lastSample.status==OUTSIDE_WORLD);
    put(game+0x5c8,5); runUpdate(); assert(replacement[0x5c]==1); // Relog/zone state reset.

    replacement[0x5c]=0; put(image+0x91fd9c,1); runUpdate(); assert(!replacement[0x5c] && lastSample.status==OTHER_VIEW);
    put(image+0x91fd9c,0); put(image+0x9d2630,pointer(otherPlayer)); runUpdate();
    assert(!replacement[0x5c] && lastSample.status==OTHER_VIEW); put(image+0x9d2630,pointer(player));
    put(replacement+0x24,pointer(actor)); runUpdate(); assert(!replacement[0x5c] && lastSample.status==ATTACHED_ACTOR);
    put(replacement+0x24,0); put(replacement+0x13c,0); runUpdate(); assert(!replacement[0x5c] && lastSample.status==VISIBLE);
    put(replacement+0x13c,1);
    put(replacement,0); runUpdate(); assert(lastSample.status==BAD_ACTOR); setupActor(replacement);
    graphics[0x3b1a0]^=1; runUpdate(); assert(lastSample.status==BAD_GRAPHICS && !replacement[0x5c]); graphics[0x3b1a0]^=1;
    put(graphics+0x137074+0x240,0); runUpdate(); assert(lastSample.status==BAD_ACTOR && !replacement[0x5c]);
    put(graphics+0x137074+0x240,pointer(graphics+0x3b190));

    put(player+0x101c,1); runUpdate(); assert(lastSample.status==BAD_ACTOR); put(player+0x101c,pointer(replacement));
    DWORD protection=0,unused=0;
    assert(VirtualProtect(replacement,0x2000,PAGE_READONLY,&protection));
    runUpdate(); assert(!replacement[0x5c] && lastSample.status==BAD_ACTOR);
    assert(VirtualProtect(replacement,0x2000,protection,&unused));
    LONG before=originals; unsigned priorAttempts=attempts;
    HANDLE thread=CreateThread(NULL,0,otherThread,NULL,0,NULL); assert(thread);
    assert(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0); CloseHandle(thread);
    assert(originals==before+1 && !replacement[0x5c] && attempts==priorAttempts);
    runUpdate(); assert(replacement[0x5c]==1 && attempts==priorAttempts+1);
    attempts=128; replacement[0x5c]=0; camera[0x4c]=1; runUpdate();
    assert(!replacement[0x5c] && lastSample.status==ATTEMPT_LIMIT && attempts==128);
    reports=512; haveSample=false; runUpdate(); assert(reports==512);
    puts("PASS: particle callback x86 ABI/original-first ordering, diagnostics/repair/opt-out, actor lifecycle, scope/thread/read safety, exact-layout guards and bounded retries/logs");
}
