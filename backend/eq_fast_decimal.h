// Fast subset of ROF2's caret-delimited integer reader. All other inputs use
// the original reader, including whitespace, overflow and long/truncated fields.
#pragma once
#ifdef _MSC_VER
#pragma optimize("gt", on)
#endif
namespace trasc_loading {
inline bool decimal(const char **cursor, int separator, int &value) {
    if (!cursor || !*cursor || separator != '^') return false;
    const char *p = *cursor;
    bool negative = *p == '-';
    if (*p == '-' || *p == '+') ++p;
    const char *digits = p;
    unsigned number = 0, count = 0;
    while (*p >= '0' && *p <= '9') {
        if (++count > 9) return false;
        number = number * 10 + static_cast<unsigned>(*p++ - '0');
    }
    if (*p && *p != '^' && *p != '\r' && *p != '\n') return false;
    if (p == digits && digits != *cursor) return false;
    value = negative ? -static_cast<int>(number) : static_cast<int>(number);
    *cursor = *p == '^' ? p + 1 : p;
    return true;
}
#ifdef _MSC_VER
#pragma optimize("", on)
#endif
}
