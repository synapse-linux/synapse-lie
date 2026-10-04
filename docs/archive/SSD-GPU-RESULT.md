# SSD restart: 512-token pass, 8K thermal stop

> Historical technical record. See [current usage](../guides/USAGE.md) and
> [benchmark tables and graphs](../benchmarks/README.md). Results below retain
> their original build, protocol and limitations.

Campaign `ssd-gpu-r1` on `.157` ran 2026-10-02 07:34:47–07:39:00 UTC against
runtime checkpoint `0e1387d`, using the unchanged qualified Gufo state-access
archives. **The campaign is FAILED/INCOMPLETE:** two arms passed, the third
stopped thermally, and the remaining 13 were not launched. There is no SSD
performance result through 8K/128K and no shared-core/HTTP device result here.

The 512-token producer durably committed one complete hybrid checkpoint. A
separate process established the identical full-content model/build/device
identity, read that file and passed all three exact fresh/restored comparisons.
The prompt stopped early: each pair made **two decode calls and emitted one
token**, including the seeded-sampling pair. Every available full-logit frontier,
token, position and stop matched; this does not qualify a 16-token continuation.
The reader never captured a replacement or fell back to fresh prefill on its
restored side. Context capacity was 262144, chunk 2048, checkpoint 512.

## Complete observed values

These are state-diagnostic timings, not serving latency or throughput claims.
The disk checkpoint was read once; each pair subsequently uploaded that retained
host state independently. Full-content identity and supervisor inventory hashing
warm OS file caches. No cold-device/reboot claim or cache-drop operation.

| Stage | Producer | Restarted reader |
|---|---:|---:|
| Model load | 20.559 s | 25.245 s |
| Full-content identity hashing | 60.059 s | 52.770 s |
| Device state capture | 7.977 ms | — |
| Durable write, including fsync | 1852.212 ms | — |
| File lookup/read/checksum | — | 61.517 ms |
| Retained component state | 134,778,968 bytes | 134,778,968 bytes |
| File bytes | 134,769,832 | 134,769,832 |
| Allocated disk bytes | 134,770,688 | unchanged |
| Peak staging reservation | 134,778,968 bytes | 4,294,967,296 bytes |

The reader reserves the declared full 4 GiB staging cap while its one operation
is admitted; this is a reservation, not a measured 4 GiB allocation. The payload
has 112 typed components. Quota is 8 GiB, with no RAM prefix tier in this direct
state diagnostic. Startup hashing cost is material and is not request prefill.

| Pair | Generation | Fresh prefill | Owner upload | New PP tokens | Output tokens |
|---|---|---:|---:|---:|---:|
| 0 | Greedy | 627.892 ms | 4.388 ms | 0 | 1 |
| 1 | Seed 123 sampling | 718.825 ms | 8.174 ms | 0 | 1 |
| 2 | Independent greedy | 540.484 ms | 3.780 ms | 0 | 1 |

Fresh prefill covers all 512 tokens. Restored prefill executes zero tokens;
the recorded 0.00014–0.00018 ms tail values are empty-loop timing overhead.
Full-hit PP tokens/s is unavailable. Model load/hash, file read and owner upload
are separate measurements and must not be presented as a measured core TTFT.

## Thermal stop and closure

| Arm | CPU peak | GPU peak | NVMe sensor peak | Child / supervisor exits |
|---|---:|---:|---:|---|
| 512 write | 64.875 C | 73 C | 71.85 C | 0 / 0 |
| 512 read | 75.750 C | 78 C | 76.85 C | 0 / 0 |
| 8192 write | 84.000 C | 86 C | 75.85 C | 1 / 1 |

The 8K producer finished model loading and identity hashing, then crossed the
85 C GPU ceiling during prefill, before capture/durable-write evidence. The
supervisor sent SIGTERM only to its own child; the harness noticed interruption,
reported failure and retired without forced SIGKILL. Sampling can observe an
overshoot; it does not guarantee temperatures stay physically below the ceiling.
No retry, limit increase, foreign termination, fan/power/clock change or cleanup
of retained store files occurred.

At **07:39:00.622454 UTC**, all six supervisor/child PID/start identities were
absent, KFD empty and four expected lease inodes unchanged/free. Independent
status confirmed controller retirement. All 39 collected evidence files passed
SHA-256 verification; model stat witnesses and staged artifacts stayed unchanged.
The window was returned to Q2, which must perform its own fresh admission.
No permanent listener or process remains from this campaign.

Sampled totals included 35/36 threads during execution and up to 51 during model
loading. Those samples do not individually attribute every TID. The store adds
one opt-in I/O worker, not another inference pool; this campaign measures no
reactive/concurrency gain. Denied-FD/desktop observation limitations and absence
of a formal DS4 ACK remain as documented in coordination.

[Raw arm results, all state values and manifests](../benchmarks/2026-10-02/ssd-prefix-r1/summary.json),
[CSV](../benchmarks/2026-10-02/ssd-prefix-r1/state.csv),
[closure](../benchmarks/2026-10-02/ssd-prefix-r1/postflight.json) and
[source-bound CPU checks](../benchmarks/2026-10-02/ssd-qualification/cpu-receipt.json)
are retained. The [16-arm protocol](../development/protocols/SSD-GPU-PROTOCOL.md) is not complete.
Long-prefix restart/extension and matched core off/RAM/SSD timings still need a
separately coordinated temperature-safe continuation. Deliberate pauses could
serve a correctness-only campaign, but would not qualify unpaced performance.
