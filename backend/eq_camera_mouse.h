// TRASC camera mouse adapter v2. Read-only ROF2 state; no game-code patches.
#pragma once
#include <windows.h>
#include <dinput.h>
#include <string.h>
#include <stdio.h>

namespace trasc_camera {
static const char marker[] = "TRASC_EQ_CAMERA_MOUSE_V2";

inline void logLine(const char *path, const char *line) {
    HANDLE file = CreateFileA(path, FILE_APPEND_DATA | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return;
    LARGE_INTEGER size = {}; DWORD written = 0;
    if (GetFileSizeEx(file, &size) && size.QuadPart < 256 * 1024)
        WriteFile(file, line, static_cast<DWORD>(strlen(line)), &written, NULL);
    CloseHandle(file);
}

template<class T> bool read(const void *address, T &value) {
    SIZE_T count = 0;
    return ReadProcessMemory(GetCurrentProcess(), address, &value, sizeof(value), &count)
        && count == sizeof(value);
}

// Exact mapped-image signature of the MIT-licensed SpellbookSizeUpdate patch,
// commit 38a153d273f448ad1953d0b89497470443fd590e. See THIRD_PARTY_NOTICES.md.
// Only code/raw padding is checked: the mutable book starts at section+0x200.
inline bool expandedSpellbook(const BYTE *image, LONG peOffset, const IMAGE_NT_HEADERS32 &nt) {
    if (nt.OptionalHeader.SizeOfImage != 0x12c5000
        || nt.OptionalHeader.ImageBase != 0x400000
        || !(nt.FileHeader.Characteristics & IMAGE_FILE_LARGE_ADDRESS_AWARE)
        || nt.FileHeader.SizeOfOptionalHeader != sizeof(IMAGE_OPTIONAL_HEADER32)
        || nt.FileHeader.NumberOfSections < 2 || nt.FileHeader.NumberOfSections > 32) return false;
    IMAGE_SECTION_HEADER section = {};
    const BYTE *table = image + peOffset + 24 + nt.FileHeader.SizeOfOptionalHeader;
    if (!read(table + (nt.FileHeader.NumberOfSections - 1) * sizeof(section), section)
        || memcmp(section.Name, ".sbook\0\0", 8)
        || section.Misc.VirtualSize != 0x2000 || section.VirtualAddress != 0x12c3000
        || section.SizeOfRawData != 0x200 || section.PointerToRawData != 8774656
        || section.PointerToRelocations || section.PointerToLinenumbers
        || section.NumberOfRelocations || section.NumberOfLinenumbers
        || section.Characteristics != 0xe0000060) return false;
    for (unsigned i = 0; i + 1 < nt.FileHeader.NumberOfSections; ++i) {
        IMAGE_SECTION_HEADER earlier = {};
        if (!read(table + i * sizeof(earlier), earlier)
            || !memcmp(earlier.Name, ".sbook\0\0", 8)
            || earlier.VirtualAddress >= 0x12c3000) return false;
    }
    const BYTE hook1[] = {0xe8,0x2a,0x64,0x14,0x01,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90};
    const BYTE hook2[] = {0xe9,0xa5,0xa0,0x14,0x01,0x90,0x90};
    BYTE actual1[sizeof(hook1)] = {}, actual2[sizeof(hook2)] = {};
    if (!read(image + 0x17cbd1, actual1) || memcmp(actual1, hook1, sizeof(hook1))
        || !read(image + 0x178fd6, actual2) || memcmp(actual2, hook2, sizeof(hook2))) return false;
    const BYTE first[] = {0x50,0x51,0x57,0xbf,0x00,0x32,0x6c,0x01,0xb9,0xa0,0x05,0x00,0x00,0x83,0xc8,0xff,0xfc,0xf3,0xab,0x5f,0x59,0x58,0x68,0xa0,0x05,0x00,0x00,0x68,0x00,0x32,0x6c,0x01,0x8b,0xce,0xe8,0xd9,0x85,0xeb,0xfe,0xc7,0x05,0x80,0x48,0x6c,0x01,0x01,0x00,0x00,0x00,0x56,0x57,0xbe,0x00,0x32,0x6c,0x01,0x8d,0xbf,0xbc,0x1a,0x00,0x00,0xb9,0xd0,0x02,0x00,0x00,0xfc,0xf3,0xa5,0x5f,0x5e,0xc3};
    const BYTE second[] = {0x81,0xfe,0xd0,0x02,0x00,0x00,0x73,0x0c,0x8b,0xbc,0xb3,0xbc,0x1a,0x00,0x00,0xe9,0x49,0x5f,0xeb,0xfe,0x83,0x3d,0x80,0x48,0x6c,0x01,0x00,0xbf,0xff,0xff,0xff,0xff,0x74,0x07,0x8b,0x3c,0xb5,0x00,0x32,0x6c,0x01,0xe9,0x2f,0x5f,0xeb,0xfe};
    BYTE expected[512], actual[512] = {};
    memset(expected, 0xcc, sizeof(expected));
    memcpy(expected, first, sizeof(first)); memcpy(expected + 0x80, second, sizeof(second));
    const unsigned fixups[] = {4,28,41,52,150,165};
    const DWORD delta = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(image)) - 0x400000;
    for (unsigned offset : fixups) {
        DWORD address = 0; memcpy(&address, expected + offset, sizeof(address)); address += delta;
        memcpy(expected + offset, &address, sizeof(address));
    }
    return read(image + 0x12c3000, actual) && !memcmp(actual, expected, sizeof(expected));
}

// This layout was checked against the supplied May 10 2013 ROF2 executable.
// The launcher also verifies the complete file and protected original before
// enabling an adapter; expanded images additionally need the exact code above.
inline bool supported(const BYTE *image) {
    IMAGE_DOS_HEADER dos = {};
    IMAGE_NT_HEADERS32 nt = {};
    if (!read(image, dos) || dos.e_magic != IMAGE_DOS_SIGNATURE
        || dos.e_lfanew < 64 || dos.e_lfanew > 1048576
        || !read(image + dos.e_lfanew, nt)) return false;
    return nt.Signature == IMAGE_NT_SIGNATURE && nt.FileHeader.Machine == IMAGE_FILE_MACHINE_I386
        && nt.FileHeader.TimeDateStamp == 0x518de58f
        && nt.OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC
        && (nt.OptionalHeader.SizeOfImage == 0x12c3000 || expandedSpellbook(image, dos.e_lfanew, nt));
}

inline bool looking(const BYTE *image) {
    DWORD game = 0, alternate = 0, state = 0;
    BYTE toggle = 0, held = 0;
    if (!read(image + 0xa67ccc, game) || !game
        || !read(reinterpret_cast<const BYTE *>(game) + 0x5c8, state) || state != 5)
        return false;
    if (!read(image + 0x9df702, toggle)) return false;
    if (toggle) return true;
    return read(image + 0xa63980, alternate) && alternate
        && read(reinterpret_cast<const BYTE *>(alternate) + 8, held) && held;
}

// Called only AFTER DirectInput has delivered movement. Never alter the input
// data, cooperative level, cursor visibility, clipping, or acquisition state.
inline bool recenter(HWND window, bool camera) {
    if (!camera || !window || GetForegroundWindow() != window) return false;
    DWORD process = 0;
    if (!GetWindowThreadProcessId(window, &process) || process != GetCurrentProcessId()) return false;
    CURSORINFO cursor = {}; cursor.cbSize = sizeof(cursor);
    if (!GetCursorInfo(&cursor) || (cursor.flags & CURSOR_SHOWING)) return false;
    RECT rect = {};
    if (!GetClientRect(window, &rect) || rect.right < 4 || rect.bottom < 4) return false;
    POINT center = {(rect.right - rect.left) / 2, (rect.bottom - rect.top) / 2};
    if (!ClientToScreen(window, &center)) return false;
    // Avoid manufacturing events when the pointer is already centered.
    if (cursor.ptScreenPos.x == center.x && cursor.ptScreenPos.y == center.y) return false;
    return SetCursorPos(center.x, center.y) != FALSE;
}

// The verified ROF2 call at RVA 0x1f9e8e uses its own DIMOUSESTATE2 buffer and
// the DIDF_RELAXIS format at RVA 0x60056c. Wine 10 cannot GetProperty(AXISMODE):
// that query returns DIERR_UNSUPPORTED even on a correctly configured mouse.
// Bind to this exact read instead of requiring that unsupported query.
template<class Device> const char *processRead(Device *device, HRESULT result, DWORD size,
                                              void *data, const BYTE *image) {
    if (FAILED(result)) return "read_failed";
    if (size != sizeof(DIMOUSESTATE2) || data != image + 0xa67884) return "other_buffer";
    if (!looking(image)) return "menu";
    DIDEVCAPS caps = {}; caps.dwSize = sizeof(caps);
    if (FAILED(device->GetCapabilities(&caps)) || GET_DIDEVICE_TYPE(caps.dwDevType) != DI8DEVTYPE_MOUSE)
        return "not_mouse";
    return recenter(GetForegroundWindow(), true) ? "recentered" : "cursor_or_focus";
}

template<class Device> void afterRead(Device *device, HRESULT result, DWORD size, void *data) {
    if (size != sizeof(DIMOUSESTATE2)) return;
    const BYTE *image = reinterpret_cast<const BYTE *>(GetModuleHandleW(NULL));
    static const bool enabled = []() {
        char value[4] = {};
        const BYTE *image = reinterpret_cast<const BYTE *>(GetModuleHandleW(NULL));
        return GetEnvironmentVariableA(marker, value, sizeof(value)) == 1 && value[0] == '1'
            && GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "wine_get_version") && supported(image);
    }();
    const char *reason = enabled ? processRead(device, result, size, data, image) : "disabled_or_unverified";
    static DWORD last = 0, polls = 0, warps = 0, lookPolls = 0;
    ++polls;
    if (!strcmp(reason, "recentered")) ++warps;
    if (!strcmp(reason, "recentered") || !strcmp(reason, "cursor_or_focus")) ++lookPolls;
    DWORD now = GetTickCount();
    if (last && now - last < 5000) return;
    last = now;
    char line[256];
    snprintf(line, sizeof(line), "ticks=%lu adapter=v2 enabled=%d reason=%s polls=%lu look_polls=%lu warps=%lu\r\n",
        now, enabled, reason, polls, lookPolls, warps);
    logLine("Z:\\logs\\client-camera.log", line);
}
}
