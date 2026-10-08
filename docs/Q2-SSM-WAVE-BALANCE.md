<!-- SPDX-License-Identifier: MIT -->
# SSM operand reuse at unchanged tile size

The .157 component rejects this candidate: median complete-operator latency
rises from4918.818333 to5677.352667 microseconds, **+15.421068%**. All five
measured pairs regress, with disjoint observed ranges. All72 guarded whole
outputs are byte-identical;144 independent FP64 checks pass, maximum relative
RMS1.067384e-5 against the unchanged0.002 limit. The component exits0.
No model trial or production promotion follows. The original129K prefill and
30-token/s C1 objectives remain unmet.

| Complete2048-row SSM projection plus convolution | Retained | Wave-balanced |
| --- | ---: | ---: |
| Median completed wall time, microseconds |4918.818333|5677.352667|
| Minimum |4875.423000|5637.633333|
| Maximum |4930.728000|5692.392000|
| Mean |4911.255933|5672.405867|

All14 raw HIP event durations are invalid zero; the figures above use five
completed host-wall samples per arm after two warmups. The unchanged fixture
times three distinct weight/output states per sample, with allocation, input
upload, reset and validation outside timing. Source-level LDS traffic is not
the measured limit here: fewer operand reads coexist with slower execution.
The test does not isolate register pressure, instruction scheduling or bank
behavior as the cause.

The CPU-only supervisor fixture passes both success and failure paths on
.157 before admission10:23:18.954294UTC. The GPU component finishes at
10:23:43.227229 with CPU/GPU peaks51.375/48C. All11 raw artifacts collect and
verify before release10:25:05.089864UTC, SHA
`f7703956a2bbddc82549e4a75605631dd50d00115be018b80a9eab9fa1181806`.
The latest registry receipt matches;1958 process identities/1564 groups are
retired, KFD empty, five leases free, seven model stat tuples unchanged and
no remote cleanup. Core receives the release. There is no outstanding Q2
GPU handle, lease, reservation or waiter.

[All samples and checks](../config/q2-ssm-wave-balance-results.json),
[frozen plan](../config/q2-ssm-wave-balance-plan.json),
[raw evidence analyzer](../tools/analyze-q2-ssm-wave-balance.py).

The following records the original preparation.

This private prefill candidate retains BM256/BN128/BK2 and changes only the
eight-wave assignment from WM8/WN1 to WM4/WN2. The prior BM128 resident and
compact-LDS experiments changed tile size/storage; their failures remain
preserved. This candidate keeps the original grid, 48 KiB LDS, encoded Q8
weights, F16 operand rounding, each output's ordered K16 accumulation,
32-token convolution transpose and boundary-convolution launch.

Each lane now reads four weight and four activation fragments per K32 stage,
instead of two weight and eight activation fragments. Logical operand reads
fall from 640 to 512 bytes per lane/stage (20%). These are source-level LDS
requests, not measured DRAM traffic or a speed prediction. Local gfx1151
compilation uses 237 VGPR versus the retained 220, with zero spills/private
scratch and identical 49152-byte LDS. Higher register pressure can erase the
reuse benefit; only a completed GPU comparison can decide.

The existing SSM complete-operator fixture is reused with the new candidate
symbol. It covers N1024/1025/1057/2048/2049, all raw-output/live masks,
projection plus convolution/history, original guarded inputs, 72 complete
output pairs and 144 sampled independent FP64 checks. The timed 2048 case
rotates three Q8 matrices totaling 133693440 bytes and checks every actual
timed output. Two warmups and five measured samples alternate arms. Completed
host wall time is primary; zero HIP event durations remain invalid.

The binary is compiled locally and only the coordinated .157 runs it. Two
initial auxiliary build attempts fail because required compile definitions
and the crypto link library were missing; both actual exits and logs are
preserved. The corrected object and link commands pass. Production dispatch
and original model files are untouched. No new throughput or quality result
is established by compilation. A model run requires a component result that
justifies it, then the original input/capacity/chunk comparison.

The changed fixture/include pass the shared clang-format settings. The full
upstream formatting check exits1 on existing retained-provider files (first
reported in `src/core/sampling.cpp`); those1028 source files are unchanged.
Both format outputs and the actual exit are preserved with the compile logs.

[Source binding](../config/q2-ssm-wave-balance-source.json),
[static resources](../config/q2-ssm-wave-balance-static.json),
[generator](../tools/prepare-q2-ssm-wave-balance.py).
