/* SPDX-License-Identifier: MIT */
/* Model-neutral byte grammar runtime; schema/lexeme compilation is separate. */
#ifndef LIE_GRAMMAR_H
#define LIE_GRAMMAR_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_GRAMMAR_ABI 1u
#define LIE_GRAMMAR_TERMINAL (UINT32_C(1) << 31)
#define LIE_GRAMMAR_LEXEME (UINT32_C(1) << 30)
typedef enum {
  LIE_GRAMMAR_OK,
  LIE_GRAMMAR_INVALID,
  LIE_GRAMMAR_RESOURCE,
  LIE_GRAMMAR_STATE_LIMIT,
  LIE_GRAMMAR_STACK_LIMIT,
  LIE_GRAMMAR_WORK_LIMIT,
  LIE_GRAMMAR_PREDICATE,
  LIE_GRAMMAR_NO_TOKEN,
  LIE_GRAMMAR_VOCABULARY_LIMIT,
  LIE_GRAMMAR_MASK_WORK_LIMIT
} lie_grammar_status;
typedef struct {
  void *context;
  void *(*allocate)(void *, size_t);
  void (*release)(void *, void *);
} lie_grammar_allocator;
typedef struct { uint32_t offset, count; } lie_grammar_range;
typedef struct {
  const uint32_t *symbols;
  size_t symbol_count;
  const uint8_t *lexeme;
  size_t lexeme_bytes;
} lie_grammar_frame;
typedef struct {
  uint32_t abi_version, struct_bytes;
  size_t max_states, max_stack, max_work, max_lexeme_bytes;
} lie_grammar_limits;
typedef struct {
  const void *context;
  bool (*allows)(const void *, uint32_t, uint8_t);
  lie_grammar_status (*advance)(const void *, uint32_t, const uint8_t *, size_t,
                                uint8_t, uint8_t *, size_t, size_t *,
                                bool *, bool *);
  lie_grammar_status (*canonical)(const void *, uint32_t, uint8_t *, size_t *,
                                  size_t, size_t);
} lie_grammar_predicates;
typedef struct {
  uint32_t abi_version, struct_bytes, root;
  const lie_grammar_range *rules;
  size_t rule_count;
  const lie_grammar_range *sequences;
  size_t sequence_count;
  const uint32_t *symbols;
  size_t symbol_count;
  /* 32 bytes per terminal class; byte b uses bit (b % 8) of byte (b / 8). */
  const uint8_t *classes;
  size_t class_count, lexeme_count;
  lie_grammar_predicates predicates;
  lie_grammar_allocator allocator;
  lie_grammar_limits limits;
} lie_grammar_description;
typedef struct lie_grammar_program lie_grammar_program;
typedef struct lie_grammar_state lie_grammar_state;
void lie_grammar_limits_init(lie_grammar_limits *);
void lie_grammar_description_init(lie_grammar_description *);
/* The immutable program copies all tables. Predicate/allocator contexts are
 * borrowed and must outlive the program and its states. NULL allocator hooks
 * select malloc/free. Allocation returns fresh, suitably aligned storage.
 * Hooks are paired, nonthrowing and caller-synchronized. Predicate advance
 * must support identical input/output storage; all hooks respect capacities.
 * State snapshots own their frames and preserve caller inputs. No thread,
 * model/device/HTTP operation, RNG or global mutable cache belongs here.
 * All operations preserve *output on refusal; caller releases successful
 * outputs. Empty state is a valid dead prefix, not a resource failure. */
lie_grammar_status lie_grammar_program_create(const lie_grammar_description *,
                                             lie_grammar_program **output);
void lie_grammar_program_release(lie_grammar_program *);
lie_grammar_status lie_grammar_state_import(const lie_grammar_program *,
                                           const lie_grammar_frame *, size_t,
                                           lie_grammar_state **output);
/* Synchronous model-neutral provider snapshot bridge, separate ABI 1.
 * Reader views stay valid until the next read callback or call completion.
 * Write callbacks allocate fresh private staging. Successful writable views
 * remain valid until call completion; storage/capacity may change on refusal.
 * The caller publishes the staging result only after OK and retires it on all
 * other statuses. C validates all writable spans before copying any payload,
 * rejects writable overlap with every input/output span, and owns bounded
 * planning/import/copy lifetimes. Callbacks are nonthrowing and serialize with
 * their storage owner; no callback pointer/context is retained. */
#define LIE_GRAMMAR_SNAPSHOT_ABI 1u
typedef struct {
  uint32_t abi_version, struct_bytes;
  const void *context;
  size_t count;
  lie_grammar_status (*frame)(const void *, size_t, lie_grammar_frame *);
} lie_grammar_snapshot_reader;
typedef struct {
  uint32_t *symbols;
  size_t symbol_capacity;
  uint8_t *lexeme;
  size_t lexeme_capacity;
} lie_grammar_writable_frame;
typedef struct {
  uint32_t abi_version, struct_bytes;
  void *context;
  lie_grammar_status (*prepare)(void *, size_t);
  lie_grammar_status (*frame)(void *, size_t, size_t, size_t,
                              lie_grammar_writable_frame *);
} lie_grammar_snapshot_writer;
lie_grammar_status lie_grammar_state_read(const lie_grammar_program *,
  const lie_grammar_snapshot_reader *, lie_grammar_state **);
lie_grammar_status lie_grammar_state_write(const lie_grammar_state *,
  const lie_grammar_snapshot_writer *);
void lie_grammar_state_release(lie_grammar_state *);
size_t lie_grammar_state_count(const lie_grammar_state *);
/* Exported pointers are borrowed until state release and never mutable. */
lie_grammar_status lie_grammar_state_frame(const lie_grammar_state *, size_t,
                                          lie_grammar_frame *);
/* Snapshot identity is ordered by symbols, unsigned lexeme bytes and frames.
 * Hashes are internal accelerators, not persistence or protocol identities.
 * NULL precedes every actual state. Clone refuses incompatible frames. */
int lie_grammar_state_compare(const lie_grammar_state *, const lie_grammar_state *);
uint64_t lie_grammar_state_hash(const lie_grammar_state *);
lie_grammar_status lie_grammar_state_clone(const lie_grammar_program *,
                                          const lie_grammar_state *,
                                          lie_grammar_state **);
lie_grammar_status lie_grammar_expand(const lie_grammar_program *,
                                      const lie_grammar_state *,
                                      lie_grammar_state **output);
lie_grammar_status lie_grammar_start(const lie_grammar_program *,
                                     lie_grammar_state **output);
lie_grammar_status lie_grammar_advance(const lie_grammar_program *,
                                      const lie_grammar_state *, uint8_t,
                                      lie_grammar_state **output);
bool lie_grammar_complete(const lie_grammar_state *);
lie_grammar_status lie_grammar_canonical(const lie_grammar_program *,
                                        const lie_grammar_state *, size_t,
                                        lie_grammar_state **output);
/* Apply a precompiled token mask to dense or mapped compact logits. Exact
 * in-place operation is allowed; other overlap/invalid IDs refuse before
 * changing output. An allowed NaN/Inf retains its original representation. */
lie_grammar_status lie_grammar_mask_logits(const float *, size_t,
                                          const uint32_t *, size_t,
                                          const uint8_t *, size_t,
                                          float *, size_t);
#ifdef __cplusplus
}
#endif
#endif
