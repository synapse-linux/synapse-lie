<!-- SPDX-License-Identifier: MIT -->
# Ordered IQ2 signs on the canonical context curve

The ordered packed-sign kernel improves complete Q2 decode by **4.446–5.188%**
across all eight context depths against an unchanged Q2 control run immediately
after it. The median per-depth increase is **5.143%**. This is original-weight
HTTP model throughput on `.157`, following the same Gufo prose recipe and
frozen C17 executor timers as the prior canonical curves. UD is still running;
Q2/UD parity is not established by this within-Q2 comparison.

Both candidate and repeated control preserve all 20 baseline request payloads,
completion texts, finish reasons and physical work counts, including calibration,
warmup and prefix preparation. Every measured continuation completes 128 tokens.
This confirms observed output replay, not independent full-model numerical or
quality qualification. Earlier Q2 numerical failures remain open.

## Decode gain, with prefill order effects retained

| Prefix target | Q2 control PP tok/s | Ordered IQ2 PP tok/s | Q2 control TG tok/s | Ordered IQ2 TG tok/s | TG change % |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1398.334 | 1397.861 | 25.517 | 26.833 | +5.161 |
| 4096 | 1329.349 | 1330.162 | 25.512 | 26.835 | +5.188 |
| 8192 | 1315.652 | 1317.565 | 25.486 | 26.797 | +5.146 |
| 12288 | 1308.705 | 1285.465 | 25.451 | 26.761 | +5.145 |
| 16384 | 1299.850 | 1300.349 | 25.429 | 26.736 | +5.142 |
| 32768 | 1275.940 | 1274.496 | 25.314 | 26.589 | +5.037 |
| 65536 | 1179.648 | 1193.506 | 25.068 | 26.277 | +4.826 |
| 131072 | 1158.997 | 1158.643 | 24.559 | 25.651 | +4.446 |

The initial Q2 baseline, candidate and post-candidate Q2 control are all
retained. At depth zero their prefill rates are **833.320, 1397.861 and
1398.334 tokens/s**. The unmodified control reproduces the candidate's high
prefill rate, so the initial 67.746% apparent increase must not be attributed
to the packed-sign patch. Relative to the repeated control, candidate PP
varies from −1.776% to +1.175%. This sequence is consistent with prior storage
warming evidence; it is not a controlled cold/warm filesystem experiment.
No page cache was flushed or original model file changed.

Source inspection supports the distinction: `PrefillPhase` makes both
`MatrixRows` and `ExpertMatrixRows` select tiled prefill, including partial
chunks. The changed `vec_dot_iq2_xxs_q8_1` belongs to MMVQ; the IQ2 MMQ traits
use separate tile loaders and Q8 dot functions. Thus a large PP change was a
reason to run an unchanged control, not a reason to claim a prefill optimization.
The measured 41.364% component-time reduction applies to one decode stage;
it must not be added directly to full-model throughput.

Each provider is rebuilt from full MMQ sources, with the same 333-file C17
core and exact qualified runtime harness. The candidate changes only the IQ2
vector-dot header in the 1020-file Q2 provider. C1 greedy sampling, thinking,
MTP and vision settings, RAM prefix policy, context capacity 133760, chunk2048,
seeds, calibration and all timing boundaries are unchanged. PLE cache-first
and larger-cache experiments are absent from every arm.

## Evidence and remaining work

Host checks pass 19/19 Debug and 19/19 ASan/UBSan. The first three model arms
each complete with five command exits zero and 30 collected artifacts verified.
The candidate and repeated-control validations retain all eight actual counts,
PP/TG durations, cache timings and complete-history comparisons:

- [Initial baseline validation](../config/q2-iq2-curve-baseline-validation.json).
- [Candidate validation](../config/q2-iq2-curve-candidate-validation.json).
- [Repeated-control validation](../config/q2-iq2-curve-repeat-validation.json).
- [Order-control comparison](../config/q2-iq2-curve-order-control.json).

The unchanged repeat is admitted at 01:15:08 UTC after all 23 existing owned
identities retire, KFD is empty and all four original leases are free. An
earlier local preflight mistakenly included an observed desktop PID in the
retirement set; that attempt exits 1 before any admission or workload. It is
retained, and the checker is corrected to inspect only owned command/session
identities. No foreign process is terminated or changed.

The extended analyzer accepts the optional repeated control, validates it
against the same provider/core/harness and preserves both baselines in JSON,
plots and CSV. A UD comparison and verified window closure remain pending.
The candidate is not promoted and the whole-curve Q2/UD goal remains open.
