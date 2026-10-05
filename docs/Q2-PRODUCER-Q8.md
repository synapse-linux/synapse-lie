<!-- SPDX-License-Identifier: MIT -->
# Routed IQ2 producer-Q8 and bounded integer Q2 down

This candidate is prepared from retained scaled-wave-pack1574.505432 PP /
25.17589001 TG. It has no GPU component or model result yet. Fixed original
Q2 remains1443.672867 PP, UD1685.777092 PP; closing the point requires7.067086%
more PP before expanding the context curve. Q4 and qualified control reruns
remain excluded.

The paired IQ2 WMMA gate/up retains its weight decoding, K accumulation and
rounded F32 SwiGLU operations. Its epilogue emits64-value Q8 groups directly
in the existing expert routing layout. A new bounded consumer uses original
Q2_K weights, integer MMQ arithmetic and a single F16 output rounding. It
masks all nonlive rows before loading and initializes the full640..767 stored
activation tail. At2048/top10/512,24,330,240 packed bytes fit in the existing
52,428,800-byte gate allocation. No allocation or stream is added; the F32
gate materialization and separate scaled-half packing dispatch disappear.

This explicitly changes activation arithmetic from row-scaled F16 to Q8.
It is not an exact numerical replacement claim. Existing fallback and scalar
paths remain in the source. Safe numerical differences retain exit1 and do
not suppress performance measurement; memory faults/nonfinite outputs stop
further device work. Independent model task quality remains unqualified.

## Static evidence and retained initial revision

The original prototype preserves all162 parent kernel instruction bodies,
operands and resource metadata, but its new integer consumer spills. The
bounded revision adds the original MMQ128-thread launch contract and keeps
ordered K loops rolled. The copied dot helper has exactly the upstream
arithmetic tokens after removing its name and the new loop directive.
All initial source, assembly and actual command exits remain available.

| Consumer token width | Initial private bytes, full/ragged M | Bounded private bytes | Bounded VGPR |
| --- | ---: | ---: | ---: |
| 16 | 612 /620 | 0 | 241 |
| 48 | 1672 /1712 | 0 | 241 |
| 64 | 2512 /2540 | 0 | 241 |

The producer specializations also have zero private scratch. These are static
compiler resources, not occupancy measurements or throughput evidence.
[Initial source](../config/q2-producer-q8-source.json),
[bounded source](../config/q2-producer-q8-source-v2.json),
[bounded static audit](../config/q2-producer-q8-bounded-static.json).

## Prepared qualification

The new fixture compares the retained F16 and candidate Q8 full chains in
one binary.60 small cases cover1/9/17/33/97 tokens, four gate widths, three down
widths, ragged M129 and allocation-end inputs. Four production checks surround
timing on balanced/skew2048/top10/512 routing, with762,839,040 active weight
bytes beyond MALL capacity. Zero inputs, poisoned inactive rows,640/768 tails,
immutable inputs/weights/maps and leading/trailing output guards are checked.

Every case saves17 complete arrays. Actual GPU slot maps canonicalize the
D2S6 bytes against the unchanged original GPU quantizer, and the down outputs
against the existing raw MMQ reference narrowed by an independent IEEE half
conversion. These are implementation comparisons. A separate96-sample FP64
affine Q2 operator decodes original weights and actual Q8 data, including the
six original sums and two reconstructed sums per128 values. Its unchanged
0.002 RMS/scaled limits are not waived if either implementation disagrees.
Parent F16 output changes are recorded separately and expected.

Gate/up and routing+gate/up+packing+down timings each retain two warmups and
five alternating measured pairs, three iterations each:56 samples total.
Allocation, uploads and checking stay outside timers. Only the new candidate
then uses the original exact2048/tg128 direct-executor model recipe, including
one warmup, three measurements, capacity9216/chunk2048, C1 greedy/MTP off.
The saved parent and original Q2/UD cohorts are reused without rebuild/rerun.

Local host/device syntax checks for both fixture translation units pass, as
do138 launcher guards. Staging verifies1029 provider files and82 frozen
fixtures in both capsules without executing SSH. The shared provider format
check retains exit1 with the same88 historical findings across the same seven
files as the preceding experiment; every changed numerical file passes the
focused check preserving include order. No GPU/device execution or .157 host
qualification is implied by those editing-host checks.

[Plan](../config/q2-producer-q8-plan.json),
[staging audit](../config/q2-producer-q8-staging.json).
Fresh coordinated host qualification and GPU admission are still required;
release88dcb8d8 transfers no new ownership. No remote cleanup is permitted.

## Provenance and boundaries

The independently fetched official Gufo pin remains
f783fedb9bea2ec7de941f6da4e02f4a4596b29e. The new numerical consumer adapts that
Qwen MMQ port's Q2 load/dot helpers; their original llama.cpp/Gufo attribution
and mmq/VENDOR.md remain. The official DeepSeek source is a design reference,
not an import from another agent's DS4 or the sibling CachyOS workspace.
The manifests bind inspected files, full inventories and patches. No core C17
ABI, persistent state, scheduler or public metrics contract changes.
