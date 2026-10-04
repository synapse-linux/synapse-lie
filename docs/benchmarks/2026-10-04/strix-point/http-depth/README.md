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
