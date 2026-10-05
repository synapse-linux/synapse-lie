<!-- SPDX-License-Identifier: MIT -->
# Eight-half Q2 output stores

This candidate starts from the measured half-pair model at 1566.950178 PP /
25.19259094 TG. When the output base is 16-byte aligned and the row width is
divisible by eight, each lane copies eight existing half values with one
128-bit LDS load and one 128-bit global store. Two lanes cover a token's
16-value wave-local tile row. The retained four-round paired store is the
fallback for all other bases and widths. Neither arithmetic nor rounding,
routing, consumer layout, allocations, streams or barriers change.

The output index and row width are multiples of eight on the vector branch,
so a live starting index implies all eight values are inside the output row.
The shared allocation is explicitly aligned to 16 bytes; wave offsets are
512 bytes and vector offsets are 16-byte multiples. Invalid token slots skip
both the producer and consumer. The fixture tests output base offset 68,
which satisfies the parent's half2 alignment but requires the new fallback.

Only `q2_down_half_storage.inc` changes among the 1026 provider files.
The [static report](../config/q2-down-half-vector-static.json) verifies 158
unchanged bodies and three changed half-down bodies. BN16/48/64 retain
85/96/104 VGPR, 14464/18560/20608 LDS bytes and zero private scratch.
The compiler emits one/three/four new 128-bit global stores for those widths.
Whole-body instruction counts grow 1153→1209, 2321→2482 and 2921→3131
because both the new aligned route and retained fallback are present.
Static body totals do not count executed work or establish a speedup.

The new component includes a literal measured1566 parent template. It checks
720 complete guarded down pairs and 108 ordered-consumer pairs, including
BN16/48/64, narrow/odd/aligned row widths, partial token tiles and unaligned
output bases. The unchanged F32 down path and independent integer RN-even
conversion remain additional format evidence. Both timed arms use the same
half representation and unchanged consumer. There are 168 timing samples
over six full distributions, two scopes and three rotated weight sets beyond
cache capacity. Guard or unwritten-output failure stops device work; safe
numerical differences preserve output arrays and timings.

The [plan](../config/q2-down-half-vector-plan.json) freezes 68 fixture files
and four manifests. Only the new candidate runs the original exact2048,
context9216/chunk2048, tg128/127 timed-decode-call, MTP-off model comparison,
with one warmup and three measured samples. Saved Q2, UD and1566 parent
evidence are reused. No Q4 or full-curve rerun is scheduled.

The original half-storage precision change remains independently unqualified.
Exact agreement with1566 would preserve its arithmetic, not establish task
quality or full-curve parity. No runtime default is promoted by preparation.

Local gfx1151 assembly, host/device syntax and121 launcher guards pass.
The .157 CPU-only gate passes27 Debug and27 ASan/UBSan checks, with all six
commands exiting0 and seven artifacts verified. Component and original-model
results are pending. A fresh window
must validate the previous release
`f2415f576f49438911a070b53fd43fb2b937e83a7837854a916fb4e1fe2092e9` and the
coordination protocol before remote GPU build or execution. No prior lease
is inherited and no cleanup is scheduled.
