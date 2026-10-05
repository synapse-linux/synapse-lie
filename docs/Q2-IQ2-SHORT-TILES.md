<!-- SPDX-License-Identifier: MIT -->
# Whole short-expert IQ2 tiles

This isolated candidate starts from the measured1505.152258 PP /25.15493858 TG
IQ2 raw-prefetch provider. Entire nonempty expert buckets containing1..48 rows
use the existing BN48 gate/up kernel. All other experts retain original128/64
descriptors; original Q2 down routing, weights, arithmetic, tables and decode
remain unchanged. The own C17 builder preserves map capacity and allocates
nothing. No extra count download or GPU stream is introduced.

The [saved routing audit](../config/q2-iq2-tail-audit.json) contains11280 short
buckets out of14620 active expert-layer buckets across48 layers. It describes
an earlier selective composition, not a new current-best trace. A lower row
reservation does not establish a throughput gain. Only whole short buckets
are eligible: changing a hot expert's64-row tail to48 would misinterpret its
width-relative index.

The first prepared provider is retained without overwrite. A distinct counted
provider stores at most256 span records in the executor and emits them only
at teardown, after the original tester's complete event. Copies stay inside
inference timing; no timed I/O, device allocation or count transfer is added.
Its1027-file inventory changes five files, including the new C17 builder/header.
All eleven numerical HIP/include sources match the measured parent exactly.

Local independent row-coverage, descriptor-preservation and capacity checks
pass, including all single counts and two-expert splits up to4096 rows and
the512-expert bound. The same binary passes ASan/UBSan/LeakSanitizer outside
sandbox ptrace; the initial LeakSanitizer environmental failure remains saved.
Host/device fixture syntax and executor syntax pass; an initial standalone
executor command missing the existing MMQ include directory also remains saved.
The105 launcher scope guards pass. These are preparation, not GPU evidence.

The new GPU fixture compares the same production kernels under original128/64
and proposed128/64/48 maps. It covers n1/15/17/33/48/49/65/128/129, ragged output
columns, empty experts and three2048x640x2560/top10 distributions: uniform64,
uniform512 and512 experts with8 hot buckets plus504 short buckets. Three weight
rotations give39 complete output pairs; alternating arms retain42 timing
samples including warmups. Large weight sets exceed32MiB MALL. Output guards,
unwritten values and immutable inputs are checked; unsafe cases stop device
work. Safe numerical or timing rejection does not suppress the original model
performance run.

The original exact2048/tg128 input, capacity9216, chunk2048, C1 greedy, MTP-off,
one warmup/three measurements and127 timed decode calls stay fixed. Saved Q2
1443.672867, best1505.152258 and UD1685.777092 comparisons are reused without
rebuilding or rerunning them. The full-model run includes map construction,
upload, any additional dispatch and bounded record costs excluded from the
synthetic kernel interval. Q4 and the complete context curve remain deferred.
No numerical acceptance, performance improvement or parity is claimed yet.

[Counted source](../config/q2-iq2-short-tiles-source-v2.json),
[preparation audit](../config/q2-iq2-short-tiles-static.json),
[fixed plan](../config/q2-iq2-short-tiles-plan.json).
