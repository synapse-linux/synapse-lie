/* SPDX-License-Identifier: MIT */
/* Only linked into the synthetic test executor; never a production timer. */
#include <inttypes.h>
#include <time.h>
static uint64_t fixture_clock(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return 0;
    return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;
}
static bool fixture_trace(unsigned sequence, unsigned from, size_t end,
                          uint64_t begin_ns, uint64_t end_ns) {
    const char *path=getenv("LIE_BENCH_TEST_TRACE");
    if (!path) return true;
    FILE *f=fopen(path,"a");
    if (!f) return false;
    bool ok=fprintf(f,"%u %u %zu %" PRIu64 " %" PRIu64 "\n",
                    sequence,from,end,begin_ns,end_ns)>0;
    return fclose(f)==0 && ok;
}
