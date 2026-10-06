<!-- SPDX-License-Identifier: MIT -->
# Exact selector key reuse across two queries

This private component follows the owner's new decode/full-prefill-through-128K
priority. Fixed-point UD parity remains paused. It does not modify a production
provider, prompt, prefill chunk, attention precision, ranking rule or context
capacity. It is distinct from upstream's rejected paired-lane score calculation:
one thread here still computes a complete original score, for two query rows.

The draft loads one F16 key and reuses it for two independent FP32 queries.
Every query retains the original four-FMA partials, descending32-partial tree,
head order, ReLU and final sum. Each row's causal bound still controls its store;
an odd last query and the budget boundary remain separate cases. The original
SelectMarkKernel consumes scores unchanged, with lower-index tie ordering.

The compiler preserves all164 original device bodies. The selected draft uses
184 descriptor VGPRs, versus115 in the control, and zero scratch/LDS bytes.
This register cost is a tradeoff to measure, not a gain. Five other compiler
probes are retained: implicit packed keys do not reduce allocation, a rolled
query loop still uses185 VGPRs, explicit bitpack/compiler barriers introduce
3604 scratch bytes, and head-interleaved versions use173 VGPRs plus32 scratch
bytes. These are static observations, not measured rejections. The GPU trial
uses only the zero-scratch original query-pair draft.
[Static audit](../config/q2-select-query-pair-static.json).

The fixture times the complete score plus mark operation, with two warmups
and five measured repetitions, alternating control/candidate order. Every timed
score and mask is checked before overwrite: full-byte comparison, finite valid
scores, unchanged inactive score sentinels, mask cardinality and causal tails,
device guards and immutable inputs. Sampled FP64 dots retain the2e-5 thresholds;
CPU rank/tie checks consume sampled complete score rows. Finite disagreements
retain timings and their actual exit. Invalid outputs or device faults stop.

| Component case | Query rows | Chunk start | First query in chunk |
|---|---:|---:|---:|
| Last complete chunk of saved32K prefix | 512 | 28672 | 1536 |
| Last complete chunk of saved128K prefix | 512 | 126976 | 1536 |
| Last selector slice of saved128K final tail | 365 | 129024 | 1536 |

These are actual selector subdivisions of the original2048-token prefill
chunks. The final128K input is still130925 tokens:63 complete chunks and1901
final tokens. The365 rows above are the final slice of those1901, not a new
model input or an intermediate shortened prefill. Capacity133760, padded score
pitch33440,1045 mask words, ratio4 and512 selected blocks match the executor.
Additional cases cover one/three query rows, small inputs and zero-score ties
across the non-sparse boundary. Synthetic query/key values check the component;
they provide no original-weight model throughput or quality result.

No saved Q2/UD control, Q4, full curve or model run is scheduled by this plan.
Collect and release the .157 window before analysis. A component win must still
survive a separate model trial on the original saved requests.
