<!-- SPDX-License-Identifier: MIT -->
# Original-weight long-context recall on Strix Point

This functional gate uses the native `synapse-lie-bench --suite http` client
with `--preset long-context-recall`. It measures whether the served model can
retrieve three seeded bindings and continue the same conversation. Capacity
stress with repeated token IDs and cold-prefill performance are separate tests.
The historical 1M capacity result does not qualify this workload or runtime.

## Workload

One separately admitted window runs one size, seed and RoPE profile, with two
turns, 128 output tokens per turn, no warmups and one repetition. Turn one asks
for the middle binding; turn two asks for the start and end bindings, retaining
the original ledger and the actual first answer. Neither follow-up nor oracle
is allowed to supply the requested values. All requests use greedy generation,
one active sequence and disabled RAM/SSD prefix caching. The client exports the
complete ledger, exact follow-up and expected answers before measured requests.

Use three independently seeded corpora: **77, 991 and 20261007**. These are
independent binding/content seeds, not three repeats of the same request.
Qualify AR first. MTP is a separate cohort with the original predictor and
actual measured proposal/acceptance counts; do not infer MTP from configuration.

| RoPE profile | Configured capacity | Physical prompt targets |
| --- | ---: | --- |
| Native | 262,144 | 8,192; 131,072; 261,632 |
| YaRN 2× | 524,288 | 8,192; 131,072; 261,632; 523,776 |
| YaRN 4× | 1,048,576 | 8,192; 131,072; 261,632; 523,776; 786,432; 1,048,064 |

The short control belongs to each profile: static scaling can change short
answers. Native and scaled results must stay separate. Targets round down to
complete calibrated records; retain actual input tokens rather than calling
the configured capacity an input measurement. Near-capacity targets reserve
512 tokens for both output budgets and the continuation question/template.
The client refuses nonlinear calibration or unexpected first-turn physical
counts. Its three 8/16/32-record calibration requests are not quality samples.

Start with chunk and scratch capacity **256**, matching the historical physical
1M memory reference. Other chunks are explicitly separate configurations;
larger scratch reservations need their own admission and memory observations.
Each 512K/1M-capacity window requires an explicit GTT peak estimate and minimum
available RAM in the manifest. Previous AR memory fit does not establish
current WMMA or MTP fit. No host GTT, power, clocks or fan tuning is implicit.

## Optional development coordinator

`tools/strix-point-campaign.py` selects `bench_profile: "modern-http-recall"`.
Stage the SHA-bound `tools/strix-point-http-recall-gate.py` as
`http-recall-gate.py` in an exclusive persistent job directory. Bind that SHA
as `http_recall_gate_sha256`. Stage `http-recall-settings.json`, bind its SHA as
`http_recall_settings_sha256`, and include its identical object as `http_recall`:

```json
{
  "context": 1048576,
  "rope_scaling": "yarn4",
  "size": 1048064,
  "chunk": 256,
  "seed": 77,
  "request_timeout_seconds": 14400,
  "load_timeout_seconds": 900
}
```

The supervisor still requires a coherent runtime/model binding, separately
fresh peer/global/in-lease checks and the unchanged original `.161` lease.
The helper starts only its server and native client, on two private ephemeral
loopback ports. It supplies actual context/RoPE/chunk settings to the server
and the same declarations to the client. RAM cache is zero; SSD is not enabled.
It does not install, deploy, convert/hash weights, stop foreign processes,
automatically retry, or reserve a later window.

The request deadline covers one actual prefill and answer. The client deadline
covers all three calibration requests and both measured turns; the container
deadline additionally covers model loading and owned cleanup. With the example
these are 14,400, 72,030 and 72,990 seconds, respectively. A bound is not an
expected duration. The old physical 1M prefill took about 7,455 seconds, so a
1,200-second general HTTP gate cannot substitute for this test.

Python is optional development coordination only. The benchmark, evaluator,
server, reports, graphs and default build/tests remain native and Python-free.
Focused coordinator HOST checks run with:

```sh
python3 -B tests/test_strix_point_http_recall.py
python3 -B tests/test_strix_point_campaign.py
```

These use synthetic counters/canned replies and mocked children, not model
inference, GPU qualification or benchmark evidence.

## Acceptance and evidence

Preserve `measurements.jsonl`, `requests.jsonl`, complete SSE chunks and actual
request bodies, client stdout/stderr, server log, helper result, model stats,
thermal/resource observations, controller/container records and exact closure.
Re-evaluate each answer against independently reconstructed seed bindings and
the exported per-turn oracle. Require complete cold samples, calibrated first
input, retained full history on continuation and admitted mode/timing counts.
Member order/JSON escapes may differ; missing/extra/duplicate keys, prose, tools
and incorrect values fail. A budget-limited complete answer is scored normally
and its finish remains recorded; no fixed generation length is imposed.

The native client keeps both observations on quality misses and exits1 with
`quality_failed`. The helper records `QUALITY_FAILED`, distinct from `FAILED`
for transport, workload, timeout or cleanup failure. It retains available raw
artifacts and actual child exit codes even when the gate fails. A summary alone
cannot establish acceptance. After collection and hash verification, prove all
owned PID/start identities and the whole container cgroup retired, restore the
authorized router and release the original lease before declaring the window
closed. Do not rewrite questions or relabel failures as passes.

Record exact matches per seed, turn, physical size and profile. A successful
8K window proves only that control; it does not close the ladder or the 1M
quality gate. Synthetic associative recall does not establish natural-language
quality, a vendor quality suite, fault coverage or comparative performance.
Matched Gufo/Halogen timings follow quality checks. Terminal Bench remains last.
