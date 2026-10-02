/* SPDX-License-Identifier: MIT */
#ifndef LIE_STORE_H
#define LIE_STORE_H
#include "lie/state.h"
#include "lie/cache_policy.h"
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Prefix checkpoints only. Zero-initialized options perform no store I/O.
 * Enabling requires an explicit private directory and independent byte limits.
 * One bounded I/O worker; no provider calls on that worker. */
typedef struct {
    const char *directory;
    uint64_t quota_bytes, staging_bytes;
} lie_store_options;
typedef struct {
    bool enabled;
    bool utility_policy, compression_enabled;
    uint64_t quota_bytes, disk_bytes, allocated_bytes, staging_budget_bytes;
    uint64_t staging_bytes, peak_staging_bytes;
    uint64_t lookups, hits, misses, writes, evictions, skipped, errors, cancelled;
    uint64_t read_bytes, written_bytes, read_ns, write_ns;
    uint64_t index_bytes, index_budget_bytes;
    unsigned entries, pending;
} lie_store_info;
typedef struct { unsigned char bytes[32]; } lie_state_identity;

/* Explicit SSD admission only: hashes the complete bound weight files and
 * executable/loaded libraries in C. FDs remain caller-owned. Runtime policy
 * must identify device/arithmetic and all model execution options. */
lie_status lie_state_identity_files(const int *,size_t,const char *policy,
                                    lie_state_identity *,lie_error *);
/* Provider supplies bound files/device policy and its current live domain.
 * Never called when SSD is disabled. Potentially expensive, before READY. */
lie_status lie_model_state_identity(lie_model *,lie_state_identity *,uint64_t *,lie_error *);

typedef struct lie_store lie_store;
typedef struct {
    uint64_t ticket, read_ns;
    bool read;
    lie_state *state; /* Owned result, or NULL for miss/cancel/write. */
    lie_cache_metadata metadata; /* Owned until result_release. */
} lie_store_result;
lie_status lie_store_open(const lie_store_options *,const lie_state_identity *,uint64_t domain,
                          lie_store **,lie_error *);
int lie_store_fd(const lie_store *);
/* Single producer (core owner), one admitted operation including completed
 * results. Zero means busy/refused; no unbounded queue or disk access here. */
uint64_t lie_store_read(lie_store *,const int32_t *,size_t,uint32_t chunk);
uint64_t lie_store_read_key(lie_store *,const int32_t *,size_t,uint32_t chunk,uint32_t flags);
bool lie_store_can_write(lie_store *,uint64_t retained_bytes);
bool lie_store_write(lie_store *,lie_state *);
bool lie_store_write_ex(lie_store *,lie_state *,const lie_cache_metadata *);
/* Text matching keeps the payload's exact token history. The owner must rebuild
 * and validate the suffix before restoring. All copied inputs are bounded. */
uint64_t lie_store_read_text(lie_store *,const char *,size_t,uint32_t chunk);
uint64_t lie_store_read_text_key(lie_store *,const char *,size_t,uint32_t chunk,uint32_t key_flags);
void lie_store_cancel(lie_store *,uint64_t ticket);
bool lie_store_take(lie_store *,lie_store_result *);
/* Release the completed operation after any owner upload. The slot and staging
 * reservation remain held from take through release, including cancellation.
 * May retain state into RAM first. Release each taken result before close. */
void lie_store_result_release(lie_store *,lie_store_result *);
void lie_store_snapshot(lie_store *,lie_store_info *);
/* Joins the one I/O worker; pending writes drain, pending reads cancel.
 * No retained result or borrowed state survives close. No deletion on close. */
void lie_store_close(lie_store **);
#ifdef __cplusplus
}
#endif
#endif
