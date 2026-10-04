/* SPDX-License-Identifier: MIT */
#include "lie/metrics.h"
#include <json-c/json.h>
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed %s:%d: %s\n", __FILE__, __LINE__, #x); abort(); } } while (0)
static uint64_t time_ns;
static uint64_t clock_now(void *ctx) { (void)ctx; return time_ns; }
static double statistic(lie_metrics *r, const char *name, const lie_tag *filter, size_t n, const char *stat) {
    char *text = NULL; CHECK(lie_metrics_detail(r, name, filter, n, &text) == LIE_METRIC_OK);
    json_object *j = json_tokener_parse(text), *measurements;
    CHECK(j && json_object_object_get_ex(j, "measurements", &measurements));
    double result = NAN;
    for (size_t i = 0; i < json_object_array_length(measurements); ++i) {
        json_object *m = json_object_array_get_idx(measurements, i), *s, *v;
        CHECK(json_object_object_get_ex(m, "statistic", &s) && json_object_object_get_ex(m, "value", &v));
        if (!strcmp(json_object_get_string(s), stat)) result = json_object_get_double(v);
    }
    free(text); json_object_put(j); CHECK(isfinite(result)); return result;
}
typedef struct { lie_metrics *registry; lie_meter counter, timer; } work;
static void *thread(void *p) {
    work *w = p;
    for (unsigned i = 0; i < 2500; ++i) {
        CHECK(!lie_counter_add(w->registry, w->counter, 1));
        CHECK(!lie_timer_record(w->registry, w->timer, .5));
        if (!(i % 100)) { char *s = lie_metrics_prometheus(w->registry); CHECK(s); free(s); }
    }
    return NULL;
}
int main(void) {
    lie_metrics *r = lie_metrics_create(clock_now, NULL); CHECK(r);
    double bounds[] = {.1, 1, 10};
    lie_metric_spec spec = {"llm.request.duration", "Request duration\nseconds\\safe", "seconds", LIE_TIMER, bounds, 3};
    lie_tag a[] = {{"model", "qwen"}, {"backend", "hip"}}, b[] = {{"backend", "hip"}, {"model", "other"}};
    lie_meter ma, mb, duplicate;
    CHECK(!lie_metrics_register(r, &spec, a, 2, &ma));
    CHECK(!lie_metrics_register(r, &spec, b, 2, &mb));
    lie_tag reversed[] = {a[1], a[0]};
    CHECK(!lie_metrics_register(r, &spec, reversed, 2, &duplicate) && duplicate == ma);
    CHECK(!lie_timer_record(r, ma, 2)); CHECK(!lie_timer_record(r, ma, 0)); CHECK(!lie_timer_record(r, mb, 4));
    lie_tag filter = {"backend", "hip"};
    CHECK(statistic(r, spec.name, &filter, 1, "COUNT") == 3);
    CHECK(statistic(r, spec.name, &filter, 1, "TOTAL_TIME") == 6);
    CHECK(statistic(r, spec.name, &filter, 1, "MAX") == 4);
    char *json = NULL;
    CHECK(!lie_metrics_detail(r, spec.name, &filter, 1, &json));
    CHECK(strstr(json, "\"tag\":\"model\"") && !strstr(json, "\"tag\":\"backend\"")); free(json);
    CHECK(!lie_metrics_detail(r, spec.name, a, 2, &json)); CHECK(strstr(json, "\"availableTags\":[]")); free(json);
    lie_tag absent = {"backend", "cuda"};
    CHECK(lie_metrics_detail(r, spec.name, &absent, 1, &json) == LIE_METRIC_NOT_FOUND);
    lie_tag repeat[] = {filter, filter};
    CHECK(lie_metrics_detail(r, spec.name, repeat, 2, &json) == LIE_METRIC_INVALID);
    CHECK(lie_metrics_register(r, &spec, &filter, 1, &duplicate) == LIE_METRIC_CONFLICT);
    spec.description = "drift"; CHECK(lie_metrics_register(r, &spec, a, 2, &duplicate) == LIE_METRIC_CONFLICT);
    spec = (lie_metric_spec){"llm.request.duration.seconds.count", "collision", NULL, LIE_GAUGE, NULL, 0};
    CHECK(lie_metrics_register(r, &spec, NULL, 0, &duplicate) == LIE_METRIC_CONFLICT);
    CHECK(lie_timer_record(r, ma, -1) == LIE_METRIC_INVALID);
    CHECK(lie_timer_record(r, ma, NAN) == LIE_METRIC_INVALID);
    CHECK(lie_counter_add(r, ma, 1) == LIE_METRIC_INVALID);
    time_ns = UINT64_C(179000000000); CHECK(statistic(r, "llm.request.duration", NULL, 0, "MAX") == 4);
    time_ns = UINT64_C(180000000000); CHECK(statistic(r, "llm.request.duration", NULL, 0, "MAX") == 0);
    CHECK(statistic(r, "llm.request.duration", NULL, 0, "COUNT") == 3);
    CHECK(!lie_timer_record(r, ma, .25)); CHECK(statistic(r, "llm.request.duration", NULL, 0, "MAX") == .25);
    spec = (lie_metric_spec){"llm.tokens.generated", "Generated", "tokens", LIE_COUNTER, NULL, 0};
    lie_meter counter; CHECK(!lie_metrics_register(r, &spec, NULL, 0, &counter));
    CHECK(lie_counter_add(r, counter, -1) == LIE_METRIC_INVALID);
    CHECK(lie_counter_add(r, counter, INFINITY) == LIE_METRIC_INVALID);
    work w = {r, counter, ma}; pthread_t workers[4];
    for (size_t i = 0; i < 4; ++i) CHECK(!pthread_create(&workers[i], NULL, thread, &w));
    for (size_t i = 0; i < 4; ++i) CHECK(!pthread_join(workers[i], NULL));
    CHECK(statistic(r, "llm.tokens.generated", NULL, 0, "COUNT") == 10000);
    CHECK(statistic(r, "llm.request.duration", NULL, 0, "COUNT") == 10004);
    char *prom = lie_metrics_prometheus(r); CHECK(prom);
    CHECK(strstr(prom, "llm_tokens_generated_total 10000\n"));
    CHECK(strstr(prom, "llm_request_duration_seconds_bucket{backend=\"hip\",model=\"qwen\",le=\"+Inf\"} 10003\n"));
    CHECK(strstr(prom, "# TYPE llm_request_duration_seconds histogram")); free(prom);
    spec = (lie_metric_spec){"test.value", "Gauge", "bytes", LIE_GAUGE, NULL, 0};
    lie_tag escape = {"kind", "quotes\" slash\\ newline\n"}; lie_meter gauge;
    CHECK(!lie_metrics_register(r, &spec, &escape, 1, &gauge)); CHECK(!lie_gauge_set(r, gauge, 10));
    CHECK(statistic(r, "test.value", NULL, 0, "VALUE") == 10);
    prom = lie_metrics_prometheus(r); CHECK(strstr(prom, "test_value_bytes{kind=\"quotes\\\" slash\\\\ newline\\n\"} 10")); free(prom);
    spec = (lie_metric_spec){"test_value", "collision", "bytes", LIE_GAUGE, NULL, 0};
    CHECK(lie_metrics_register(r, &spec, NULL, 0, &gauge) == LIE_METRIC_CONFLICT);
    lie_metrics_destroy(r);
    r = lie_metrics_create(NULL, NULL); CHECK(r);
    spec = (lie_metric_spec){"bounded", "bounded registration", NULL, LIE_COUNTER, NULL, 0};
    for (unsigned i = 0; i < LIE_MAX_SERIES; ++i) {
        char value[16]; snprintf(value, sizeof(value), "%u", i); lie_tag t = {"slot", value};
        CHECK(!lie_metrics_register(r, &spec, &t, 1, &counter));
    }
    lie_tag overflow = {"slot", "extra"}; CHECK(lie_metrics_register(r, &spec, &overflow, 1, &counter) == LIE_METRIC_FULL);
    lie_tag invalid_utf8 = {"slot", "\xff"};
    CHECK(lie_metrics_register(r, &spec, &invalid_utf8, 1, &counter) == LIE_METRIC_INVALID);
    lie_metrics_destroy(r); puts("metrics: aggregation, filters, identity, collisions, windows, buckets, escaping, threads, bounds PASS"); return 0;
}
