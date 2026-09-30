/* SPDX-License-Identifier: MIT */
#include "lie/metrics.h"
#include <json-c/json.h>
#include <math.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define NAME 128
#define DESC 384
#define TEXT 128
#define UNIT 24
#define MAX_EXACT 9007199254740991.0
#define WINDOW_NS UINT64_C(60000000000)
#define WINDOWS 3

typedef struct { char key[32], value[TEXT]; } tag;
typedef struct {
    char name[NAME], prom[NAME + UNIT], description[DESC], unit[UNIT];
    lie_metric_type type;
    size_t tags, buckets;
    char keys[LIE_MAX_TAGS][32];
    double bounds[LIE_MAX_BUCKETS];
} family;
typedef struct {
    size_t family;
    tag tags[LIE_MAX_TAGS];
    double value, count, total, buckets[LIE_MAX_BUCKETS];
    uint64_t epochs[WINDOWS];
    double maxima[WINDOWS];
} series;
typedef struct {
    size_t nf, ns;
    uint64_t now;
    family families[LIE_MAX_METERS];
    series values[LIE_MAX_SERIES];
} view;
struct lie_metrics { pthread_mutex_t mutex; lie_clock clock; void *context; view state; };

uint64_t lie_monotonic_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) abort();
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static uint64_t now(lie_metrics *r) { return r->clock ? r->clock(r->context) : lie_monotonic_ns(); }
lie_metrics *lie_metrics_create(lie_clock clock, void *context) {
    lie_metrics *r = calloc(1, sizeof(*r));
    if (!r) return NULL;
    if (pthread_mutex_init(&r->mutex, NULL)) { free(r); return NULL; }
    r->clock = clock; r->context = context;
    return r;
}
void lie_metrics_destroy(lie_metrics *r) {
    if (r) { pthread_mutex_destroy(&r->mutex); free(r); }
}
static bool valid_text(const char *text) {
    const unsigned char *p = (const unsigned char *)text;
    while (*p) {
        unsigned code = *p++, more, minimum;
        if (code < 128) {
            if ((code < 32 && code != '\n') || code == 127) return false;
            continue;
        }
        if (code >= 0xc2 && code <= 0xdf) { code &= 31; more = 1; minimum = 0x80; }
        else if (code >= 0xe0 && code <= 0xef) { code &= 15; more = 2; minimum = 0x800; }
        else if (code >= 0xf0 && code <= 0xf4) { code &= 7; more = 3; minimum = 0x10000; }
        else return false;
        for (unsigned i = 0; i < more; ++i) {
            if ((*p & 0xc0) != 0x80) return false;
            code = (code << 6) | (*p++ & 63);
        }
        if (code < minimum || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) return false;
    }
    return true;
}
static bool copy(char *dst, size_t cap, const char *s) {
    if (!s || strlen(s) >= cap || !valid_text(s)) return false;
    memcpy(dst, s, strlen(s) + 1); return true;
}
static bool identifier(const char *s, bool dots) {
    if (!s || !((*s >= 'a' && *s <= 'z') || *s == '_')) return false;
    if (s[0] == '_' && s[1] == '_') return false;
    for (; *s; ++s)
        if (!((*s >= 'a' && *s <= 'z') || (*s >= '0' && *s <= '9') || *s == '_' || (dots && *s == '.'))) return false;
    return true;
}
static int tag_compare(const void *a, const void *b) { return strcmp(((const tag *)a)->key, ((const tag *)b)->key); }
static bool tags_copy(tag *out, const lie_tag *in, size_t n) {
    if (n > LIE_MAX_TAGS || (n && !in)) return false;
    for (size_t i = 0; i < n; ++i) {
        if (!identifier(in[i].key, false) || !strcmp(in[i].key, "le") ||
            !copy(out[i].key, sizeof(out[i].key), in[i].key) ||
            !copy(out[i].value, sizeof(out[i].value), in[i].value)) return false;
        /* UTF-8 label values are permitted; embedded NUL is excluded by the C API. */
    }
    qsort(out, n, sizeof(*out), tag_compare);
    for (size_t i = 1; i < n; ++i) if (!strcmp(out[i - 1].key, out[i].key)) return false;
    return true;
}
static size_t names_for(const family *f, char out[5][NAME + UNIT + 16]) {
    if (f->type == LIE_TIMER) {
        const char *suffix[] = { "", "_count", "_sum", "_max", "_bucket" };
        for (size_t i = 0; i < 5; ++i) snprintf(out[i], NAME + UNIT + 16, "%s%s", f->prom, suffix[i]);
        return 5; /* Reserve bucket namespace even when histograms are disabled. */
    }
    snprintf(out[0], NAME + UNIT + 16, "%s%s", f->prom, f->type == LIE_COUNTER ? "_total" : "");
    if (f->type == LIE_COUNTER) {
        /* Prometheus clients may normalize the family by stripping _total. */
        snprintf(out[1], NAME + UNIT + 16, "%s", f->prom);
        return 2;
    }
    return 1;
}
static bool same_family(const family *a, const family *b) {
    /* Compare semantic fields, never struct padding across compilers/call sites. */
    if (strcmp(a->name, b->name) || strcmp(a->prom, b->prom) ||
        strcmp(a->description, b->description) || strcmp(a->unit, b->unit) ||
        a->type != b->type || a->tags != b->tags || a->buckets != b->buckets) return false;
    for (size_t i = 0; i < a->tags; ++i) if (strcmp(a->keys[i], b->keys[i])) return false;
    for (size_t i = 0; i < a->buckets; ++i) if (a->bounds[i] != b->bounds[i]) return false;
    return true;
}
static bool conflict(const family *a, const family *b) {
    char an[5][NAME + UNIT + 16], bn[5][NAME + UNIT + 16];
    size_t na = names_for(a, an), nb = names_for(b, bn);
    for (size_t i = 0; i < na; ++i)
        for (size_t j = 0; j < nb; ++j) if (!strcmp(an[i], bn[j])) return true;
    return false;
}
lie_metric_status lie_metrics_register(lie_metrics *r, const lie_metric_spec *s,
                                      const lie_tag *tags, size_t n, lie_meter *out) {
    family f = {0}; series v = {0};
    if (!r || !s || !out || !identifier(s->name, true) ||
        s->type < LIE_COUNTER || s->type > LIE_TIMER ||
        !copy(f.name, sizeof(f.name), s->name) ||
        !copy(f.description, sizeof(f.description), s->description ? s->description : "") ||
        !copy(f.unit, sizeof(f.unit), s->unit ? s->unit : "") ||
        !tags_copy(v.tags, tags, n) || s->bucket_count > LIE_MAX_BUCKETS ||
        (s->bucket_count && (!s->buckets || s->type != LIE_TIMER)) ||
        (s->type == LIE_TIMER && strcmp(f.unit, "seconds"))) return LIE_METRIC_INVALID;
    f.type = s->type; f.tags = n; f.buckets = s->bucket_count;
    for (size_t i = 0; i < n; ++i) copy(f.keys[i], sizeof(f.keys[i]), v.tags[i].key);
    for (size_t i = 0; i < f.buckets; ++i) {
        if (!isfinite(s->buckets[i]) || s->buckets[i] <= 0 || (i && s->buckets[i] <= s->buckets[i - 1])) return LIE_METRIC_INVALID;
        f.bounds[i] = s->buckets[i];
    }
    copy(f.prom, sizeof(f.prom), f.name);
    for (char *p = f.prom; *p; ++p) if (*p == '.') *p = '_';
    if (f.type == LIE_TIMER || !strcmp(f.unit, "bytes") || !strcmp(f.unit, "seconds")) {
        char suffix[UNIT + 2]; snprintf(suffix, sizeof(suffix), "_%s", f.unit);
        size_t len = strlen(f.prom), slen = strlen(suffix);
        if (len < slen || strcmp(f.prom + len - slen, suffix)) strcat(f.prom, suffix);
    }
    lie_metric_status status = LIE_METRIC_OK;
    pthread_mutex_lock(&r->mutex);
    view *state = &r->state;
    size_t fi = state->nf;
    for (size_t i = 0; i < state->nf; ++i) {
        if (!strcmp(state->families[i].name, f.name)) {
            if (!same_family(&state->families[i], &f)) status = LIE_METRIC_CONFLICT;
            fi = i; break;
        }
        if (conflict(&state->families[i], &f)) status = LIE_METRIC_CONFLICT;
    }
    if (status != LIE_METRIC_OK) goto done;
    for (size_t i = 0; i < state->ns; ++i) {
        if (state->values[i].family == fi && !memcmp(state->values[i].tags, v.tags, sizeof(v.tags))) {
            *out = (lie_meter)(i + 1); goto done;
        }
    }
    if (state->ns == LIE_MAX_SERIES || (fi == state->nf && state->nf == LIE_MAX_METERS)) { status = LIE_METRIC_FULL; goto done; }
    if (fi == state->nf) state->families[state->nf++] = f;
    v.family = fi; state->values[state->ns++] = v;
    *out = (lie_meter)state->ns;
done:
    pthread_mutex_unlock(&r->mutex);
    return status;
}
static lie_metric_status update(lie_metrics *r, lie_meter h, double x, lie_metric_type type) {
    if (!r || !h || !isfinite(x) || (type != LIE_GAUGE && x < 0)) return LIE_METRIC_INVALID;
    lie_metric_status status = LIE_METRIC_INVALID;
    pthread_mutex_lock(&r->mutex);
    if (h > r->state.ns) goto done;
    series *s = &r->state.values[h - 1]; const family *f = &r->state.families[s->family];
    if (f->type != type) goto done;
    if (type == LIE_GAUGE) s->value = x;
    else if (type == LIE_COUNTER) {
        if (!isfinite(s->value + x) || s->value + x > MAX_EXACT) goto done;
        s->value += x;
    } else {
        uint64_t epoch = now(r) / WINDOW_NS;
        if (s->count >= MAX_EXACT || !isfinite(s->total + x)) goto done;
        s->count++; s->total += x;
        for (size_t i = 0; i < f->buckets; ++i) if (x <= f->bounds[i]) s->buckets[i]++;
        size_t slot = epoch % WINDOWS;
        if (s->epochs[slot] != epoch) s->maxima[slot] = 0;
        s->epochs[slot] = epoch;
        if (x > s->maxima[slot]) s->maxima[slot] = x;
    }
    status = LIE_METRIC_OK;
done:
    pthread_mutex_unlock(&r->mutex); return status;
}
lie_metric_status lie_counter_add(lie_metrics *r, lie_meter h, double x) { return update(r, h, x, LIE_COUNTER); }
lie_metric_status lie_gauge_set(lie_metrics *r, lie_meter h, double x) { return update(r, h, x, LIE_GAUGE); }
lie_metric_status lie_timer_record(lie_metrics *r, lie_meter h, double x) { return update(r, h, x, LIE_TIMER); }
static view *snapshot(lie_metrics *r) {
    if (!r) return NULL;
    view *v = malloc(sizeof(*v));
    if (v) { pthread_mutex_lock(&r->mutex); *v = r->state; v->now = now(r); pthread_mutex_unlock(&r->mutex); }
    return v;
}
static double maximum(const view *v, const series *s) {
    double result = 0; uint64_t epoch = v->now / WINDOW_NS;
    for (size_t i = 0; i < WINDOWS; ++i)
        if (epoch >= s->epochs[i] && epoch - s->epochs[i] < WINDOWS && s->maxima[i] > result) result = s->maxima[i];
    return result;
}
static char *json_finish(json_object *j) {
    if (!j) return NULL;
    char *s = strdup(json_object_to_json_string_ext(j, JSON_C_TO_STRING_PLAIN));
    json_object_put(j); return s;
}
char *lie_metrics_names(lie_metrics *r) {
    view *v = snapshot(r); if (!v) return NULL;
    json_object *j = json_object_new_object(), *a = json_object_new_array();
    for (size_t i = 0; i < v->nf; ++i) json_object_array_add(a, json_object_new_string(v->families[i].name));
    json_object_object_add(j, "names", a); free(v); return json_finish(j);
}
static void measurement(json_object *a, const char *stat, double x) {
    json_object *m = json_object_new_object();
    json_object_object_add(m, "statistic", json_object_new_string(stat));
    json_object_object_add(m, "value", json_object_new_double(x)); json_object_array_add(a, m);
}
static bool filtered(const series *s, size_t nt, const tag *filters, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        bool found = false;
        for (size_t j = 0; j < nt; ++j) if (!strcmp(filters[i].key, s->tags[j].key) && !strcmp(filters[i].value, s->tags[j].value)) found = true;
        if (!found) return false;
    }
    return true;
}
lie_metric_status lie_metrics_detail(lie_metrics *r, const char *name, const lie_tag *filters, size_t n, char **out) {
    tag ft[LIE_MAX_TAGS] = {0};
    if (!out || !name || !tags_copy(ft, filters, n)) return LIE_METRIC_INVALID;
    *out = NULL; view *v = snapshot(r); if (!v) return LIE_METRIC_NOMEM;
    size_t fi;
    for (fi = 0; fi < v->nf && strcmp(name, v->families[fi].name); ++fi) {}
    if (fi == v->nf) { free(v); return LIE_METRIC_NOT_FOUND; }
    family *f = &v->families[fi];
    for (size_t i = 0; i < n; ++i) {
        bool found = false;
        for (size_t k = 0; k < f->tags; ++k) if (!strcmp(ft[i].key, f->keys[k])) found = true;
        if (!found) { free(v); return LIE_METRIC_NOT_FOUND; }
    }
    bool selected[LIE_MAX_SERIES] = {0}; size_t matched = 0;
    double count = 0, total = 0, mx = 0, value = 0;
    for (size_t i = 0; i < v->ns; ++i) {
        series *s = &v->values[i];
        if (s->family != fi || !filtered(s, f->tags, ft, n)) continue;
        selected[i] = true; ++matched;
        count += s->count; total += s->total; value += s->value;
        double m = maximum(v, s); if (m > mx) mx = m;
    }
    if (!matched) { free(v); return LIE_METRIC_NOT_FOUND; }
    if (!isfinite(count) || !isfinite(total) || !isfinite(value)) { free(v); return LIE_METRIC_INVALID; }
    json_object *j = json_object_new_object(), *a = json_object_new_array(), *available = json_object_new_array();
    json_object_object_add(j, "name", json_object_new_string(f->name));
    json_object_object_add(j, "description", json_object_new_string(f->description));
    json_object_object_add(j, "baseUnit", *f->unit ? json_object_new_string(f->unit) : NULL);
    if (f->type == LIE_TIMER) { measurement(a, "COUNT", count); measurement(a, "TOTAL_TIME", total); measurement(a, "MAX", mx); }
    else measurement(a, f->type == LIE_GAUGE ? "VALUE" : "COUNT", value);
    json_object_object_add(j, "measurements", a);
    for (size_t k = 0; k < f->tags; ++k) {
        bool fixed = false;
        for (size_t t = 0; t < n; ++t) if (!strcmp(ft[t].key, f->keys[k])) fixed = true;
        if (fixed) continue;
        json_object *t = json_object_new_object(), *values = json_object_new_array();
        for (size_t i = 0; i < v->ns; ++i) if (selected[i]) {
            bool duplicate = false;
            for (size_t prev = 0; prev < i; ++prev)
                if (selected[prev] && !strcmp(v->values[prev].tags[k].value, v->values[i].tags[k].value)) duplicate = true;
            if (!duplicate) json_object_array_add(values, json_object_new_string(v->values[i].tags[k].value));
        }
        json_object_object_add(t, "tag", json_object_new_string(f->keys[k]));
        json_object_object_add(t, "values", values); json_object_array_add(available, t);
    }
    json_object_object_add(j, "availableTags", available);
    free(v); *out = json_finish(j); return *out ? LIE_METRIC_OK : LIE_METRIC_NOMEM;
}
static void escaped(FILE *f, const char *s, bool label) {
    for (; *s; ++s) {
        if (*s == '\\') fputs("\\\\", f);
        else if (*s == '\n') fputs("\\n", f);
        else if (*s == '"' && label) fputs("\\\"", f);
        else fputc((unsigned char)*s, f);
    }
}
static void labels(FILE *out, const family *f, const series *s, const char *le) {
    if (!f->tags && !le) return;
    fputc('{', out);
    for (size_t i = 0; i < f->tags; ++i) {
        if (i) fputc(',', out);
        fprintf(out, "%s=\"", s->tags[i].key); escaped(out, s->tags[i].value, true); fputc('"', out);
    }
    if (le) fprintf(out, "%sle=\"%s\"", f->tags ? "," : "", le);
    fputc('}', out);
}
static void sample(FILE *out, const family *f, const series *s, const char *suffix, const char *le, double value) {
    fprintf(out, "%s%s", f->prom, suffix); labels(out, f, s, le); fprintf(out, " %.17g\n", value);
}
char *lie_metrics_prometheus(lie_metrics *r) {
    view *v = snapshot(r); if (!v) return NULL;
    char *text = NULL; size_t size = 0; FILE *out = open_memstream(&text, &size);
    if (!out) { free(v); return NULL; }
    for (size_t fi = 0; fi < v->nf; ++fi) {
        const family *f = &v->families[fi]; const char *suffix = f->type == LIE_COUNTER ? "_total" : "";
        fprintf(out, "# HELP %s%s ", f->prom, suffix); escaped(out, f->description, false);
        fprintf(out, "\n# TYPE %s%s %s\n", f->prom, suffix,
                f->type == LIE_COUNTER ? "counter" : f->type == LIE_GAUGE ? "gauge" : f->buckets ? "histogram" : "summary");
        for (size_t i = 0; i < v->ns; ++i) {
            const series *s = &v->values[i]; if (s->family != fi) continue;
            if (f->type != LIE_TIMER) sample(out, f, s, suffix, NULL, s->value);
            else {
                for (size_t k = 0; k < f->buckets; ++k) {
                    char bound[32]; snprintf(bound, sizeof(bound), "%.17g", f->bounds[k]);
                    sample(out, f, s, "_bucket", bound, s->buckets[k]);
                }
                if (f->buckets) sample(out, f, s, "_bucket", "+Inf", s->count);
                sample(out, f, s, "_count", NULL, s->count);
                sample(out, f, s, "_sum", NULL, s->total);
            }
        }
        if (f->type == LIE_TIMER) {
            fprintf(out, "# HELP %s_max Maximum over three 60-second rotation buckets\n# TYPE %s_max gauge\n", f->prom, f->prom);
            for (size_t i = 0; i < v->ns; ++i) if (v->values[i].family == fi) sample(out, f, &v->values[i], "_max", NULL, maximum(v, &v->values[i]));
        }
    }
    bool failed = ferror(out); if (fclose(out)) failed = true; free(v);
    if (failed) { free(text); return NULL; } return text;
}
