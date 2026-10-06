<!-- SPDX-License-Identifier: MIT -->
# HC raw-Q8 injection model integration

The retained parent is **1587.893545 PP / 25.12414406 TG**. Fixed UD remains
**1685.777092 PP / 24.34174251 TG**. This integration has no new model result yet.
The benchmark remains exact 2048 input, 128 output tokens, 127 timed decode
calls, capacity 9216, chunk 2048, C1 greedy, MTP off, one warmup and three
measurements with 15-second pauses outside the timers.

Only the raw-Q8 HC route changes. The producer uses normalized values already
in registers to emit compact injection products; the reducer consumes these
products instead of rereading four normalized streams. The existing numerical
component reported a marginal 0.211436% complete-cycle reduction and finite
injection differences up to 4.768371582e-7. Neither is a model-level gain or
independent task-quality result. The existing component is not rerun.

The 20 MiB product buffer borrows the original `down_e` allocation. The C17
policy requires the allocation base, sufficient bytes, exactly 2048 rows,
H2560/rank320/four streams, and no pending expert output. Offset RowScratch
views fail admission. Capacity arithmetic rejects overflow. The allocation
identity is owned by the executor and never modified by scratch view switches.
Combine, producer, reducer and the next expert writer use the same ordered
stream; no borrow remains published between calls. Failed launches return
before half/Q8 cache identities are published; no fallback retries after writes.
Other shapes and routes use the retained implementation. Device allocations,
streams, graph behavior and persistent caches do not change.

Static compilation preserves all 164 parent kernel bodies and both component
bodies instruction-for-instruction and resource-for-resource. The private
provider has 1030 files. All 37 CTests and 37 ASan/UBSan CTests pass on .157,
including allocation identity, offsets, pending readers, exact capacity and
overflow cases. CPU policy checks are not model inference or a GPU race proof.

The frozen plan admits one original-model candidate after fresh ownership
checks. Saved Q2, stable parent, experimental parent and UD are reused without
rebuild or rerun. All outputs, logits, timing samples and numerical differences
will be retained. No Q4 or full-context curve is admitted at this point.

[Source binding](../config/q2-hc-inject-raw-q8-source.json),
[static comparison](../config/q2-hc-inject-raw-q8-static.json),
[frozen plan](../config/q2-hc-inject-raw-q8-plan.json),
[component findings](Q2-HC-INJECTION-REUSE-RESULTS.md).
