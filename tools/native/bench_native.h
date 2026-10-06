/* SPDX-License-Identifier: MIT */
#ifndef LIE_BENCH_NATIVE_H
#define LIE_BENCH_NATIVE_H
#include <json-c/json.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#define NB_LIMIT (32u * 1024u * 1024u)
/* Seconds. Matches the server's maximum configurable request deadline.
 * The 1M physical prefill already exceeds the former two-hour client limit. */
#define NB_HTTP_TIMEOUT_MAX_SECONDS 86400.0
#define NB_HTTP_LONG_CONTEXT_TIMEOUT_SECONDS 14400.0
typedef struct {
  char message[256];
} nb_error;
bool nb_fail(nb_error *, const char *);
json_object *nb_get(json_object *, const char *);
const char *nb_string(json_object *, const char *);
int64_t nb_number(json_object *, const char *);
bool nb_count(json_object *, const char *, int64_t, int64_t, int64_t *);
bool nb_same(json_object *, json_object *, const char *);
void nb_add(json_object *, const char *, json_object *);
void nb_str(json_object *, const char *, const char *);
void nb_num(json_object *, const char *, int64_t);
void nb_real(json_object *, const char *, double);
json_object *nb_event(const char *);
json_object *nb_copy(json_object *);
const char *nb_encoded(json_object *);
bool nb_hash(const void *, size_t, char[65]);
bool nb_json_hash(json_object *, char[65]);
bool nb_file_hash(const char *, char[65]);
bool nb_ids_hash(json_object *, char[65]);
uint64_t nb_now(void);
json_object *nb_parse(const char *, size_t, nb_error *);
json_object *nb_read(const char *, bool, nb_error *);
bool nb_emit(FILE *, json_object *);
FILE *nb_exclusive(const char *, nb_error *);
bool nb_mkdir(const char *, nb_error *);
json_object *nb_distribution(const double *, size_t);
bool nb_write_json(const char *, json_object *, nb_error *);
int nb_report(const char *, const char *, const char *, const char *,
              const char *, bool, nb_error *);
int nb_report_main(int, char **);
int nb_http_main(int, char **);
int nb_http_multi_main(int, char **);
int nb_http_curve_main(int, char **);
char *nb_gufo_text(uint64_t, size_t, nb_error *);
char *nb_gufo_turn(double, double, const char *, uint64_t, unsigned, unsigned, nb_error *);
const char *nb_gufo_instruction(const char *);
size_t nb_gufo_words(double, double);
size_t nb_gufo_word_count(const char *);
json_object *nb_http_curve_summary(json_object *, nb_error *);
int nb_http_curve_export(json_object *, json_object *, const char *, const char *, const char *, nb_error *);
json_object *nb_http_multi_summary(json_object *, nb_error *);
int nb_http_multi_export(json_object *, json_object *, const char *,
                         const char *, const char *, nb_error *);
int nb_ssd_main(int, char **);
/* Private deterministic I/O-gate hook for synthetic contract tests only.
 * The production CLI passes NULL and cannot select a gate. */
int nb_ssd_main_with_gate(int, char **, void (*)(void *, bool), void *);
int lie_bench_graphs(const char *, const char *, const char *);

typedef struct {
  const char *label;
  const char **ticks;
  size_t count;
  double *median, *low,
      *high; /* NaN means unavailable, never a zero-speed hit. */
} nb_plot_series;
typedef struct {
  const char *title, *unit, *x_label;
  bool mean; /* Otherwise median; the subtitle must identify the statistic. */
  nb_plot_series series[3];
  size_t count;
} nb_plot_panel;
bool nb_plot(const char *, const char *, const nb_plot_panel *, size_t,
             nb_error *);

typedef struct {
  const char *url, *model, *provider;
  double timeout;
  bool responses, stream, strict;
  void (*on_output)(void *);
  void *userdata;
  atomic_bool *cancel;
  volatile sig_atomic_t *interrupted;
  const char *client_id;
  json_object *client_ids; /* Optional cohort header IDs; borrowed. */
} nb_http_options;
/* Returns a complete observation, never an inferred success from HTTP 200. */
json_object *nb_http_request(const nb_http_options *, json_object *,
                             nb_error *);
/* Always retains ordered partial observations; complete is false on any
 * failure. All 1..8 handles start from one client gate with no per-request
 * worker. */
json_object *nb_http_cohort(const nb_http_options *, json_object *, bool *,
                            nb_error *);
json_object *nb_http_get(const char *, double, nb_error *);
bool nb_http_url(const char *, nb_error *);
bool nb_http_timing_contract(json_object *, int64_t, int64_t, int64_t,
                             nb_error *);
#endif
