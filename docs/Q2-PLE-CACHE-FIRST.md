<!-- SPDX-License-Identifier: MIT -->
# Consume existing PLE hits before publishing misses

This isolated candidate addresses a possible loss of already resident rows
within a large gather. It starts from the measured canonical Q2 provider,
not the IQ2 packed-sign candidate. No performance gain is established yet.
The acceptance target remains both PP and TG across the complete canonical
0–128K HTTP curve, with unchanged request histories and numerical gates.

The current `NgramTable::StartRead` deduplicates rows and sorts large gathers.
Workers then check the cache and read misses concurrently. A low-numbered
miss can replace a direct-mapped cache entry before a later job consumes its
already resident row. Small gathers already consume hits before publication.

The candidate applies that existing hit pass to every gather, then sorts and
publishes only misses. It removes the worker's second cache lookup. This is
safe because jobs have unique row IDs, `StartRead` holds the queue mutex,
and a new gather is rejected until `WaitRead` has observed all previous jobs
complete. Different missing rows cannot populate each other's row identity.
The change preserves row encoding, dequantization, hash, capacity, worker
count and output/duplicate ordering. It changes only `ngram.cpp`; the other
1019 provider files remain byte-identical to the canonical Q2 baseline.

The tradeoff is explicit: cached-row lookup and conversion happen on the
calling thread before GPU work can be enqueued. Their cost could outweigh
saved reads. Fewer residual misses can also select the existing small-gather
queue policy. This does not reduce the storage cost of genuinely new rows.
The previous profile's approximately 3% Q2 row hit rate is not evidence of
the candidate's potential gain, since it does not record the evicted hits.

`tools/prepare-q2-ple-cache-first.py` verifies the complete parent inventory,
refuses to overwrite an existing candidate, and writes the minimal source
patch and full manifest. Sources remain under durable `.deps/` storage.
The output is `.deps/gufo-q2-curve-ple-cache-first` and its manifest is
`config/q2-ple-cache-first-source.json`.

The new host fixture uses private unlinked sparse files, 160-column BF16 and
IQ4_NL rows, independent expected values, guards and duplicate output slots.
It primes 128 high rows, then mixes them with 1024 cold rows whose early IDs
alias the warm entries at both existing capacities. Linker-wrapped `pread`
counts actual reads without changing the table implementation. The candidate
must perform no reads for the initially resident rows; a second wholly warm
large gather must perform no reads at all. `--control` retains the original
provider's reread count without imposing the candidate's new ordering guarantee.
The existing upstream n-gram suite covers failure/recovery, invalid requests,
unlinked/replaced backing paths, empty reads and destructor completion.

The host wiring is now applied, after the independent IQ2 campaign completed
and released its window. `experiments/q2-ple-cache-first-host.patch` retains
the earlier preparation recipe; the current implementation additionally stages
the complete unchanged parent as `ple-control-source`. Both 1020-file inventories
are verified before staging, with exactly one differing file. The two fixtures
link their own reader and identical quantization support. `ple-cache-first-cpu`
rejects alternate sources and GPU rebuilds, masks GPU devices and accesses no
original model. It runs **21 CTest checks in Debug and ASan/UBSan**.

The collision fixture now assigns different values to aliased high/low rows,
so a wrong cache-key match cannot pass simply because their contents coincide.
Verbose CTest preserves the actual candidate/control read counters. The analyzer
checks both source inventories, collected artifact hashes, all six command exits,
both complete suites and the four BF16/IQ4 observations per configuration.
Missing pairs, false exactness and inconsistent counters are rejected. A control
with zero rereads is retained as failure to reproduce the proposed mechanism,
not converted into a speedup. Report-parser checks run inside `q2_remote`.

[Local preparation evidence](../config/q2-ple-cache-first-host-preparation.json)
verifies 2040 provider files, both C++ syntax checks and five Python AST checks.
These are source checks, separate from the subsequent runtime evidence below.
No canonical model arm for this candidate has been admitted or implemented.

## Paired host results on .157 — 2026-10-04

The admitted `q2-ple-wmma-host-r1` cohort passes **21/21 Debug and 21/21
ASan/UBSan**, with all six command exits zero and seven collected artifacts
hash-verified. Both complete 1020-file provider inventories match their pins.
The unchanged control reproduces collision-induced rereads in all four cases:

| Configuration | Row format | Original preads | Candidate preads | Original resident-row rereads | Candidate resident-row rereads |
| --- | --- | ---: | ---: | ---: | ---: |
| Debug | BF16 | 1144 | 1024 | 120 | 0 |
| Debug | IQ4_NL | 1152 | 1024 | 128 | 0 |
| ASan/UBSan | BF16 | 1152 | 1024 | 128 | 0 |
| ASan/UBSan | IQ4_NL | 1152 | 1024 | 128 | 0 |

Every row matches the independent oracle, guards remain intact, and the wholly
warm repeat issues no preads. Control variation reflects concurrent cache
replacement; the candidate consumes every initially resident row before misses
can replace it. These are actual read counts from deliberately colliding private
fixtures. No fixture latency, original-model hit rate, throughput gain or parity
is inferred. The [verified result](../config/q2-ple-cache-first-host-results.json)
preserves both configurations and their counts.

Next, measure the same canonical Q2 curve with a distinct provider identity.
Preserve all
raw histories, preparation costs, PP/TG counts and durations. A reduced fixture
read count alone is not a full-model speedup or a parity result.

## Canonical composition with ordered decode

`tools/prepare-q2-ple-ordered.py` composes the exact host-qualified reader with
the measured ordered IQ2 decode provider. It verifies both complete source
inventories and their canonical parent. Only `ngram.cpp` differs from ordered
Q2; the other 1019 files, including all numerical kernels, are identical. The
[manifest](../config/q2-ple-ordered-source.json) records both parents and the
host result. The slower WMMA sign-load experiment is absent.

The isolated `q2-curve-ple-cache-first` mode requires its matching source and
full MMQ rebuild. The build and HTTP client use a distinct provider identity,
rejected by the unchanged-control and diagnostic-profile selectors. Context,
prompt recipe, sampling, chunk size, cache capacity and timing boundaries remain
identical to the measured canonical curves. A new host cohort qualifies these
selection checks before any model run.

The [bounded plan](../config/q2-ple-ordered-plan.json) measures ordered Q2,
ordered Q2 plus PLE, unchanged ordered Q2 again, then pristine UD, all at
0/4K/8K/12K/16K/32K/64K/128K. The second control is mandatory for this comparison.
Analysis validates all complete request/output histories and source compositions;
plots and CSV retain both controls and every PP/TG value. Prior canonical results
reanalyze identically after adding this separate provider. Local configuration
verifies the new build identity and complete build graph without executing a
model. Fresh `.157` admission at 03:11:36 UTC admits the host cohort and these
four sequential arms. No canonical result is claimed before their completion.
