/* Fixed-size JSONL output budget for read-only native diagnostics. */
#ifndef TRASC_OBSERVE_LOG_H
#define TRASC_OBSERVE_LOG_H
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define TRASC_OBSERVE_MAX_BYTES (128u * 1024u)
#define TRASC_OBSERVE_END_RESERVE 2048u
#define TRASC_OBSERVE_LINE_BYTES 4096u
struct trasc_observe_log {
    FILE *file;
    size_t bytes;
    uint64_t records, dropped;
    int full, failed;
};

static int trasc_observe_emit(struct trasc_observe_log *log, int final,
                              const char *format, ...) {
    char line[TRASC_OBSERVE_LINE_BYTES];
    va_list args;
    va_start(args, format);
    int length = vsnprintf(line, sizeof(line), format, args);
    va_end(args);
    if (length < 0 || (size_t)length >= sizeof(line) - 1u) {
        log->dropped++;
        return 0;
    }
    size_t bytes = (size_t)length;
    line[bytes++] = '\n';
    size_t limit = TRASC_OBSERVE_MAX_BYTES - (final ? 0u : TRASC_OBSERVE_END_RESERVE);
    if (log->failed || log->bytes > limit || bytes > limit - log->bytes) {
        log->dropped++;
        log->full = 1;
        return 0;
    }
    if (fwrite(line, 1, bytes, log->file) != bytes) {
        log->failed = 1;
        return 0;
    }
    log->bytes += bytes;
    log->records++;
    return 1;
}

/* Escape device-name bytes without trusting them as JSON or UTF-8. */
static void trasc_observe_quote(char *out, size_t capacity, const char *source) {
    size_t used = 0;
    if (!capacity) return;
    if (!source) source = "";
    for (; *source && used + 1u < capacity; source++) {
        unsigned char byte = (unsigned char)*source;
        if (byte >= 32u && byte < 127u && byte != '"' && byte != '\\') {
            out[used++] = (char)byte;
        } else if (used + 6u < capacity) {
            int size = snprintf(out + used, capacity - used, "\\u%04x", byte);
            if (size != 6) break;
            used += 6u;
        } else break;
    }
    out[used] = 0;
}
#endif
