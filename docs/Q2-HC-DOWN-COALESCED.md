<!-- SPDX-License-Identifier: MIT -->
# HC down: coalesced stage fetches

The retained MoE/HC profile spends 130.462 ms in 96 original-F16 HC down calls
during 2K prefill. The previous [tile/scheduling probes](Q2-HC-DOWN-TILES.md)
were exact but slower. This experiment changes how threads fetch stage data,
retaining the measured 64x128 tile and both ordered FP32 accumulation chains.
It is isolated from the reactive PLE and half-wave experiments.

## Mechanism and boundary

The original staging assigns a complete 64-byte K32 block to a thread. Four
separate vector loads visit that block's 16-byte chunks; adjacent threads visit
other K blocks or rows. The candidate distributes those chunks across adjacent
threads. Each thread stages two weight chunks and four activation chunks for
the HC down tile. It writes each chunk to the same swizzled LDS cell as before.

Only the original-F16 64x128/BK2/WM2/WN4/row-group5 specialization selects this
path. Stored weight bytes, quantization, tile dispatch, shared layout, prefetch
boundary, synchronizations, WMMA order, split K16 chains and epilogue are fixed.
Other dense projections and quantized kernels keep their original source path.
No persistent weight cache, format conversion or CPU model forward is added.

## Static checks

| Resource/instruction count | Reference | Candidate |
| --- | ---: | ---: |
| VGPRs | 251 | 186 |
| SGPRs | 22 | 26 |
| LDS bytes | 24576 | 24576 |
| Private bytes | 0 | 0 |
| Static global 128-bit loads | 16 | 12 |
| Static WMMA instructions | 16 | 16 |
| Static block barriers | 2 | 2 |

These are compiler records and instruction counts, not a runtime occupancy or
throughput measurement. Both initial and loop-prefetch loads are counted; no
dynamic transaction reduction is inferred from instruction counts alone.

Device-only gfx1151 compilation succeeds. The standalone patch reconstructs all
1019 files exactly from the measured official-Gufo-derived MoE/HC checkpoint.
Changed-file formatting and Python syntax pass. Full-tree formatting preserves
the inherited exit 1 in unchanged upstream serving/generator test files, and
the compiler retains two inherited switch warnings. See the
[source receipt](../config/q2-hc-down-coalesced-source.json) and
[static/reconstruction receipt](../config/q2-hc-down-coalesced-static.json).

## Runtime qualification

The updated source-admission fixtures pass 12/12 Debug and 12/12 ASan/UBSan
checks on `.157`. Fresh reference and candidate component arms retain all 22
complete output hashes exactly. Both retain the four known unchanged-library
numerical failures at 2e-5: `320x10240-n32-p0`, `320x10240-n95-p0`,
`319x10240-n129-p0` and `320x10208-n129-p0`. Both actual operator/benchmark
command exits are **1**, with performance preserved; no tolerance is relaxed.

| Component | Reference median us | Candidate median us | Elapsed change |
| --- | ---: | ---: | ---: |
| HC down | 1177.428 | 1169.698 | -0.66% |
| Unchanged HC up control | 945.251 | 954.314 | +0.96% |

Down samples, in order, are 1135.057, 1179.911, 1166.981, 1201.042 and
1177.428 us for reference; 1169.698, 1144.424, 1220.904, 1171.043 and
1141.004 us for candidate. The distributions overlap strongly. The 0.66%
median rate increase is not a demonstrated robust gain and does not justify
a complete-model sweep. Lower static register usage alone did not establish
a useful throughput improvement. This candidate remains unpromoted.

[All checks and samples](../config/q2-hc-down-coalesced-operators.json) retain
the numerical failures and real command exits. The Q2/UD parity goal, earlier
complete-model drift and long-context qualification remain open. The enclosing
window subsequently proceeds to the separate first-access reactive PLE probe.

## Source reconstruction

Run `python3 tools/prepare-q2-hc-down-coalesced.py` with the recorded base in
`.deps/gufo-q2-bench-hc-moe-fused` and a fresh destination. The isolated output
is `.deps/gufo-q2-bench-hc-down-coalesced`; the generator refuses an existing
directory. The first-party MIT delta is
`experiments/q2-hc-down-coalesced.patch`, against official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, retaining all upstream notices.
No antirez engine, sibling project artifact or DS4 implementation is imported.
