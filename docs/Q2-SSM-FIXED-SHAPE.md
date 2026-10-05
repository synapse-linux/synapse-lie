<!-- SPDX-License-Identifier: MIT -->
# Fixed-shape SSM compilation experiments

Both candidates derive from retained original exact2048/tg128 Q2
1580.226725 PP /25.10411864 TG. They have only local compilation evidence;
neither has GPU numerical or throughput results. The fixed UD comparator
remains1685.777092 PP, with another6.679444% required from the retained Q2.

The existing SSM launch already requires M16384/K2560, channels10240 and
four convolution taps. `ssm-fixed-shape` exposes M/K as constants inside only
that template specialization. Batch remains dynamic and all other dense
specializations retain their runtime dimensions. The launcher is unchanged.
The candidate keeps row-group1; it does not compose the separate group4 trial.

`ssm-fixed-bounds` additionally removes row/K predicates that are universally
true for this unchanged geometry. Integer enumeration checks32768 weight-fetch
owners,10240 K-fetch owners and65536 float4-store owners. All token-tail checks
remain. These proofs establish the index assumptions, not GPU execution safety
or numerical equivalence after compiler optimization.

| Static property | Saved1580 | Fixed M/K | Fixed M/K and bounds |
| --- | ---: | ---: | ---: |
| SSM instructions | 4027 | 3882 | 3864 |
| Change | — | -3.600695% | -4.047678% |
| Compiler-reported VGPRs | 222 | 220 | 220 |
| Descriptor VGPR reservation | 241 | 241 | 241 |
| Descriptor SGPR reservation | 23 | 19 | 17 |
| LDS bytes | 49152 | 49152 | 49152 |
| Scratch bytes | 0 | 0 | 0 |
| Static occupancy field | 4 | 4 | 4 |
| WMMA instructions | 64 | 64 | 64 |
| Block barriers | 2 | 2 | 2 |
| Global128-bit loads | 144 | 144 | 144 |
| Global128-bit stores | 64 | 64 | 64 |
| LDS128-bit loads | 208 | 208 | 232 |

The bounds variant has fewer total instructions but24 additional static LDS
loads. Two of its four global16-bit loads use `global_load_d16_b16` instead of
`global_load_u16`. Neither smaller instruction count nor unchanged static
occupancy establishes speed. Floating scheduling/packing also changes, so
source formulas and equal WMMA counts do not establish numerical equivalence.

Both durable providers contain1027 files, with only `kernels.hip.cpp` changed.
Saved-parent assembly is reused;161 other kernels match instructions, operands
and resources. The existing guarded SSM fixture and literal parent control
compile for host and gfx1151 device against both candidates. No saved comparator
is recompiled or rerun. The row-group campaign's88 fixtures, five manifests and
window helper remain byte-identical; these additional variants have no remote
launcher admission yet.

The initial bounds analyzer exited1 because it wrongly required identical
load mnemonics. Its code and actual command/logs are preserved. The corrected
analyzer records the extra LDS work and opcode substitution, and fixes a loop
variable that shadowed the variant name. The candidate source and assembly
were unchanged. This was an analysis-tool failure, not a numerical result.

Next: finish the already frozen row-group GPU campaign after actual Core-19
CPU closure and fresh .157 handover. Qualify these variants separately with
the existing complete-output, sampled FP64, guard and full-cycle timing scope;
then run only the new candidate on the original model point. Safe numerical
rejection retains timing; memory/write failures stop dependent device work.
No Q4 or context-curve expansion is included.

[Fixed-shape source](../config/q2-ssm-fixed-shape-source.json),
[assembly comparison](../config/q2-ssm-fixed-shape-static.json),
[bounds source](../config/q2-ssm-fixed-bounds-source.json),
[bounds assembly comparison](../config/q2-ssm-fixed-bounds-static.json).
Actual commands are retained in local
`evidence/q2-ssm-fixed-{shape,bounds}-preparation/`.

## Producer/consumer fusion boundary

A separate [source audit](../config/q2-producer-fusion-boundary.json) finds ten
independent64-column gate/up producer blocks per complete640-value activation
row. The current half packing needs the maximum across that whole row.
Down has20 output tiles, each consuming the640-value input. Simply moving
F32-to-half conversion into every down tile therefore changes unpadded logical
payload from625 to1050MiB per layer at2048/top10, before routing padding and
cache effects. These are source-derived demand counts, not measured DRAM bytes.

True producer fusion could remove the50MiB F32 write and50MiB pack read per
layer, but needs whole-row ownership or another qualified representation.
A last-producer counter removes a launch while retaining those two passes.
Per64-column scales change the rounding contract and require qualification.
The full-row staging sketches remain unimplemented; the audit preserves fusion
as an open optimization and does not claim any measured gain or rejection.
