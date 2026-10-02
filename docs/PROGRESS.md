<!-- SPDX-License-Identifier: MIT -->
# Progress — Q2 compatibility workstream

2026-10-02: work began on `feature/antirez-compat-audit`, from empty `develop`
commit `ce3ce59aaa8234c2c5aeadc328fead85c5999822`, in a persistent worktree.
The user requires official Gufo support for antirez compressions, Q2 first,
with no performance degradation. No antirez Qwen engine is selected.

Completed: independently pinned source audit, exact historical Q2 layout
manifest, binding/packing/dtype/resource proposal and per-profile PP/TG
no-regression protocol. The official Gufo HEAD examined is still missing Q2
model wiring. A concrete down-width mismatch blocks the examined llama.cpp
reference. Neither source inspection nor historical evidence is a fresh run.

Open: establish an independently runnable exact-Q2 reference on `.157`, then
the minimum Gufo implementation and numerical/performance qualification under
current coordination. The inherited reference-first gate remains open; no
withdrawn source was restored. Q4 follows Q2. Runtime source is unchanged.

LIE baseline `c14ef26` provides `REPLAN.md`, `ANTIREZ-BENCHMARKS.md` and the
historical model inventory. Read-only documentation checkpoint `83d178a`
provides the engine C17 → model family C17 → numerical C ABI separation. The
new format contract fits that boundary without coupling to cache/session ports.
No server branch was merged or copied into this branch.

Provenance: selected files from official `gufo-org/gufo`, `ggml-org/llama.cpp`,
and antirez's format documentation/licenses were downloaded at the exact pins
in [the audit](ANTIREZ-Q2-AUDIT.md). Gufo's quantized HIP vendor notice records
llama.cpp `5c0e9468378eba6bf3cc1989ff5d62fbbe4d9e3a` with MIT provenance; that
vendored-kernel pin differs from the independently examined model-reference
pin. Third-party source remains ignored, read-only research, not redistributed
under a new notice. No source hashes beyond Git identities were introduced.

The saved layout comes from this repository's existing
`evidence/antirez-layout-readonly-r2/layouts.jsonl`, not imported sibling code.
The small manifest records historical model/header identities explicitly;
payload and full hashes were not reread/recomputed. Source-fetch failures and
actual tool exit codes are retained in `evidence/reference-audit-r1/`.

Validation scope: documentation/manifest consistency and Git whitespace checks
only. No runtime change, CTest/ASan execution, remote build, model conversion,
GPU run, new performance sample or deployment. Implementation tests remain
required on `.157` when implementation begins.

## Authorized implementation — 2026-10-02

The user approved replacing the pre-implementation independent-Q2-engine gate
with independent operator oracles and an unchanged UD control. The previous
blocked-reference audit remains historical evidence, not the active work plan.

Implemented a minimal patch from the independently downloaded official base:
MXFP4 descriptor extent, strict 640/768 binding, IQ2/Q2 quantized HIP dispatch,
paired/fused IQ2 gate/up, zero-padding inside existing activation quantization,
and exact load-time F16 HC widening. Fixed the directly observed integer
truncation of IQ2 fractional eighths in the inherited vector dot formula.
No withdrawn source or sibling engine artifacts were restored.

On `.157`, `q2-host-r1` passed four debug and four ASan/UBSan CTests.
`q2-operators-r2` passed independent synthetic HIP checks; maximum measured
relative RMS error was 0.000159285, under the predeclared 0.002 threshold.
Full-model capsule qualification is in progress. Build failures and actual
exit codes remain in local evidence. The official formatting check passes
486 files. No performance or complete Q2 model-quality verdict yet.
