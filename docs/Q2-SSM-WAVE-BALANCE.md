<!-- SPDX-License-Identifier: MIT -->
# SSM operand reuse at unchanged tile size

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

[Source binding](../config/q2-ssm-wave-balance-source.json),
[static resources](../config/q2-ssm-wave-balance-static.json),
[generator](../tools/prepare-q2-ssm-wave-balance.py).
