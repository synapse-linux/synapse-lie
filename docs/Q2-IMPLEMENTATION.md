<!-- SPDX-License-Identifier: MIT -->
# Original Q2 compatibility — qualification in progress

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
| `q2-operators-r1` | 1 | Build capsule missing HIP compile definition; no GPU operator |
| `q2-operators-r2` | 0 | Independent synthetic quantized HIP operators and F16 widening pass |
| `q2-model-r1` | 1 | CMake HIP language scope error; no model payload |
| `q2-model-r2` | 1 | Missing argmax link dependency; no model payload |
| `q2-model-r3` | 1 | Executable built; original metadata refused for missing RoPE sections before upload |

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
Full-model correctness, no-regression, C2/4/8, HTTP and long-context gates are
still open. Values from absent tests must remain absent, never zero-filled.
