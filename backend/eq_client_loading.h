// Optional exact-build spell parser experiment. No file caches or data edits.
#pragma once
#include "eq_camera_mouse.h"
#include "eq_fast_decimal.h"

namespace trasc_loading {
static const char marker[] = "TRASC_EQ_LOAD_V1";
typedef int (__cdecl *NumberReader)(const char **, int);
typedef bool (__thiscall *SpellLoader)(void *, const char *, const char *);
static NumberReader originalNumber = NULL;
static SpellLoader originalLoad = NULL;
static unsigned fastCount = 0, fallbackCount = 0;

// This helper alone is optimized; the upstream add-on keeps its original ABI
// and /Od recipe. No assumptions about locale, overflow or malformed fields.
#ifdef _MSC_VER
#pragma optimize("gt", on)
#endif
static int __cdecl number(const char **cursor, int separator) {
    int value;
    if (decimal(cursor, separator, value)) { ++fastCount; return value; }
    ++fallbackCount;
    return originalNumber(cursor, separator);
}
#ifdef _MSC_VER
#pragma optimize("", on)
#endif

static bool __fastcall load(void *self, void *, const char *spells, const char *associations) {
    DWORD start = GetTickCount();
    unsigned beforeFast = fastCount, beforeFallback = fallbackCount;
    char line[256];
    snprintf(line, sizeof(line), "ticks=%lu spell_load=start\r\n", start);
    trasc_camera::logLine("Z:\\logs\\client-loading.log", line);
    bool result = originalLoad(self, spells, associations);
    snprintf(line, sizeof(line), "ticks=%lu spell_load=end elapsed_ms=%lu success=%d fast_fields=%u fallback_fields=%u\r\n",
        GetTickCount(), GetTickCount() - start, result, fastCount - beforeFast, fallbackCount - beforeFallback);
    trasc_camera::logLine("Z:\\logs\\client-loading.log", line);
    return result;
}

// Only CALL operands in this build's spell constructor are redirected. The
// original number reader remains available and all other callers retain it.
// Exact sites are checked before any write; a changed client fails closed.
static const DWORD numberCalls[] = {
    // Generated from the verified 2013 constructor; see loading-0418.md.
    0xae734, 0xae830, 0xae83f, 0xae84e, 0xae85d, 0xae86f, 0xae87e, 0xae88d,
    0xae8a7, 0xae8c8, 0xae8e9, 0xae905, 0xae917, 0xae934, 0xae958, 0xae97c,
    0xae9a0, 0xae9bc, 0xae9ce, 0xae9e0, 0xae9f2, 0xaea0f, 0xaea2b, 0xaea3d,
    0xaea4f, 0xaea61, 0xaea73, 0xaea85, 0xaeaa5, 0xaeac1, 0xaead3, 0xaeae5,
    0xaeaf7, 0xaeb09, 0xaeb2c, 0xaeb4e, 0xaeb60, 0xaeb6c, 0xaeb7e, 0xaeb90,
    0xaeba7, 0xaebb9, 0xaebd0, 0xaebea, 0xaebfc, 0xaec13, 0xaec2a, 0xaec41,
    0xaec58, 0xaec83, 0xaec95, 0xaeca7, 0xaecb9, 0xaecd0, 0xaece7, 0xaecfe,
    0xaed10, 0xaed25, 0xaed37, 0xaed4e, 0xaed60, 0xaed72, 0xaed97, 0xaeda9,
    0xaedbb, 0xaedcd, 0xaeddf, 0xaedf1, 0xaee03, 0xaee15, 0xaee27, 0xaee3c,
    0xaee4e, 0xaee60, 0xaee72, 0xaee89, 0xaeea0, 0xaeeb7, 0xaeec9, 0xaeede,
    0xaeef0, 0xaef02, 0xaef14, 0xaef26, 0xaef38, 0xaef4a, 0xaef5c, 0xaef76,
    0xaef8d, 0xaefa4, 0xaefbb, 0xaefd2, 0xaefe4, 0xaeff6, 0xaf00d, 0xaf01c,
    0xaf033, 0xaf045, 0xaf057, 0xaf069, 0xaf080, 0xaf097, 0xaf0a9, 0xaf0c3,
    0xaf0da, 0xaf0f1, 0xaf108, 0xaf114, 0xaf126, 0xaf138, 0xaf14f, 0xaf164,
    0xaf176, 0xaf188, 0xaf19a, 0xaf1c3, 0xaf273, 0xaf28a, 0xaf29c, 0xaf2b3,
    0xaf2bf
};

inline bool validateCalls(const BYTE *image) {
    for (DWORD rva : numberCalls) {
        BYTE opcode = 0; DWORD displacement = 0;
        if (!trasc_camera::read(image + rva, opcode) || opcode != 0xe8
            || !trasc_camera::read(image + rva + 1, displacement)
            || rva + 5 + displacement != 0x4089a0) return false;
    }
    return true;
}

inline bool patchCalls(BYTE *image, NumberReader replacement) {
    if (!validateCalls(image)) return false;
    BYTE *start = image + numberCalls[0];
    SIZE_T size = numberCalls[sizeof(numberCalls)/sizeof(numberCalls[0])-1] + 5 - numberCalls[0];
    DWORD protection = 0, ignored = 0;
    if (!VirtualProtect(start, size, PAGE_EXECUTE_READWRITE, &protection)) return false;
    for (DWORD rva : numberCalls) {
        DWORD displacement = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(replacement)
            - reinterpret_cast<ULONG_PTR>(image + rva + 5));
        memcpy(image + rva + 1, &displacement, sizeof(displacement));
    }
    FlushInstructionCache(GetCurrentProcess(), start, size);
    VirtualProtect(start, size, protection, &ignored);
    return true;
}

inline void install() {
    static bool attempted = false;
    if (attempted) return;
    attempted = true; // DirectInput8Create runs on EQ's startup thread.
    char mode[16] = {};
    GetEnvironmentVariableA(marker, mode, sizeof(mode));
    bool fast = !strcmp(mode, "fast");
    if (!fast && strcmp(mode, "profile")) return;
    BYTE *image = reinterpret_cast<BYTE *>(GetModuleHandleW(NULL));
    if (!GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "wine_get_version") || !trasc_camera::supported(image)) return;
    DWORD current = 0;
    const DWORD slot = 0x5c6144, expected = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(image + 0x673f0));
    if (!trasc_camera::read(image + slot, current) || current != expected || !validateCalls(image)) {
        trasc_camera::logLine("Z:\\logs\\client-loading.log", "adapter=v1 status=layout_mismatch\r\n");
        return;
    }
    originalNumber = reinterpret_cast<NumberReader>(image + 0x4089a0);
    originalLoad = reinterpret_cast<SpellLoader>(image + 0x673f0);
    DWORD protection = 0, ignored = 0;
    if (!VirtualProtect(image + slot, sizeof(DWORD), PAGE_READWRITE, &protection)) return;
    *reinterpret_cast<SpellLoader *>(image + slot) = reinterpret_cast<SpellLoader>(&load);
    VirtualProtect(image + slot, sizeof(DWORD), protection, &ignored);
    bool applied = fast && patchCalls(image, number);
    trasc_camera::logLine("Z:\\logs\\client-loading.log", applied
        ? "adapter=v1 mode=fast status=installed\r\n" : "adapter=v1 mode=profile status=installed\r\n");
}
}
