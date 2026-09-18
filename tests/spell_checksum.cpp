// Harness template; build_checksum_fixture.py injects original and overlaid
// upstream functions so differential testing covers the actual production edit.
#include "eq_spell_checksum.h"
#include <assert.h>
#include <stdio.h>
#include <vector>
#include <chrono>
#ifndef _WIN32
#define __cdecl
#endif
struct mckey { union { int x; unsigned char a[4]; char sa[4]; }; };
struct OurDetours {
    uintptr_t addr; unsigned count; unsigned char array[50]; OurDetours *pNext;
};
static OurDetours *ourdetours = NULL;
static unsigned table[256], *extern_array0 = table, *extern_array1 = table;
static unsigned *EQADDR_ENCRYPTPAD0 = table, *EQADDR_ENCRYPTPAD1 = table;
static int gDetourCS = 0, locks = 0;
struct CAutoLock { explicit CAutoLock(int *) { ++locks; } ~CAutoLock() { --locks; } };
static bool enabled = false;
static unsigned fastCalls = 0, fallbackCalls = 0;
extern "C" bool trasc_spell_checksum_fast() { return enabled; }
extern "C" void trasc_spell_checksum_result(bool fast, unsigned) { if (fast) ++fastCalls; else ++fallbackCalls; }

// UPSTREAM_FUNCTION_BODIES

static void compare(unsigned char *data, int count) {
    unsigned a = legacy_memcheck0(data,count);
    for (bool fast : {false,true}) {
        enabled=fast; assert(static_cast<unsigned>(patched_memcheck0(data,count))==a);
        for (unsigned key : {0u,1u,0xff001122u,0xffffffffu}) {
            mckey k; k.x=static_cast<int>(key);
            assert(patched_memcheck1(data,count,k)==legacy_memcheck1(data,count,k));
        }
        assert(locks==0);
    }
}
int main() {
    for(unsigned i=0;i<256;++i) {
        unsigned x=i;
        for(int bit=0;bit<8;++bit) x=(x>>1)^((x&1)?0xedb88320u:0u);
        table[i]=x;
    }
    std::vector<unsigned char> data(8192); unsigned seed=919;
    for(auto &byte:data) { seed=seed*1664525u+1013904223u; byte=static_cast<unsigned char>(seed>>24); }
    OurDetours nodes[3] = {};
    nodes[0].pNext=&nodes[1]; nodes[1].pNext=&nodes[2]; ourdetours=nodes;
    uintptr_t base=reinterpret_cast<uintptr_t>(data.data());
    for(int count : {0,1,7,1256,8192}) {
        for(int offset : {-50,-1,0,1,31,1255,8191,8192}) {
            nodes[0].addr=base+offset; nodes[0].count=32;
            nodes[1].addr=base+17; nodes[1].count=19;
            nodes[2].addr=base+100000; nodes[2].count=0;
            for(unsigned i=0;i<50;++i) { nodes[0].array[i]=static_cast<unsigned char>(i^37);nodes[1].array[i]=static_cast<unsigned char>(i^98); }
            compare(data.data(),count);
        }
    }
    // Disjoint lists, disabled nodes, list mutations and boundary adjacency.
    nodes[0].addr=base-32; nodes[0].count=32; nodes[1].addr=base+data.size();
    for(int count=0;count<8192;count+=97) compare(data.data(),count);
    enabled=true;
    assert(trasc_checksum::disjoint(data.data(),8192,ourdetours));
    nodes[1].addr=base+8;
    assert(!trasc_checksum::disjoint(data.data(),8192,ourdetours));
    compare(data.data(),8192);
    assert(!trasc_checksum::disjoint(data.data(),-1,ourdetours));
    assert(!trasc_checksum::disjoint(reinterpret_cast<unsigned char *>(UINTPTR_MAX-1),5,ourdetours));
    nodes[0].addr=UINTPTR_MAX-1;nodes[0].count=4;
    assert(!trasc_checksum::disjoint(data.data(),1,ourdetours));
    assert(fastCalls && fallbackCalls);

    std::vector<OurDetours> registry(120);
    for(size_t i=0;i<registry.size();++i) {
        registry[i].addr=0x10000+i*64;registry[i].count=8;
        registry[i].pNext=i+1<registry.size()?&registry[i+1]:NULL;
    }
    ourdetours=registry.data();
    unsigned baseline=0;
    for(bool fast : {false,true}) {
        enabled=fast; volatile unsigned sum=0; fastCalls=fallbackCalls=0;
        auto start=std::chrono::steady_clock::now();
        for(unsigned i=0;i<4096;++i) sum+=static_cast<unsigned>(patched_memcheck0(data.data(),1256));
        auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
        if(fast) assert(sum==baseline && fastCalls==4096 && fallbackCalls==0);else baseline=sum;
        printf("spell checksum fixture: fast=%d records=4096 bytes=5144576 patches=120 elapsed_ms=%lld checksum=%u\n",fast,static_cast<long long>(ms),sum);
    }
    puts("PASS: actual upstream checksum bodies, keyed seeds, overlap fallback, list mutation, boundaries and scope switch");
}
