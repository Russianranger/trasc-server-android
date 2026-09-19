#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_boat_diagnostics.h"
#include <assert.h>
#include <initializer_list>
using namespace trasc_boats;
static void put(BYTE *p,DWORD value){memcpy(p,&value,4);}
int main(){
    static_assert(sizeof(void*)==4,"x86 state layout required");
    BYTE *image=static_cast<BYTE*>(VirtualAlloc(NULL,0x12c3000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));assert(image);
    static BYTE player[0x1100],ship[0x1100],npc[0x1100],game[0x700],info[0x40];
    IMAGE_DOS_HEADER *dos=reinterpret_cast<IMAGE_DOS_HEADER*>(image);dos->e_magic=IMAGE_DOS_SIGNATURE;dos->e_lfanew=128;
    IMAGE_NT_HEADERS32 *nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(image+128);nt->Signature=IMAGE_NT_SIGNATURE;
    nt->FileHeader.Machine=IMAGE_FILE_MACHINE_I386;nt->FileHeader.TimeDateStamp=0x518de58f;
    nt->OptionalHeader.Magic=IMAGE_NT_OPTIONAL_HDR32_MAGIC;nt->OptionalHeader.SizeOfImage=0x12c3000;
    put(image+0x4cfce0,0x0150818b);put(image+0x5d7240,address(image+0x19e530));assert(supported(image));
    image[0x4cfce0]^=1;assert(!supported(image));image[0x4cfce0]^=1;
    for(BYTE *p:{player,ship,npc}){put(p,address(image+0x5d71f0));put(p+0x234,address(info));}
    put(player+0x148,10);put(ship+0x148,20);put(ship+0xeb4,72);put(info+0x2c,3);
    memcpy(ship+0xa4,"Test\nship",10);put(player+0x150,address(ship));
    put(image+0xa67ccc,address(game));put(game+0x5c8,5);put(image+0x9d2630,address(player));
    put(image+0x9d2648,address(ship));put(image+0x9e0858,69);
    BYTE before[sizeof(player)],shipBefore[sizeof(ship)];memcpy(before,player,sizeof(player));memcpy(shipBefore,ship,sizeof(ship));
    Sample s={};assert(inspect(image,s));assert(s.zone==69&&s.player.id==10&&s.targetValid&&s.vehicleValid);
    assert(s.target.id==20&&s.target.flags==3&&!strcmp(s.target.name,"Test?ship"));
    assert(!memcmp(before,player,sizeof(player))&&!memcmp(shipBefore,ship,sizeof(ship)));
    put(info+0x2c,8);assert(inspect(image,s)&&s.targetValid); // Known race with absent boat flag is still useful evidence.
    put(image+0x9d2648,address(npc));assert(inspect(image,s)&&!s.targetValid&&s.vehicleValid);
    put(player+0x150,0);assert(inspect(image,s)&&!s.vehicleValid);
    put(player+0x150,1);assert(inspect(image,s)&&!s.vehicleValid); // Unreadable state must never be dereferenced.
    put(image+0x9d2648,1);assert(inspect(image,s)&&!s.targetValid);
    put(game+0x5c8,4);assert(!inspect(image,s));put(game+0x5c8,5);
    put(image+0x9d2630,1);assert(!inspect(image,s));put(image+0x9d2630,address(player));
    put(player,0);assert(!inspect(image,s));put(player,address(image+0x5d71f0));
    put(player+0x64,0x7fc00000);assert(!inspect(image,s));put(player+0x64,0);
    SetLastError(0x1234);trasc_boat_after_read(E_FAIL,sizeof(DIMOUSESTATE2),image+0xa67884);assert(GetLastError()==0x1234);
    SetLastError(0x3456);trasc_boat_after_read(S_OK,256,player);assert(GetLastError()==0x3456);
    VirtualFree(image,0,MEM_RELEASE);
    puts("PASS: read-only boat snapshots, exact-client guards, missing/invalid actor data, names, nonboats, zoning and unchanged input/error state");
}
