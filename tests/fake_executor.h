/* SPDX-License-Identifier: MIT */
#ifndef LIE_FAKE_EXECUTOR_H
#define LIE_FAKE_EXECUTOR_H
/* Test process only: deterministic in-flight lifetime barrier, never a model. */
void fake_barrier_arm(void);
void fake_barrier_wait(void);
void fake_barrier_release(void);
#endif
