<!-- SPDX-License-Identifier: MIT -->
# Halogen performance clues for the Q2 long-context goal

This is an independent, read-only comparison of [Halogen's published
measurements](https://github.com/peonist-ai/halogen-flash-server#measured) and
[release notes](https://github.com/peonist-ai/halogen-flash-server/blob/main/CHANGELOG.md)
as viewed on 2026-10-07. The public repository publishes documentation,
deployment and API tooling, but not the numerical engine source. No Halogen
binary, kernel or model artifact is imported into LIE. Its model weights,
compression, arena and measurement conditions differ from the retained Q2
benchmark, so its rates are not LIE controls.

## What matters for the present goal

| Published clue | LIE evidence | Decision |
| --- | --- | --- |
| Halogen 0.14.1 changes its routed-expert prefill kernel. Its own 131,072-token prefill moves from 1,390 to 1,517 token/s, with rounding-level numerical differences. | The saved LIE 2,048-token profile attributes 401.058 ms of 1,321.833 ms kernel time to routed IQ2 gate/up and Q2 down. This older profile is a ranking aid, not a 128K attribution. | Highest-priority algorithm family. Qualify a complete expert-chain change on original routing and arithmetic; do not infer its speed from Halogen's result. |
| Halogen 0.12.0 parallelizes sparse-index selection for one-row decode and reuses block keys in prefill scoring. Its published improvement is largest at 262K–1M. | LIE has a partition-selector component with exact output and 22.429% lower 128K selector latency, but its generous full-prefill extrapolation is only about 8.36 ms against 12.593 seconds needed. Four-query key reuse was exact but 2.15–4.09 times slower. | Index selection can be tested separately for long-context decode. Neither result closes the prefill goal; keep the current scorer. |
| Halogen ships a shape-tuned matrix plan. | LIE already has shape-specific native kernels and a hipBLASLt HC-down comparison. All seven tested library alternatives changed numerical outputs; the selected native route remains the qualified one. Dense Q8/F16 is 293.227 ms in the older 2K profile. | Tune an active Q8 shape only with a matched operator and original-model numerical gate. Do not substitute the Halogen plan or claim its result. |
| Halogen's prompt cache avoids repeated prefill on follow-up turns; the 0.12.1 release removed a redundant DeltaNet replay during cold capture. | The LIE target is one complete cold request with zero cached tokens and its original capture policy. LIE's saved long diagnostic has no attributed second recurrence pass. | Audit capture cost only if an actual duplicate pass is found. Cache-hit TTFT cannot count toward cold prefill throughput. |
| Halogen's reported serial greedy decode is 37.6 token/s at 1.5K and 34.1 at 32K; larger served rates use MTP and sometimes prompt lookup. | LIE's 128K record has only eight output calls, so its 25.344 token/s is not a sustained TG128 measure. The native C1 completion-to-next-submission gap is 0.092–0.097 ms, leaving numerical execution as the likely major cost. | Compare serial C1 with serial C1. MTP, lookup and batching may improve serving separately; they do not establish the 30 token/s C1 goal. |

Halogen's 131K uplift is 9.137% in rate. Applying that percentage to LIE's
retained 1,310.875 token/s would give only 1,430.645 token/s; another 4.848%
rate gain would still be required. This is arithmetic, **not** a prediction.
LIE needs the complete 130,925-token request to fall from 99.876067 s to at
most 87.283333 s, with capacity 133760, chunk 2048, the exact saved prompt,
and zero cached tokens. Its 63 intermediate chunks are full 2048-token chunks;
the 1901-token tail is the only partial chunk.
The saved native 32K serial decode interval is 38.606–38.681 ms per step;
30 token/s requires at most 33.333 ms, about 5.27–5.35 ms less per step.
Its observed host completion-to-next-submission gap is under 0.10 ms, so
reactive wakeups alone cannot supply that reduction.

## Bounded next expert experiment

The [saved fixed-input routing](../config/q2-current-routing-v2-results.json)
contains all 48 layers, 512 expert counts per layer and 20,480 routed rows per
layer. Recomputing the active `floor(ceil(rows / 64) / 2)` wide-IQ2 descriptor
rule gives 6,813 128-token descriptors, matching the archived counts. Of
these, 4,592 (67.4%) belong to the 892 expert/layer pairs receiving at least
256 rows. Pairing successive wide descriptors within each expert would cover
4,180 descriptors (61.35% of all wide descriptors). These are logical work
counts, not measured DRAM reads: cache residency, register pressure, LDS size
and occupancy may erase or reverse any saved fetches. This route fixture is
the fixed 2K input; long-context routing must be checked before extrapolation.

The next distinct trial is reuse of one expert's encoded IQ2 weights across
successive **token** tiles, restricted to experts with at least two wide
descriptors. Preserve the existing 640-by-2560 paired gate/up arithmetic,
output order, top-10 routing, 2048-token model chunks and fixed comparator.
First compile a private 2-tile component and record registers, scratch, LDS,
occupancy limits and code size. Stop if it spills or loses enough occupancy to
make the route implausible. Then time complete compact+gate/up+pack+down cycles
on the archived actual counts, checking every output and independent numeric
references. Advance to one original 32K model request only if the full-chain
component gain could materially reduce the 12.593-second 128K deficit; test
the unchanged original 128K request only after that gate. Keep the retained
provider unless the complete-model measurement improves. The prior BM256
experiment enlarged **output** rows and regressed, so it is not evidence for
or against this token-side design.

The [Halogen benchmark conditions](https://github.com/peonist-ai/halogen-flash-server#measured)
also name ROCm, power, IOMMU and arena differences; they explain why its
absolute rates cannot be used as a control. This audit authorizes no host
tuning, GPU run or altered benchmark input.
