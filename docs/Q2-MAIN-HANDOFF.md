<!-- SPDX-License-Identifier: MIT -->

# Q2 branch handoff to the main LIE integration

This branch is an isolated Q2 qualification lineage, not a replacement for the
current C17 server and model contracts. Integrate selected changes into the
current root deliberately; do not merge its historical source capsules or
overwrite current sampling, KVC, MTP, vision, steering or reactive scheduling.

## Native benchmark transfer

The DS4 advancing-walk implementation is the tracked
[`ds4-walk-bench.patch`](../experiments/ds4-walk-bench.patch), applied by
[`prepare-ds4-walk-bench.py`](../tools/prepare-ds4-walk-bench.py) to the
byte-verified counting benchmark capsule. The chain is
[`q2-exact-bench-source.json`](../config/q2-exact-bench-source.json) →
[`q2-counting-bench-source.json`](../config/q2-counting-bench-source.json) →
[`ds4-walk-bench-source.json`](../config/ds4-walk-bench-source.json).
The last manifest covers 1,290 source files. The patch targets
`tools/lie-bench.c`, the source of `synapse-lie-bench`, rather than the separate
`tools/executor-bench.c` C1 fresh-session harness. Its other hunks update
`tools/q2_exact_prompt.inc`, `tools/native/report.c`, `tools/bench-report.py`,
`tests/test_lie_bench.py`, `tests/test_native_bench.c` and focused CTest wiring.
Adapt those hunks to the current root interfaces; the old capsule is not an
integration base.

The walk tokenizes one raw-text corpus once, then advances one logical sequence
through contiguous exact frontiers. Each monotonic prefill interval encloses
only the newly appended tokens, with `frontier - previous` as numerator.
Each frontier runs greedy decode up to 128 emitted tokens. Before decode, it
captures bounded prefix state (at most 1 GiB) or chooses replay; restoring or
replaying happens outside prefill/decode intervals. LIE's state API restores
only into a pristine physical sequence, so the benchmark replaces that handle
between frontiers. DS4 restores in place. LIE may stop at EOS; DS4 excludes EOS.
These differences and incomplete output budgets remain visible in results.
Legacy direct suites are explicitly selected and marked deprecated pending
review. The report must keep the walk and full-prefill contracts distinct.

## Numerical executor actually measured

The Q2 DS4-walk GPU executable uses official Gufo pin
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`, linked locally against
four retained archives. Their complete SHA-256 values are fixed in
[`q2-counting-bench-build.json`](../config/q2-counting-bench-build.json), and
[`cmake/ds4-walk-bench/CMakeLists.txt`](../cmake/ds4-walk-bench/CMakeLists.txt)
verifies them before linking:

| Archive under `.deps/` | SHA-256 prefix | Role |
| --- | --- | --- |
| `build-prefill-chunks/cmake/curve/libq2_curve_adapter.a` | `b33c2608` | LIE/Gufo curve adapter |
| `build-prefill-chunks/cmake/hip/qwen/libgufo_qwen38_flash_next.a` | `7064043d` | Q2 host and HIP provider |
| `build-prefill-chunks/libq2_host.a` | `dfc418a7` | Host Q2 support |
| `build-hc-scalar-matched/cmake/hip/qwen/libgufo_qwen38_flash_next_mmq.a` | `5daa0088` | Matched-build numerical MMQ |

The provider source lineage is
[`q2-iq2-fixed-bounds-source.json`](../config/q2-iq2-fixed-bounds-source.json)
(parent `q2-ssm-fixed-bounds-source.json`) →
[`q2-hc-scalar-model-source.json`](../config/q2-hc-scalar-model-source.json) →
[`q2-hc-scalar-isolated-source.json`](../config/q2-hc-scalar-isolated-source.json) →
[`q2-decode-down-rows-model-source.json`](../config/q2-decode-down-rows-model-source.json) →
[`q2-prefill-chunks-source.json`](../config/q2-prefill-chunks-source.json).
Each manifest names its parent and tracked patch. The last manifest separates
seven provider files from three historical core files. Transfer the selected
provider implementation through the current provider build and ABI, while
retaining the current C17 core. The historical core patch is not a replacement
for the current server. The locally linked executable has SHA-256
`24b19cb7baa9b2a81af461e4dc69f16f6f66a010b9ef463452668d0c19e05a3b`
in [`ds4-walk-bench-build.json`](../config/ds4-walk-bench-build.json). Its
archives are ignored local artifacts, not portable merge inputs. A new root
build needs its own numerical, feature and performance qualification.

## Closed gates and limits

Focused synthetic DS4 accounting passes Debug and ASan/UBSan CTest, including
snapshot and replay. On `.157`, one real Q2 Promessi walk completed 2K/4K/6K/8K,
chunk 2K, C1 greedy, TG128, zero warmup. The child and runner exited 0; all 15
collected result files hash-verify; release and independent strong closure
completed. Prefill rates are 1598.535459, 1515.414412, 1502.308859 and
1485.978589 token/s; decode rates are 27.877890, 27.878246, 27.903018 and
27.964465 token/s. All four prefill/decode logits hashes and 128 output IDs
match the earlier full-prefill samples. See the [table and measurement
contract](DS4-WALK-BENCH.md), [validated result](../config/q2-ds4-walk-promessi-results.json)
and [raw evidence](../evidence/q2-ds4-walk-promessi-r1/results/00-q2-c2048.jsonl).

This does not qualify a DS4 walk beyond 8K, sustained 30-token/s C1 decode,
1500-token/s prefill through 128K, inherited task-quality neutrality, or the
current root's C17 feature composition. Earlier full-prefill curves have
different numerators and warmup policy, so their rates cannot be ranked
directly against the incremental walk. The inherited F16 intermediate change
still has an open quality gate. Preserve rejected or unpromoted experiments,
including lossy Q5 overlay, the negative V-block model trial, marginal IQ2
LDS/selector trials and generally slower 4K/8K prefill chunks. See
[quality status](Q2-QUALITY-PRESERVING-STATUS.md) and
[remaining work](Q2-REMAINING-WORK.md).
