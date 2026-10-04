# C17 RAM prefix state qualification

The user authorized this roadmap increment, required reusable state/cache logic
in the shared engine, and clarified that RAM is on by default and only SSD is
off. Q2 returned the coordinated `.157` window at 2026-10-02 03:14:56.579 UTC.
CPU CTest and ASan/UBSan run on `.157` before GPU admission. Local activity is
editing, compile/link and offline analysis only.

The candidate uses the independently acquired official Gufo pin `f783fedb`,
with the three exact friend-access declarations in two headers recorded in
`adapters/gufo-state/access-edits.json`. All selected archives are rebuilt in a
separate source/build tree. No numerical source, pristine archive, Q2 patch,
model weights or DS4 state is changed. C17 owns typed state layout, allocation,
compatibility, retention and replacement; the adapter binds fields/transfers.

## Predeclared arms and acceptance

1. Candidate cache-off executor `fresh`: 8192 and 131072 physical tokens,
   context 262144, chunk 2048, TG128, two repetitions. Compare exact prompt,
   output IDs and PP/TG float frontier hashes against the sealed pristine
   candidate from `core-gpu-r2/candidate-fresh`. Timing against historical data
   is descriptive, not a concurrent performance regression experiment.
2. `--suite state`: exact 512-token and 8192-token checkpoints, an 8192-token
   input restored from a 4096-token checkpoint, and a 131072-token checkpoint.
   Every arm uses context 262144, chunk 2048 and 16 decode steps, honoring EOS.
   Three fresh/restored pairs (greedy, seed-123 sampling, independent greedy)
   require bitwise equality of all logits after prefill and every decode step,
   output IDs, stop and positions. Fresh samplers are configured independently.
   Any difference rejects the state implementation. Save, restore, tail PP and
   full recomputation timings remain separate. This is same-provider restore
   correctness, not independent model numerical qualification.
3. Direct shared core: 8192 and 131072-token inputs, C1, context 262144, TG128,
   one warmup plus two measured repetitions, explicit RAM off versus default
   RAM on (4 GiB). Additional C2/C4/C8 pairs use 2048-token inputs and context
   4096, one warmup and three measured repetitions. Require output IDs equal to
   fresh executor witnesses; no expected cache speedup threshold. Preserve
   cold capture and all warm samples, hits, newly processed PP tokens, copy
   timings, total wall, TTFT, retained bytes and sampled process threads/RSS.
4. HTTP on port 8000: default RAM, repeated ordinary Chat JSON/SSE smoke cases.
   Require identical output/finish and total input/output usage; cached-token
   details must reflect reuse and executed PP plus reused tokens must equal
   prompt length. Check management's RAM-on/SSD-off budget and counters.
   This is a private test listener, not deployment or a new Pi qualification.

RAM hits avoid work; a ratio of prompt length to restore time is not fresh PP
throughput. Full hits report zero executed PP and no PP tokens/s. Caches retain
the largest complete chunk frontier per request (or exact short prompts).
Unaligned checkpoints may serve exact hits only, preserving numerical chunk
partition for extensions. A longer recurrent state cannot be truncated.

## Ownership and closure

Each sequential arm reacquires the four established leases EX|NB in order and
checks their recorded device/inode identities, current KFD/DRM observations,
model read-only stat identities, source/binary/DSO hashes and memory admission.
The ordinary trunk-size estimate includes an additional 4 GiB available-memory
reserve for cache-enabled arms; this is not a total allocation/fit guarantee.
No automatic admission retry or replacement of failed evidence. Stop on a
failed arm, retain it, repair only established defects before a separately
declared retry. Retire only owned children. Verify process identities, KFD,
unchanged/free leases and collected SHA-256 before returning the window.

No SSD I/O, exact-generation resume, MTP, vision, 1M-context, kernel overlap,
extra engine threads, package installation, remote GPU build or power tuning
is included. CPU fixtures alone do not qualify device failures or inference.
