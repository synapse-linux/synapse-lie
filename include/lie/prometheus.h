/* SPDX-License-Identifier: MIT */
#ifndef LIE_PROMETHEUS_H
#define LIE_PROMETHEUS_H
#include <stddef.h>
/* Strict validator for OUR finite-valued 0.0.4 subset, not a PromQL engine or
 * substitute for promtool. Independently implemented from the exporter. */
typedef struct {
    double generated_tokens, uptime_seconds, ready;
    size_t samples, histograms;
    unsigned long long layout_hash;
} lie_scrape;
int lie_prometheus_check(const char *text, lie_scrape *out, char *error, size_t cap);
/* 1: delta valid; 0: n/d (first sample, reset, changed series/buckets or time).
 * Instance identity is checked by the caller, never inferred from seed/PID alone. */
int lie_scrape_token_rate(const lie_scrape *previous, const lie_scrape *current,
                         double elapsed_seconds, int same_instance, double *rate);
#endif
