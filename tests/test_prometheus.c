/* SPDX-License-Identifier: MIT */
#include "lie/prometheus.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"CHECK failed line %d: %s\n",__LINE__,#x); abort(); } } while (0)
static const char valid[] =
    "# TYPE runtime_ready gauge\nruntime_ready 0\n"
    "runtime_uptime_seconds 2\nllm_tokens_generated_total 10\n"
    "# TYPE http_server_requests_seconds histogram\n"
    "http_server_requests_seconds_bucket{method=\"GET\",le=\"1\"} 1\n"
    "http_server_requests_seconds_bucket{le=\"+Inf\",method=\"GET\"} 2\n"
    "http_server_requests_seconds_count{method=\"GET\"} 2\n"
    "http_server_requests_seconds_sum{method=\"GET\"} 3\n";
int main(void) {
    lie_scrape a, b; char error[128]; double rate;
    CHECK(!lie_prometheus_check(valid, &a, error, sizeof(error)));
    CHECK(a.histograms == 1 && a.generated_tokens == 10);
    b = a; b.generated_tokens = 20; b.uptime_seconds = 3;
    CHECK(lie_scrape_token_rate(&a, &b, 2, 1, &rate) && rate == 5);
    CHECK(!lie_scrape_token_rate(NULL, &b, 2, 1, &rate));
    CHECK(!lie_scrape_token_rate(&a, &b, 0, 1, &rate));
    CHECK(!lie_scrape_token_rate(&a, &b, NAN, 1, &rate));
    CHECK(!lie_scrape_token_rate(&a, &b, 1, 0, &rate));
    b.generated_tokens = 1; CHECK(!lie_scrape_token_rate(&a, &b, 1, 1, &rate));
    b = a; b.uptime_seconds = 0; CHECK(!lie_scrape_token_rate(&a, &b, 1, 1, &rate));
    b = a; b.layout_hash++; CHECK(!lie_scrape_token_rate(&a, &b, 1, 1, &rate));
    b = a; CHECK(lie_scrape_token_rate(&a, &b, 1, 1, &rate) && rate == 0);
    const char *bad[] = {
        "runtime_ready 0\n", "runtime_ready{a=\"unfinished\\\"} 0\n",
        "runtime_ready{a=\"x\",a=\"y\"} 0\n", "# TYPE x nonsense\n",
        "runtime_ready NaN\n", "runtime_ready 0 trailing\n"
    };
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) CHECK(lie_prometheus_check(bad[i], &a, error, sizeof(error)));
    /* Malformed input at every byte boundary must not read past its terminator. */
    for (size_t i = 0; i < sizeof(valid) - 1; ++i) {
        char *prefix = malloc(i + 1); CHECK(prefix); memcpy(prefix, valid, i); prefix[i] = 0;
        (void)lie_prometheus_check(prefix, &a, error, sizeof(error)); free(prefix);
    }
    puts("monitor parser and deltas: zero/first sample/reset/restart/series/bucket layout/time/truncation PASS");
}
