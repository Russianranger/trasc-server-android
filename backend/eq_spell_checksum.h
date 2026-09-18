// Equivalent fast path for ordinary spell-data checksums. Overlapping patched
// memory retains the upstream implementation. No changed checksums or cache.
#pragma once
#include <stdint.h>
#include <stddef.h>

extern "C" bool trasc_spell_checksum_fast();
extern "C" void trasc_spell_checksum_result(bool fast, unsigned bytes);

#ifdef _MSC_VER
#pragma optimize("gt", on)
#endif
namespace trasc_checksum {
template<class Node>
bool disjoint(const unsigned char *buffer, int count, const Node *head) {
    uintptr_t start = reinterpret_cast<uintptr_t>(buffer);
    if (!buffer || count < 0 || static_cast<uintptr_t>(count) > UINTPTR_MAX-start) return false;
    uintptr_t end = start + static_cast<uintptr_t>(count);
    for (const Node *node = head; node; node = node->pNext) {
        if (!node->count) continue;
        uintptr_t patch = node->addr;
        if (static_cast<uintptr_t>(node->count) > UINTPTR_MAX-patch) return false;
        if (start < patch+node->count && patch < end) return false;
    }
    return true;
}

inline unsigned crc(const unsigned char *buffer, int count, const unsigned *table, unsigned seed) {
    for (int i=0; i<count; ++i) seed = (seed >> 8) ^ table[(seed ^ buffer[i]) & 255];
    return seed;
}
}
#ifdef _MSC_VER
#pragma optimize("", on)
#endif
