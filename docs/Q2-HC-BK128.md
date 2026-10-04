<!-- SPDX-License-Identifier: MIT -->
# HC-down BK128 staging experiment

The measured original-F16 BK256 bounded parent gives1477.969324 PP on the
unchanged exact2048 model input. It is12.327120% below fixed UD1685.777092;
the full parity objective remains open. These two new candidates change only
the launch template in its attributed numerical include. No original provider
or qualified result is overwritten. Each complete source inventory has1023
files,1022 unchanged; patches reproduce the one-file changes.

| Candidate | BK | LDS buffers | LDS bytes | VGPRs | Private bytes/thread |
| --- | ---: | ---: | ---: | ---: | ---: |
| Measured bounded parent | 256 | 1 | 50688 | 138 | 0 |
| New single buffer | 128 | 1 | 26112 | 97 | 0 |
| New double buffer | 128 | 2 | 52224 | 98 | 0 |

Compiler observations use the same original numerical flags on the editing
host. Both configure-independent compile/unbundle/metadata commands exit0;
no device is executed. The shared upstream format check exits1 for74 inherited
violations in each source and reports no new numerical-include complaint.
Compilation/resource counts are not GPU numerical or performance evidence.

Both keep BM64/BN32,256 threads, two FP32 K16 chains and ascending K16 order.
BK128 is divisible by32, preserving which partial chain receives each K16.
Original F16 weights/activations and dispatch bounds96–2048/M320/K10240 remain.
Single buffering reduces LDS and the number of per-thread prefetched chunks,
but doubles K steps/barriers. Double buffering keeps the previous barrier
count and overlaps LDS stores with consumers, using roughly the same total
LDS as its parent. Generated arithmetic equivalence and speed need GPU checks.

The existing component fixture now prints unrounded error fields after
library diagnostics. Both new modes compare the exact library recipe,
retain independent FP64/full-buffer/guard checks and measure56 timings each
with100 MiB rotating weights. Numerical rejection never suppresses timing.
Model selection compares the summed complete-cycle native/library median
ratio against the saved bounded parent. At most one new model is admitted
if that ratio improves; even a marginal candidate is retained. Saved qualified
Q2/UD models are never relaunched. No context sweep precedes fixed-point parity.

Local77 launch checks pass. The `.157` CPU-only capsule verifies16 bound files,
with23/23 Debug and23/23 ASan/UBSan tests. Those tests do not execute HIP.
Fresh four-lease/process/KFD/registry/model-stat/thermal admission is required
before GPU build/run. No dependency installation, tuning or remote cleanup.

[Source and patches](../config/q2-hc-bk128-source.json),
[device objects](../config/q2-hc-bk128-object-results.json),
[host results](../config/q2-hc-bk128-host-results.json),
[frozen plan](../config/q2-hc-bk128-plan.json).
