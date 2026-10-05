<!-- SPDX-License-Identifier: MIT -->
# Selective Q2 down tile composition

The candidate starts from saved MoE-deferred PP 1496.830907 / TG 25.17435733,
with fixed Q2 1443.672867 / 25.09595499 and UD 1685.777092 / 24.34174251.
The unchanged original exact2048 input, capacity 9216, chunk 2048, one warmup
and three measured sessions, tg128 / 127 timed decode calls and 15-second
waits outside timers define the comparison. The full PP/TG context-curve target
remains; no full sweep precedes fixed-point parity.

The retained scaled-tile component already measured 48/64/128-row Q2 kernels.
Tile64 saved 4.491455% at 64 active experts / 320 rows each, but regressed
3.507319% at 128 active / 160 rows and 0.395792% at 512 active / 40 rows.
Tile128 regressed all three. All 32 operator width replays and six benchmark
outputs were exact; strict independent numerical failures remain. This
experiment reuses those qualified bytes and actual timings without rerunning
the component or changing its original rejection.

The existing model already mixes 128/64 gate/up tiles. Its Q2 down projection
still uses 48-row tiles throughout. The new owned C17 policy chooses 64 for
an expert only when its 16-padded bucket has at least 256 rows and its total
64-row reservation does not exceed its 48-row reservation. Remaining buckets
use 48. Both spans contain complete experts, so their outputs are disjoint;
the original activation packing, inverse scales, per-output K accumulation,
gate/up maps and all numerical kernels remain unchanged.

The map validates bounded expert/token counts, total routes and output
capacity before writing anything. Failure preserves the caller's map and
span metadata. Descriptors encode expert in bits 0..15 and width-relative
tile index in bits 16..30. The C17 fixtures independently enumerate live and
padded row coverage, width ownership, exact buffer capacities, sentinel guards
and preserved outputs on rejection. They exhaust bucket lengths and split
positions through 4096, reproduce all three saved synthetic distributions,
cover a mixed hot/cold distribution and test the maximum 512×4096 bound.
These host fixtures execute no model or GPU numerical forward.

The new down map occupies the existing reservation, followed by the unchanged
gate/up spans. No device allocation, stream, synchronization, weight conversion
or model-state precision change is added. A bounded 256-entry host record stores
histograms and selected/reserved row counts. It emits JSON only at executor
teardown, after the original tester's complete event and outside PP/TG timers.
The map preparation and record copies remain part of actual model execution.
Truncation must be explicit if calls exceed record capacity.

Five files change in a 1027-file provider: executor source/header, provider
CMake and the two owned C17 policy files. Every numerical kernel is exact to
the saved parent. C17 and executor syntax checks pass; local launcher scope
guards pass 81/81. The frozen plan permits one new original-weight model with
its own MMQ build, performance retained independently of numerical acceptance.
It excludes old component/model-control reruns, curve, dependencies, tuning,
deployment and cleanup. A fresh coordinated window is required for GPU work.

The `.157` host capsule passes 25/25 Debug and 25/25 ASan/UBSan, including the
new exact-capacity map fixture. All six command exits are zero; seven artifacts
and 29 frozen fixtures verify. No GPU or model is opened by this gate. Parent
and old component result hashes remain unchanged; no performance or quality
acceptance is inferred from CPU success.

[Source and original kernel identities](../config/q2-scaled-selective-source.json),
[owned policy](../experiments/q2_scaled_tiles_map.h),
[coverage fixture](../tests/q2_scaled_tiles_map.c),
[composition patch](../experiments/q2-scaled-selective.patch),
[retained component and failures](../config/q2-scaled-tiles-results.json),
[static checks](../config/q2-scaled-selective-static.json),
[host receipt](../config/q2-scaled-selective-host-results.json),
[frozen model plan](../config/q2-scaled-selective-plan.json).
