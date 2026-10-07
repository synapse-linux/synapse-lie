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
| Halogen 0.15.2 optionally keeps its compressed trunk unpacked in memory, using about 5.5 GiB extra for faster long prompts. | LIE already tested a persistent 5,348,130,816-byte Q8 mirror: exact outputs, but original 2K prefill fell 2.165%. The representation, packing and kernels differ. | Do not repeat an unconditional mirror. A new residency design needs an identified consumer and a whole-model win. |
| Halogen 0.15.3 reports faster prompts of every length, and 0.16.1 reports faster decode, especially with concurrent conversations. The changelog does not expose the numerical kernel implementation or a matched C1 rate for these changes. | LIE's serial C1 target and concurrency/reactive measurements are separate. | Treat the release notes as attribution leads, not measured transferable gains. |

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
occupancy limits and code size. The first coordinated GPU screen compares
the whole gate/up output and completed timings on the archived routing counts.
Stop if numerical differences or occupancy loss make the route implausible.
Only a positive screen proceeds to complete compact+gate/up+pack+down cycles,
checking every output and independent numeric references. Advance to one
original 32K model request only if the full-chain component gain could
materially reduce the 12.593-second 128K deficit; test
the unchanged original 128K request only after that gate. Keep the retained
provider unless the complete-model measurement improves. The prior BM256
experiment enlarged **output** rows and regressed, so it is not evidence for
or against this token-side design.

The private token-side probe is prepared without changing production dispatch.
Its C17 map covers every live 64-row unit exactly on all 48 saved routing
layers and 18 boundary shapes. A locally linked gfx1151 HIP fixture compares
the retained 128/64-token producer with a 256/128/64-token producer on whole
guarded outputs and rotating weights; this fixture has **not** run on the GPU.
Static device compilation preserves all 164 retained bodies and adds one
256-token body without private scratch. That body uses 242 VGPR and 42,112
bytes of LDS, versus 150 VGPR and 25,728 bytes for the 128-token body.
Its resource increase makes occupancy a concrete risk. Local compilation and
coverage establish neither numerical acceptance nor a speed gain. The exact
manifest, assembly analysis and isolated patch are in
`../config/q2-iq2-token256-probe-source.json`,
`../config/q2-iq2-token256-probe-static.json` and
`../experiments/q2-iq2-token256-probe.patch`. A coordinated GPU component
comparison is the next gate; no model run follows from this preparation.

The [Halogen benchmark conditions](https://github.com/peonist-ai/halogen-flash-server#measured)
identify its measured rows as the older w4b checkpoint: the 0.14.1 prefill
rows used two runs, and the serial decode rows came from 0.2.0. They also
name ROCm, power, IOMMU and arena differences; absolute rates cannot serve as
LIE controls. Halogen reports a 13–16% prefill effect from disabling IOMMU on
its machine, but that is a host-specific A/B observation, not a LIE kernel
gain. This audit authorizes no host tuning, GPU run or altered benchmark input.
