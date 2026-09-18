#include "../backend/eq_fast_decimal.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <string>
#include <chrono>

// Independent reference: copy at most 511 field bytes, consume the full field,
// leave CR/LF in place, then use the C runtime conversion just like ROF2.
static int reference(const char **cursor, int separator) {
    char field[512]; size_t n = 0;
    const char *p = *cursor;
    while (*p && *p != '\r' && *p != '\n' && *p != separator) {
        if (n < 511) field[n++] = *p;
        ++p;
    }
    field[n] = 0; *cursor = *p == separator ? p+1 : p;
    return atoi(field);
}
static void compare(const std::string &text, int separator = '^') {
    const char *fast = text.c_str(), *slow = fast;
    int expected = reference(&slow, separator), actual = 123;
    bool accepted = trasc_loading::decimal(&fast, separator, actual);
    if (!accepted) { assert(fast == text.c_str()); actual = reference(&fast, separator); }
    assert(actual == expected && fast == slow);
}
int main() {
    const char *cases[] = {"", "^next", "0", "-0^", "+12\r\n", "999999999^", "-999999999^",
        "2147483647^", "-2147483648^", "2147483648^", "-2147483649^", " 12^", "\t-3^", "+^",
        "-^", "1.5^", "1e3^", "12z^", "\xff^", "\nrest", "\r\nrest", "000000000000001^"};
    for (const char *s : cases) { compare(s); compare(s, '|'); }
    compare(std::string(600, '9') + "^rest");
    unsigned seed = 918;
    for (int i=0; i<100000; ++i) {
        seed = seed * 1664525u + 1013904223u;
        int value = static_cast<int>(seed % 1000000000u);
        compare(std::to_string(value) + "^rest");
        compare("-" + std::to_string(value) + "\r\n");
    }
    // Timing is evidence, never a flaky release threshold. Hardware acceptance
    // must compare complete server-to-character loads, not this microbenchmark.
    std::string row;
    for(int i=0; i<180; ++i) row += std::to_string((i*17)%5000) + '^';
    unsigned baseline = 0;
    for (bool fast : {false, true}) {
        volatile unsigned sum = 0;
        auto start = std::chrono::steady_clock::now();
        for(int i=0; i<40914; ++i) {
            const char *p = row.c_str();
            while(*p) { int value; if (!fast || !trasc_loading::decimal(&p, '^', value)) value = reference(&p, '^'); sum += value; }
        }
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
        printf("spell integer fixture: fast=%d fields=%d elapsed_ms=%lld checksum=%u\n", fast,40914*180,static_cast<long long>(elapsed),sum);
        if (fast) assert(sum == baseline); else baseline = sum;
    }
    puts("PASS: integer values, cursor advancement, delimiters, signs, overflow and fallback");
}
