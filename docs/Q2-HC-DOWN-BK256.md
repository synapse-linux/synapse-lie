<!-- SPDX-License-Identifier: MIT -->
# Original-F16 HC-down candidate

This prepared numerical port targets only M320/K10240 at 96–2048 token rows
on gfx1151. Its parent is the measured, model-exact Q8+row provider with
1451.924906 PP. It replaces that parent's hipBLASLt 7526 HC-down dispatch;
all other model kernels, original F16 weights and original F16 activations
remain unchanged. No F16-to-BF16 conversion, additional model copy, device
allocation, stream or context mechanism is introduced.

The native vector loaders, BK256 staging and direct accumulator stores derive
from the public MIT `mmb_hcd_kernel` and fragment helper in
[GSQHalo.cpp at 5fc881b](https://github.com/Aristo94/GSQHalo.cpp/blob/5fc881b114c1ea130f5df6a30a98be2f8d397de6/ggml/src/ggml-cuda/mmb.cu).
The imported copyright and full MIT text are retained in the numerical include
and [license](../third_party/gsqhalo/LICENSE). This adaptation uses the F16
WMMA intrinsic, two FP32 K16 accumulation chains, one LDS buffer and a
64-output-row by 32-token tile. Original half bits are loaded directly.
Ragged token loads clamp to the final valid row; stores remain bounds checked.

Two persistent source candidates are prepared and locally compiled with the
original Gufo numerical flags. These are compiler observations, not GPU tests:

| Candidate | K16 unroll | VGPRs | Fixed private bytes / thread | LDS bytes | Wave size |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial port | 16 | 256 | 500 | 50688 | 32 |
| Bounded sibling | 2 | 138 | 0 | 50688 | 32 |

The sibling changes only the K16 loop unroll pragma. It keeps all source
arithmetic and the same two accumulation chains; generated floating-point
equivalence still needs a real GPU check. The first version and its spilled
device object are retained. The initial metadata reader failed because the
compiler produces an offload bundle; unbundling the gfx1151 member corrects
inspection without recompiling or replacing that failed command evidence.

Each complete provider has 1023 verified files. The initial candidate changes
three dispatch/declaration/include files and adds one numerical include against
the 1022-file measured parent. The sibling changes only that include against
the initial candidate. Both have reconstructible patches and full source
inventories. Neither is wired into the default backend or remote runner.

Runtime work remains: compare every output and guards against the unchanged
library route, independently check FP64 dot products on ordinary/tiny/ragged
inputs, and measure the complete norm/HC-down cycle with 16 original-F16
weight matrices rotating 100 MiB beyond MALL. Keep 2048 as the diagnostic
point, retaining 96/97/129 checks for launch tails. Preserve timing even when
a numerical verdict fails. Then run only the new fixed 2048 model candidate
against the saved Q2/UD input and measurements. No qualified inference control
rerun or context curve is scheduled by this preparation.

No GPU run, numerical acceptance, performance gain or current model promotion
is claimed. Fresh `.157` admission remains required before remote GPU build
or execution. The fixed 1443.672867 Q2 /1685.777092 UD comparator is unchanged.

[Initial source](../config/q2-hc-down-bk256-source.json),
[initial device object](../config/q2-hc-down-bk256-object-results.json),
[bounded source](../config/q2-hc-down-bk256-bounded-source.json),
[bounded device object](../config/q2-hc-down-bk256-bounded-object-results.json).

The shared upstream formatting check was run with the installed ROCm clang-format and exits 1 for both candidates, including inherited provider formatting and the new declaration alignment. No source is changed by that check. Formatting correction remains pending; this is separate from the successful numerical-target compilation and pending GPU qualification.

## Runtime qualification prepared

Two separate runtime source trees now format the new declaration, dispatch
and numerical include, preserving all noncomment source tokens against each
retained draft. The original drafts and objects remain unchanged. Both new
providers retain 1023-file inventories. The upstream formatting check still
reports 74 inherited violations, with no new HC API alignment complaint;
those formatting exits remain separate from numerical/GPU evidence.

The component target links a test-only copy of the exact measured library
recipe. Only its class name, include guard and header path are renamed, with
the Gufo license retained. Control algorithm7526, original row-major F16
operands, descriptor geometry and zero-workspace policy stay unchanged.
Both arms use the same paired norm producer. Five shapes/patterns and both
ordinary/MoE inputs retain full replay, guards and original FP64 limits.
Strict numerical rejection does not skip timing: 56 samples cover projection
and complete-cycle scopes with two warmups and five measured repetitions,
alternating arm order and rotating 100 MiB of weights.

The launcher permits only matched new component/counting modes. All 77 local
guard tests pass; the new fixture/control pass HIP syntax compilation. The
`.157` host capsule verifies 16 bound files, with 23/23 Debug and 23/23
ASan/UBSan CTest passes. These CPU checks do not execute the HIP fixture.
The frozen window permits two new components, then at most one new model:
select the faster complete-cycle candidate and retain any numerical rejection.
Use the unchanged original2048 input/timers and saved Q2/UD measurements;
no qualified inference control or full context curve is rerun.

[Runtime source identities](../config/q2-hc-bk256-run-source.json),
[frozen plan](../config/q2-hc-bk256-run-plan.json),
[host receipt](../config/q2-hc-bk256-run-host-results.json).
