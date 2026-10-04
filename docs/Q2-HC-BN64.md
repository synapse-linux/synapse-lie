<!-- SPDX-License-Identifier: MIT -->
# HC-down with wider token tiles

The two new candidates derive from the measured original-F16 bounded provider
at 1477.969324 PP / 25.10545360 TG. Fixed Q2 1443.672867 / UD 1685.777092,
the original exact2048 input/timers and the full context-curve target remain.
No qualified provider or model evidence is overwritten or rerun.

The previous smaller K staging experiment regressed despite fewer static
instructions. These candidates increase the token tile from 32 to 64 instead:
each workgroup reuses its weights across twice as many tokens, with twice the
independent accumulator groups per wave. BK128 keeps LDS at 34816 bytes;
both use one LDS buffer. Only the launch template and corresponding token-grid
division change, in one file per 1023-file provider. All 1022 other files remain.

| Candidate | BM/BN/BK | WTM/WTN | VGPRs | LDS bytes | Private bytes/thread |
| --- | --- | --- | ---: | ---: | ---: |
| Measured parent | 64/32/256 | 16/16 | 138 | 50688 | 0 |
| Token-wide waves | 64/64/128 | 16/32 | 143 | 34816 | 0 |
| Output-wide waves | 64/64/128 | 32/16 | 144 | 34816 | 0 |

The 2048-token grid has 160 workgroups versus 320 in the parent. Each output
still receives the original ascending K16 sequence split into the same two
FP32 chains, then the same final addition. Original F16 bits, dispatch bounds,
allocation, streams and public transitional API remain. Ragged rows still
clamp loads to the final row and mask stores. Generated full-buffer equality
and speed require actual GPU evidence; source algebra and resource counts
alone do not establish either.

Both offline compile/unbundle/metadata sequences exit 0/0/0. The shared
format check retains exit 1 for 74 inherited violations, with no new include
complaint. Local 77 launch tests pass. The `.157` host CPU capsule verifies
16 fixtures and passes 23/23 Debug plus 23/23 ASan/UBSan, with no model or GPU.

The frozen runtime plan admits two new component candidates with independent
FP64 checks, full output hashes, guards and 100 MiB rotating original-F16 weights.
Numerical rejection does not suppress the 56 timings per candidate. At most
one new model follows if the summed native/library complete-cycle ratio
improves the saved bounded parent. Marginal/failed candidates remain retained.
No model reference rerun, full context curve, installation, tuning or cleanup.
Fresh coordinated admission is required before GPU build/execution.

[Source and patches](../config/q2-hc-bn64-source.json),
[device objects](../config/q2-hc-bn64-object-results.json),
[host receipt](../config/q2-hc-bn64-host-results.json),
[frozen plan](../config/q2-hc-bn64-plan.json).
