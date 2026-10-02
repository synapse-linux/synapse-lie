# Q2 weight staging: prepared, not GPU qualified

<!-- SPDX-License-Identifier: MIT -->

The retained MoE/HC profile spends 288.934 ms in 48 routed Q2 down calls,
17.94% of prefill kernel time. The packed-Q2 path decodes each K32 weight row
in both half-waves before WMMA. This candidate moves that decode into the
cooperative LDS producer so consumers load the same decoded F16 values.
Original Q2_K storage, both activation planes, WMMA order and final residual
correction remain unchanged. It adds no persistent dequantized weight cache.

Only `kQ2 && kPacked` selects the change. The ordinary F32-input Q2 entry and
other quantizations keep the previous source branches. Affine coefficients
remain F32, with register barriers preserving the former LDS rounding boundary.
The compiler still emits mixed FMA-to-half operations. Numerical equivalence
must be verified on the GPU; source expressions alone are not sufficient.

Static gfx1151 compilation succeeds:

| Token tile | Reference / candidate VGPRs | Reference / candidate LDS bytes | Private bytes | Reference / candidate static mixed-half FMA instructions |
|---|---:|---:|---:|---:|
| 16 | 112 / 158 | 16,640 / 20,736 | 0 / 0 | 64 / 32 |
| 48 | 144 / 169 | 24,832 / 28,928 | 0 / 0 | 64 / 32 |
| 64 | 169 / 217 | 28,928 / 33,024 | 0 / 0 | 64 / 32 |

WMMA instruction counts are unchanged (8/24/32). The increased register and
LDS requirements may offset the reduction in decoding. These are static
instruction/resource counts, not measured occupancy, speed or numerical results.

The new `q2_packed_bench` uses synthetic original-shape matrices: 512 experts,
10 selected experts per token, 2,048 tokens, M=2,560, logical K=640 and stored
K=768. Encoded weights occupy 315 MiB. Both input paths run in alternating
order for five samples of eight launches, after warmup. Transfers, compact
routing, hashing and output checks are outside HIP-event timings. Complete
outputs and guards are compared; 1,024 independent sampled FP64 dot products
retain the existing 0.002 relative/peak tolerance. Timing is preserved before
any numerical verdict; a numerical failure still returns exit 1.

Source reconstruction matches all 1,019 files. Changed-source formatting,
device compilation and benchmark host syntax pass on the editing host.
`config/q2-staged-weights-{source,static}.json` records the source, commands,
actual exits, assembly hash and resources. No runtime test or model measurement
has run for this candidate. The qualified runtime and retained measured
checkpoint are unchanged.

Once core returns the `.157` window, independent fresh lease admission is
required for host guards, the existing 30 packed operator cases, the matched
synthetic benchmark and any justified full-model pp2048/tg128 comparison.
Fixed remote modes accept:

```sh
python3 tools/q2-remote.py packed-operators q2-stage-operators-NEW --source-variant staged-weights
python3 tools/q2-remote.py packed-bench q2-stage-micro-ref-NEW --source-variant hc-moe-fused
python3 tools/q2-remote.py packed-bench q2-stage-micro-NEW --source-variant staged-weights
```

No remote job, reservation or automatic retry is started by this preparation.
Reactive PLE prompt lookahead is a separate I/O-overlap experiment and must
not be combined with this numerical-kernel change in a causal A/B.
