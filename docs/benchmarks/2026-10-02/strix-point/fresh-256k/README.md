<!-- SPDX-License-Identifier: MIT -->
# Paired original UD fresh-prefill benchmark near 256K

Read the [full results and scope](../../../../STRIX-POINT-BENCHMARK-RESULT.md).
On `.161`, LIE and the direct Gufo reference each passed
`synapse-lie-bench --suite fresh` with **258794 entirely new physical prompt
tokens**, capacity 262144 and TG128. There were no warmups and two measured
repetitions per arm. All four samples completed full 128-token outputs;
physical input IDs, generated IDs and complete PP/TG frontier hashes match.
This is direct original-weight GPU inference, without HTTP or a prefix-cache
hit. The 100 C supervisor ceiling was explicitly authorized; any lower sensor
max remained in force.

`input/{lie,gufo}/` holds seven original campaign files per arm and each
SHA-256 collection/retirement receipt. `input/thread-observations.json`
contains two read-only point-in-time `/proc` snapshots tied to the owned child
PIDs and start ticks. The 27 observed process threads in each arm include
HIP/runtime threads and are not a count of reactive scheduler workers.
`generated/` contains complete median/min/max CSV/JSON, normal and zero-axis
PP/TG plots, size estimates, sampled resource peaks, temperature/GTT timelines,
validated thread snapshots and source/output hashes. GTT is whole-device
accounting, not an allocation-exact model peak.

Reproduce the report offline with existing Matplotlib:

```sh
python3 -B docs/benchmarks/2026-10-02/strix-point/make-paired-report.py \
  fresh-256k run/strix-point-fresh-256k-reproduced-new
```

Use a new output directory. The generator checks all collected source hashes,
exit and cleanup receipts, complete samples, physical inputs, output IDs,
frontier equality and thread snapshot process identities without opening a
model or GPU.
