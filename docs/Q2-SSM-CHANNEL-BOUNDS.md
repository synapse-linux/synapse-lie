<!-- SPDX-License-Identifier: MIT -->
# Block-uniform channel predicates in the SSM projection

This source-only candidate derives from the retained original exact2048/tg128
Q2 result, **1585.308983 prefill tokens/s /25.16079073 decode calls/s**.
That result and fixed Q2 **1443.672867 /25.09595499** and UD
**1685.777092 /24.34174251** are unchanged. The retained Q2 still needs
6.337447% more prefill throughput to reach this UD point. There is no new GPU
or model measurement and no full-context comparison in this preparation.

The unchanged SSM wrapper admits M16384, K2560,10240 convolution channels,
four taps and BM256 blocks. The channel boundary is exactly40 blocks from
the start: no block straddles it. Each per-output `row < channels` predicate
therefore equals `r_block < channels`. The candidate states that block-uniform
condition explicitly for the raw projection stores and fused convolution.
All token-tail, history and tile-edge predicates remain. Weight conversion,
ordered K16 WMMA, transpose addresses, convolution expressions, grid, launches
and allocations are unchanged in source.

Integer enumeration covers4096 unique float4 owners and all16384 scalar rows,
including the channel boundary. It checks that every owner has the same channel
classification as its block. This proves the integer partition for the guarded
launch; it does not prove floating-point compiler equivalence or GPU safety.

Matched local gfx1151 compilation reuses saved1585 assembly without recompiling
its provider or benchmark. The source patch reconstructs the candidate exactly,
all1027 provider files verify, and the other161 compiled kernel bodies preserve
instructions, operands and resources. Only the SSM body changes:

| Static property | Saved1585 | Candidate |
| --- | ---: | ---: |
| Instructions, including scheduling |3864 |3825 |
| Next-free VGPR |241 |241 |
| Next-free SGPR |17 |17 |
| LDS bytes |49152 |49152 |
| Private segment bytes |0 |0 |

The static instruction reduction is1.009317%. WMMA, block-barrier, global128-bit
load/store and LDS128-bit load/store counts are unchanged. This is not a1%
throughput prediction. Changes in branch masks also change paired F32
instructions and compiler scheduling; the full mnemonic delta is retained.
Unchanged source arithmetic does not establish unchanged compiled rounding.

Generation, production assembly, existing fixture host/device syntax and the
static audit each exit0. Compiler diagnostics retain the inherited weight-enum
switch and fixture `hipFree` warnings. These local checks do not initialize a
GPU or execute inference. No .157 build, job, lease, waiter, reservation or
cleanup occurs. The latest GPU release remains
[`7a3722f3`](../config/q2-counter-calibration-v2-window-release.json).

The candidate is now bound into the leased runner under its own component
and original counting modes. A separate source registry preserves all four
historical SSM registrations. Fresh .157 host qualification completes at
2026-10-06T01:27:38UTC:31 Debug and31 ASan/UBSan tests pass, six commands exit0
and seven collected artifacts verify. The frozen plan binds105 fixtures,
13 manifests and1027 provider files; no qualified model control is rebuilt.
The existing syntax-checked SSM fixture uses
the literal saved1580 control; that identity must stay explicit if reused.
Fresh GPU admission is still required. Measure the new candidate on .157 with guarded complete outputs and the
unchanged original2048/tg128 model. Compare saved1585 outputs and all fixed
historical rates without rerunning qualified controls. Safe numerical or
component timing rejection still permits the requested model performance run;
unsafe writes/runtime errors stop device work. Independent task quality and
full context/concurrency parity remain open.

[Source inventory](../config/q2-ssm-channel-bounds-source.json),
[static audit](../config/q2-ssm-channel-bounds-static.json),
[patch](../experiments/q2-ssm-channel-bounds.patch),
[generator](../tools/prepare-q2-ssm-channel-bounds.py),
[audit tool](../tools/analyze-q2-ssm-channel-bounds-static.py).
[Runtime plan](../config/q2-ssm-channel-bounds-plan.json).

The separate compressed expert-cache experiment already references original
**antirez/ds4**, independently fetched at0aaea5a238fb41a35106a551e73c8409dfb751ac.
It retains original IQ2/Q2 bytes in bounded slots and does not require a225GiB
FP16 expansion. Its measured1576.007692 /24.32799080 is below the resident
parent, with1.852607GiB lower known allocations after upload buffers. Prefetch
and transfer overlap are not ported. See the complete
[cache results and limits](Q2-COMPRESSED-CACHE.md).
