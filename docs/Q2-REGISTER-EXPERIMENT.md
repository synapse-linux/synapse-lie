<!-- SPDX-License-Identifier: MIT -->
# Q2 integer scheduling experiment

Both GPU candidates pass the independent operator tolerances but fail the
predeclared exact replay gate. Neither is retained. The original qualified
runtime is restored byte-for-byte; no new model benchmark or speedup is claimed.

## Hypothesis and static inspection

The qualified original Q2 phase trace reports 320/860/1196 private bytes per
work item for down-projection tiles 32/48/64. These kernels account for 1382.876 ms
of the measured 3364.126 ms prefill kernel total. UD routed kernels have no private
allocation in the same diagnostic. This suggests register pressure as an
optimization target; it does not prove how much runtime is spent on spills.

Device-only compilation with local AMD clang 22 and gfx1151 code generation
shows scratch load/store instructions in those Q2 kernels. It executes no GPU
program or model. Local tile 48/64 allocation differs slightly from the retained
target trace (848/1204 versus 860/1196 bytes); each static candidate is compared
with its matching local baseline, not substituted for target measurements.

| Q2 tile columns | Baseline private B/item | Token barrier B/item | Bounded K loop B/item | Forced full K + barrier B/item |
| --- | ---: | ---: | ---: | ---: |
| 16 | 296 | 516 | 0 | 296 |
| 32 | 320 | 176 | 0 | 1064 |
| 48 | 848 | 456 | 0 | 1940 |
| 64 | 1204 | 0 | 0 | 2816 |
| 80 | 2764 | 0 | 0 | 5692 |

The bounded K loop has no static scratch instructions for these widths and
uses 112/123/160/187/217 VGPRs, versus 256 in the baseline. This is not a speedup
measurement. The first token-barrier screen increases tile16 scratch; the GPU
barrier candidate therefore leaves tile16 unchanged. Forcing full K expansion
with a barrier increases scratch at every larger width and was rejected before
GPU execution. Full metadata and command-receipt paths are retained in
`config/q2-register-static.json`.

## Target verification

All runtime tests run on `.157`. Core explicitly handed over after state-gpu-r1;
each Q2 build/GPU arm acquires the four existing EX|NB leases and performs a fresh
admission check. Host fixtures pass 6/6 Debug and 6/6 ASan/UBSan, including the new
marked-phase resource-report fixture.

The extended operator harness covers IQ2/Q2 PP/TG, paired gate/up, expert 0/511,
small/ordinary activations, every selected Q2 tile width, aligned 64/ragged 65
output rows, and exhaustive finite F16 widening. It saves 44 F32 operator outputs.
Each candidate must pass the unchanged independent relative-RMS and error/peak
limits of 0.002, then match the original implementation's bytes at the same width.
Original outputs already vary slightly across tile widths; they are never
compared against a different width as an exact golden.

| Arm | Independent checks | Maximum relative RMS | Exact files versus original | Maximum absolute delta | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| Original Q2 | 44/44 pass | 0.000164016 | reference | 0 | Reference retained |
| Bounded K loop | 44/44 pass | 0.000164013 | 20/44 | 4.76837158203125e-7 | Exact replay failed |
| Barrier at widths >=32, original unroll policy | 44/44 pass | 0.000164015 | 24/44 | 4.76837158203125e-7 | Exact replay failed |

Maximum independent error/peak is 0.000200514 for all arms. The byte differences
are small and remain within operator tolerance; they are not evidence of broad
model-quality degradation. They do disprove the required exact scheduling-only
behavior. In this compiler configuration, changing unrolling/scheduling changes
rounding despite unchanged source arithmetic. Model quality and performance of
these variants remain unmeasured. The declared gate stops before model profiling
or C1 timing, so no long-context or UD control sweep follows these failures.

All 15 remote commands and all 4 transports exit 0. The numerical acceptance
failures are recorded separately, without rewriting command exit codes.
The four arms have 150 SHA-verified collected artifacts. See
`config/q2-register-results.json` and the per-file comparison reports
`config/q2-register-operators-r1.json` / `q2-register-operators-r2.json`.

## Retained work and next direction

The expanded harness, frozen-reference mode, resource reporting, protocol and
results remain. Rejected code is preserved only in `experiments/`:
`q2-token-barrier.patch`, `q2-bounded-k.patch`, `q2-full-unroll-barrier.patch` and
`q2-wide-token-barrier.patch`. Apply these to the restored Q2 source when
reconstructing an experiment; none is active. Checkpoint `cfe7931` preserves the
bounded-K candidate as it was before qualification.

The active runtime patch SHA256 is again
`3029cd490bc75d045e9dcf696ac6c1b23092684ad25641c93d500cb9f2727473`;
all 1019 source files match the frozen original-Q2 reference. This experiment
supports investigating bounded register lifetimes, but a retained implementation
must control the actual FP32 accumulation/contraction order while preserving
Q8 activation bytes and rounded Q2 scale/min terms. Merely changing a compiler
pragma or copying UD's barrier is insufficient under the exact replay contract.
Dense F16 HC projection remains a separate decode bottleneck from the prior
profile; these experiments did not address it. The no-regression target versus
UD is still unmet.

Fresh closure at 2026-10-02 04:22:17.419 UTC verifies four runners absent, 15 command
PID/start identities and owned groups retired, KFD empty, and all four expected
leases acquired EX|NB and released. Core received the explicit handover. No Q2
job or retry remains; no deployment, merge or publication occurred.

## Subsequent owner-authorized performance exploration

The owner later requested measuring speed before fixing numerical differences.
[Q2-PERFORMANCE-EXPLORATION.md](Q2-PERFORMANCE-EXPLORATION.md) retains the resulting
four-arm campaign, measurable PP gains and model-frontier drift. This historical
operator campaign and its exact replay failures remain unchanged.
