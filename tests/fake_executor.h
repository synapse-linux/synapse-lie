/* SPDX-License-Identifier: MIT */
#ifndef LIE_FAKE_EXECUTOR_H
#define LIE_FAKE_EXECUTOR_H
/* Test process only: deterministic dispatch barriers, never a model. */
typedef enum { FAKE_PREFILL, FAKE_DECODE } fake_phase;
typedef struct { unsigned prefill, decode, text, create, close, batch; } fake_calls;
void fake_barrier_arm(void); /* Existing decode barrier. */
void fake_barrier_arm_phase(fake_phase);
void fake_barrier_wait(void);
void fake_barrier_release(void);
/* Reset only with no fixture worker running. */
void fake_calls_reset(void);
fake_calls fake_calls_snapshot(void);
#endif
