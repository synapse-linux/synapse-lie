<!-- SPDX-License-Identifier: MIT -->
# DeepSeek follow-up: IQ2 prefill data reuse

This follow-up inspects the independently fetched official Gufo DeepSeek port
at `f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. No sibling DS4 workspace source,
build, model or evidence is imported or modified. The target remains the full
canonical Q2/UD curve; the counting replay is a separate regression control.
[Inspected source identities and dispositions](../config/q2-deepseek-prefill-followup.json).

## Two isolated candidates

DeepSeek's IQ2 loaders place the 256-entry magnitude codebook in shared memory
once per workgroup and reuse it across rows. The new **grid-lds** probe adapts
that storage mechanism to Qwen's paired IQ2 prefill kernel. It stages the same
2 KiB table before the K loop; sign decoding, scale rounding, WMMA order and
SwiGLU remain unchanged. It adds one setup barrier and no barrier inside the
K loop. Every production launch has 256 threads, so each entry is initialized
before any thread consumes the table. Random LDS accesses and additional LDS
occupancy can still be worse than the existing cached global lookups.

DeepSeek's Q2 down loader also demonstrates reusing a quantized superblock
over successive K steps. The **scale-reuse** probe applies the narrower idea
to IQ2: its F16 block scale currently reloads and widens on each two-block
stage. Cache the exact widened scale for the four stages of that superblock.
The original multiplication order and F16 rounding remain in place. This
removes three of four dynamic header loads/conversions, while adding a uniform
refresh branch and a longer-lived register. It does not eliminate three
quarters of total weight reads or kernel instructions.

Both candidates start independently from the measured ordered-IQ2 provider.
Each changes only `kernels.hip.cpp`; the other 1019 files remain exact.
They contain neither the mixed map nor the earlier live-stage experiment.
The [generator](../tools/prepare-q2-iq2-prefill-reuse.py),
[grid patch](../experiments/q2-iq2-prefill-grid-lds.patch),
[scale patch](../experiments/q2-iq2-prefill-scale-reuse.patch), and full
[grid](../config/q2-iq2-prefill-grid-lds-source.json)/
[scale](../config/q2-iq2-prefill-scale-reuse-source.json) inventories are retained.

## Matched static device compilation

Reference and both candidates compile with identical gfx1151 production flags.
This is local device assembly only, with no GPU or runtime fixture execution.
Every non-IQ2 kernel body remains identical. All eight IQ2 specializations are
recorded in the [complete static report](../config/q2-iq2-prefill-reuse-static.json).
The ordinary-output specializations used by the active prefill show:

| Token tile | Instructions: original / grid / scale | Global-load instructions: original / grid / scale | VGPR: original / grid / scale |
| ---: | ---: | ---: | ---: |
| 16 | 661 / 679 / 663 | 25 / 18 / 25 | 82 / 82 / 83 |
| 48 | 1161 / 1170 / 1161 | 32 / 25 / 32 | 94 / 94 / 95 |
| 64 | 1391 / 1379 / 1382 | 34 / 27 / 34 | 102 / 102 / 103 |
| 128 | 2381 / 2357 / 2375 | 48 / 41 / 48 | 148 / 169 / 149 |

All variants have zero scratch. Grid staging adds 2048 LDS bytes per workgroup:
11392→13440, 15488→17536, 17536→19584 and 25728→27776 bytes respectively.
Scale reuse leaves LDS unchanged. Its static header-load instruction still
exists inside the refresh branch, so unchanged static load counts do not
contradict less frequent execution. These are static bodies, not throughput
measurements. The grid variant's BN128 register increase is a material risk.

## Ideas that should not be copied again

- Qwen already narrows the input once per token matrix and reuses it through
  `rows_token`; the DeepSeek token-compact idea is not a new top-k-fold saving
  in this active path.
- The Q2 scaled kernel already emits a 64-bit LDS store for each affine pair.
  The compiler combines both pairs as `ds_store_2addr_stride64_b64`. DeepSeek's
  scalar-to-wide store patch therefore does not establish a missing Qwen fix.
- Q2 weight staging, wider output fragments and epilogue scatter have previous
  negative measurements. Reuse them only with a distinct measured bottleneck.
- DeepSeek's active large-prompt IQ2 dispatch uses Q8 MMQ; replacing the Qwen
  F16 path would change activation rounding and accumulation. HIP D2R stubs
  cannot supply the CUDA direct-fused path on this GPU.

The earlier live-stage candidate is still a third separate prefill hypothesis:
it avoids repeated stores for empty fragments that WMMA never reads. It has
static evidence but no GPU qualification and is not included in these patches.

## Next measurement

First compare scale reuse and grid staging separately against the same ordered
reference using the existing complete gate/up fixture, recorded short/128K
routing histograms, full-tile control, original-size weights beyond 32 MiB,
independent FP64 checks and complete output replay. Include setup, compaction,
narrowing and all GPU launches in each cycle; keep all warmups and samples.
Numerical failures must retain timing evidence with a failing exit code.
Only an attributable complete-cycle gain can advance to the unchanged
canonical 0–128K Q2/control/UD workload. No new runtime or performance gain is
claimed here, and neither candidate is promoted.
