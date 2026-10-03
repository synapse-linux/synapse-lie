<!-- SPDX-License-Identifier: MIT -->
# DS4 runtime payload evidence on Strix Halo

See [the result](../../../KVC-GPU-RESULT.md) and
[declared protocol](../../../KVC-GPU-PROTOCOL.md). All 15 GPU arms use the
frozen `a4008b9` source with explicit legacy/KVC provider variants. CPU fixture
receipts are separate. The raw archive contains commands, source, numerical
witnesses, timings, actual exits, thermals and closure; no weights or checkpoint
payload. Same-provider/cross-variant tests do not establish foreign DS4-produced
checkpoint interoperability.

Extract the archive into a new directory, then reproduce the report with Python
and installed Matplotlib; no GPU/model invocation is involved:

```sh
python3 analyze.py EXTRACTED/ssd-gpu-r12 NEW-OUTPUT
python3 analyze-thermal.py EXTRACTED/ssd-gpu-r12-live-thermal/samples.jsonl NEW-THERMAL
```

JSON retains all state pairs, separate identity/capture/SSD-read/upload costs,
cold and measured core data. `core-jobs.csv` preserves all 48 jobs; `state-pairs.csv` contains all 24 pairs
and the writer transfer. Summary CSV exposes executed prefill, decode, first-token
latency and retained bytes; a full cache hit has no executed PP throughput.
