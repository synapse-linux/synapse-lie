<!-- SPDX-License-Identifier: MIT -->
# DS4-style cache policy GPU evidence

See [the result](../../../CACHE-DS4-GPU.md). R8 retains the initial source
failure. R9 retains its failed cache-depth assumption under memory pressure,
with all nine device children exit0. R10 retains a failed harness assumption
about the legacy aligned boundary on raw text. R9/R10/R11 qualify frozen source `f11ab7f`;
the report independently validates every completed numerical comparison.
The later cache-disabled
shortcut in `fffaabb` has separate CPU evidence and is not part of this binary.

The archive includes commands, source capsules, timings, thermal observations,
actual exits and closure receipts. It contains no model or checkpoint payload.
Extract it into a new directory and reproduce graphs without GPU/model access:

```
python3 analyze.py EXTRACTED/ssd-gpu-r9,EXTRACTED/ssd-gpu-r10,EXTRACTED/ssd-gpu-r11 NEW-OUTPUT
python3 analyze-thermal.py EXTRACTED/ssd-gpu-r9-live-thermal/samples.jsonl NEW-THERMAL
```

Python and Matplotlib are required. JSON/CSV retain cold and warm samples,
executed prefill, restore/capture cost and retained allocation. These are
same-provider exact-state checks, not DS4 KVC interoperability or model quality.
