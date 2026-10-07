<!-- SPDX-License-Identifier: MIT -->

# BF16 row-sized reader trial

The [native diagnostic](Q2-LONG-PROFILE.md) identifies45–70ms late-chunk CPU
gaps before the20MiB PLE upload. The retained reader requests an aligned
4096/8192-byte window even when the encoded BF16/160 row is only320 bytes.
The [earlier I/O investigation](Q2-PLE-ANALYSIS.md) established that compressed
Q2 extents already use buffered I/O underneath the direct-I/O descriptor.
This new candidate selects a private buffered descriptor for BF16/160 and
uses the existing exact-row offset/length reader. Other shapes and formats
retain their prior direct mode and fallback.

Only `src/models/qwen38_flash_next/ngram.cpp` differs from the retained
1028-file provider;1027 files remain exact. The encoded row cache, workers,
hashing, ordering, dequantization and numerical kernels are unchanged. This
does permit reclaimable file-cache residency. It does not reserve another
copy of the model, change model files or evict existing pages. Any measured
memory/I/O change must accompany the performance result.

The new host fixture wraps `pread` to verify320-byte requests and a descriptor
without `O_DIRECT`, exact BF16 conversion, duplicate/warm-cache behavior,
interrupted reads and EOF without an output overwrite. Existing upstream
reader tests also run against the exact candidate translation unit. On .157,
`q2-ple-row-bytes-host-r1` passes42/42 Debug and42/42 ASan/UBSan tests, with
six command exits0. Seven collected artifacts hash-verify. These are host
checks, not model performance or GPU qualification.

[Source manifest](../config/q2-ple-row-bytes-source.json) binds the independently
fetched Gufo parent, generator, patch and exact host fixture. Source remains
durable under `.deps/gufo-q2-ple-row-bytes-run`; remote capsules remain under
the project `run/` tree. No source or qualified evidence is cleaned up.

[Plan](../config/q2-ple-row-bytes-plan.json) `56c1948c` binds332 fixtures for
one new candidate build. The qualified MMQ archive and native
`synapse-lie-bench` executable are reused. The nine original serialized
requests retain all preparations, both original8K observations and the
complete32711-token prefill. Capacity133760, chunks2048, C1 AR, MTP off and
zero prefix hits remain mandatory. The original saved unprofiled control
and replies are the comparison; the intervening instrumented profile is not.

## Completed native model trial — 2026-10-07 UTC

All six commands exit0 and all12 artifacts verify. The native client and
server both exit0; nine streamed replies and usage records match their saved
references. The candidate binary is`8d15434d`. The original preparations,
requests,2048 chunks, natural final tails and timing scope are unchanged.

| Physical input tokens | Saved Q2 PP t/s | Row-byte PP t/s | PP change | Saved Q2 TG t/s | Row-byte TG t/s |
|---:|---:|---:|---:|---:|---:|
|4088|1512.809054|1421.993430|−6.003%|26.471407|25.123726|
|8138|1511.203024|1449.089101|−4.110%|26.390490|25.942326|
|8177|1476.050829|1503.063103|+1.830%|26.268072|25.755995|
|12242|1445.124766|1445.155170|+0.002%|26.328681|26.364031|
|16317|1435.353775|1428.209623|−0.498%|26.334428|26.624232|
|32711|1402.245716|1440.767919|+2.747%|26.234155|26.483395|

At32K full prefill saves0.623716 seconds, from23.327581 to22.703865.
These are individual original-prefix observations against saved,
noncontemporaneous controls. TG uses the original eight decode calls per
prefix, not TG128. Shorter-prefix results are mixed, including regressions;
do not promote this candidate globally or update the retained graph yet.
Greedy agreement does not establish independent task quality.

Session telemetry peaks at91.75°C CPU/93°C GPU, with at least66.18GiB
system memory available. System cached pages fall from53.42 to45.51GiB over
the whole session including model startup. These counters include existing
cache and model allocations; they do not isolate memory caused by the reader.
The runner's `/proc` I/O is for its controller. A separate identity-checked
snapshot of the actual server at04:17:02 records43,540,012,430 logical and
46,358,425,600 physical read bytes including startup; it is not a complete
request-I/O delta or a saved-control I/O comparison.

[Complete results](../config/q2-ple-row-bytes-results.json) preserve all
timings, requests, replies and the limitations. Collection`fddea32e` precedes
04:17:50.486075UTC release`91b98645`:1837 identities/1466 groups retired,
empty KFD, original CPU/four GPU leases free and seven model stat tuples
unchanged. Canonical/main/remote mirrors match; Core is notified before
analysis. No cleanup or control rerun occurred.

The observed32K improvement motivates two new64K/128K observations using
this saved candidate binary and the saved native client. Each cooled session
retains the original three preparations and corresponding long prefix.
This follow-up adds no32K rerun and no control rebuild. It cannot establish
the128K target until actual results are collected.

The [long-prefix plan](../config/q2-ple-row-bytes-long-plan.json) `071b49e1`
binds335 fixtures after the updated launcher passes42 Debug/42 sanitizer
tests on .157. Before both sessions CPU must be≤60°C; the existing inclusive
98°C stop remains. Server/client hashes and all original input bindings are
checked before execution. No model binary will be rebuilt for this follow-up.
