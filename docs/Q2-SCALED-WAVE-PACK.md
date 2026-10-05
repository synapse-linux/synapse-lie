<!-- SPDX-License-Identifier: MIT -->
# Wave-owned scaled Q2 activation packing

This new experiment starts from the retained shared-pair provider at
1573.621201 PP /25.11363913 TG. The original exact2048/tg128 fixture, saved
Q2 1443.672867 and UD 1685.777092 comparisons remain fixed. GPU numerical and
complete-model performance measurements are pending; static resources and host
tests do not establish a speedup. Independent inherited F16 quality remains open.

The active IQ2 gate/up kernel already fuses SwiGLU. Its 640-value output row
is produced by ten independent64-column blocks. Moving the existing whole-row
maximum into that epilogue would require cross-block coordination or a changed
scaling/accumulation contract. This preparation preserves that contract and
instead changes ownership inside the subsequent packing pass.

One wave owns each full640-value row, and eight waves prepare eight independent
rows per256-thread block. Each lane retains five float4 values, reduces its
absolute maximum within the wave, broadcasts the original bounded power-of-two
multiplier and writes four rounded halves per group. Entire tail waves return
together. Unaligned input/output bases retain bounded accesses; the final input
row ends at the allocation boundary in the fixture. No additional allocation,
stream, buffer layout, public ABI, state or metric changes are introduced.

At2048 tokens and ten experts/token the packing grid falls from20480 to2560
blocks. The saved1571 diagnostic attributes17.096259ms to the original packing
pass; it does not profile this candidate or predict an additive model gain.
The whole F32 row is still read once and the F16 row written once.

Same-flag gfx1151 compilation replaces one kernel and preserves the other161
production instruction/operand/resource bodies. Packing resources change from
13 to30 VGPRs,36 to0 LDS bytes, and retain zero private bytes. Two block barriers
become zero; the static instruction body grows174 to238 instructions because
each lane owns more values and the bounded alignment paths remain. These are
static counts, not dynamic instruction totals or measured GPU throughput.

The new fixture has25 complete packing cases with full independent scalar
double-ldexp/integer RN-even checks, two complete unchanged-down replays and28
alternating timing samples. Ragged row counts, signed zero, subnormals, large
finite values, halfway ties and input/output alignment are covered. Production
input52,428,800bytes and512-expert weights330,301,440bytes independently exceed
32MiB. Packing-only and packing-plus-down have separate scopes; original-model
timing follows even after a safe numerical or timing rejection. A guard fault,
unwritten/nonfinite result or device error prevents further device work.

Local host/device fixture compilation and132 launcher guards pass. Separate
.157 host27/27 Debug and27/27 ASan/UBSan checks finish at16:21:56.353618UTC,
with six zero command exits and seven collected artifacts. The shared formatter
retains its88 findings in seven unchanged provider files. The initial new-file
format check used the editing-root fallback style; its failed result and source
are retained. Regeneration with the provider style passes the changed-file
check and preserves every compiled instruction/resource body. The initial
local staging helper import failure is also retained and corrected; it launches
no remote process.

[Source](../config/q2-scaled-wave-pack-source.json),
[static evidence](../config/q2-scaled-wave-pack-static.json),
[host evidence](../config/q2-scaled-wave-pack-host-results.json),
[plan](../config/q2-scaled-wave-pack-plan.json).
