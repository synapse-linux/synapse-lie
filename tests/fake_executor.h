/* SPDX-License-Identifier: MIT */
#ifndef LIE_FAKE_EXECUTOR_H
#define LIE_FAKE_EXECUTOR_H
#include <stdbool.h>
/* Test process only: deterministic dispatch barriers, never a model. */
typedef enum { FAKE_PREFILL, FAKE_DECODE, FAKE_CAPTURE, FAKE_RESTORE, FAKE_CLOSE } fake_phase;
typedef struct { unsigned prefill, decode, text, create, close, batch, capture, restore; } fake_calls;
void fake_barrier_arm(void); /* Existing decode barrier. */
void fake_barrier_arm_phase(fake_phase);
void fake_barrier_wait(void);
void fake_barrier_release(void);
/* Reset only with no fixture worker running. */
void fake_calls_reset(void);
void fake_state_fault(unsigned); /* 1 invalid layout, 2 read fault, 3 mutating write fault. */
void fake_state_padding(unsigned); /* Extra deterministic bytes; set between requests only. */
fake_calls fake_calls_snapshot(void);
void fake_tokenizer_merge(bool);
#endif
