<!-- SPDX-License-Identifier: MIT -->
# Compact shared memory for the fused SSM projection

This candidate changes only the fused SSM projection in the retained
1580.226725 PP /25.10411864 TG provider. It has local source, integer-layout
and compilation evidence, with no GPU numerical or timing result. The saved
1571 [profile](Q2-CURRENT-BEST-PROFILE.md) attributes160.217893ms over36 calls
to this projection. That profile identifies a useful target; it is not a fresh
1580 trace or a predicted saving.

The original BK2 stage holds two K32 blocks for256 output rows and128 tokens,
requiring49152 LDS bytes. Switching to BK1 halves staging to24576 bytes, but
the fused convolution still needs a32-token transpose for each of eight waves.
Its original36-float stride requires36864 bytes. The candidate replaces the
four-float padding with an XOR row permutation:

```
index(token, row) = token * 32 + (row ^ ((token & 7) << 2))
```

Each wave now uses1024 floats, so the complete transpose fits32768 bytes.
The low two row bits stay unchanged, preserving aligned contiguous float4
loads. Projection stores and all three earlier convolution reads use the
same mapping. The existing block grid,32-token convolution windows, history
boundary kernel, output masks and convolution arithmetic remain unchanged.
No allocation, stream or launch is added, and scalar decode is unaffected.

Integer enumeration checks1024 unique producer stores and3808 scalar read
coordinates per wave, including every current/history float4 component.
A model with32 banks of four bytes gives the same store-bank multiplicity as
the padded layout over32 store cases. This models store addresses only; it
does not measure hardware bank conflicts or establish vector-read behavior.
Both BK schedules visit the same160 K16 fragments in the same order.

## Compilation and tradeoffs

| Property | Saved parent | Compact LDS |
| --- | ---: | ---: |
| Static instructions | 4027 | 4120 |
| Shared bytes/block | 49152 | 32768 |
| Compiler-reported VGPRs | 222 | 207 |
| Descriptor VGPR reservation | 241 | 207 |
| Scratch bytes/thread | 0 | 0 |
| Compiler occupancy field | 4 | 7 |
| Static WMMA opcodes | 64 | 32 |
| Source K stages | 40 | 80 |
| Source block barriers in K loop | 80 | 160 |

Lower LDS/register use could permit more concurrent work, but the shorter K
stage doubles synchronization and changes load scheduling. Static WMMA totals
reflect a different loop body, not fewer matrix products. No throughput gain
or measured residency follows from these compilation numbers.

The complete1027-file inventory and patch are retained. Only `kernels.hip.cpp`
changes, and161 other kernels retain exact instructions, operands and resource
metadata. The unchanged saved parent assembly is reused. The literal SSM
control still matches the current parent, and the independent FP64 formula
changes only its event name.

## Prepared qualification

The separate fixture retains1024/1025/1057/2048/2049 tokens,30 complete
projection/convolution pairs and60 sampled FP64 checks of24 outputs each.
Original RMS/scaled-maximum limits remain0.002. Fourteen timing records cover
only2048, with two warmups/five measured repetitions per arm and three distinct
weight sets totaling133,693,440 bytes. Timings include projection and unchanged
boundary convolution; allocation, preparation and readback remain outside.
Safe numerical rejection retains timings; guard/write/runtime failures stop.

Two new metadata records will read HIP function attributes and its computed
maximum active blocks for each arm on .157. These API limits are theoretical,
not measured active blocks. Host and gfx1151 device syntax pass locally,
including those calls. Zero GPU checks or resource queries have executed.
Launcher wiring and original-model qualification remain pending after actual
Core-19 CPU closure and fresh coordinated ownership.

The frozen row-group campaign stays first and unchanged:88 fixtures, five
manifests and its original window helper. This candidate starts from saved1580
with row-group1 and does not silently compose the unmeasured fixed-M/K variants.
The fixed Q2/UD comparison, full-curve gate and deferred Q4 scope remain intact.

[Source and integer proof](../config/q2-ssm-compact-lds-source.json),
[assembly and fixture contract](../config/q2-ssm-compact-lds-static.json),
[fixture](../tests/q2_ssm_compact_lds.hip).
Actual local command exits are retained under
`evidence/q2-ssm-compact-lds-preparation/`.
