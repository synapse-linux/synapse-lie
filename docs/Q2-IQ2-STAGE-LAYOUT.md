<!-- SPDX-License-Identifier: MIT -->
# IQ2 expert stage-pair layout probe

Halogen reports a routed-expert prefill kernel change that raised its own
131,072-token rate from 1,390 to 1,517 token/s. Its numerical engine source is
not public, so this probe is an independent LIE hypothesis, not a port of a
Halogen kernel. The retained LIE 130,925-token cold prefill is 1,310.874605
token/s (99.876067 s); the 1,500 target requires at most 87.283333 s. The
unchanged prompt, capacity 133760, 2048-token chunks and zero prefix hits are
the eventual model comparison contract.

The existing IQ2_XXS gate/up kernel processes two neighboring 32-value groups
per stage. In the retained format, every expert is 640 output rows by ten
66-byte superblocks per row. The two group loads for neighboring lanes sit
within one row, but consecutive output rows are 660 bytes apart. The probe
transposes the original encoded bytes into 40 stage-pair planes of 640 rows x
16 bytes, followed by ten 640-row x 2-byte scale planes. Each expert remains
422,400 bytes: 409,600 group bytes plus 12,800 scale bytes. It preserves every
quantized code, sign and scale byte. The two lane loads for 16 successive rows
now occupy one contiguous 256-byte stage segment. Whether this improves actual
DRAM transactions or occupancy is a GPU question; the static access pattern is
not a bandwidth measurement.

The private provider adds a single BN128 stage-layout body and leaves the
production selector unchanged. Its 164 retained device bodies have identical
instruction operands and resources after accounting for the added template
parameter. The new body uses 25,728 bytes of LDS, no private scratch and 153
next-free VGPR, versus 150 for the retained BN128 body. The C17 packer has a
byte-exact inverse reconstruction test over two experts and checks guards,
lengths and overlap. Focused CTest and ASan/UBSan pass locally and on .157;
the HIP fixture compiles for gfx1151 and completed there. It retains the
same 128/64-token route maps on both arms, rotates three synthetic weight banks,
checks whole-output bytes and guards, and records completed wall times. Its
measurements are operator evidence only, not a model PP/TG result.

The private variant's [source manifest](../config/q2-iq2-stage-layout-source.json),
[static report](../config/q2-iq2-stage-layout-static.json) and
[isolated patch](../experiments/q2-iq2-stage-layout.patch) bind the probe.
The coordinated .157 component now verifies 15 exact route maps and 51
guarded, byte-exact whole-output replays across three rotating weight sets.
It records 84 interleaved timing rows; all HIP event durations are invalid
zero, so the following medians use five completed host-wall samples per arm
after two warmup repetitions. Each timed iteration runs the full 2048-token
gate/up component over three weight rotations, divided by three for the table.

| Routing | Retained median µs | Stage layout median µs | Time change |
| --- | ---: | ---: | ---: |
| Saved layer 0 | 5203.547 | 5219.466 | +0.306% |
| Saved layer 3 | 4264.176 | 4295.085 | +0.725% |
| Saved layer 22 | 5506.948 | 5514.758 | +0.142% |
| Uniform 160 experts | 3614.167 | 3550.659 | −1.757% |
| Uniform 512 experts | 5485.242 | 5499.078 | +0.252% |
| Skewed 64 experts | 3774.746 | 3695.458 | −2.100% |

Paired per-repetition changes on saved layer 3 straddle zero; its paired
median is −0.443% despite the +0.725% ratio of arm medians. The saved routing
cases therefore provide no robust gain. The small synthetic gains do not
justify an original-model trial or a production dispatch change. The
[complete samples and validity checks](../config/q2-iq2-stage-layout-component-results.json)
are retained. The first admission ended without a GPU run because the staging
parser omitted the new variant from one allowlist; its exit 2 and release
remain preserved. The corrected second host gate passed 44/44 Debug and
44/44 ASan/UBSan tests. Its GPU component exited 0, all four artifacts were
collected, and the .157 window was released with KFD empty, original leases
free, unchanged model stats and no remote cleanup.

Full-model memory fit remains unverified. Holding
both old and transposed gate/up experts for every layer would add roughly
20.8 GB (19.3 GiB), so a successful component would still require a replacement or
on-demand layout design before any original-model trial. No whole-model PP/TG
speedup is claimed.

The saved 128K trace also has 4.510309 s total in the largest CPU API gaps
per chunk. Even the unrealistic assumption that all of this time disappears
would leave 95.365758 s, or about 1,373 token/s. This does not prove those
gaps are removable; it shows that a host-only lookahead cannot close the full
12.592734 s target gap by itself. The expert numerical path remains the more
consequential first test.
