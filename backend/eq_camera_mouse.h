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
