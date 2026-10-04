<!-- SPDX-License-Identifier: MIT -->
# Skip empty IQ2 paired epilogue fragments

Inspection for the [routing diagnostic](Q2-ROUTE-PROFILE.md) finds an opportunity
smaller than a mixed-width map. The active IQ2 gate/up matrix loop already skips
16-row fragments beyond `live_tok_tiles`. Its paired epilogue still writes eight
accumulators per thread to shared memory and executes two workgroup barriers
for each such fragment, although every output-row predicate is false.

The candidate adds a workgroup-uniform guard before those stores. It is limited
to paired IQ2 specializations with more than one token fragment. Every live
fragment keeps its arithmetic, output addressing and both barriers, including
the last live fragment. The condition depends only on the tile descriptor and
expert bucket bounds, which are identical across all threads in the workgroup;
there is no barrier reached by only a subset of threads.

The source starts from measured ordered IQ2 decode, changes only
`kernels.hip.cpp`, and leaves the other 1019 files exact. It retains the original
PLE reader, routing map, tile widths, weight conversion, accumulation order,
SwiGLU expression and down projection. It includes neither the rejected WMMA
sign expansion nor PLE cache-first. The source is separate from the running
routing profile and has no instrumentation.

Both providers compile locally to gfx1151 device assembly with identical
flags; no GPU program is executed by this check. The unpacked IQ2 specializations
used by the model show:

| Token tile | Static instructions before/after | VGPR before/after | SGPR before/after | LDS bytes | Scratch bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 661 / 661 | 82 / 82 | 24 / 24 | 11392 | 0 |
| 48 | 1161 / 1190 | 94 / 94 | 30 / 30 | 15488 | 0 |
| 64 | 1391 / 1414 | 102 / 102 | 30 / 32 | 17536 | 0 |
| 128 | 2381 / 2432 | 148 / 148 | 38 / 40 | 25728 | 0 |

The static body grows because of the guards. Shared-store/barrier instructions
remain present for live fragments; their potential saving is dynamic when a
tail is empty. Unchanged VGPR/LDS and zero scratch do not prove a speedup or
identical compiled outputs. Extra branch/layout cost may outweigh tail savings.

The required next check is a matched complete GPU gate/up cycle, covering full
and partial 16-row boundaries, packed/unpacked outputs, independent FP64 checks,
full-output replay and guard regions. Existing numerical limits remain unchanged;
finite output and performance must remain available on a numerical rejection.
Use original-size rotating weights beyond the 32 MiB MALL cache. Only a qualified
component improvement may advance to an uninstrumented full canonical 0–128K
Q2/control/UD comparison. No model gain, promotion or parity is claimed.

[Source manifest](../config/q2-iq2-live-epilogue-source.json),
[static evidence](../config/q2-iq2-live-epilogue-static.json),
[minimal patch](../experiments/q2-iq2-live-epilogue.patch).
