<!-- SPDX-License-Identifier: MIT -->
# Q2 bitfields and direct floating-point construction

Direct mantissa construction can remove conversions for bounded integer codes.
Changing the spelling from shifts to a bitfield does not by itself establish a
speed improvement. A static gfx1151 probe at the current compiler settings
distinguishes these two mechanisms. No device execution or runtime speed was
measured for this probe; it does not change the retained model executor.

| Operation | Ordinary expression | Bit representation expression | Static finding |
| --- | --- | --- | --- |
| Extract bits 6..7 | `(word >> 6) & 3` | A two-bit field after six discarded bits | Identical complete instruction bodies; one `v_bfe_u32`; 4 VGPRs each |
| Unsigned byte fixed point, four fractional bits | `float(q) * 0.0625` | Place `q` in binary32 mantissa at exponent 146, then subtract 524288 | Two principal data instructions each; bit construction additionally materializes a scalar mask; 4 VGPRs each |
| Same fixed-point construction | Explicit integer mask/OR | Sign/exponent/mantissa bitfields in a union | Identical complete instruction bodies |
| Two Q2 codes to packed FP16 | Two integer-to-FP32 conversions, then FP16 and packing | Insert codes into two FP16 mantissas and use packed subtraction | 7 versus 5 extraction/conversion/packing instructions; 5 versus 4 VGPRs |

The counts omit address calculation, memory operations and scheduling waits.
They are static instruction counts, not latency or throughput measurements.
The comparison of identical bodies includes memory instructions and waits.
The [source](../experiments/q2-bitfield-isa.hip.cpp) and
[compiler command, hashes, assembly and resource record](../config/q2-bitfield-isa.json)
make the bounded probe reviewable. Raw compiler output remains in
`evidence/q2-bitfield-isa-r1/`.

For the fixed-point example, binary32 spacing at `2^19` is `1/16`. Therefore
`bit_cast<float>(0x49000000 | q) - 524288` yields `q/16` exactly for every
unsigned byte `q`. This construction is not a generic reinterpretation of an
integer as a float. Arbitrary inputs require the correct normalization,
rounding and treatment of exceptional ranges. Bits discarded during rounding
can affect the result, whereas bits excluded from unsigned field extraction
need not survive. The ordinary shift expression already communicates that
fact to this compiler.

The union in the HIP/C++ probe gives a representation vocabulary. It does not
read an inactive union member: `__builtin_bit_cast` transfers the representation
and the active member is explicit. The observed bitfield layout is specific to
this target/compiler, with four-byte size assertions. No universal C/C++ layout
or language-level union speedup is claimed.

## What the retained executor already does

The independently fetched Gufo-derived source already contains `CodesToHalves`:
for a bounded code, FP16 bits `0x6400 | q` represent `1024 + q`, which a packed
half addition converts to `q`. Multiple codes travel in integer registers and
become half pairs without a scalar conversion per code. This is the same
mantissa-construction principle proposed by the owner.

The current packed-Q2 route instead uses the retained
[affine palette](Q2-AFFINE-PALETTE.md). Each sixteen-weight group has four possible
weights, `round_half(fma(q, d, bias))`, with floating scale and bias. It computes
those four values once and selects their existing half bits using register
byte permutes. It has already removed the per-weight integer-to-float/affine
conversion from that route. Its matched complete-model prefill gain was 1.35%,
with exact saved frontiers; shaped component time decreased 7.10%, alongside a
1.84% improvement in the unchanged control. Those measured gains must not be
attributed to this new static probe.

Further opportunities are redundant extraction, conversion and packing that
remain in a measured hot path. A simple syntax replacement is unsupported by
the identical extraction result. Discarding the compensated activation residual
would change the arithmetic contract and cannot inherit this exact conversion
argument. Matrix multiplication remains a separate operation: AMD describes
[WMMA](https://gpuopen.com/learn/wmma_on_rdna3/) as cooperative hardware matrix
multiply-accumulate. Replacing it with scalar bit operations would need its own
numerical and complete-model performance evidence.
