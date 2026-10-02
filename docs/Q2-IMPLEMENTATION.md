<!-- SPDX-License-Identifier: MIT -->
# Original Q2 compatibility — initial model screen

The implementation is a reviewable patch to official Gufo `f783fedb`, in the
isolated `feature/antirez-compat-audit` worktree. No antirez Qwen engine or
sibling project source is used. The C17 LIE core and server branch are unchanged.
This is the transitional numerical implementation, not an owned C17 forward.

## Runtime change

- Recognize MXFP4 descriptor size (32 values / 17 bytes) so the original file's
  unused predictor can be validated with MTP off. No MXFP4 forward is enabled.
- Bind the AR IQ2_XXS gate/up matrices and padded Q2_K down matrices strictly.
  Logical FF stays 640; stored down input is 768. Other role contracts stay
  intact. No on-disk conversion or expert expansion to dense weights occurs.
- Use the existing HIP Q8 activation quantizers with logical input strides;
  they zero the padded lanes. This avoids a separate float padding pass.
- Route IQ2/Q2 through quantized vector and matrix kernels, including paired
  gate/up PP and fused gate/up/SwiGLU TG. Preserve the fractional eighths in
  the IQ2 vector dot product instead of truncating them with integer division.
- Widen 96 small F16 HC injection matrices exactly to F32 once at load. Their
  additional final resident cost is 7,864,320 bytes; source/staging overlap is
  separate. The original F32 fused injection path then remains available.
- The original file lacks `qwen4exp.rope.dimension_sections`. Only the known
  padded-Q2 source profile (repository/revision plus both down-width markers)
  supplies the pinned model's `[11,11,10,0]` sections when absent. Explicit
  malformed metadata still refuses. This is a format compatibility rule, not
  relaxed general parsing or long-context scaling.

## Retained runs on .157

| Run | Actual exit | Result and scope |
|---|---:|---|
| `q2-host-r1` | 0 | 4 debug + 4 ASan/UBSan CTests; no GPU/model forward |
| `q2-host-r2` | 0 | Same suites pass after the legacy RoPE rule |
| `q2-operators-r1` | 1 | Build capsule missing HIP compile definition; no GPU operator |
| `q2-operators-r2` | 0 | Independent synthetic quantized HIP operators and F16 widening pass |
| `q2-model-r1` | 1 | CMake HIP language scope error; no model payload |
| `q2-model-r2` | 1 | Missing argmax link dependency; no model payload |
| `q2-model-r3` | 1 | Executable built; original metadata refused for missing RoPE sections before upload |
| `q2-bench-r1` | 0 | Original Q2 semantic smoke and 12 C1 samples complete |

The GPU operator set covers 1/3/8/9/33 tokens, experts 0 and 511, five output
rows (ragged tile), paired/fused IQ2 paths and Q2 down with exact 640-float input
allocations. Weights in the extra stored columns are nonzero; zero activation
padding must remove their contribution. Small and ordinary activations are
checked. F16 widening is exhaustive over finite half bit patterns, including
signed zero and subnormals. These are independent synthetic operator formulas,
not CPU inference or full-model teacher parity.

The fixed relative RMS and scaled maximum error limits are both 0.002.
Maximum observed RMS was 0.000159285 (Q2 PP); maximum scaled error was 0.000186223.
The IQ2 cases were below 0.00000021 RMS. Coverage does not establish unsanitized
full-model finiteness, every expert/batch geometry, memory-safety instrumentation
on the GPU, concurrency correctness or performance. Model and UD controls follow.

Four existing leases were acquired EX|NB in order for every HIP build/run and
released after owned-child retirement. Model files are stat-checked against the
inventory; full payload hashes are historical and have not been recomputed.
The r3 pre/post observations show six desktop DRI processes and unreadable
processes; empty KFD is not universal exclusivity proof. No foreign process,
dependency, power setting, model or DS4 artifact was changed.

## Reproduction and evidence

The exact official archive hash is in `config/gufo-source.json`; the reconstructed
candidate comes from `tools/prepare-gufo.py`. `tools/refresh-patch.py` saves the
source delta, including the numerical vendor files and their retained notices.
The official formatting check passes 486 files (its upstream vendor exclusions
apply). Repository reconstruction checks are local; runtime tests use `.157`.

`tools/q2-remote.py` stages an exclusive persistent run directory, records the
source capsule hash and actual SSH exit, and invokes fixed modes. `cpu` performs
debug/sanitizer CTests with GPU visibility disabled. `operators` acquires leases,
builds and runs synthetic HIP checks. `q2-smoke` and `q2-bench` use the original
Q2 file. `ud-base` uses pristine official source, `ud-patched` the candidate, both
with the same existing UD-Q4 files. `status` is read-only; `collect` saves raw
logs, telemetry, tokens and frontier buffers. No automatic GPU retry is present.

The acceptance protocol and timing scope are in [Q2-VALIDATION.md](Q2-VALIDATION.md).
Full-model teacher parity, no-regression, C2/4/8, HTTP and long-context gates
remain open; the initial practical performance gate failed. Values from absent tests must remain absent, never zero-filled.

## First original-Q2 model result

`q2-bench-r1` completed at 2026-10-02 01:24:00 UTC, exit 0. The original
unchanged GGUF loaded in 11.7014 seconds. Reported resident weights were
43,156,012,544 bytes; per-session allocated state was 376,777,748 bytes at a
9216-token capacity. These are component allocations, not total peak RAM.
The PLE table stayed on the upstream bounded row-I/O path; MTP was disabled.

Arithmetic returned `42`; counting returned `1, 2, 3, 4, 5`. All sampled
frontiers were finite. All four repetitions at each PP length produced identical
input/output tokens and identical complete PP/final logit buffers byte for byte.
This establishes bounded deterministic behavior, not an independent full-model
quality comparison or a general accuracy score.

| Physical prompt | PP min / median / max (tok/s) | TG min / median / max (decode calls/s) |
|---:|---:|---:|
| 512 | 546.96 / 547.20 / 548.72 | 20.75 / 20.79 / 20.80 |
| 2048 | 606.04 / 606.29 / 607.02 | 20.38 / 20.40 / 20.40 |
| 8192 | 559.59 / 559.89 / 560.05 | 20.36 / 20.38 / 20.39 |

One retained warmup plus three measured fresh sessions per length. Each
performance sample emitted 128 tokens with 127 subsequent decode calls; no
EOS occurred in those samples. PP/TG use synchronized executor wall time as
specified in the protocol. This initial Q2 log inherited upstream's two-decimal
stream formatting: printed seconds and rates are rounded, with rates computed
from the original clocks. Later harness logging restores ten significant digits.
No model/kernel algorithm changes accompany that logging correction.

All 52 collected artifacts match the remote SHA-256 manifest. Model stat identity
and binary hash stayed unchanged; postflight KFD was empty and all four lease
path identities matched preflight. Six desktop DRI clients and inaccessible
process observations remain recorded limitations. The UD before/after control is complete in [Q2-RESULTS.md](Q2-RESULTS.md).
Q2 is slower than UD; the performance gate is not met.


## Profiled optimization outcome

The bounded profiler and pristine UD control now have separate PP/TG evidence
in [Q2-PROFILING.md](Q2-PROFILING.md). The first down WMMA candidate passed
synthetic operators but failed its model-frontier gate; its measured 34–64%
PP gain is retained as a [rejected experiment](Q2-DOWN-EXPERIMENT.md).
The runtime described above is restored exactly. `q2-profile` and `ud-profile`
are diagnostic modes, not headline benchmark modes.
