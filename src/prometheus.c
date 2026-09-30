/* SPDX-License-Identifier: MIT */
#include "lie/prometheus.h"
#include <ctype.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SAMPLE_LIMIT 2048
#define LABEL_LIMIT 5
typedef struct { char key[40], value[128]; } label;
typedef struct { char name[160]; label labels[LABEL_LIMIT]; size_t nlabels; double value; } sample;
static int compare(const void *a, const void *b) { return strcmp(((const label *)a)->key, ((const label *)b)->key); }
static bool ident(const char **input, char *out, size_t cap) {
    const char *p = *input; size_t n = 0;
    if (!(isalpha((unsigned char)*p) || *p == '_')) return false;
    while (isalnum((unsigned char)*p) || *p == '_') { if (n + 1 == cap) return false; out[n++] = *p++; }
    out[n] = 0; *input = p; return true;
}
static bool parse(const char *p, sample *s) {
    if (!ident(&p, s->name, sizeof(s->name))) return false;
    if (*p == '{') {
        ++p;
        while (*p && *p != '}') {
            if (s->nlabels == LABEL_LIMIT) return false;
            label *l = &s->labels[s->nlabels++];
            if (!ident(&p, l->key, sizeof(l->key)) || *p++ != '=' || *p++ != '"') return false;
            size_t n = 0;
            while (*p && *p != '"') {
                char ch = *p++;
                if (ch == '\\') { ch = *p++; if (ch == 'n') ch = '\n'; else if (ch != '\\' && ch != '"') return false; }
                else if ((unsigned char)ch < 32) return false;
                if (n + 1 == sizeof(l->value)) return false;
                l->value[n++] = ch;
            }
            if (*p++ != '"') return false;
            l->value[n] = 0;
            if (*p == ',') { ++p; if (*p == '}') return false; }
            else if (*p != '}') return false;
        }
        if (*p++ != '}') return false;
    }
    if (*p != ' ' && *p != '\t') return false;
    char *end; s->value = strtod(p, &end);
    if (p == end || !isfinite(s->value)) return false;
    while (*end == ' ' || *end == '\t') ++end;
    if (*end) return false; /* No timestamps/exemplars in this subset. */
    qsort(s->labels, s->nlabels, sizeof(label), compare);
    for (size_t i = 1; i < s->nlabels; ++i) if (!strcmp(s->labels[i - 1].key, s->labels[i].key)) return false;
    return true;
}
static const char *le_value(const sample *s) {
    for (size_t i = 0; i < s->nlabels; ++i) if (!strcmp(s->labels[i].key, "le")) return s->labels[i].value;
    return NULL;
}
static bool same_labels(const sample *a, const sample *b, bool skip_le) {
    size_t i = 0, j = 0;
    for (;;) {
        if (skip_le) {
            while (i < a->nlabels && !strcmp(a->labels[i].key, "le")) ++i;
            while (j < b->nlabels && !strcmp(b->labels[j].key, "le")) ++j;
        }
        if (i == a->nlabels || j == b->nlabels) return i == a->nlabels && j == b->nlabels;
        if (strcmp(a->labels[i].key, b->labels[j].key) || strcmp(a->labels[i].value, b->labels[j].value)) return false;
        ++i; ++j;
    }
}
static bool suffix(const char *s, const char *end) {
    size_t a = strlen(s), b = strlen(end); return a >= b && !strcmp(s + a - b, end);
}
static unsigned long long hash(unsigned long long h, const char *s) {
    while (*s) { h ^= (unsigned char)*s++; h *= 1099511628211ULL; } return h;
}
int lie_prometheus_check(const char *text, lie_scrape *out, char *error, size_t cap) {
    if (!text || !out || !error || !cap) return -1;
    const char *failure = "invalid scrape";
    sample *samples = calloc(SAMPLE_LIMIT, sizeof(*samples)); char *copy = strdup(text);
    if (!samples || !copy) { free(samples); free(copy); snprintf(error, cap, "allocation failure"); return -1; }
    memset(out, 0, sizeof(*out)); out->layout_hash = 1469598103934665603ULL;
    size_t n = 0; bool have_tokens = false, have_uptime = false, have_ready = false;
    char *save = NULL;
    for (char *line = strtok_r(copy, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (*line == '#') {
            if (strncmp(line, "# HELP ", 7) && strncmp(line, "# TYPE ", 7)) { failure = "unsupported metadata"; goto fail; }
            const char *p = line + 7; char name[160];
            if (!ident(&p, name, sizeof(name)) || *p++ != ' ') { failure = "invalid metadata name"; goto fail; }
            if (!strncmp(line, "# TYPE ", 7) && strcmp(p, "counter") && strcmp(p, "gauge") && strcmp(p, "histogram") && strcmp(p, "summary")) {
                failure = "unsupported metric type"; goto fail;
            }
            continue;
        }
        if (!*line) continue;
        if (n == SAMPLE_LIMIT || !parse(line, &samples[n])) { failure = "invalid sample grammar/bound"; goto fail; }
        sample *s = &samples[n];
        for (size_t i = 0; i < n; ++i) if (!strcmp(samples[i].name, s->name) && same_labels(&samples[i], s, false)) { failure = "duplicate series"; goto fail; }
        unsigned long long sh = hash(1469598103934665603ULL, s->name);
        for (size_t i = 0; i < s->nlabels; ++i) { sh = hash(sh, s->labels[i].key); sh = hash(sh, "="); sh = hash(sh, s->labels[i].value); sh = hash(sh, "\xff"); }
        out->layout_hash ^= sh;
        if (suffix(s->name, "_total") || suffix(s->name, "_count") || suffix(s->name, "_sum") || suffix(s->name, "_bucket")) {
            if (s->value < 0) { failure = "negative cumulative value"; goto fail; }
        }
        if (!strcmp(s->name, "llm_tokens_generated_total") && !s->nlabels) { have_tokens = true; out->generated_tokens = s->value; }
        if (!strcmp(s->name, "runtime_uptime_seconds") && !s->nlabels) { have_uptime = true; out->uptime_seconds = s->value; }
        if (!strcmp(s->name, "runtime_ready") && !s->nlabels) { have_ready = true; out->ready = s->value; }
        ++n;
    }
    if (!have_tokens || !have_uptime || !have_ready || (out->ready != 0 && out->ready != 1) || out->uptime_seconds < 0) { failure = "required series missing/invalid"; goto fail; }
    for (size_t i = 0; i < n; ++i) if (suffix(samples[i].name, "_bucket")) {
        const sample *s = &samples[i]; const char *le = le_value(s);
        if (!le) { failure = "histogram bucket lacks le"; goto fail; }
        char *end; double bound = !strcmp(le, "+Inf") ? INFINITY : strtod(le, &end);
        if (strcmp(le, "+Inf") && (!*le || *end || !isfinite(bound) || bound <= 0)) { failure = "invalid histogram bound"; goto fail; }
        char count_name[160], sum_name[160]; size_t base = strlen(s->name) - 7;
        snprintf(count_name, sizeof(count_name), "%.*s_count", (int)base, s->name);
        snprintf(sum_name, sizeof(sum_name), "%.*s_sum", (int)base, s->name);
        bool count_found = false, sum_found = false, inf_found = false;
        for (size_t j = 0; j < n; ++j) if (same_labels(s, &samples[j], true)) {
            const sample *t = &samples[j];
            if (!strcmp(count_name, t->name)) {
                count_found = true;
                if (s->value > t->value || (isinf(bound) && s->value != t->value)) { failure = "bucket/count mismatch"; goto fail; }
            }
            if (!strcmp(sum_name, t->name)) sum_found = true;
            if (!strcmp(s->name, t->name)) {
                const char *tle = le_value(t); if (!tle) { failure = "missing le"; goto fail; }
                double other = !strcmp(tle, "+Inf") ? INFINITY : strtod(tle, NULL);
                if (isinf(other)) inf_found = true;
                if (bound < other && s->value > t->value) { failure = "noncumulative buckets"; goto fail; }
                if (i != j && bound == other) { failure = "duplicate numeric bucket bound"; goto fail; }
            }
        }
        if (!count_found || !sum_found || !inf_found) { failure = "incomplete histogram"; goto fail; }
        if (isinf(bound)) ++out->histograms;
    }
    if (!out->histograms) { failure = "required histogram missing"; goto fail; }
    out->samples = n; free(samples); free(copy); *error = 0; return 0;
fail:
    snprintf(error, cap, "%s", failure); free(samples); free(copy); return -1;
}
int lie_scrape_token_rate(const lie_scrape *previous, const lie_scrape *current,
                         double elapsed, int same_instance, double *rate) {
    if (!rate) return 0;
    *rate = 0;
    if (!previous || !current || !same_instance || !isfinite(elapsed) || elapsed <= 0 ||
        previous->layout_hash != current->layout_hash ||
        current->generated_tokens < previous->generated_tokens ||
        current->uptime_seconds < previous->uptime_seconds) return 0;
    double value = (current->generated_tokens - previous->generated_tokens) / elapsed;
    if (!isfinite(value) || value < 0) return 0;
    *rate = value; return 1;
}
