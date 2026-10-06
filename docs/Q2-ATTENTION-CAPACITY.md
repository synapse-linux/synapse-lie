<!-- SPDX-License-Identifier: MIT -->
# Sparse attention at the 256K capacity boundary

The completed [256K curve](Q2-CURVE256.md) exposes a dispatch problem shared
by Q2 and UD: the allocated mask pitch reaches 2080 words at capacity 266240,
and the original WMMA launcher rejects pitches above 2048. Short visible
contexts therefore also take the existing scalar attention route. This is
separate from the fixed exact2048 benchmark, whose capacity remains 9216 and
whose retained Q2/UD prefill is 1587.893545/1685.777092 token/s.

The new private providers distinguish allocation pitch from visible extent.
The C17 guard rejects zero length, arithmetic overflow, insufficient pitch and
visible spans beyond 266240. Within this extent, larger pitch remains a valid
row stride. The GPU scan has nine local words per thread and 2080 shared union
entries. The compact selected-block list keeps its existing 2052-entry limit;
its switch to the bitset representation is unchanged. Removing the original
launcher guard without these storage changes would be unsafe.

No matrix, softmax, F16 rounding or output arithmetic expression is changed.
The saved parent assembly is reused: 162 of 164 numerical bodies preserve
every instruction/operand and resource count. Only the two sparse attention
bodies change. VGPR counts stay 223/231, private scratch stays zero and shared
memory grows from 29744 to 29856 bytes. Static instruction counts grow by 87
in each body, from 4968/4966 to 5055/5053. These are compilation observations,
not measured GPU speed or numerical acceptance.

## Qualification scope

The new C17 test exhausts visible lengths through the admitted boundary and
scan ownership through 2080 mask words. GPU checks use the unchanged official
Gufo FP64 formula and the unchanged per-token attention implementation. Eight
new cases cover oversized pitch at short context, both attention schedules,
the native 262144 boundary, the 266240 headroom limit, compact and noncompact
masks, replay, guarded outputs, last-only rows, rejected launches and immutable
inputs. The selected masks include the first and last complete block.

Two additional 128-row cases at 16K and 256K compare complete gated attention
via WMMA and the fallback. They retain two warmups and five alternating
measurements, synchronized wall time and raw HIP event time. Every timed
output is compared to its pre-timing result. Finite numerical failures remain
visible and do not suppress timing; unwritten/nonfinite values, changed
guards/inputs or device faults stop execution. This fixture performs no model
inference and cannot establish whole-model or whole-curve parity.

The original FP64 tolerance remains 1e-6 for per-token attention and the
original WMMA absolute envelope remains 2e-2. Correctness rows evaluate the
complete FP64 formula; timed 128-row cases compare all outputs to the unchanged
GPU fallback. These scopes are explicit in the machine-readable records.

Local production assembly, fixture host/device compilation and launcher
checks pass. The shared upstream formatter retains 101 inherited diagnostics;
the new header and GPU fixture pass their formatting check. The initial
12 header formatting diagnostics and the whitespace-only correction are
preserved. The .157 host cohort finishes at15:56:48 UTC with38/38 Debug and38/38
ASan/UBSan checks, six zero command exits and seven collected artifacts. The
frozen plan binds226 runtime fixtures and six manifests. GPU admission and
operator results are pending; no new throughput result is claimed by preparation.

Sources: [manifest](../config/q2-attention-capacity-source.json),
[static audit](../config/q2-attention-capacity-static.json),
[GPU fixture](../tests/q2_attention_capacity_gpu.hip),
[provenance](../third_party/gufo/LIE-Q2-ATTENTION-CAPACITY.md).

The change is private and experimental. Public ABI, serialized state, metric
definitions, expert cache and model files are unchanged. Capacity beyond model
metadata still needs independent model-quality qualification. This correction
addresses the long-curve dispatch defect; it does not close the fixed PP gap.
