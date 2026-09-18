// Optional exact-build spell parser experiment. No file caches or data edits.
#pragma once
#include "eq_camera_mouse.h"
#include "eq_fast_decimal.h"
#include "eq_spell_checksum.h"

namespace trasc_loading {
static const char marker[] = "TRASC_EQ_LOAD_V2";
typedef int (__cdecl *NumberReader)(const char **, int);
typedef bool (__thiscall *SpellLoader)(void *, const char *, const char *);
typedef bool (__thiscall *TextLoader)(void *, const char *, const char *, void *);
typedef int (__thiscall *Associations)(void *, const char *, int);
typedef void (__thiscall *MapLoader)(void *);
typedef void *(__cdecl *RecordLoader)(const char *);
typedef DWORD (__cdecl *Checksum)(const char *);
typedef int (__thiscall *NextLine)(void *);
typedef DWORD (__thiscall *RecordChecksum)(void *);
static NumberReader originalNumber = NULL;
static SpellLoader originalLoad = NULL;
static TextLoader originalText = NULL;
static Associations originalAssociations = NULL;
static MapLoader originalMap = NULL;
static RecordLoader originalRecord = NULL;
static Checksum originalChecksum = NULL;
static NextLine originalNext = NULL;
static RecordChecksum originalRecordChecksum = NULL;
static unsigned fastCount = 0, fallbackCount = 0;
static volatile LONG profileThread = 0;
static bool fastMode = false;
static unsigned checksumDepth = 0, fastChecksums = 0, fallbackChecksums = 0;
static unsigned checksumBytes = 0;
struct LineContext {
    unsigned lines = 0, records = 0, recordChecksums = 0;
    DWORD readMs = 0, recordMs = 0, recordChecksumMs = 0;
    void reset() { lines = records = recordChecksums = 0; readMs = recordMs = recordChecksumMs = 0; }
};
static LineContext spellLines, associationLines;
static LineContext *activeLines = NULL;
inline bool profiling() { return static_cast<DWORD>(InterlockedCompareExchange(&profileThread, 0, 0)) == GetCurrentThreadId(); }

inline void stageLog(const char *stage, DWORD start, int success, const LineContext *lines = NULL) {
    char line[384];
    snprintf(line, sizeof(line), "ticks=%lu stage=%s elapsed_ms=%lu result=%d read_ms=%lu record_ms=%lu record_checksum_ms=%lu records=%u record_checksums=%u lines=%u\r\n",
        GetTickCount(), stage, GetTickCount()-start, success, lines ? lines->readMs : 0,
        lines ? lines->recordMs : 0, lines ? lines->recordChecksumMs : 0,
        lines ? lines->records : 0, lines ? lines->recordChecksums : 0, lines ? lines->lines : 0);
    trasc_camera::logLine("Z:\\logs\\client-loading.log", line);
}

static int __fastcall nextLine(void *reader, void *) {
    if (!profiling() || !activeLines) return originalNext(reader);
    DWORD start = GetTickCount();
    int result = originalNext(reader);
    activeLines->readMs += GetTickCount() - start;
    ++activeLines->lines;
    return result;
}

static DWORD __fastcall recordChecksum(void *record, void *) {
    if (!profiling() || !activeLines) return originalRecordChecksum(record);
    DWORD start = GetTickCount();
    ++checksumDepth;
    DWORD result = originalRecordChecksum(record);
    --checksumDepth;
    activeLines->recordChecksumMs += GetTickCount() - start;
    ++activeLines->recordChecksums;
    return result;
}

static void *__cdecl record(const char *line) {
    if (!profiling() || !activeLines) return originalRecord(line);
    DWORD start = GetTickCount();
    void *result = originalRecord(line);
    activeLines->recordMs += GetTickCount() - start;
    ++activeLines->records;
    return result;
}

static bool __fastcall textLoad(void *self, void *, const char *spells, const char *associations, void *table) {
    if (!profiling() || activeLines) return originalText(self, spells, associations, table);
    spellLines.reset(); activeLines = &spellLines;
    DWORD start = GetTickCount();
    bool result = originalText(self, spells, associations, table);
    activeLines = NULL;
    stageLog("text_and_associations", start, result, &spellLines);
    return result;
}

static int __fastcall associationsLoad(void *self, void *, const char *path, int flags) {
    if (!profiling() || activeLines != &spellLines) return originalAssociations(self, path, flags);
    associationLines.reset(); activeLines = &associationLines;
    DWORD start = GetTickCount();
    int result = originalAssociations(self, path, flags);
    activeLines = &spellLines;
    stageLog("associations", start, result, &associationLines);
    return result;
}

static DWORD checksum(const char *path, const char *stage) {
    DWORD start = GetTickCount();
    bool active = profiling();
    if (active) ++checksumDepth;
    DWORD result = originalChecksum(path);
    if (active) --checksumDepth;
    if (profiling()) stageLog(stage, start, result != 0);
    return result;
}
static DWORD __cdecl spellChecksum(const char *path) { return checksum(path, "spell_checksum"); }
static DWORD __cdecl associationChecksum(const char *path) { return checksum(path, "association_checksum"); }
static void __fastcall mapLoad(void *self, void *) {
    DWORD start = GetTickCount();
    originalMap(self);
    if (profiling()) stageLog("post_load_mapping", start, 1);
}

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
    if (InterlockedCompareExchange(&profileThread, static_cast<LONG>(GetCurrentThreadId()), 0))
        return originalLoad(self, spells, associations);
    DWORD start = GetTickCount();
    unsigned beforeFast = fastCount, beforeFallback = fallbackCount;
    fastChecksums = fallbackChecksums = checksumBytes = checksumDepth = 0;
    char line[384];
    snprintf(line, sizeof(line), "ticks=%lu spell_load=start\r\n", start);
    trasc_camera::logLine("Z:\\logs\\client-loading.log", line);
    bool result = originalLoad(self, spells, associations);
    snprintf(line, sizeof(line), "ticks=%lu spell_load=end elapsed_ms=%lu success=%d fast_fields=%u fallback_fields=%u fast_checksums=%u fallback_checksums=%u checksum_bytes=%u\r\n",
        GetTickCount(), GetTickCount() - start, result, fastCount - beforeFast, fallbackCount - beforeFallback, fastChecksums, fallbackChecksums, checksumBytes);
    trasc_camera::logLine("Z:\\logs\\client-loading.log", line);
    activeLines = NULL;
    InterlockedExchange(&profileThread, 0);
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

struct StageCall { DWORD rva, target; const void *replacement; };
static const StageCall stageCalls[] = {
    {0x6740e, 0x1c1c30, reinterpret_cast<const void *>(textLoad)},
    {0x1c1e9c, 0x3d50b0, reinterpret_cast<const void *>(associationsLoad)},
    {0x6741e, 0x408d90, reinterpret_cast<const void *>(spellChecksum)},
    {0x6742a, 0x408d90, reinterpret_cast<const void *>(associationChecksum)},
    {0x6743a, 0x67300, reinterpret_cast<const void *>(mapLoad)},
    {0x1c1dbe, 0xafaf0, reinterpret_cast<const void *>(record)},
    {0x1c1dd3, 0xaca30, reinterpret_cast<const void *>(recordChecksum)},
    {0x1c1d5d, 0x408860, reinterpret_cast<const void *>(nextLine)},
    {0x1c1e6b, 0x408860, reinterpret_cast<const void *>(nextLine)},
    {0x3d4e5f, 0x408860, reinterpret_cast<const void *>(nextLine)},
    {0x3d4e66, 0x408860, reinterpret_cast<const void *>(nextLine)},
    {0x3d4fcf, 0x408860, reinterpret_cast<const void *>(nextLine)}
};

inline bool callMatches(const BYTE *image, DWORD rva, DWORD target) {
    BYTE opcode = 0; DWORD displacement = 0;
    return trasc_camera::read(image+rva, opcode) && opcode == 0xe8
        && trasc_camera::read(image+rva+1, displacement) && rva+5+displacement == target;
}

inline bool validateLayout(const BYTE *image) {
    DWORD current = 0;
    if (!trasc_camera::read(image+0x5c6144, current)
        || current != static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(image+0x673f0))
        || !validateCalls(image)) return false;
    for (const StageCall &site : stageCalls)
        if (!callMatches(image, site.rva, site.target)) return false;
    return true;
}

inline void writeCall(BYTE *image, DWORD rva, const void *replacement) {
    DWORD displacement = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(replacement)
        - reinterpret_cast<ULONG_PTR>(image+rva+5));
    memcpy(image+rva+1, &displacement, sizeof(displacement));
}

inline bool patchLayout(BYTE *image, bool fast) {
    if (!validateLayout(image)) return false;
    // Acquire both write permissions before any mutation. All sites are in the
    // same executable text section and are installed once at startup.
    BYTE *start = image+0x6740e;
    SIZE_T size = 0x3d4fcf+5-0x6740e;
    DWORD textProtection = 0, slotProtection = 0, ignored = 0;
    if (!VirtualProtect(start, size, PAGE_EXECUTE_READWRITE, &textProtection)) return false;
    if (!VirtualProtect(image+0x5c6144, sizeof(DWORD), PAGE_READWRITE, &slotProtection)) {
        VirtualProtect(start, size, textProtection, &ignored);
        return false;
    }
    originalNumber = reinterpret_cast<NumberReader>(image+0x4089a0);
    originalLoad = reinterpret_cast<SpellLoader>(image+0x673f0);
    originalText = reinterpret_cast<TextLoader>(image+0x1c1c30);
    originalAssociations = reinterpret_cast<Associations>(image+0x3d50b0);
    originalMap = reinterpret_cast<MapLoader>(image+0x67300);
    originalRecord = reinterpret_cast<RecordLoader>(image+0xafaf0);
    originalChecksum = reinterpret_cast<Checksum>(image+0x408d90);
    originalNext = reinterpret_cast<NextLine>(image+0x408860);
    originalRecordChecksum = reinterpret_cast<RecordChecksum>(image+0xaca30);
    fastMode = fast;
    for (const StageCall &site : stageCalls) writeCall(image, site.rva, site.replacement);
    if (fast) for (DWORD rva : numberCalls) writeCall(image, rva, reinterpret_cast<const void *>(number));
    *reinterpret_cast<SpellLoader *>(image+0x5c6144) = reinterpret_cast<SpellLoader>(&load);
    FlushInstructionCache(GetCurrentProcess(), start, size);
    VirtualProtect(start, size, textProtection, &ignored);
    VirtualProtect(image+0x5c6144, sizeof(DWORD), slotProtection, &ignored);
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
    if (!patchLayout(image, fast)) {
        trasc_camera::logLine("Z:\\logs\\client-loading.log", "adapter=v2 status=layout_or_protection_mismatch\r\n");
        return;
    }
    trasc_camera::logLine("Z:\\logs\\client-loading.log", fast
        ? "adapter=v2 mode=fast status=installed checksum_range_check=once\r\n" : "adapter=v2 mode=profile status=installed\r\n");
}
}

// Defined only in the eqgame.cpp overlay; the checksum source uses these
// narrow callbacks without a second copy of the loading state.
extern "C" bool trasc_spell_checksum_fast() {
    return trasc_loading::fastMode && trasc_loading::profiling() && trasc_loading::checksumDepth;
}
extern "C" void trasc_spell_checksum_result(bool fast, unsigned bytes) {
    if (fast) { ++trasc_loading::fastChecksums; trasc_loading::checksumBytes += bytes; }
    else ++trasc_loading::fallbackChecksums;
}
