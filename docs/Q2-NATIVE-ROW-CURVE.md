<!-- SPDX-License-Identifier: MIT -->
# Canonical model gate for scaled-row input reuse

The [scaled-row component probe](Q2-SCALED-ROW-REUSE.md) improves packing
medians by about 15%, while complete packing/down improves only 0.4–1.8%
against the repeated unchanged control. It preserves all tested output bytes
and also the control's independent numerical failures. This model gate tests
whether that component gain survives the complete canonical workload.

[Frozen plan](../config/q2-native-row-curve-plan.json): ordered Q2 reference,
scaled-row Q2, ordered Q2 repeated, then pristine UD. All eight cached depths
0/4/8/12/16/32/64/128K, prose calibration, approximately 2048 new tokens,
128 outputs, one warmup and one measured sample per depth remain unchanged.
The client is the same frozen native C `synapse-lie-bench` at `b598e4c`;
the measured C17 server is the same `15c6082` snapshot. Each model arm rebuilds
its complete MMQ library. No new scale-reuse or mixed-tile patch is combined.

The separate `q2-curve-row` mode requires the native client, matched source
manifest and unchanged component evidence. Its build identity is
`q2-canonical-curve-scaled-row-reuse`. The CMake composition checks the full
provider inventory and rejects other numerical or diagnostic compositions.
There is no core ABI, state-layout, scheduling or metrics contract change.
Python only supervises owned processes/leases and audits retained evidence;
the native C client generates and issues all model requests.

The RAM prefix checkpoint budget remains 16 GiB, capture at finish enabled,
SSD/MTP/vision/thinking disabled. The 128K point measures new-token prefill
after a prepared prefix, not fresh prefill of the entire 128K. System file-cache
occupancy is recorded separately; its machine-wide size is not per-model
residency or KV size. No cache drop, cold-cache claim or tuning is admitted.

Keep all failures and both controls. Compare the entire Q2 calibration,
warmup, prefix and measured request/reply/count histories before attributing
a change to the candidate. The unchanged-control drift and all separate cache
capture/restore/HTTP timings remain visible. Exact replay cannot replace
independent numerical qualification, and whole-curve parity remains open.

## Qualification status

Host Debug and ASan/UBSan complete 22/22 each on .157; six commands exit zero.
Their source capsule must match the frozen plan before GPU admission. The
client's existing .157 conformance remains applicable because its complete
source inventory and command protocol are unchanged. Model results and fresh
admission are not established by these CPU checks.
