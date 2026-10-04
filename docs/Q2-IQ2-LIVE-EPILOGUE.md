<!-- SPDX-License-Identifier: MIT -->
# Skip empty IQ2 paired epilogue fragments

Inspection for the [routing diagnostic](Q2-ROUTE-PROFILE.md) finds an opportunity
smaller than a mixed-width map. The active IQ2 gate/up matrix loop already skips
16-row fragments beyond `live_tok_tiles`. Its paired epilogue still writes eight
accumulators per thread to shared memory and executes two workgroup barriers
for each such fragment, although every output-row predicate is false.

The candidate adds a workgroup-uniform guard before those stores. It is limited
to paired IQ2 specializations with more than one token fragment. Every live
fragment keeps its arithmetic, output addressing and both barriers, including
the last live fragment. The condition depends only on the tile descriptor and
expert bucket bounds, which are identical across all threads in the workgroup;
there is no barrier reached by only a subset of threads.

The source starts from measured ordered IQ2 decode, changes only
`kernels.hip.cpp`, and leaves the other 1019 files exact. It retains the original
PLE reader, routing map, tile widths, weight conversion, accumulation order,
SwiGLU expression and down projection. It includes neither the rejected WMMA
sign expansion nor PLE cache-first. The source is separate from the running
routing profile and has no instrumentation.

Both providers compile locally to gfx1151 device assembly with identical
flags; no GPU program is executed by this check. The unpacked IQ2 specializations
used by the model show:

| Token tile | Static instructions before/after | VGPR before/after | SGPR before/after | LDS bytes | Scratch bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 661 / 661 | 82 / 82 | 24 / 24 | 11392 | 0 |
| 48 | 1161 / 1190 | 94 / 94 | 30 / 30 | 15488 | 0 |
| 64 | 1391 / 1414 | 102 / 102 | 30 / 32 | 17536 | 0 |
| 128 | 2381 / 2432 | 148 / 148 | 38 / 40 | 25728 | 0 |

The static body grows because of the guards. Shared-store/barrier instructions
remain present for live fragments; their potential saving is dynamic when a
tail is empty. Unchanged VGPR/LDS and zero scratch do not prove a speedup or
identical compiled outputs. Extra branch/layout cost may outweigh tail savings.

The required next check is a matched complete GPU gate/up cycle, covering full
and partial 16-row boundaries, packed/unpacked outputs, independent FP64 checks,
full-output replay and guard regions. Existing numerical limits remain unchanged;
finite output and performance must remain available on a numerical rejection.
Use original-size rotating weights beyond the 32 MiB MALL cache. Only a qualified
component improvement may advance to an uninstrumented full canonical 0–128K
Q2/control/UD comparison. No model gain, promotion or parity is claimed.

[Source manifest](../config/q2-iq2-live-epilogue-source.json),
[static evidence](../config/q2-iq2-live-epilogue-static.json),
[minimal patch](../experiments/q2-iq2-live-epilogue.patch).

## Component qualification prepared — 2026-10-04

The fixed `iq2-live-epilogue-check` mode now builds the reference or candidate
kernel directly, with no MMQ archive reuse or model access. Both use the same
fixture and measured ordered-IQ2 parent. The component fixture uses four exact
count distributions from accepted canonical continuations. Activations and
encoded weights are synthetic; it does not replay model hidden states.

| Case | New tokens | Gate/up tile | Active weight bytes |
| --- | ---: | ---: | ---: |
| Depth 0, layer 6 | 2040 | 128 | 286387200 |
| Depth 0, layer 0 | 2040 | 64 | 321868800 |
| Depth 131072, layer 16 | 2046 | 128 | 274560000 |
| Depth 131072, layer 6 | 2046 | 64 | 310041600 |
| Full-tile control | 2048 | 128 | 135168000 |

The control has 160 experts with exactly 128 rows each: no fragment can be
skipped, so it exposes the added guard cost. Every active weight set exceeds
32 MiB. Each timed cycle includes activation narrowing, routing compaction and
fused IQ2 gate/up with SwiGLU; allocations and uploads stay outside. Two warmup
samples precede five retained samples of eight calls. Units are microseconds
per complete component cycle, never model token/s.

The assignment builder preserves each recorded count, places ten distinct
experts on every token and independently verifies the resulting histogram.
Operator cases cover both sides of 16-row and tile boundaries, tiny/normal
inputs, partial output rows, packed/unpacked outputs and guard regions.
There are 46 full operator FP64 comparisons and five 256-value independent
cycle samples, retaining the original 0.002 limits. Reference/candidate replay
also compares every value of the five complete cycle outputs. All 102 arrays
occupy 262319680 bytes; only this fixed mode receives a 384000000-byte collection
limit. Tolerance failures retain arrays and performance and return exit 1;
runtime faults and guard corruption stop execution.

The analyzer verifies exact count provenance from the diagnostic log, accepted
request attribution, input/count/route hashes, all outputs, complete cycles,
source/fixture identities and ownership receipts. The separate host route
builder and parser/selection tests require fresh Debug and ASan/UBSan runs on
`.157`; the expected normal host cohort is now 21 tests. Local syntax checks,
CMake configuration and a dry build pass, with no fixture or GPU execution.
The core owns the next GPU window. This preparation does not admit a new run,
establish a numerical result or change any model-rate claim.

[Fixed plan](../config/q2-iq2-live-epilogue-plan.json),
[static wiring receipt](../config/q2-iq2-live-epilogue-wiring.json).
