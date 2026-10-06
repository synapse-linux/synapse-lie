/* SPDX-License-Identifier: MIT */
/* Host-only debugger fixture: no model, GPU API or inference arithmetic. */
#include <signal.h>
#include <stdint.h>
#include <string.h>

volatile int32_t routing_sink;

__attribute__((noinline)) int lie_iq2_mixed_tiles(const int32_t *counts,
    int experts, int tokens, int used, void *tiles, int capacity, void *spans)
{
    (void)tiles; (void)capacity; (void)spans;
    routing_sink = counts[0] + experts + tokens + used;
    return 1;
}

int main(int argc, char **argv)
{
    const char *mode = argc == 2 ? argv[1] : "good";
    int32_t counts[512];
    for (int i = 0; i < 512; ++i) counts[i] = 40;
    if (strcmp(mode, "bad-count") == 0) counts[0] = -1;
    int calls = strcmp(mode, "short") == 0 ? 95 :
        strcmp(mode, "extra") == 0 ? 97 : 96;
    for (int i = 0; i < calls; ++i) {
        const int tokens = strcmp(mode, "bad-shape") == 0 ? 2047 : 2048;
        lie_iq2_mixed_tiles(counts, 512, tokens, 10, counts, 512, counts);
    }
    if (strcmp(mode, "signal") == 0) raise(SIGTERM);
    return strcmp(mode, "exit-error") == 0 ? 7 : 0;
}
