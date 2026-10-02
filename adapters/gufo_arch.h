/* SPDX-License-Identifier: MIT */
#ifndef LIE_GUFO_ARCH_H
#define LIE_GUFO_ARCH_H
#include <string.h>
/* HIP can append feature flags, e.g. gfx1150:xnack-. No prefix/ISA spoofing. */
static inline int lie_gufo_arch_matches(const char *actual, const char *expected) {
    if (!actual || !expected ||
        (strcmp(expected, "gfx1150") && strcmp(expected, "gfx1151"))) return 0;
    size_t n = strlen(expected);
    return !strncmp(actual, expected, n) && (actual[n] == '\0' || actual[n] == ':');
}
#endif
