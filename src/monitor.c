/* SPDX-License-Identifier: MIT */
#include "lie/prometheus.h"
#include <curl/curl.h>
#include <json-c/json.h>
#include <errno.h>
#include <locale.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define LIMIT (1024 * 1024)
typedef struct { char *data; size_t size; } buffer;
static double monotonic(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (double)t.tv_sec + (double)t.tv_nsec / 1e9; }
static size_t append(char *data, size_t size, size_t count, void *ctx) {
    buffer *b = ctx;
    if (size && count > LIMIT / size) return 0;
    size_t n = size * count;
    if (n > LIMIT - b->size) return 0;
    char *p = realloc(b->data, b->size + n + 1); if (!p) return 0;
    b->data = p; memcpy(p + b->size, data, n); b->size += n; p[b->size] = 0; return n;
}
static json_object *parse_json(const char *data, size_t size) {
    if (!data || size > LIMIT) return NULL;
    json_tokener *t = json_tokener_new_ex(32); if (!t) return NULL;
    json_tokener_set_flags(t, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
    json_object *j = json_tokener_parse_ex(t, data, (int)size);
    size_t end = json_tokener_get_parse_end(t);
    while (end < size && (data[end] == ' ' || data[end] == '\n' || data[end] == '\r' || data[end] == '\t')) ++end;
    if (json_tokener_get_error(t) != json_tokener_success || end != size) { json_object_put(j); j = NULL; }
    json_tokener_free(t); return j;
}
static bool get(const char *base, const char *path, bool prometheus, bool health, buffer *body, long *status) {
    char url[1024]; int n = snprintf(url, sizeof(url), "%s%s", base, path);
    if (n < 0 || (size_t)n >= sizeof(url)) return false;
    CURL *c = curl_easy_init(); if (!c) return false;
    curl_easy_setopt(c, CURLOPT_URL, url); curl_easy_setopt(c, CURLOPT_PROXY, "");
    curl_easy_setopt(c, CURLOPT_PROTOCOLS_STR, "http,https");
    curl_easy_setopt(c, CURLOPT_CONNECTTIMEOUT_MS, 1500L); curl_easy_setopt(c, CURLOPT_TIMEOUT_MS, 3000L);
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION, append); curl_easy_setopt(c, CURLOPT_WRITEDATA, body);
    curl_easy_setopt(c, CURLOPT_NOSIGNAL, 1L);
    struct curl_slist *headers = curl_slist_append(NULL, prometheus ? "Accept: text/plain; version=0.0.4" : "Accept: application/vnd.spring-boot.actuator.v3+json");
    curl_easy_setopt(c, CURLOPT_HTTPHEADER, headers);
    CURLcode rc = curl_easy_perform(c); char *type = NULL;
    curl_easy_getinfo(c, CURLINFO_RESPONSE_CODE, status); curl_easy_getinfo(c, CURLINFO_CONTENT_TYPE, &type);
    bool ok = rc == CURLE_OK && (*status == 200 || (health && *status == 503)) && type &&
        (prometheus ? strstr(type, "text/plain") == type && strstr(type, "version=0.0.4") : strstr(type, "application/vnd.spring-boot.actuator.v3+json") == type);
    if (!ok) fprintf(stderr, "Fetch failed: %s HTTP %ld (%s)\n", path, *status, curl_easy_strerror(rc));
    curl_slist_free_all(headers); curl_easy_cleanup(c); return ok;
}
static json_object *field(json_object *j, const char *name, enum json_type type) {
    json_object *value = NULL;
    return j && json_object_is_type(j, json_type_object) && json_object_object_get_ex(j, name, &value) && json_object_is_type(value, type) ? value : NULL;
}
static const char *string(json_object *j, const char *name) {
    json_object *v = field(j, name, json_type_string); return v ? json_object_get_string(v) : NULL;
}
static bool number(json_object *j, double *value) {
    if (!j || !(json_object_is_type(j, json_type_int) || json_object_is_type(j, json_type_double))) return false;
    *value = json_object_get_double(j); return isfinite(*value);
}
static json_object *capture(const char *base) {
    const char *paths[] = {"/actuator", "/actuator/info", "/actuator/health/readiness", "/actuator/metrics"};
    const char *keys[] = {"actuator", "info", "health", "names"};
    json_object *bundle = json_object_new_object();
    json_object_object_add(bundle, "schema", json_object_new_string("synapse-lie.monitor.v1"));
    json_object_object_add(bundle, "source", json_object_new_string(base));
    for (size_t i = 0; i < 4; ++i) {
        buffer b = {0}; long status = 0;
        if (!get(base, paths[i], false, i == 2, &b, &status)) { free(b.data); goto fail; }
        json_object *j = parse_json(b.data, b.size); free(b.data);
        if (!j) goto fail;
        json_object_object_add(bundle, keys[i], j);
        if (i == 2) json_object_object_add(bundle, "readiness_http_status", json_object_new_int((int)status));
    }
    json_object *names_doc = field(bundle, "names", json_type_object), *names = field(names_doc, "names", json_type_array);
    if (!names || json_object_array_length(names) > 32) goto fail;
    json_object *details = json_object_new_object(); json_object_object_add(bundle, "details", details);
    for (size_t i = 0; i < json_object_array_length(names); ++i) {
        json_object *item = json_object_array_get_idx(names, i);
        if (!json_object_is_type(item, json_type_string)) goto fail;
        const char *name = json_object_get_string(item); size_t len = strlen(name);
        if (!len || len > 127 || strspn(name, "abcdefghijklmnopqrstuvwxyz0123456789._") != len) goto fail;
        char path[180]; snprintf(path, sizeof(path), "/actuator/metrics/%s", name);
        buffer b = {0}; long status;
        if (!get(base, path, false, false, &b, &status)) { free(b.data); goto fail; }
        json_object *j = parse_json(b.data, b.size); free(b.data); if (!j) goto fail;
        json_object_object_add(details, name, j);
    }
    buffer b = {0}; long status;
    if (!get(base, "/actuator/prometheus", true, false, &b, &status)) { free(b.data); goto fail; }
    json_object_object_add(bundle, "prometheus", json_object_new_string_len(b.data ? b.data : "", (int)b.size)); free(b.data);
    json_object_object_add(bundle, "monotonic_seconds", json_object_new_double(monotonic()));
    time_t time_now = time(NULL); struct tm utc; gmtime_r(&time_now, &utc); char stamp[32];
    strftime(stamp, sizeof(stamp), "%Y-%m-%dT%H:%M:%SZ", &utc);
    json_object_object_add(bundle, "recorded_at", json_object_new_string(stamp));
    return bundle;
fail:
    json_object_put(bundle); return NULL;
}
static bool verify(json_object *bundle, lie_scrape *scrape, char *error, size_t cap) {
    const char *failure = "invalid bundle/schema";
    const char *schema = string(bundle, "schema");
    if (!schema || strcmp(schema, "synapse-lie.monitor.v1")) goto fail;
    json_object *info = field(bundle, "info", json_type_object), *health = field(bundle, "health", json_type_object);
    json_object *actuator = field(bundle, "actuator", json_type_object), *links = field(actuator, "_links", json_type_object);
    json_object *names_doc = field(bundle, "names", json_type_object), *names = field(names_doc, "names", json_type_array);
    json_object *details = field(bundle, "details", json_type_object);
    if (!info || !health || !links || !names || !details || !string(info, "instance") ||
        !*string(info, "instance") || strlen(string(info, "instance")) >= 128) goto fail;
    const char *required_links[] = {"health", "liveness", "readiness", "info", "metrics", "prometheus", "llm"};
    for (size_t i = 0; i < sizeof(required_links) / sizeof(*required_links); ++i) {
        json_object *link = field(links, required_links[i], json_type_object);
        if (!link || !string(link, "href") || !field(link, "templated", json_type_boolean)) { failure = "discovery link missing/invalid"; goto fail; }
    }
    bool required[6] = {0}; const char *required_names[] = {"runtime.ready", "runtime.uptime", "http.connections.active", "llm.requests.rejected", "llm.tokens.generated", "http.server.requests"};
    size_t n = json_object_array_length(names); if (!n || n > 32) goto fail;
    for (size_t i = 0; i < n; ++i) {
        json_object *item = json_object_array_get_idx(names, i); if (!json_object_is_type(item, json_type_string)) goto fail;
        const char *name = json_object_get_string(item);
        for (size_t k = 0; k < 6; ++k) if (!strcmp(name, required_names[k])) { if (required[k]) goto fail; required[k] = true; }
        json_object *detail = field(details, name, json_type_object), *base = NULL;
        const char *reported = string(detail, "name");
        if (!reported || strcmp(reported, name) || !string(detail, "description") || !json_object_object_get_ex(detail, "baseUnit", &base) ||
            (base && !json_object_is_type(base, json_type_string))) goto fail;
        json_object *a = field(detail, "measurements", json_type_array), *tags = field(detail, "availableTags", json_type_array);
        if (!a || !tags || json_object_array_length(tags) > 4) goto fail;
        size_t count = json_object_array_length(a);
        bool timer = !strcmp(name, "http.server.requests"), counter = !strcmp(name, "llm.tokens.generated") || !strcmp(name, "llm.requests.rejected");
        if (count != (timer ? 3U : 1U)) goto fail;
        const char *statistics[] = {timer || counter ? "COUNT" : "VALUE", "TOTAL_TIME", "MAX"};
        for (size_t k = 0; k < count; ++k) {
            json_object *m = json_object_array_get_idx(a, k), *v = NULL;
            const char *statistic = string(m, "statistic"); double value;
            if (!statistic || strcmp(statistic, statistics[k]) || !json_object_object_get_ex(m, "value", &v) || !number(v, &value) || value < 0) goto fail;
        }
        if (timer && (!base || strcmp(json_object_get_string(base), "seconds"))) goto fail;
        for (size_t k = 0; k < json_object_array_length(tags); ++k) {
            json_object *tag = json_object_array_get_idx(tags, k), *values = field(tag, "values", json_type_array);
            if (!string(tag, "tag") || !values || json_object_array_length(values) > 128) goto fail;
            for (size_t q = 0; q < json_object_array_length(values); ++q) if (!json_object_is_type(json_object_array_get_idx(values, q), json_type_string)) goto fail;
        }
    }
    for (size_t i = 0; i < 6; ++i) if (!required[i]) { failure = "required metric missing"; goto fail; }
    const char *prometheus = string(bundle, "prometheus");
    if (!prometheus || lie_prometheus_check(prometheus, scrape, error, cap)) return false;
    const char *state = string(health, "status"); json_object *http_status = field(bundle, "readiness_http_status", json_type_int);
    if (!state || !http_status || (scrape->ready == 1 ? strcmp(state, "UP") || json_object_get_int(http_status) != 200 : strcmp(state, "OUT_OF_SERVICE") || json_object_get_int(http_status) != 503)) { failure = "readiness/metric mismatch (or transition; retry)"; goto fail; }
    *error = 0; return true;
fail:
    snprintf(error, cap, "%s", failure); return false;
}
static json_object *from_file(const char *path) {
    FILE *f = fopen(path, "rb"); if (!f) return NULL;
    char *data = malloc(LIMIT + 1); if (!data) { fclose(f); return NULL; }
    size_t n = fread(data, 1, LIMIT + 1, f); bool ok = !ferror(f) && n <= LIMIT;
    fclose(f); json_object *j = ok ? parse_json(data, n) : NULL; free(data); return j;
}
static bool seconds(const char *s, double *out) {
    char *end; errno = 0; double n = strtod(s, &end);
    if (errno || !*s || *end || !isfinite(n) || n < .05 || n > 86400) return false;
    *out = n; return true;
}
int main(int argc, char **argv) {
    setlocale(LC_ALL, "C");
    if (argc < 2 || !strcmp(argv[1], "--help")) {
        puts("Usage: synapse-lie-monitor check|watch|record [--url http://127.0.0.1:19880] [--file bundle.json] [--require-ready] [--interval seconds] [--duration seconds] [--output run.jsonl]\nExit: 0 contract valid; 1 transport/contract failure; 2 usage; 3 not ready. check does not require a loaded model unless requested. record output must not exist."); return argc < 2 ? 2 : 0;
    }
    const char *mode = argv[1], *base = "http://127.0.0.1:19880", *file = NULL, *output = NULL;
    bool ready_required = false; double interval = 1, duration = 10;
    if (strcmp(mode, "check") && strcmp(mode, "watch") && strcmp(mode, "record")) return 2;
    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--require-ready")) { ready_required = true; continue; }
        if (i + 1 == argc) return 2;
        if (!strcmp(argv[i], "--url")) base = argv[++i];
        else if (!strcmp(argv[i], "--file")) file = argv[++i];
        else if (!strcmp(argv[i], "--output")) output = argv[++i];
        else if (!strcmp(argv[i], "--interval")) { if (!seconds(argv[++i], &interval)) return 2; }
        else if (!strcmp(argv[i], "--duration")) { if (!seconds(argv[++i], &duration)) return 2; }
        else return 2;
    }
    if ((file && strcmp(mode, "check")) || (!strcmp(mode, "record") != (output != NULL)) ||
        (strncmp(base, "http://", 7) && strncmp(base, "https://", 8)) || strchr(base, '@') || strchr(base, '?') || strchr(base, '#')) return 2;
    if (curl_global_init(CURL_GLOBAL_DEFAULT)) return 1;
    FILE *record = output ? fopen(output, "wx") : NULL;
    if (output && !record) { perror("record output"); curl_global_cleanup(); return 1; }
    struct history_entry { lie_scrape scrape; double time; char instance[128]; } history[32] = {0};
    double start = monotonic();
    int exit_code = 0; size_t samples = 0;
    do {
        json_object *bundle = file ? from_file(file) : capture(base);
        char error[256] = "unavailable snapshot"; lie_scrape scrape;
        if (!bundle || !verify(bundle, &scrape, error, sizeof(error))) { fprintf(stderr, "Contract failure: %s\n", error); json_object_put(bundle); exit_code = 1; break; }
        double time_now = monotonic(); const char *instance = string(field(bundle, "info", json_type_object), "instance");
        double rate = 0;
        const struct history_entry *previous = samples ? &history[(samples - 1) % 32] : NULL;
        bool has_rate = lie_scrape_token_rate(previous ? &previous->scrape : NULL, &scrape,
            previous ? time_now - previous->time : 0, previous && !strcmp(instance, previous->instance), &rate);
        json_object_object_add(bundle, "elapsed_seconds", json_object_new_double(time_now - start));
        json_object_object_add(bundle, "generated_tokens_per_second", has_rate ? json_object_new_double(rate) : NULL);
        json_object_object_add(bundle, "delta_status", json_object_new_string(!samples ? "insufficient_history" : has_rate ? "valid" : "reset_or_series_layout_changed"));
        if (record) {
            if (fprintf(record, "%s\n", json_object_to_json_string_ext(bundle, JSON_C_TO_STRING_PLAIN)) < 0 || fflush(record)) { json_object_put(bundle); exit_code = 1; break; }
        } else {
            printf("Contract OK readiness=%s samples=%zu histograms=%zu tokens/s=", scrape.ready == 1 ? "UP" : "OUT_OF_SERVICE", scrape.samples, scrape.histograms);
            if (has_rate) printf("%.3f\n", rate); else puts("n/d");
        }
        struct history_entry *entry = &history[samples % 32];
        snprintf(entry->instance, sizeof(entry->instance), "%s", instance);
        entry->scrape = scrape; entry->time = time_now; ++samples; json_object_put(bundle);
        if (ready_required && scrape.ready != 1) { exit_code = 3; break; }
        if (!strcmp(mode, "check")) break;
        double remaining = duration - (monotonic() - start);
        if (remaining <= 0) break;
        double wait = interval < remaining ? interval : remaining;
        struct timespec delay = {(time_t)wait, (long)((wait - floor(wait)) * 1e9)};
        while (nanosleep(&delay, &delay) && errno == EINTR) {}
    } while (monotonic() - start < duration);
    if (record && fclose(record)) exit_code = 1;
    curl_global_cleanup(); return exit_code;
}
