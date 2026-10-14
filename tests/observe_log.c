#include <assert.h>
#include <stdlib.h>
#include "../native/presentation/observe-log.h"

int main(void) {
    FILE *file = tmpfile();
    assert(file);
    struct trasc_observe_log log = {.file = file};
    char escaped[128];
    trasc_observe_quote(escaped, sizeof(escaped), "mouse\"\\\n\001\377");
    assert(!strcmp(escaped, "mouse\\u0022\\u005c\\u000a\\u0001\\u00ff"));
    char small[5];
    trasc_observe_quote(small, sizeof(small), "a\nignored");
    assert(!strcmp(small, "a"));
    char line[TRASC_OBSERVE_LINE_BYTES + 10];
    memset(line, 'x', sizeof(line) - 1);
    line[sizeof(line) - 1] = 0;
    assert(!trasc_observe_emit(&log, 0, "%s", line));
    assert(log.dropped == 1 && log.bytes == 0 && !log.full);
    while (trasc_observe_emit(&log, 0, "{\"record\":\"sample\",\"value\":123456789}")) {}
    assert(log.full && !log.failed && log.bytes <= TRASC_OBSERVE_MAX_BYTES - TRASC_OBSERVE_END_RESERVE);
    assert(trasc_observe_emit(&log, 1, "{\"record\":\"end\",\"dropped\":%llu}", (unsigned long long)log.dropped));
    assert(log.bytes <= TRASC_OBSERVE_MAX_BYTES);
    assert(fflush(file) == 0 && fseek(file, 0, SEEK_END) == 0);
    assert((size_t)ftell(file) == log.bytes);
    log.bytes = TRASC_OBSERVE_MAX_BYTES;
    assert(!trasc_observe_emit(&log, 1, "end"));
    fclose(file);
    puts("PASS: escaped device labels, oversized lines, 128 KiB cap and reserved end record");
    return 0;
}
