/* SPDX-License-Identifier: MIT */
#include "lie/text.h"
#include <stdint.h>
#include <string.h>
static unsigned utf8_width(unsigned char c) {
    if (c < 0x80) return 1;
    if (c >= 0xc2 && c <= 0xdf) return 2;
    if (c >= 0xe0 && c <= 0xef) return 3;
    if (c >= 0xf0 && c <= 0xf4) return 4;
    return 0;
}
static bool continuation(const unsigned char *p, unsigned used, unsigned char c) {
    if (c < 0x80 || c > 0xbf) return false;
    if (used != 1) return true;
    return !(p[0] == 0xe0 && c < 0xa0) && !(p[0] == 0xed && c > 0x9f) &&
           !(p[0] == 0xf0 && c < 0x90) && !(p[0] == 0xf4 && c > 0x8f);
}
bool lie_utf8_valid(const char *s, size_t n, bool allow_nul) {
    const unsigned char *p = (const unsigned char *)s;
    if (!p && n) return false;
    for (size_t i = 0; i < n;) {
        unsigned w = utf8_width(p[i]);
        if (!w || w > n - i || (!p[i] && !allow_nul)) return false;
        for (unsigned j = 1; j < w; ++j) if (!continuation(p+i, j, p[i+j])) return false;
        i += w;
    }
    return true;
}
bool lie_utf8_feed(lie_utf8_decoder *d, const char *src, size_t n, bool final,
                   char *out, size_t cap, size_t *written) {
    if (!d || (!src && n) || !out || !written || n > (SIZE_MAX-4)/3 || cap < (n+1)*3) return false;
    size_t size = 0;
    for (size_t i = 0; i < n;) {
        unsigned char c = (unsigned char)src[i];
        if (d->used) {
            if (!continuation(d->pending, d->used, c)) {
                memcpy(out+size, "\xef\xbf\xbd", 3); size+=3; d->used=d->wanted=0; continue;
            }
            d->pending[d->used++] = c; ++i;
            if (d->used == d->wanted) {
                memcpy(out+size, d->pending, d->used); size+=d->used; d->used=d->wanted=0;
            }
        } else {
            unsigned w = utf8_width(c); ++i;
            if (!w) { memcpy(out+size, "\xef\xbf\xbd", 3); size+=3; }
            else if (w == 1) out[size++] = (char)c;
            else { d->pending[0]=c; d->used=1; d->wanted=w; }
        }
    }
    if (final && d->used) { memcpy(out+size, "\xef\xbf\xbd", 3); size+=3; d->used=d->wanted=0; }
    *written = size; return true;
}
