# Extended Q2 operator checks — two arithmetic corrections, 88 controls pass

On 2026-10-01 the operator renewed the GPU window. All GPU attempts below used
four existing EX|NB leases, fresh in-lease preflight, the private LIE supervisor,
fixed order/tolerance, recorded exits and retirement. There was **no model
payload access, model forward, benchmark, remote build, installation or DS4
change**. Builds were serial and GPU-masked on `.155`.

**24 extended cases and 64 original grid-zero controls pass with the corrected
private kernels. This is not full-format/model qualification.** The source
receipt field in three run manifests has a recorded metadata defect, described
below; it must not be represented as a clean manifest-consistency pass.

## RED evidence and scoped corrections

1. `q2-operator-extended-red-r1` used a new test driver linked against the sealed
   **r5 MMQ archive**, without rebuilding/modifying that archive. The first IQ2
   vector case failed: actual `0.38671875`, reference `0.3875732421875`, absolute
   error `0.0008544921875`. The independent scalar golden is `3175 / 8192`.
   `vec_dot_iq2_xxs_q8_1` performed integer `sumi * ls / 8`, losing fractional
   eighths for grid magnitudes 25/43. The earlier grid-zero tests could not expose
   this. The private overlay now converts the integer product to float and
   multiplies by `0.125f`. Its maximum integer magnitude is below `2^24`.
2. After that correction, `q2-operator-extended-green-r2` passed five cases, then
   failed Q2 tiled case 5 at the real 2560-output shape and non-power-of-two
   weight scales. First mismatch: `0.7469024062156677` versus
   `0.7471690773963928`. Offline reconstruction of half-rounded scale/minimum
   products gives `0.7469023838639259`, explaining the GPU result within
   `2.2351741790771484e-8`. Across that retained case, **3714 outputs** fail the
   unchanged tolerance; largest error `0.000522911548614502`.
   Q2 MMA loaders now retain `d*scale` and `dmin*minimum` as FP32 pairs, not half
   products. Sixteen float2 pairs fit the **existing 32-word scale region**;
   row pitch, shared-memory allocation and bounds remain unchanged, with static
   assertions. The raw and SoA loaders and MMA consumer agree on this layout.
   **SoA and non-gfx1151 execution are not tested**; the DP4A branch is unchanged.

These changes are confined to the private `vecdotq.hpp` and `mmq.hpp` overlay.
No pristine file/archive, production provider, host recipe, public LIE ABI or
weight upload guard was changed. Existing licenses/notices are retained.
There is no performance claim: even unchanged allocation size does not imply
unchanged bandwidth, occupancy, instruction cost or throughput.

All failures remain failures in their original records. Each subsequent GPU
attempt used corrected source, a new binary/run identity and new admission;
there was no automatic retry/fallback or tolerance relaxation.

## Fixed extended coverage

`q2-operator-probe --list-extended` emits the 24 ordered case declarations without
GPU work. `--gpu-extended NEW-RAW-DIR` runs them only under an external admitted
supervisor. `--gpu-synthetic` retains the original 64 grid-zero controls.

- Independently written scalar decode/dot expressions; the licensed **256-entry
  IQ2 codebook** is extracted from the independently acquired pinned Gufo MMQ
  `ggml-common.h`, SHA256
  `3a6ac624e0c93e18168e31fd6c2b0f418dc6528723e2f489d6b272393bd6555b`.
  This shares canonical table data, not the GPU dot implementation, and is not a
  second independent model engine. CPU goldens check fractional scale, sign
  parity, Q2 affine values and codebook coverage.
- All 256 IQ2 entries are represented in the mixed fixtures; weight half
  mantissas vary. Activations remain deliberately exactly Q8-quantizable:
  the original integer/128 pattern plus an isolated 127-valued impulse.
  Arbitrary activation distributions, all field combinations and subnormal/
  extreme scale values are **not** qualified.
- Production output widths **IQ2 640 / Q2 2560**, tightly packed source widths
  **2560 / 640**, physical Q2 weight width **768**, quantized padding to 1024.
- Requested tiled widths **16/32/48/64/80**, vector and grouped/fused gate/up,
  zero rows, duplicate/different/inactive routes and output guards. Full width-80
  tiles occur in the capacity cases; this is not every shape/width cross-product.
- Last expert **511** at real output widths; 512 routing bins and maximum
  **2048 × 32 = 65536** assignments at small output width 3. Flattened Q2 down
  reaches 65536 expert rows. These are separate cases, not a full-capacity model.
- The workspace always has 512 routing bins. Case `experts` describes the
  allocated weight fixture/ID range; other bins are empty. Last-expert and
  capacity cases allocate the full 512-expert weight fixture.
- One prepared workspace across the suite, dirty initialization and smaller
  calls after maximum-capacity work without reset. This checks operator storage
  reuse, **not Executor/RowScratch integration or model reload**.

Tolerance remains `0.0002 + 0.00004 * abs(reference)`. Every call waits for
completed stream work before comparison. There are no performance samples.

## Results and raw evidence

| Run | Result |
| --- | --- |
| `q2-operator-extended-red-r1` | First IQ2 vector mismatch, child/supervisor 1; 0 completed cases |
| `q2-operator-extended-green-r1` | Local helper-test name typo, exit 1 **before staging/GPU**; retained |
| `q2-operator-extended-green-r2` | IQ2 correction passes; Q2 MMA mismatch, child/supervisor 1; 5 completed cases |
| `q2-operator-extended-green-r3` | **24/24 PASS**, 15 IQ2 + 9 Q2, child/supervisor 0 |
| `q2-operator-legacy-green-r1` | **64/64 PASS** on corrected kernels, child/supervisor 0; not original-UD model regression |

The final two runs use `build/q2-extended-linked-r2/hip/q2-operator-probe`, SHA256
`fd402ffef6ce25b68f7ca99c3d33f8209d1bc374ab7106a336d3a83b706ccbbe`.
The extended supervisor ran **08:07:26.081861–08:07:34.989080 UTC**, legacy controls
**08:09:43.394055–08:09:45.979849 UTC**. These intervals include preflight, CPU
reference work and cleanup: **not kernel timings or PP/TG measurements**.

Extended raw evidence contains **70 F32 arrays**, including expected values and
actual outputs with 64-element leading/trailing canaries. They are native
little-endian IEEE F32 on the recorded x86-64 target. The offline audit rechecks
**1,725,239 output values**, zero mismatches, maximum absolute error
**3.0517578125e-5**. It also confirms both prior numerical failures from their
raw arrays. The legacy run retains case records, not full output arrays; maximum
reported absolute error is **4.76837158e-7**. No failed sample was discarded.

All four GPU runs have hash-verified collections, start/end register entries,
unchanged binary/DSO observations and retired process identities. The final
postflight in `evidence/q2-extended-closure-r1/` finds empty KFD and four unchanged
lease identities without holders at **08:14:28.029966 UTC**. Desktop clients and denied FD observations
still limit exclusivity claims. No listener/waiter/lease remains; the completed
window is not standing authorization.

### Manifest metadata defect — retained, not silently repaired

The manifests for extended `green-r2`, `green-r3` and legacy `green-r1` inherited
an old **`source_receipt_sha256`** field from r5. The supervisor did not validate
that field. The actual binary hashes, build identities and new HIP recipe hashes
are correct and independently bound to the immutable build/source receipts by
`source-binding-addendum.json` in each evidence directory. Original manifests
are unchanged. The audit explicitly reports
`Q2_EXTENDED_AND_LEGACY_NUMERICS_PASS_WITH_RECORDED_MANIFEST_METADATA_DEFECT_NOT_MODEL_QUALIFICATION`.
Audit exit 0 means these checks and the disclosed defect were accounted for,
**not** that the stale field was valid. Future manifests must derive this field
from the selected build, not clone it. No GPU rerun was used to conceal it.

## Build/CPU evidence and remaining gates

`q2-extended-probe-red-r1` retains a generated-header missing-cstdint compile
failure; r2 fixes the self-contained header and links against immutable r5.
`q2-extended-linked-r1/r2` are fresh full private builds with shared formatting,
HIP linkage, masked refusal and scalar checks. `q2-extended-cpu-r1/r2` pass the
17 default compiler/sanitizer/header suites; r2 includes **11** HIP source/tool
checks, including codebook hash/golden/exclusive-output refusal checks. Earlier
receipts remain historical. `tools/build-q2-probe.py` provides an editing-host-only
driver rebuild against a hash-checked sealed private MMQ archive; identity guards
do not depend on Python assertions. `q2-extended-driver-closure-r1` checks that
hardened helper and reproduces the same generated codebook header; its new driver
binary was **CPU-tested only**, not substituted for the GPU-measured r2 binary.
Neither build helper launches GPU/model work.

Still required: arbitrary activation/quantization oracles, broader field/shape
interactions, Executor/RowScratch lifetime/failure integration, matched original
UD regression, role-aware PLE/weights/staging/workspace/context memory admission,
an independent within-format model reference, and real Q2 finite-frontier/model
qualification. Only then run fresh PP512/2048/8192 + TG≤128 and the separate
updated-worker HTTP lane. Q4 and cache work remain later. **Both runtime linkage
and model upload refusals stay closed.**
