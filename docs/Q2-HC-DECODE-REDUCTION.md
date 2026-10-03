<!-- SPDX-License-Identifier: MIT -->
# Scalar HC down: preserve the sum tree with fewer shuffle instructions

This candidate is **prepared, not GPU-qualified**. It changes the scalar F16
HC down reduction only. The original kernel is retained as an exact source
and assembly control in the same component binary. No runtime performance or
numerical acceptance follows from the static results below. Q2/UD parity
remains unmet; the latest measured checkpoint is [e6f425e](Q2-DECODE-BASELINE.md).

The corrected historical-prompt comparison leaves Q2 about **0.60013 ms/token**
behind fresh UD. The preceding diagnostic profile attributes 2.97921 ms/token
to Q2 HC down, versus 1.68305 ms/token for UD's corresponding quantized path.
These are different stored formats; all of that difference is not necessarily
recoverable. The actual full-model rate, including prefill, remains the gate.

## Why this mechanism

Sixteen waves per row are already retained. Four-wave register prefetch and
32-wave row partitioning were previously slower; those negative results remain.
Inspection of the current compiler output also shows that vector loading is
already done: each iteration uses one 64-bit weight load and one 128-bit
activation load. Adding source-level vector types would not establish fewer
loads or less traffic.

Each original wave sum uses five dynamically addressed `ds_bpermute_b32`
exchanges, plus lane-address calculations and waits. HC down performs one sum
for each wave and another over the wave partials. Pinned Gufo already has an
immediate XOR primitive in `ReduceKQuantWave` and a row-DPP primitive in GDN.
The candidate applies those mechanisms to this HC specialization:

1. XOR16 uses one immediate `ds_swizzle_b32` exchange.
2. XOR8, XOR4, XOR2 and XOR1 use row-DPP operations.
3. Explicit round-to-nearest additions preserve the descending 16,8,4,2,1 tree.

The matrix, F16 weight bytes, F32 inputs, multiply/FMA sequence, five-iteration
load loop, 16-wave/512-thread row ownership, LDS partials and barrier are fixed.
The compiler's global-cache invalidation at that barrier is also retained.
There is no change to prefill, HC up, expert kernels, model storage, allocation,
C17 scheduling, public ABI or persistent state. Dispatch remains n1/M320/K10240.

## Static evidence

| Generated-code property | Original control | Candidate |
|---|---:|---:|
| Static assembly instruction lines | 123 | 91 |
| Dynamic-address LDS permutations | 10 | 0 |
| Immediate LDS XOR permutations | 0 | 2 |
| DPP operations | 0 | 8 |
| Vector registers | 13 | 13 |
| Scalar registers | 12 | 12 |
| LDS bytes | 64 | 64 |
| Private scratch bytes | 0 | 0 |

The eight DPP operations are six fused add modifiers and two DPP moves with
separate final additions. The count includes branch/wait/cache instructions;
it is a static instruction inventory, not a dynamic execution count, bandwidth
measurement or speedup estimate. The removed 32 instructions are outside the
multiply/load loop. Both original-control assembly bodies match exactly, and
the candidate's entire multiply/load loop matches after normalizing label IDs.
Both kernels compile as wave32 for gfx1151 with the recorded production flags.

The [static audit](../config/q2-hc-decode-reduce-static.json) verifies the full
1020-file reconstruction through a zero-fuzz patch. Two source files change;
1018 remain unchanged. Device-only compilation, strict host-only fixture syntax
and changed-file formatting pass. These editing-host checks execute no GPU or
model code. The shared formatter retains the same five untouched upstream-test
violations as the parent source, with exit 1 and identical logs. An initial
fixture-syntax warning exposed the original `main`'s implicit successful return
when reused under another function name. Its return is now explicit; the
initial warning is retained and strict `-Wall -Wextra -Werror` syntax passes.
The reused first-party fixture also receives whitespace-only formatting; its
initial format failure and successful recheck are preserved separately.

## Prepared GPU qualification

Runtime checks must use `.157` after core's verified handover, with the original
four leases and unchanged thermal/model ownership rules. Core currently retains
that window for its C17 sampler/MTP/cache qualification. No Q2 remote job,
waiter or automatic restart is scheduled.

The new component fixture uses the real `SmallGemm` candidate dispatch and a
preserved-control entry point. It retains the eleven independent FP64 HC cases
and their original 2e-5 relative-RMS/error-over-peak limits. Six direct full-buffer
pairs cover ordinary, tiny, alternating-sign and signed-zero inputs, F16
subnormal weights and F32 subnormal inputs. Inputs end at their live allocations;
output guards and finite/full-write checks remain active.

The benchmark rotates sixteen original-layout F16 matrices, **100 MiB** in
aggregate, in the same `hipMalloc` allocation for both kernels. Every rotated
matrix has a saved reference/candidate output pair. After warmup, five measured
pairs alternate which kernel runs first, with 128 launches per arm and GPU-event
timing. Output copies/comparisons are outside those intervals. All 27 complete
pairs and the eleven independent outputs are saved: **65 data files**. Numerical
failures retain exit 1 while allowing the paired performance measurements;
resource/runtime failures still stop the experiment.

Required sequence after fresh admission:

```sh
python3 tools/q2-remote.py cpu q2-hc-decode-reduce-host-r1
python3 tools/q2-remote.py collect q2-hc-decode-reduce-host-r1
python3 tools/q2-remote.py hc-decode-reduce-bench q2-hc-decode-reduce-component-r1 --source-variant hc-decode-reduce
python3 tools/q2-remote.py collect q2-hc-decode-reduce-component-r1
python3 tools/analyze-q2-hc-decode-reduce.py evidence/q2-hc-decode-reduce-component-r1 --output config/q2-hc-decode-reduce-results.json
```

The launcher accepts this source only for its component experiment. Host CTest
and ASan/UBSan, GPU pair equality, independent metrics and throughput are all
**pending**. A useful component saving with exact replay is required before
admitting fresh complete-model measurements. Existing scaled/library numerical
rejection remains separate and cannot be cleared by this scalar experiment.

## Provenance and reconstruction

The generator derives from the measured `library-norm-bound` source at official
Gufo pin `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. It verifies every parent
file, preserves the original kernel, records all child hashes and refuses
existing destinations. Upstream licenses/notices remain; the first-party
experimental delta is MIT. No DS4, sibling-workspace or antirez engine code
is imported.

- [Generator](../tools/prepare-q2-hc-decode-reduce.py)
- [Patch](../experiments/q2-hc-decode-reduce.patch)
- [Source inventory](../config/q2-hc-decode-reduce-source.json)
- [Actual static command receipts](../config/q2-hc-decode-reduce-static-commands.json)
- [GPU fixture](../tests/q2_hc_decode_reduce.cpp)
- [Runtime analyzer](../tools/analyze-q2-hc-decode-reduce.py)
- [Coordination and acceptance plan](../config/q2-hc-decode-reduce-plan.json)
