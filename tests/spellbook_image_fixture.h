// Synthetic mapped-image fixture from the published MIT SpellbookSizeUpdate
// code (38a153d273f448ad1953d0b89497470443fd590e), not game assets.
#pragma once
#include <assert.h>
#include <string.h>
namespace spellbook_fixture {
static const DWORD stockSize = 0x12c3000, expandedSize = 0x12c5000;
inline IMAGE_NT_HEADERS32 *metadata(BYTE *image, bool expanded) {
    IMAGE_DOS_HEADER *dos = reinterpret_cast<IMAGE_DOS_HEADER *>(image);
    IMAGE_NT_HEADERS32 *nt = reinterpret_cast<IMAGE_NT_HEADERS32 *>(image + 128);
    dos->e_magic = IMAGE_DOS_SIGNATURE; dos->e_lfanew = 128;
    nt->Signature = IMAGE_NT_SIGNATURE; nt->FileHeader.Machine = IMAGE_FILE_MACHINE_I386;
    nt->FileHeader.TimeDateStamp = 0x518de58f;
    nt->FileHeader.SizeOfOptionalHeader = sizeof(IMAGE_OPTIONAL_HEADER32);
    nt->FileHeader.NumberOfSections = expanded ? 2 : 1;
    nt->FileHeader.Characteristics = 0x123;
    nt->OptionalHeader.Magic = IMAGE_NT_OPTIONAL_HDR32_MAGIC;
    nt->OptionalHeader.ImageBase = 0x400000;
    nt->OptionalHeader.SizeOfImage = expanded ? expandedSize : stockSize;
    return nt;
}
inline void bytes(BYTE *target, const char *hex) {
    for (unsigned i = 0; hex[i]; i += 2) {
        const char *digits = "0123456789abcdef";
        *target++ = static_cast<BYTE>((strchr(digits, hex[i]) - digits) * 16 + (strchr(digits, hex[i+1]) - digits));
    }
}
inline void expanded(BYTE *image) {
    IMAGE_NT_HEADERS32 *nt = metadata(image, true);
    IMAGE_SECTION_HEADER *sections = reinterpret_cast<IMAGE_SECTION_HEADER *>(reinterpret_cast<BYTE *>(nt) + sizeof(*nt));
    memset(sections, 0, sizeof(*sections) * 2);
    memcpy(sections[0].Name, ".text", 5); sections[0].VirtualAddress = 0x1000;
    memcpy(sections[1].Name, ".sbook", 6);
    sections[1].Misc.VirtualSize = 0x2000; sections[1].VirtualAddress = stockSize;
    sections[1].SizeOfRawData = 0x200; sections[1].PointerToRawData = 0x85e400;
    sections[1].Characteristics = 0xe0000060;
    bytes(image + 0x17cbd1, "e82a6414019090909090909090909090909090");
    bytes(image + 0x178fd6, "e9a5a014019090");
    BYTE *code = image + stockSize; memset(code, 0xcc, 512);
    bytes(code, "505157bf00326c01b9a005000083c8fffcf3ab5f595868a00500006800326c018bcee8d985ebfec70580486c01010000005657be00326c018dbfbc1a0000b9d0020000fcf3a55f5ec3");
    bytes(code + 0x80, "81fed0020000730c8bbcb3bc1a0000e9495febfe833d80486c0100bfffffffff74078b3cb500326c01e92f5febfe");
    // Apply the PE loader's six HIGHLOW relocation fixups at the actual ASLR base.
    const unsigned offsets[] = {0x4,0x1c,0x29,0x34,0x96,0xa5};
    const DWORD relocation = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(image)) - 0x400000;
    for (unsigned offset : offsets) {
        DWORD value = 0; memcpy(&value, code + offset, 4); value += relocation; memcpy(code + offset, &value, 4);
    }
}
inline void rejectionChecks(BYTE *image) {
    IMAGE_NT_HEADERS32 *nt = metadata(image, false);
    assert(trasc_camera::supported(image));
    nt->OptionalHeader.SizeOfImage = expandedSize;
    assert(!trasc_camera::supported(image)); // Increased size alone cannot qualify.
    expanded(image); assert(trasc_camera::supported(image));
    IMAGE_SECTION_HEADER *sections = reinterpret_cast<IMAGE_SECTION_HEADER *>(reinterpret_cast<BYTE *>(nt) + sizeof(*nt));
    BYTE *last = reinterpret_cast<BYTE *>(sections + 1);
    for (unsigned i = 0; i < sizeof(*sections); ++i) {
        last[i] ^= 1; assert(!trasc_camera::supported(image)); last[i] ^= 1;
    }
    memcpy(sections[0].Name, ".sbook\0\0", 8); assert(!trasc_camera::supported(image));
    memcpy(sections[0].Name, ".text\0\0\0", 8);
    sections[0].VirtualAddress = stockSize; assert(!trasc_camera::supported(image)); sections[0].VirtualAddress = 0x1000;
    const WORD invalidCounts[] = {0,33};
    for (WORD count : invalidCounts) {
        nt->FileHeader.NumberOfSections = count; assert(!trasc_camera::supported(image));
    }
    nt->FileHeader.NumberOfSections = 2;
    nt->FileHeader.SizeOfOptionalHeader = 0; assert(!trasc_camera::supported(image));
    nt->FileHeader.SizeOfOptionalHeader = sizeof(IMAGE_OPTIONAL_HEADER32);
    nt->OptionalHeader.ImageBase ^= 1; assert(!trasc_camera::supported(image)); nt->OptionalHeader.ImageBase ^= 1;
    nt->FileHeader.Characteristics ^= IMAGE_FILE_LARGE_ADDRESS_AWARE; assert(!trasc_camera::supported(image)); nt->FileHeader.Characteristics ^= IMAGE_FILE_LARGE_ADDRESS_AWARE;
    nt->FileHeader.TimeDateStamp ^= 1; assert(!trasc_camera::supported(image)); nt->FileHeader.TimeDateStamp ^= 1;
    for (unsigned i = 0; i < 19; ++i) {
        image[0x17cbd1+i] ^= 1; assert(!trasc_camera::supported(image)); image[0x17cbd1+i] ^= 1;
    }
    for (unsigned i = 0; i < 7; ++i) {
        image[0x178fd6+i] ^= 1; assert(!trasc_camera::supported(image)); image[0x178fd6+i] ^= 1;
    }
    for (unsigned i = 0; i < 512; ++i) {
        image[stockSize+i] ^= 1; assert(!trasc_camera::supported(image)); image[stockSize+i] ^= 1;
    }
    // The profile loader writes this area at runtime, never the checked cave.
    memset(image + stockSize + 512, 0x7f, 0x2000 - 512);
    assert(trasc_camera::supported(image));
}
}
