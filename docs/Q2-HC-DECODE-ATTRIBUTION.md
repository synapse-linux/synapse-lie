<!-- SPDX-License-Identifier: MIT -->
# Decode cost after separating HC up from generic Q8 projections

The retained Q2/UD trace exposes two HC costs in scalar decode. Q2 HC down
costs 1.296157 ms/token more than UD; HC up plus its input preparation costs
1.002879 ms/token more. Q2 routed experts are already faster in this trace.
This reanalysis changes which operations deserve attention, not the measured
throughput or the original UD target.

The original profiler grouped Q2's specialized `HcUpF16VecKernel` under `other`,
while UD's same operation shared the generic `mul_mat_vec_q8` symbol with
ordinary dense projections. A symbol-only comparison cannot separate them.
The new analyzer uses the actual frozen executor order:

```text
HC down → SiLU/scale → [UD input quantization] → HC up → HC mix/injection
```

It verifies every one of the 1455 HC blocks in each trace, their same-stream
ordering, complete phase boundaries and original database/source-capsule
hashes. UD has 1455 Q8 up calls, all preceded by input quantization; Q2 has
1455 specialized F16 up calls. There is no inference from the net difference
in generic kernel call counts. All 23,594 Q2 and 26,144 UD decode dispatches
remain accounted for exactly once.

## Measured stage totals

These are the existing diagnostic pp2048/tg16 traces, with **15 completed
decode calls**, rather than a new runtime test. Values below divide the kernel
sums by those fifteen calls.

| Stage | Q2 ms/token | UD ms/token | Q2 minus UD |
|---|---:|---:|---:|
| HC down | 2.979207 | 1.683050 | +1.296157 |
| HC up projection | 2.915551 | 1.792555 | +1.122996 |
| HC up input quantization | 0 | 0.120117 | -0.120117 |
| HC mix/injection epilogue | 1.005154 | 1.010516 | -0.005362 |
| Routed expert gate/up | 4.260255 | 4.664778 | -0.404523 |
| Routed expert down | 2.346478 | 3.170263 | -0.823785 |

The net whole-phase kernel difference remains **8.411433 ms**, or
**0.560762 ms/token**. Positive HC differences exceed that net difference
because other Q2 stages save time. The remaining Q8 dense group changes from
the previous aggregate -24.383135 ms to +2.505197 ms after moving UD's HC-up
calls into their own group. The generic `other` group changes from +36.200786
to -7.562748 ms. No kernel duration or total is changed by this attribution.

The current unprofiled original-C17 2042-token comparison is separately
25.514 Q2 versus 26.061 UD, a 0.822636 ms/token latency difference. Its prompt,
output length, benchmark path and cohort differ from this diagnostic trace.
Do not subtract these trace costs from that result to claim a new rate or
assign the remainder to host overhead.

## Consequence for the next decode experiment

The measured HC down reduction saved only 0.3345% component time despite
32 fewer static instructions. Both HC up and down still read the original
6,553,600-byte F16 matrix per call. UD's corresponding Q8 weights have a
different stored representation and smaller payload. These are not otherwise
identical dot products, and their entire timing difference is not necessarily
recoverable by instruction scheduling.

HC up is followed by a roughly 1.0 ms/token mix/injection epilogue across
97 calls. A useful next hypothesis is to fuse scalar up and mixing while
retaining the original injection partial layout and ordered reduction.
The native up already performs aligned vector loads, so merely adding vector
types is not a new mechanism. A fusion must preserve the four-component FMA
order, descending wave sum, sigmoid/mixing sequence, optional injection,
buffer lifetimes and the original ten injection partials. Block layout,
register pressure and bandwidth can erase the saved launch/materialization.
The epilogue's measured cost is not a promised saving.

One concrete layout to test is eight waves per block: two hidden positions
times four streams, retaining one original wave reduction per projected row.
Eight shared gate values then feed the two ordered mixing operations. One
selected block per 256 hidden positions can independently compute the original
256-element injection slice, retaining its eight wave partials and the ten
existing chunks. This requires no grid synchronization or new persistent
buffer. It changes row scheduling and register demand; matching every mixed
output and injection partial, plus whole-cycle timing with rotating production
weights, is required before any speed claim. This is a design hypothesis only.

No fusion has been implemented or promoted by this report. The ragged HC
prefill comparison is complete and its GPU window is released. The
[canonical whole-curve comparison](Q2-CURVE-PARITY.md) now takes priority;
this short-context attribution is a hypothesis, not a reason to replace it.
Any scalar fusion needs its own same-process original control, independent
operators, complete output comparisons and whole-cycle timing before a fresh
original-C17 Q2/UD comparison. Existing numerical/operator/KL rejection remains.

## Reproduction and retained evidence

```sh
python3 tools/analyze-q2-hc-decode-attribution.py
```

- [Analyzer](../tools/analyze-q2-hc-decode-attribution.py)
- [Complete dispatch identities, attribution and source hashes](../config/q2-hc-decode-attribution.json)
- [All group totals as CSV](figures/q2-hc-decode-attribution.csv)
- [Original profile and unchanged phase totals](Q2-SCALED-LIBRARY-PROFILE.md)
- [Current absolute Q2/UD baseline](Q2-DECODE-BASELINE.md)

Only existing first-party evidence and independently pinned Gufo source are
read. There is no model-file access, source import from a sibling workspace,
GPU run, ABI/state change or new numerical acceptance claim. Goal parity
remains unmet.
