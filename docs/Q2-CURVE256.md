<!-- SPDX-License-Identifier: MIT -->

# Retained Q2 and UD: requested curve through 256K

The owner requests this parallel diagnostic while the fixed-point target remains
**1685.777092 PP**, against retained **1587.893545 PP**. This curve does not
replace that comparison or establish parity before results are collected.

Both arms use the qualified native C17 `synapse-lie-bench --suite http-curve`
client, Gufo prose seed 1, prefixes 0/4K/8K/12K/16K/32K/64K/128K/192K/256K,
2048 new prefill tokens, 128 generated tokens, C1 greedy AR, one warmup and one
measured request. MTP, vision and SSD prefix caching are disabled; RAM prefix
capacity is 16384 MiB. Actual token counts, completed executor-call durations,
client timings, prefix construction and warmup evidence remain distinct.

Private server capacity is 266240, allowing the 262144-token prefix plus the
new prompt/output and calibration tolerance. The previous curve capacity was
133760: comparisons with saved older Q2 curves must state that difference.
The new Q2 and UD arms share capacity, input generation and measurement rules.
The inference endpoint is HTTP port 8000 on `.157`.

The retained Q2 provider (1028 files) and original UD provider (1019 files)
remain byte-identical to their recorded manifests. The 333-file private C17
core changes only the capacity ceiling, help text and a host regression test.
The matched numerical MMQ archives and native benchmark executable are reused
from qualified cohorts; the private server/core glue is rebuilt. No original
fixed counting control is rebuilt or rerun.

Host qualification `q2-curve256-host-r2` on `.157` completed at
2026-10-06 13:50:15.946913 UTC: **44 Debug and 44 ASan/UBSan tests pass**,
six command exits are zero and seven artifacts are collected. Host r1 retains
its actual CTest exit 8 and transport exit 1: the launcher correctly rejected an
invalid replay option, but the new test expected a later rejection message.
Only that expectation was corrected; all failure evidence remains.

The frozen [plan](../config/q2-curve256-plan.json) binds 207 runtime fixtures,
seven manifests and both new arms. GPU execution requires fresh scoped
admission. Collect both terminal cohorts and release the original ownership
leases before analyzing their numerical/performance results. No `.157`
cleanup, model conversion, dependency installation or tuning is included.
