# Persistent Q8 mirrors — prepared experiment

The new Q2 candidate derives96 read-only F16 dense-weight mirrors once on the
GPU after upload. It preserves the native Q8 single K16 accumulation chain,
SSM/convolution and attention epilogues. Original encoded Q8 tensors remain
available for decode and narrow prefill. The measured raw-prefetch1505 parent
is unchanged and no qualified cohort is rebuilt or rerun.

The own C17 admission helper checks shape/type/expert count, overflow and a
6GiB auxiliary-memory quota before allocation. Expected additional resident
memory is5,348,130,816 bytes, including96 protected allocation tails. The model
owns every allocation and publishes only after conversion synchronization;
existing failure/destruction frees its own registered allocations.

The assembly audit compares157 original kernels after explicit default-argument
binding and removal of compiler-only comments/local function numbers. All
instructions, operands, relative block IDs, directives and resources match.
Four new kernels comprise conversion and three projection paths. The mirrors
remove54–56 static instructions from large projection kernels, but double
dense weight traffic and consume more memory. No performance gain is inferred.

Prior pinned Gufo staging/hipBLASLt experiments were negative. This experiment
instead amortizes conversion at upload and keeps original Q8 decode, native
WMMA order and epilogues. It does not introduce a new stream, reactive gain,
model-file conversion, CPU model forward or new external dependency.

The frozen plan binds48 fixture files and four manifests. New component checks
cover11,534,848 code/scale combinations,66 complete guarded output pairs and42
alternating projection timings with three weight rotations exceeding32MiB.
Both full format arrays are saved. Safe numeric/timing rejection still proceeds
to the original2048/tg128 full-model test; guard or missing-store failures stop.

Fixed comparisons remain Q21443.672867/TG25.09595499, saved best
1505.152258/TG25.15493858 and UD1685.777092/TG24.34174251. None is rerun.
Q4 and the full curve remain suspended. GPU admission/results are pending.
