<!-- SPDX-License-Identifier: MIT -->

# Q2 model-owned multi-user benchmark, 2K–8K

The .157 GPU run completed all 20 independent original-weight arms. Each arm
submitted C1/C2/C4/C6/C8 identical requests to `synapse-lie-bench --suite core`.
The C17 model owner serialized each request’s prefill and sent ready decode
rows to the native reactive `DecodeBatch` path. This tests the inference core,
without HTTP transport. The earlier direct `--suite multi` looped over prefills
inside the benchmark and is a different contract.

The physical prompt for each frontier is an exact 2048/4096/6144/8192-token
prefix of the saved Promessi sposi DS4 walk. Every user in an arm received the
same complete prompt. Controls: Qwen3.8-Flash-Next-Q2, context capacity 133760,
chunk 2048, greedy AR, TG128 per user, cache off, no warmup, one measured
sample, IOMMU off, performance 120 W and existing fan curve. One process per
arm loaded the model before timing. No model, service, fan, dependency or boot
change was made.

`PP` divides all physically executed prompt tokens by the sum of completed
model-owner prefill-call durations. `TG` divides all confirmed output tokens
by native decode-dispatch duration charged once per batch. `Wall` divides all
output tokens by the whole cohort request interval; model load is excluded.
Every arm emitted 128 tokens per user. With C2–C8, all 128 decode dispatches
contained exactly C users; C1 had 128 single-row dispatches.

| Prompt/user | Users | PP tok/s | TG tok/s | Wall tok/s | Decode batches |
|---:|---:|---:|---:|---:|---:|
| 2,048 | 1 | 1,587.30 | 27.89 | 21.52 | 0 |
| 2,048 | 2 | 1,591.18 | 40.21 | 28.23 | 128 |
| 2,048 | 4 | 1,589.58 | 66.27 | 39.02 | 128 |
| 2,048 | 6 | 1,558.63 | 81.98 | 43.61 | 128 |
| 2,048 | 8 | 1,565.15 | 91.81 | 46.34 | 128 |
| 4,096 | 1 | 1,543.50 | 27.94 | 17.53 | 0 |
| 4,096 | 2 | 1,546.15 | 40.22 | 21.70 | 128 |
| 4,096 | 4 | 1,539.02 | 66.16 | 27.49 | 128 |
| 4,096 | 6 | 1,519.59 | 81.63 | 29.61 | 128 |
| 4,096 | 8 | 1,519.21 | 91.59 | 30.82 | 128 |
| 6,144 | 1 | 1,494.44 | 27.99 | 14.63 | 0 |
| 6,144 | 2 | 1,528.17 | 40.12 | 17.59 | 128 |
| 6,144 | 4 | 1,507.78 | 66.20 | 21.09 | 128 |
| 6,144 | 6 | 1,496.33 | 81.77 | 22.33 | 128 |
| 6,144 | 8 | 1,490.05 | 91.69 | 22.94 | 128 |
| 8,192 | 1 | 1,508.53 | 27.95 | 12.70 | 0 |
| 8,192 | 2 | 1,512.88 | 39.65 | 14.70 | 128 |
| 8,192 | 4 | 1,484.58 | 66.04 | 17.03 | 128 |
| 8,192 | 6 | 1,476.04 | 81.70 | 17.84 | 128 |
| 8,192 | 8 | 1,472.41 | 91.33 | 18.22 | 128 |

[Graph](figures/q2-core-model-flow-2k8k.png) · [Full CSV with phase seconds and dispatch counts](figures/q2-core-model-flow-2k8k.csv) · [Output-parity record](figures/q2-core-model-flow-2k8k-quality.json).

At 2K, native TG rises from 27.89 at C1 to 91.81 tok/s at C8
(3.29×). At 8K it rises from 27.95 to 91.33 (3.27×). Serial model PP
stays near 1.5K tok/s because all C prompts are executed; at 8K/C8, the
65,536 prompt tokens take 44.51 s. Whole-cohort output rate reaches only
18.22 tok/s there, versus 12.70 at C1 (1.43×), because prefill dominates
the request interval. These are executor and cohort rates, not isolated GPU
kernel throughput. One sample per point supplies no variance estimate.

## Output parity

All users within each cohort produced exactly the same 128 token IDs. C1
matches the retained DS4-walk continuation at all four frontiers. C2, C4,
C6 and C8 match one another at each frontier, but differ from C1:

| Prompt/user | First difference from C1 (1-based token) | Matching positions / 128 |
|---:|---:|---:|
| 2,048 | 14 | 16 |
| 4,096 | 7 | 8 |
| 6,144 | 10 | 12 |
| 8,192 | 15 | 17 |

The adapter dispatches C1 through upstream `Session::DecodeStep`, while C2+
uses `Session::DecodeBatch`. That path distinction coincides with the
different continuation; these records do not isolate which numerical
operation causes it or whether one text is better. Therefore the batch
throughput gain is measured, but output equivalence to the single-user
reference is **not qualified**. This is the next quality investigation before
promoting the batch path.

All 20 child processes, runner and report generation exited 0. The 205
result artifacts (1,750,372 bytes) were copied and SHA-verified on both
hosts before release. The .157 release and independent strong closure verify
32 retired process identities, 31 retired groups, empty KFD, five free
original leases, unchanged seven reference and GLM model stat tuples, and
IOMMU off. [Frozen plan](../config/q2-core-model-flow-2k8k-plan.json) ·
[compact result receipt](../config/q2-core-model-flow-2k8k-results.json) ·
[benchmark contract](CORE-MODEL-FLOW.md). Full raw JSONL, telemetry, logs
and remote receipts remain under local `evidence/q2-core-model-flow-2k8k/`.
