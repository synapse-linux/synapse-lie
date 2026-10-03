/* SPDX-License-Identifier: MIT */
#ifndef LIE_RECORDS_H
#define LIE_RECORDS_H
#include "lie/events.h"
typedef struct lie_records lie_records;
typedef struct lie_record lie_record;
typedef struct {
  size_t max_records, max_bytes;
  uint64_t ttl_seconds;
} lie_records_options;
typedef struct {
  const char *id, *text;
  size_t bytes, call_count;
  const lie_output_call *calls;
  bool done, background;
  int64_t created;
  lie_job_info info;
} lie_record_view;
/* One owning client reactor, no HTTP types or additional threads. Retained
 * records and active jobs have separate lifetimes. All returned views are
 * borrowed until the next call on this reactor. TTL applies after retirement.
 * A caller must release every acquired record before destroying the store. */
lie_records *lie_records_create(const lie_records_options *);
void lie_records_destroy(lie_records *);
lie_record *lie_records_insert(lie_records *, const char *id, int64_t created,
                               const lie_core_request *, size_t instructions,
                               bool background);
lie_record *lie_records_get(lie_records *, const char *id, int64_t now);
bool lie_records_delete(lie_records *, const char *id);
void lie_record_release(lie_record *);
bool lie_record_charge(lie_record *,size_t bytes); /* Additional retained client projection. */
/* Transfers the consumer's job reference; that job has one semantic consumer.
 */
bool lie_record_attach(lie_record *, lie_job *);
lie_job *lie_record_job(lie_record *);
const lie_core_request *lie_record_input(lie_record *);
void lie_record_snapshot(lie_record *, lie_record_view *);
/* Foreground and background share the same collection/validation path. */
lie_flow_status lie_record_next(lie_record *, lie_event *);
bool lie_record_pump(lie_record *);
bool lie_record_cancel(lie_record *); /* Background only; idempotent. */
/* Immutable retained semantic journal; no flow loans and no second consumer.
 * Views remain borrowed until the next store operation; retain a record pin. */
size_t lie_record_event_count(lie_record *);
bool lie_record_replay(lie_record *,size_t index,lie_event *);
/* An independently owned neutral chat history, omitting previous instructions
 * and including assistant text and correlated function calls. free(storage). */
bool lie_record_history(lie_record *, lie_core_request *, void **storage);
#endif
