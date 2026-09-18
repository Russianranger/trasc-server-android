#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_camera_mouse.h"
#include <assert.h>
#include <stdio.h>

int main() {
    BYTE *image = static_cast<BYTE *>(VirtualAlloc(NULL, 0x12c3000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    assert(image);
    IMAGE_DOS_HEADER *dos = reinterpret_cast<IMAGE_DOS_HEADER *>(image);
    IMAGE_NT_HEADERS32 *nt = reinterpret_cast<IMAGE_NT_HEADERS32 *>(image + 128);
    dos->e_magic = IMAGE_DOS_SIGNATURE; dos->e_lfanew = 128;
    nt->Signature = IMAGE_NT_SIGNATURE; nt->FileHeader.Machine = IMAGE_FILE_MACHINE_I386;
    nt->FileHeader.TimeDateStamp = 0x518de58f;
    nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    nt->OptionalHeader.SizeOfImage = 0x12c3000;
    assert(trasc_camera::supported(image));
    nt->FileHeader.TimeDateStamp++; assert(!trasc_camera::supported(image)); nt->FileHeader.TimeDateStamp--;
    assert(!trasc_camera::looking(image)); // No game object at startup.
    BYTE game[0x600] = {}, alternate[16] = {};
    *reinterpret_cast<DWORD *>(image + 0xa67ccc) = reinterpret_cast<DWORD>(game);
    *reinterpret_cast<DWORD *>(image + 0xa63980) = reinterpret_cast<DWORD>(alternate);
    for (DWORD state = 0; state < 8; state++) {
        *reinterpret_cast<DWORD *>(game + 0x5c8) = state;
        image[0x9df702] = 1;
        assert(trasc_camera::looking(image) == (state == 5));
    }
    *reinterpret_cast<DWORD *>(game + 0x5c8) = 5;
    image[0x9df702] = 0;
    assert(!trasc_camera::looking(image)); // Inventory/menu pointer.
    alternate[8] = 1; assert(trasc_camera::looking(image)); // Held look.
    alternate[8] = 0; assert(!trasc_camera::looking(image)); // Release.
    image[0x9df702] = 1; assert(trasc_camera::looking(image)); // Toggle.
    *reinterpret_cast<DWORD *>(game + 0x5c8) = 2;
    assert(!trasc_camera::looking(image)); // Char select, even with stale flag.
    *reinterpret_cast<DWORD *>(image + 0xa67ccc) = 1;
    assert(!trasc_camera::looking(image)); // Unreadable state fails closed.
    assert(!trasc_camera::supported(NULL));
    VirtualFree(image, 0, MEM_RELEASE);
    puts("PASS: startup, menu, held/toggled look, character select and invalid game state");
}
