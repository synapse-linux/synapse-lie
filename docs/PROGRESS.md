<!-- SPDX-License-Identifier: MIT -->
# Progress — Q2 compatibility workstream

## Current state — 2026-10-02

The original antirez Q2 GGUF executes through a minimal patch to official Gufo
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. It passes independent synthetic GPU
operators, parser/sanitizer checks and the bounded full-model semantic/C1 screen.
**The performance gate fails relative to existing UD-Q4:** fresh PP is 48–66%
slower and decode 16–17% slower. The candidate is not accepted for integration.
No 128K/256K expansion follows this failure. [Results](Q2-RESULTS.md) retain all
values, failures, limits and plots; [implementation](Q2-IMPLEMENTATION.md) records
the exact runtime changes.

UD before/after the patch has 47/47 identical token/frontier files. Its median
PP changes by +0.22/+0.19/+0.30%, TG by +0.02/-0.19/-0.09%. The small measured
losses remain explicit; this is not a formal zero-margin no-regression pass.
Q2/UD physical prompts and generated trajectories match across these samples.
No independent full-model Q2 teacher or general model-quality score is claimed.

## Work preserved

Branch `feature/antirez-compat-audit` started from empty `develop`
`ce3ce59aaa8234c2c5aeadc328fead85c5999822`. Audit checkpoint `a0c61f3` and
implementation checkpoint `caf60eb` remain. The source is persistent in this
worktree; the official archive plus `patches/gufo-q2.patch` reproduces all 1019
candidate files byte-for-byte. Original licenses and vendor provenance are kept.
No antirez Qwen engine, withdrawn patch or sibling project source/artifact was
imported. The server/cache worktree was not merged or modified.

The user approved independent operator oracles plus existing UD control in place
of the original pre-implementation requirement for an already runnable exact-Q2
engine. The missing full-model comparator remains a quality limitation. Historical
model metadata and hashes retain their original dated provenance; current runs
check stat identity before/after without rehashing the entire model payload.

## Completed verification

- `.157` CPU: four debug and four ASan/UBSan CTests pass in both host rounds;
  final round includes strict legacy RoPE metadata compatibility.
- `.157` GPU: IQ2/Q2 independent synthetic operators and exhaustive finite F16
  widening pass; maximum RMS 0.000159285 under the predeclared 0.002 threshold.
- `.157` model: Q2 plus pristine/patched UD each complete semantic smoke and
  12 C1 samples (one warmup + three measured per 512/2048/8192 profile).
- 52 artifacts per model arm collected and SHA-256 verified; actual child,
  supervisor and transport outcomes retained. Source/build failures stay visible.
- Local repository checks: official formatting passes 486 files; exact archive
  reconstruction and report/plot generation pass. No local inference tests.

All runs acquired the four existing EX|NB leases. Final Q2-workstream GPU child
retired at 01:31:56 UTC; KFD empty, lease identities unchanged, no job or waiter
left. The next window belongs to the coordinated core test thread.

## Next bounded diagnostic

Source shows Q2 does not enter UD's specialized compacted F16 WMMA expert path
or its F16 intermediate/epilogue fusion. This is a dispatch fact, not measured
attribution of the entire gap. Quantify routed math, gathers, quantization and
synchronization before choosing a packing/layout or WMMA extension.

`experiments/q2-profile.patch` preserves a 2K/16-output profiling preparation;
it is unapplied and unqualified. Test its owned-session process handling on
`.157` before a newly coordinated GPU trace. Current core/GPU work is not to be
interrupted. No performance fix, cache enlargement, model conversion, deployment,
merge or publication is claimed.
