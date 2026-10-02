# HC down tile probe: fewer registers did not improve speed

<!-- SPDX-License-Identifier: MIT -->

The first 64x64 HC down tile is **5.93% slower** than the retained 64x128 tile
in the rotating-weight GPU component benchmark. All 22 complete output hashes
match. It is not retained for performance and no full-model arm was warranted.

| Tile | Static VGPR | LDS bytes | Private bytes | Median down microseconds |
|---|---:|---:|---:|---:|
| 64x128, two row waves | 251 | 24,576 | 0 | 1,185.290 |
| 64x64, two row waves | 184 | 18,432 | 0 | 1,255.558 |

Unchanged HC up control: 943.419 versus 954.741 microseconds. Each shape rotates
16 original F16 weight matrices (100 MiB), with a warm rotation followed by
five samples of 16 launches at 2,048 tokens. Both ordered K16 accumulation
chains remain unchanged. Static register count does not establish runtime
occupancy or memory-bandwidth benefit.

Both operator commands exit **1**, preserving the same four previously known
hipBLASLt control failures at tolerance 2e-5: n32, n95, m319 and k10208. These
cases do not dispatch the changed WMMA kernel. Every changed WMMA case passes;
all 22 output hashes, including those failing controls, match the reference.
The numerical limits are not relaxed and the nonzero exits are not relabeled
as an overall operator pass. See `config/q2-hc-down64-operators.json`.

Three follow-up scheduling sources are prepared but **not GPU tested**:

| Tile / change | VGPR | LDS bytes | Private bytes |
|---|---:|---:|---:|
| 64x64, four row waves | 183 | 18,432 | 0 |
| 64x64, four K32 blocks per stage | 256 | 32,768 | 100 |
| 64x128, four row waves | 256 | 24,576 | 16 |

Four-row-wave candidates require an independently transposed one-row epilogue.
Their first compilation failed the original paired-row static assertion; the
next generator accidentally selected an earlier W8A8 assertion. Both failed
sources/logs remain under `evidence/`. The corrected generator scopes the edit
to `DenseF16GEMMKernel`; all three final sources compile statically, reconstruct
1,019 files exactly and pass the 486-file format check. None has numerical,
GPU occupancy or model-performance qualification. User-directed PLE diagnosis
takes priority over their GPU measurements.

All variants derive from measured MoE/HC fusion, excluding the rejected norm
copy. Runtime patches and default dispatch remain unchanged. First-party MIT
generators, isolated patches and source/static receipts are named
`q2-hc-down64*` and `q2-hc-down-tiles*`. Two `.157` host capsules pass 10/10
Debug and 10/10 ASan/UBSan; each remote arm uses fresh four-lease admission.
