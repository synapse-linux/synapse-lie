<!-- SPDX-License-Identifier: MIT -->
# Compact expert producer and consumer chain

This new experiment starts from retained scaled-wave-pack1574.505432 PP /
25.17589001 TG. The preceding expert-order variant improved its isolated cycle
but measured1571.009498 PP, so it is preserved without replacing the parent.
Fixed Q2/UD remain1443.672867/1685.777092; another7.067086% PP is required at
the unchanged exact2048/tg128 point. No new GPU performance is established by
this preparation. Independent inherited F16 quality and full-curve parity stay open.

The previous layout gathered slot-major rows while packing and wrote padded
rows. The new gate/up producer instead writes compact logical expert-major
F32 rows. The original wave-owned packing kernel reads those rows contiguously,
and adapted Q2 down reads the same compact layout. Down still writes original
slot order, so weighted combination is unchanged. Actual GPU scatter order
within an expert may vary; equality must be checked after reconstructing the
permutation from each arm's saved device maps.

The existing routing prefix dispatch computes both padded map offsets and
logical activation offsets. Gate/up keeps the existing input token map and
16/48/64/128 tile arithmetic. Packing preserves the complete640-value maximum,
dyadic scale and rounded half conversion. Down keeps logical640/stored768 tails
and16/48/64 specializations. No new allocation, GPU dispatch or stream is added.
At2048/top10, scaled half rows, inverse scales and513 logical offsets occupy
26,298,372 bytes inside the existing52,428,800-byte up scratch. The original
F32 gate allocation is unchanged. Same-stream last-reader ownership is retained;
public C ABI, persistent state and metrics are unchanged.

Local same-flag production assembly preserves162 prior instruction/operand/
resource bodies and adds eight kernels with zero private scratch. These are
one routing prefix, four gate/up and three down bodies. Successful compilation
does not prove output correctness or performance. The separate fixture compiles
for host and gfx1151;136 launcher guards pass. Shared formatting retains inherited
failures rather than rewriting qualified source. The initial source-generator
anchor failure is preserved before its correction.

The GPU fixture covers twenty partial-token/gate-tile combinations plus before/
after replays of balanced and skew production routing. It saves432 full arrays:
both five-map routing sets and four numerical outputs for all24 cases. CPU
counts/prefixes and complete permutation identities independently check routing.
Every F32 gate, F16 activation, inverse scale and F16 down output is compared
after canonicalizing expert order. Scalar conversion checks every packing cell.
The offline analyzer separately reconstructs routing and conversion from saved
arrays, preserving signed-zero failures and actual command exits.

Gate/up and the complete routing/gate/up/packing/down cycle each receive two
warmups and five alternating measured pairs, three iterations per sample, for
56 timing records across the two production distributions. Active weights exceed
32MiB MALL; allocations, upload and checking are excluded. A safe numerical or
timing rejection still permits the original model performance test. Guard,
nonfinite, unwritten-output or device failures stop further GPU work.

The model arm uses the unchanged original input/timers:2048 prompt tokens,
128 outputs/127 timed decode calls, capacity9216, chunk2048, MTP off, greedy C1,
one warmup and three measured requests with15-second cooldowns outside timing.
Only the new candidate is built/run; saved parent/Q2/UD evidence is reused.
Q4, context sweeps, cleanup, dependencies, tuning and deployment are excluded.

[Source](../config/q2-compact-expert-chain-source.json),
[static comparison](../config/q2-compact-expert-chain-static.json),
[frozen plan](../config/q2-compact-expert-chain-plan.json),
[fixture](../tests/q2_compact_expert_chain.hip),
[offline replay](../tools/analyze-q2-compact-expert-chain-component.py).
