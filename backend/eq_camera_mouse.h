// TRASC camera mouse adapter v1. Read-only ROF2 state; no game-code patches.
#pragma once
#include <windows.h>
#include <dinput.h>
#include <string.h>

namespace trasc_camera {
static const char marker[] = "TRASC_EQ_CAMERA_MOUSE_V1";

template<class T> bool read(const void *address, T &value) {
    SIZE_T count = 0;
    return ReadProcessMemory(GetCurrentProcess(), address, &value, sizeof(value), &count)
        && count == sizeof(value);
}

// This layout was checked against the supplied May 10 2013 ROF2 executable.
// The launcher also requires its complete SHA256 before enabling the adapter.
inline bool supported(const BYTE *image) {
    IMAGE_DOS_HEADER dos = {};
    IMAGE_NT_HEADERS32 nt = {};
    if (!read(image, dos) || dos.e_magic != IMAGE_DOS_SIGNATURE
        || dos.e_lfanew < 64 || dos.e_lfanew > 1048576
        || !read(image + dos.e_lfanew, nt)) return false;
    return nt.Signature == IMAGE_NT_SIGNATURE && nt.FileHeader.Machine == IMAGE_FILE_MACHINE_I386
        && nt.FileHeader.TimeDateStamp == 0x518de58f
        && nt.OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC
        && nt.OptionalHeader.SizeOfImage == 0x12c3000;
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

template<class Device> void afterRead(Device *device, HRESULT result, DWORD size) {
    if (FAILED(result) || (size != sizeof(DIMOUSESTATE) && size != sizeof(DIMOUSESTATE2))) return;
    static const bool enabled = []() {
        char value[4] = {};
        const BYTE *image = reinterpret_cast<const BYTE *>(GetModuleHandleW(NULL));
        return GetEnvironmentVariableA(marker, value, sizeof(value)) == 1 && value[0] == '1'
            && GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "wine_get_version") && supported(image);
    }();
    if (!enabled || !looking(reinterpret_cast<const BYTE *>(GetModuleHandleW(NULL)))) return;
    DIDEVCAPS caps = {}; caps.dwSize = sizeof(caps);
    DIPROPDWORD mode = {}; mode.diph.dwSize = sizeof(mode);
    mode.diph.dwHeaderSize = sizeof(mode.diph); mode.diph.dwHow = DIPH_DEVICE;
    if (FAILED(device->GetCapabilities(&caps)) || GET_DIDEVICE_TYPE(caps.dwDevType) != DI8DEVTYPE_MOUSE
        || FAILED(device->GetProperty(DIPROP_AXISMODE, &mode.diph)) || mode.dwData != DIPROPAXISMODE_REL)
        return;
    recenter(GetForegroundWindow(), true);
}
}
