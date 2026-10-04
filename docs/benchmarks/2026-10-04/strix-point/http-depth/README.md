<!-- SPDX-License-Identifier: MIT -->
# Strix Point cold HTTP prefill: LIE versus official Gufo

Original Unsloth Qwen3.8 Flash Next UD-Q4_K_XL weights run on
`pop@192.168.5.161` (`gfx1150`) inside the same Fedora 43 / ROCm 10
Distrobox image. LIE and the native C `synapse-lie-bench` HTTP client use the
pinned `128f490cfff9713f84f658ad17118272a1cd4ad7` runtime bundle;
the independent official Gufo server is pinned to
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`. The campaign controller
is the `bff9a43` checkpoint. These are served, original-weight GPU runs,
separate from the earlier direct-executor context curve and the prepared
4K [multi-client report](../http-multi/README.md).

Each arm starts a fresh server on private loopback port 8000 with context
262,144, prefill chunk 2,048, one active session, and 128 requested output
tokens. The client uses the deterministic `lie-long-context-v1` varied-number
generator with seed `20261004`. Three tiny token-calibration requests are
excluded; there are no warmup repetitions. Two measured requests at each
target are required to produce all 128 output tokens with complete SSE usage.
Server phase telemetry must show **zero cached tokens**, positive prefill time
and executed prefill tokens equal to the physical prompt length. LIE disables
its RAM prefix cache with `--kv-cache-ram-mb 0` and never opts into SSD cache.
Official Gufo accepts the per-request `cache_prompt:false` control. The
auditor checks that, after removing this sole Gufo-specific field, both
engines received identical JSON requests and physical token counts. The
requests, response text, phase timings, supervisor traces, exits, model-file
stat witnesses and CPU/GPU/NVMe/GTT samples are retained and hash-checked.

Values are medians of the two measured runs; prefill throughput is executed
prompt tokens divided by **server prefill time**. Decode throughput is 128
tokens divided by server decode time. TTFT and total wall time include HTTP
transport and are reported separately in the
[complete CSV](generated/comparison.csv) and [JSON](generated/summary.json).
The [AR prefill graph](generated/ar-prefill.svg) and
[AR decode graph](generated/ar-decode.svg) show the measured curve. Generated
assistant text is recorded with per-sample hashes; equal prompts and token
counts do not imply equal text or an independent quality result.

| AR target | Physical prompt | Prefill LIE / Gufo (tok/s) | Decode LIE / Gufo (tok/s) | TTFT LIE / Gufo (s) |
| --- | ---: | ---: | ---: | ---: |
| 8,192 | 8,164 | 484.214 / 476.398 | 10.385 / 10.347 | 17.388 / 17.171 |
| 32,768 | 32,740 | 447.677 / 447.061 | 10.312 / 10.257 | 73.676 / 73.318 |
| 131,072 | 131,044 | 409.414 / 409.180 | 10.064 / 9.700 | 320.611 / 320.636 |
| 258,794 | 258,788 | 386.128 / 384.685 | 9.706 / 9.638 | 670.754 / 673.202 |

The AR prefill curve declines by 20.3% on LIE and 19.3% on Gufo from 8K to
the near-256K point. At each target their prefill rates are within 1.7%; the
largest gap is the 8K pair. This agrees in scale with the earlier direct-core
Point curve, but the runtime build, chat template and method differ, so it is
not a cross-build speedup measurement. The two repetitions within each engine
produce identical assistant text; LIE and Gufo text differs after a common
initial prefix. No quality or token-ID parity is inferred from this curve.

MTP uses the separately pinned predictor with seven allowed draft tokens.
The prefill remains a cold full-prompt computation; accepted drafts affect
decode. Counts below are per measured request, and are identical across the
two repetitions within each engine.

| MTP target | Prefill LIE / Gufo (tok/s) | Decode LIE / Gufo (tok/s) | TTFT LIE / Gufo (s) | Accepted / proposed LIE | Accepted / proposed Gufo |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8,192 | 470.453 / 467.976 | 14.407 / 13.291 | 18.034 / 17.488 | 74 / 112 | 74 / 127 |
| 32,768 | 439.684 / 438.820 | 13.396 / 14.182 | 75.141 / 74.704 | 60 / 86 | 77 / 116 |
| 131,072 | 403.518 / 402.133 | 14.328 / 12.052 | 325.468 / 326.573 | 78 / 113 | 63 / 111 |
| 258,794 | 378.945 / 378.643 | 14.293 / 12.097 | 683.606 / 683.989 | 85 / 129 | 65 / 103 |

At 8K/32K/128K/~256K, LIE's MTP/AR decode ratios are
1.387/1.299/1.424/1.473; Gufo's are 1.285/1.383/1.243/1.255.
MTP prefill is 1.4–2.8% below each engine's AR value at these points.
At ~256K, MTP's faster decode saves 4.23 s in LIE's server phase but its
prefill takes 12.70 s longer; median HTTP wall time increases by 8.51 s
(Gufo: +8.09 s). MTP lowers total wall time at 8K and 32K, but raises it
at 128K and ~256K in this cold-prompt workload. Differences in accepted
drafts and generated text
prevent interpreting an inter-engine MTP rate gap as a pure scheduler effect.
The [mode-effect CSV](generated/mode-effect.csv) and
[MTP/AR decode graph](generated/mtp-over-ar-decode.svg) contain the ratios.
Within each of the 16 windows the two outputs are byte-identical; in all eight
LIE/Gufo pairs the cross-engine output differs. This is a performance and
protocol measurement, not a quality or token-ID equivalence result.

Across all 16 successful windows, sampled maxima are 86.125 °C CPU,
88 °C GPU, 73.85 °C NVMe and 90.524 GiB GTT used. There is no thermal stop.
The CPU and NVMe guards were enforced; GPU temperature was observed only.

The server's current hard context cap is 262,144 tokens. The 258,794-token
target leaves room for the 128-token output; a one-million-token HTTP run is
outside this backend's present contract. Large-context prefill can only be
claimed for completed, independently admitted arms listed in the generated
evidence. A failure remains a failure even when the supervising process
restores the named router and releases its lease.

The launch/collection commands are implemented by
`tools/strix-point-http-depth-campaign.py`; the separate
`tools/strix-point-http-depth-report.py` validates both sides of each pair
before writing the generated tables and graphs. Only
`llama-router.service` is stopped and restored by the admitted controller;
the CPU guard is 98 °C, the NVMe guard 85 °C, and GPU temperature is observed
without a software ceiling. Every new GPU arm independently reacquires the
private lease and checks its own model stat before/after.

## Sealed evidence and offline regeneration

The [verification record](generated/verification.json) binds 361 archived
members across 16 successful model-serving windows and the retained first
pilot, which exited 1 before model load because its LIE request timeout
exceeded the server's 1,800,000 ms maximum. The pilot's child/supervisor
exits remain 1; its router and lease were restored/released. All 16 corrected
windows have client, container and supervisor exits 0, unchanged model files,
retired owned GPU processes, active router and free private lease. They
contain 32 measured 128-token responses plus excluded calibration requests.

The three raw archives include exact request/response JSONL, phase metrics,
source and binary pins, server/client logs, one-second thermal/GTT samples,
controller exits and collection hashes:

- [AR windows](data/ar.tar.gz), SHA-256
  `25ff3ceb1e51f9e85502cd28441806e45cd3ae292a24caf9e22dbae5c55632a3`.
- [MTP windows](data/mtp.tar.gz), SHA-256
  `e9980c181fdd0977b77dc79166301194669a15fe6a7587fe9e0d5955e11d6e6a`.
- [Failed pilot](data/history.tar.gz), SHA-256
  `56f2c0bd98a2a3971da57fda7391d58bbfcd2b530c7c611fc8fac446eff3355c`.

From the repository root, verify and regenerate into a **new** directory
without GPU, model files or network access:

```sh
cd docs/benchmarks/2026-10-04/strix-point/http-depth/data
sha256sum -c archives.sha256
cd ../../../../../..
python3 -B docs/benchmarks/2026-10-04/strix-point/http-depth/make-report.py \
  evidence/point-http-depth-reproduction
```

The reproduction checks each archived member, every remote collection SHA,
controller exit, source stage, router/lease closure and the failed pilot before
recalculating the eight matched comparisons. Its eight CSV/JSON/SVG outputs
match the committed [generated files](generated/) byte for byte. The
[archive inventory](data/inventory.json), [seal script](seal-data.py) and
[offline report builder](make-report.py) document the provenance and method.
The [release receipt](../../../../development/validation/point-http-depth-release-2026-10-04.json)
summarizes exits, source pins, postflight checks and archive hashes.
This C1 cold-context campaign does not measure long-context concurrent HTTP,
allocation-exact peak HIP memory, cold-file model startup or 1M context.
