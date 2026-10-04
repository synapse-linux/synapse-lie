<!-- SPDX-License-Identifier: MIT -->
# DS4 sampling profile qualification

This is a development protocol for the newly exposed shared-core candidate
filters. It adds no Python dependency to the server, native benchmark, graphs
or default tests. The optional Point supervisor only coordinates an admitted
`.161` run and validates its native output.

## Frozen controls

Declare all seven controls in an optional `generation` object in the Point
campaign manifest. Missing campaign settings preserve historical greedy behavior;
an explicitly supplied object must be complete and typed. The requested DS4
server profile is:

```json
{
  "generation": {
    "temperature": 1,
    "top_p": 1,
    "top_k": 0,
    "min_p": 0.05,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "seed": 123
  }
}
```

The native CLI equivalent is `--temperature 1 --top-p 1 --top-k 0 --min-p 0.05
--frequency-penalty 0 --presence-penalty 0 --seed 123`. This selects an explicit
profile; LIE's defaults remain greedy with both candidate filters disabled.
The supervisor refuses invalid profiles before model verification/load and
compares the complete reported generation identity to the declared controls.
Historical five-control result identities mean `top_k=0`, `min_p=0`.

## Required gates

| Gate | Acceptance |
| --- | --- |
| AR controls | Pinned original target weights, complete fixed output, matching seven-control identity and deterministic repeated AR runs with identical seed/input/lifecycle. |
| MTP controls | Same target profile plus explicitly admitted predictor; witnessed drafts and accepted target tokens, rejection/residual correction and complete fixed output. |
| Probability behavior | Independent filter/distribution oracles, including target mass outside the proposal support and forced rejection. Positive-temperature MTP must preserve the filtered target distribution. |
| Tool transitions | Required/allowed strict functions complete with valid arguments and correlated results. No provisional call is executable before successful completion. |
| Cost | Paired frozen LIE/Gufo configurations, physical input, PP/TG/TTFT, repetitions, allocations/resources and filter settings. Record overhead even when throughput declines. |
| Closure | Fresh coordinated lease, actual exit codes and failures, unchanged model stats, artifact verification and all owned processes retired with the named router restored. |

The fixed-output oracle remains unchanged: natural EOS before the declared TG
budget is a failed sample even if the native child exits 0. Live progress does
not replace completion. Equal seeds do not require equal AR and speculative
token streams: speculative acceptance uses additional random draws. Numerical
and quality claims require distribution evidence, not only sampler metadata.

The pinned provider's `qwen38_flash_next/mtp_sampling.hpp` uses the filtered
target mass for acceptance and the positive residual for correction; the
engine retains that correction as the next anchor. This source audit and local
header compilation do not qualify the newly exposed filters on original weights.

CPU protocol checks are recorded in the
[supervisor receipt](../validation/ds4-sampling-point-supervisor-2026-10-04.json);
the [native client receipt](../validation/ds4-sampling-controls-2026-10-04.json)
records parser, ABI, retained options and report compatibility. Actual GPU
qualification remains pending until `.161` is available and a new source/binary
identity is sealed and admitted.
