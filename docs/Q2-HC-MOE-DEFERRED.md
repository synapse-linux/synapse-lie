<!-- SPDX-License-Identifier: MIT -->
# MoE-only deferred normalization composition

This new candidate composes the retained deferred-norm numerical experiment
with the measured BK256 bounded provider (1477.969324 PP / 25.10545360 TG).
Fixed Q2 1443.672867 / UD 1685.777092, the original exact2048 tester/input/timers,
and the full PP/TG context-curve target remain. Existing qualified controls
and the old synthetic component are reused without rerunning them.

The old complete synthetic cycle saved 1.894% only for MoE and regressed
10.292% for ordinary combine. It had real feedback-byte differences despite
passing sampled norm/consumer checks. This candidate therefore selects deferred
normalization only for the 2048-row original-F16 MoE route; ordinary combine,
the Q8 producer/consumer and the best parent's native down remain unchanged.
Copying the retained port does not establish numerical acceptance or a model gain.

The producer omits 80 MiB of materialized F32 norm per applicable combine and
writes four scales/token (32 KiB at 2048 rows). Scales occupy the existing
HC-gate buffer beyond `rows * hc_low_rank` float elements; low-rank F16 input
occupies only the prefix. Up/mix and injection reconstruct normalized values
on the existing ordered stream before scratch can be reused. No allocation,
stream, GPU scheduling policy, model conversion or public adapter ABI changes.

An owned C17 identity helper records residual, gamma, scales and rows. A new
producer invalidates old identity; unnormalized consumers clear it. Normed
consumers refuse changed residual/gamma/rows. Unsupported fused consumers
materialize F32 norm before continuing; Q8 still takes its existing route.
The half identity is published for the down consumer, then replaced by the
mixed-row identity. Host guards do not establish GPU address safety by themselves.

The persistent source changes six of 1025 files; 1019 remain exact to the
measured parent. Original and reconstructed patches, donor/parent identities
and all earlier failures remain. The original-F16 numerical include compiles
for gfx1151; the executor compiles with the existing HIP platform definition.
The first plain-C++ attempt omitted that definition and failed; its command
and exit 1 are preserved. Shared formatting runs with exit 1 and 57 reported
violations; no formatting success is claimed.

| New kernel | VGPRs | LDS bytes | Private bytes/thread |
| --- | ---: | ---: | ---: |
| MoE deferred producer | 84 | 10368 | 0 |
| Deferred up/mix | 242 | 24576 | 0 |
| Deferred injection | 42 | 128 | 0 |
| Reconstruction fallback | 13 | 0 | 0 |

Local launch guards pass 78/78. On `.157`, the host CPU capsule passes 24/24
Debug and 24/24 ASan/UBSan, including wrong residual/gamma/row identity,
replacement, invalid publication and cleared-state rejection. Six commands
exit zero and seven artifacts verify; no GPU or model is opened by those tests.
The frozen window permits only one new original-weight model arm, with full
MMQ build, capacity9216/chunk2048, one warmup/three measured sessions,128 output
tokens/127 timed decode calls and15-second waits outside timers. It retains
numerical differences and measures performance separately. No benchmark switch,
qualified control rerun, component rerun, curve, install, tuning or cleanup.
GPU build/execution requires fresh coordinated admission.

[Source and patch](../config/q2-hc-moe-deferred-source.json),
[static results](../config/q2-hc-moe-deferred-static.json),
[host receipt](../config/q2-hc-moe-deferred-host-results.json),
[frozen plan](../config/q2-hc-moe-deferred-plan.json).
