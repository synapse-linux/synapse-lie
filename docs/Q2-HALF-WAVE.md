<!-- SPDX-License-Identifier: MIT -->
# Q2 paired half-wave decoding — static preparation

The [LDS weight-staging candidate](Q2-STAGED-WEIGHTS.md) is exact but 4.94%
slower on the shaped down projection. The next hypothesis removes duplicate
decoding without expanding LDS. These sources are prepared locally while core
owns the next `.157` window; **no GPU correctness or speedup is established**.

## Mechanism

The existing packed-Q2 kernel makes paired lanes in the two 16-lane halves
decode the same 32 weights. Each pair needs identical F16 weight fragments
for its WMMA instructions. The candidate assigns one K16 weight half to each
half-wave, decodes it with the original F32 affine/FMA and F16 rounding, then
exchanges the already-rounded 32-bit pairs with the corresponding peer lane.
Both lanes reconstruct the original low/high fragments in the original order.

The code/affine/activation LDS layout and size, compensated activation planes,
WMMA accumulation order and residual correction remain unchanged. The original
Q2 bytes are consumed directly; there is no persistent decoded-weight cache.
Only `kQ2 && kPacked` selects the new code. This is independent of reactive PLE,
the larger encoded-row cache and the rejected decoded-weight staging buffer.

Two isolated exchange primitives are prepared:

- `half-wave`: HIP XOR shuffle, lowered by the installed compiler to sixteen
  static `ds_bpermute_b32` instructions in each affected specialization.
- `half-wave-permlane`: explicit `__builtin_amdgcn_permlanex16` with identity
  lane selectors inside the opposite 16-lane row; lowered to sixteen static
  `v_permlanex16_b32` instructions and no `ds_bpermute_b32`.

LLVM documents the latter's cross-row gather and scalar selectors in its
[AMDGPU intrinsic reference](https://llvm.org/docs/AMDGPUUsage.html), with the
[Clang builtin signature](https://clang.llvm.org/docs/AMDGPUBuiltinReference.html#builtin-amdgcn-permlanex16).
These specify the operation, not its superiority. The installed rocPRIM
`warp_reduce_dpp.hpp` explicitly notes that permlanex16 can be slower in some
cases; both numerical replay and actual timings are required before selection.
No rocPRIM or external project code is copied into the candidate.

## Static resource comparison

| Token tile | Reference VGPRs | XOR-shuffle VGPRs | Per-row-permute VGPRs | LDS, all three | Private bytes, all three |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16 | 112 | 119 | 115 | 16,640 B | 0 |
| 48 | 144 | 146 | 145 | 24,832 B | 0 |
| 64 | 169 | 169 | 169 | 28,928 B | 0 |

Both candidates halve the static mixed-FMA-to-half count from 64 to 32.
WMMA instruction counts remain 8/24/32. The exchange instructions and selects
are additional work; static counts do not establish throughput or occupancy.
For comparison, rejected decoded-weight staging uses 169 VGPRs and 28,928 B
LDS at the main tile48 shape.

Device-only gfx1151 compilation and changed-file formatting pass for both
candidates. Their patches reconstruct all 1019 files byte-for-byte. The shared
formatter retains the already-recorded failures in two unchanged upstream test
files; they are not edited here. Actual command exits, assembly hashes and
compiler resource records are in
[shuffle static checks](../config/q2-half-wave-static.json) and
[permute static checks](../config/q2-half-wave-permlane-static.json).

## Runtime gates

After core returns the window, validate the updated source-admission guards
on `.157` first. They have syntax checks only since the new variant names were
added; the preceding runtime guard pass covered the staging campaign.
Each GPU arm then requires fresh four-lease admission.
Run the existing packed operator suite and the same shaped benchmark, retaining
all independent numerical checks and complete-buffer replay. The unchanged
raw-input path remains the control. Record performance even when finite
numerical errors occur, but do not relabel a failed check or relax tolerances.
Only a measured component benefit warrants the matched complete pp2048/tg128
Q2 baseline/candidate comparison and fresh UD control. Model quality, long
context support and the Q2/UD parity requirement remain open.

Generate either source into a fresh persistent directory using
`tools/prepare-q2-half-wave.py --exchange shuffle` or `--exchange permlane`.
The [shuffle source receipt](../config/q2-half-wave-source.json) and
[permute source receipt](../config/q2-half-wave-permlane-source.json) pin the
measured official-Gufo-derived base and each patch. Neither source replaces
the retained measured checkpoint or qualified runtime.

The fixed remote component modes now accept `--source-variant half-wave` and
`--source-variant half-wave-permlane` for `packed-operators` and `packed-bench`.
Both remain excluded from UD controls and require an explicit complete MMQ
rebuild for any eventual `q2-bench2k` model comparison. No launch is scheduled
by source preparation.
