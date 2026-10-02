<!-- SPDX-License-Identifier: MIT -->
# Prepared IQ2 → Q2 compensated activation layout

This candidate moves an existing activation conversion to its producer. It is
prepared and statically compiled, **not GPU-tested or performance-qualified**.
The best measured checkpoint remains 1240.52 PP/23.01 TG at 2K; parity with UD
remains unmet. The candidate is isolated from that checkpoint and from the
qualified Q2 runtime patch.

## Mechanism and numerical contract

The compensated Q2 down kernel currently reads an F32 activation and produces
two F16 operands: a rounded high value and a residual scaled by 4096. Each
output-row block repeats this conversion. At 2560 output rows and 128 rows/block,
the same routed activation is processed by 20 blocks.

The experimental IQ2 SwiGLU epilogue instead writes the high/residual pair
directly into its existing four-byte slot. Bits 0–15 hold `RN_F16(value)`;
bits 16–31 hold `RN_F16((value - F32(high)) * 4096)`. Q2 down loads two contiguous
16-byte vectors for eight slots and extracts the halves into its existing LDS
planes. It keeps the original WMMA accumulations and final residual addition.
This removes repeated conversions; it does not reduce activation buffer bytes.

Only the paired IQ2/Q2 branch interprets `gate_e` as packed words. Its producer
finishes on the same stream before the consumer reads it, and the consumer
writes the existing F32 `down_e` result for the unchanged expert epilogue.
There is no extra allocation, launch, weight transformation or concurrency
policy change. Unpacked entry points remain available for direct experimental
replay. They are not a second user-selected serving mode.

Moving arithmetic under fast-math can change contraction, so equality is a
test requirement, not an assumption. Prepared checks reuse the existing 12
independent Q2 and 18 independent IQ2 cases, then compare every packed word
against independent packing of the original F32 result. Q2 outputs must match
bit for bit on all 12 direct cases and two full IQ2→Q2 chains at width 640.
Direct/chain consumers receive exact-sized input allocations. Prefix/suffix
guards, finite/written outputs and retained full buffers accompany these checks.
The original independent FP64 tests retain their existing 0.002 limits.

The full model must reproduce saved logits and tokens from the paired-IQ2
checkpoint exactly for this proposed arithmetic-preserving move. That does
not resolve the checkpoint's earlier drift from qualified Q2. Any new failure
will be retained; no tolerance or expected value is replaced.

## Static observations

The source and fixture/executor syntax checks pass. Official formatting passes
across 486 files; all 1019 files reconstruct exactly after applying
`experiments/q2-packed-activations.patch` to the paired-IQ2 source.
The [source receipt](../config/q2-packed-source.json) retains identities and
the initial device syntax/missing-include failures followed by corrected checks.

The gfx1151 assembly has no private segment for any of the 14 relevant packed
and reference templates. IQ2 VGPR/SGPR/LDS counts are unchanged. Q2 VGPR and LDS
counts are also unchanged; SGPR counts fall 26→24, 32→30 and 32→31 for tile widths
16/48/64. These are compiler metadata, not measured occupancy or throughput.
See [the static resource record](../config/q2-packed-static.json).

## Next admitted GPU window

Core retains the current SSD window. No Q2 remote job or automatic retry has
started. The [protocol](../config/q2-packed-protocol.json) requires a current
profile of the retained paired-IQ2 checkpoint before choosing this candidate
for model performance measurement. The old pre-optimization trace cannot
establish the current remaining bottleneck.

After coordinated handover, the fixed wrapper supports:

```sh
python3 tools/q2-remote.py cpu q2-packed-host-r1
python3 tools/q2-remote.py q2-profile q2-iq2-current-profile-r1 --source-variant iq2-pair
python3 tools/q2-remote.py packed-operators q2-packed-operators-r1 --source-variant packed
python3 tools/q2-remote.py q2-bench2k q2-packed-reference-r1 --source-variant iq2-pair --rebuild-mmq
python3 tools/q2-remote.py q2-bench2k q2-packed-model-r1 --source-variant packed --rebuild-mmq
```

These commands are prepared, not queued. Model comparisons use the same C1
pp2048/tg128 scope, warmup plus three requests, and 15-second idle outside timing.
Every GPU/build arm requires four fresh nonblocking leases and the owner-approved
98 C inclusive guard, retaining lower exposed hardware thresholds. A complete
model gain and numerical results determine retention; static instruction changes
alone do not qualify the candidate. Fresh UD controls and broader performance
coverage remain necessary for the full no-regression goal.
