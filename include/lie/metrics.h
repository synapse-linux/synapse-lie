/* SPDX-License-Identifier: MIT */
#ifndef LIE_METRICS_H
#define LIE_METRICS_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_MAX_TAGS 4
#define LIE_MAX_BUCKETS 12
#define LIE_MAX_SERIES 128
#define LIE_MAX_METERS 32
/* Copied at registration. No unregister: handles live until registry destruction.
 * Updates/snapshots are thread-safe. Destruction requires all users joined.
 * Callers supply a monotonic nanosecond clock; NULL selects CLOCK_MONOTONIC. */
typedef struct lie_metrics lie_metrics;
typedef unsigned lie_meter;
typedef uint64_t (*lie_clock)(void *context);
typedef enum { LIE_COUNTER, LIE_GAUGE, LIE_TIMER } lie_metric_type;
typedef enum { LIE_METRIC_OK, LIE_METRIC_INVALID, LIE_METRIC_CONFLICT,
               LIE_METRIC_FULL, LIE_METRIC_NOT_FOUND, LIE_METRIC_NOMEM } lie_metric_status;
typedef struct { const char *key; const char *value; } lie_tag;
typedef struct {
    const char *name;
    const char *description;
    const char *unit; /* NULL or empty: no base unit; Timer must use seconds. */
    lie_metric_type type;
    const double *buckets; /* Timer seconds, positive ascending finite bounds. */
    size_t bucket_count;
} lie_metric_spec;
lie_metrics *lie_metrics_create(lie_clock clock, void *context);
void lie_metrics_destroy(lie_metrics *registry);
lie_metric_status lie_metrics_register(lie_metrics *, const lie_metric_spec *,
                                      const lie_tag *, size_t, lie_meter *);
lie_metric_status lie_counter_add(lie_metrics *, lie_meter, double increment);
lie_metric_status lie_gauge_set(lie_metrics *, lie_meter, double value);
lie_metric_status lie_timer_record(lie_metrics *, lie_meter, double seconds);
/* All returned strings are caller-owned (free). One coherent registry snapshot
 * per export, copied under a short mutex; serialization happens after unlock. */
char *lie_metrics_names(lie_metrics *);
lie_metric_status lie_metrics_detail(lie_metrics *, const char *name,
                                    const lie_tag *filters, size_t count, char **json);
char *lie_metrics_prometheus(lie_metrics *);
uint64_t lie_monotonic_ns(void);
#ifdef __cplusplus
}
#endif
#endif
