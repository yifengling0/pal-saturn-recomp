#pragma once
#include <cstdlib>
#include <cstdint>
#include <cstring>

// Strict PAL_DUMP target: r0..r15, or a complete hexadecimal uint32 address.
inline bool pal_parse_dump_target(const char* text, int& reg, uint32_t& addr) {
    reg = -1;
    addr = 0;
    if (!text || !*text) return false;
    if (text[0] == 'r') {
        if (!text[1]) return false;
        unsigned n = 0;
        for (const char* p = text + 1; *p; ++p) {
            if (*p < '0' || *p > '9') return false;
            n = n * 10 + unsigned(*p - '0');
            if (n > 15) return false;
        }
        reg = int(n);
        return true;
    }
    const char* p = text;
    if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X')) p += 2;
    if (!*p || std::strlen(p) > 8) return false;
    uint32_t n = 0;
    for (; *p; ++p) {
        unsigned digit;
        if (*p >= '0' && *p <= '9') digit = unsigned(*p - '0');
        else if (*p >= 'a' && *p <= 'f') digit = unsigned(*p - 'a' + 10);
        else if (*p >= 'A' && *p <= 'F') digit = unsigned(*p - 'A' + 10);
        else return false;
        n = (n << 4) | digit;
    }
    addr = n;
    return true;
}
