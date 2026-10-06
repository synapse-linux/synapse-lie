<!-- SPDX-License-Identifier: MIT -->

# Whole-row IQ2 producer and packing

The fixed comparison remains Q2 **1587.893545 PP / 25.12414406 TG** against
UD **1685.777092 PP / 24.34174251 TG**. The new whole640 experiment has
compiler evidence only so far. It is not selected by the model executor.

The retained expert path writes 640 F32 gate/up values per routed row, then
reads that row to choose a dyadic scale and convert it to F16 for Q2 down.
Both drafts keep all 640 values within the producing block and emit the
scaled F16 values plus the original inverse scale directly. Each block handles
one existing expert tail with at most 16 padded rows. This is a routing shape
inside the original 2048-token prefill, not a different prompt length.

The full-row maximum, rounded weight scale, WMMA accumulation order,
`up * gate * sigmoid(gate)` order, F16 rounding and destination slot are
preserved in source. Numerical equality still requires the device test.
This differs from the already tested compact-layout experiment, which retained
the global F32 intermediate.

| Draft | Accumulator storage | LDS bytes | Private bytes/thread | Static instructions |
|---|---|---:|---:|---:|
| Register | Ten groups kept live | 11,392 | 1,380 | 3,913 |
| LDS | One group at a time; full row in shared memory | 52,352 | 0 | 931 |

These are compiler resource counts, not speedups. The register draft reuses
one staged activation across ten output groups but spills. The LDS draft
rereads activation stages for each group and uses more shared memory, which
can reduce block residency. It removes the F32 global write/read without a
new device allocation; its net effect must be timed.

The [static record](../config/q2-iq2-whole640-static.json) binds both formatted
drafts to the independently fetched MIT Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`
and the retained fixed-bounds provider. All 1028 provider files and 164 parent
instruction/operand/resource bodies remain exact. The first-party numerical
drafts derive from that provider's IQ2 kernel and LIE's whole-row scaled pack;
their SPDX license is MIT. No sibling project code or artifacts are imported.

The new [.157 fixture](../tests/q2_iq2_whole640.hip) compares the parent
gate/up plus packing with both drafts:

- 32 edge cases cover 1/2/7/8/9/15/16 live rows, ineligible 17-row tails,
  descriptors beginning at 0 or 128, and aligned or two-byte-offset outputs.
- Complete outputs and inverse scales are saved, with a scalar `frexp`/`ldexp`
  check of the parent packing, guards, unwritten/nonfinite detection and
  immutable inputs. Zero, tiny and signed inputs/scales are included.
- Three 64-expert timing cases use 4/8/16 live rows, three rotated gate/up
  weight banks (about 54 MiB per pair), two warmups and five alternating
  repeats. Synchronized monotonic wall time includes gate/up and packing.
- Each timed arm's actual final buffers are checked before another device
  arm; all 21 sample buffer sets are preserved and compared without rerunning
  the producer. Those checks and transfers are outside timing.

Finite differences are retained and do not suppress timing. Guard, unwritten,
nonfinite or device failures stop further device work. The fixture covers
selected tails, not the complete mixed routing map, Q2 down consumer, model
quality or model throughput. Original model controls are not rebuilt or rerun.

Local device assembly and host/device object compilation pass. The initial
missing generated-codebook include failure is preserved and corrected in
the CMake target. New files pass formatting; the shared provider format check
still exits 1 on inherited diagnostics, without rewriting retained source.
All preparation commands and earlier drafts remain under local
`evidence/q2-iq2-whole640-*`. The .157 host gate passes 38 Debug and 38
ASan/UBSan checks, with six zero exits and all seven artifacts collected.
The [frozen component plan](../config/q2-iq2-whole640-plan.json) binds 246
fixture files and four manifests. GPU results are pending fresh admission.
