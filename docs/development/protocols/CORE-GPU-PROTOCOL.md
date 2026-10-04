# First shared-core GPU regression protocol

Operator authorization: “ok facciao il test gpu per questa prima fase di conversione”.
Target: `.157`, original UD-Q4_K_XL, unchanged official Gufo `f783fedb` archives.
Baseline: `2ba01ed`, before core extraction. Candidate: `81c2f60` engine code,
plus input-manifest binding, explicit port selection and process telemetry in
supervisors. Builds are fresh Release binaries using identical compiler settings
and exactly the same previously verified upstream static archives. No Q2 patch,
model conversion, dependency install or device/power tuning participates.

## Declared experiment

- Baseline and candidate HTTP: identical 2042-token counting prompts, 64 output
  budget, one warmup and three measured repetitions, Chat JSON/SSE C1/C2 and
  Responses JSON/SSE C1. Existing in-flight cancellation, pressure and recovery
  checks follow each HTTP performance arm. HTTP uses loopback port 8000 during
  this private run; no persistent service is deployed.
- Candidate HTTP lifecycle arm additionally checks native tools, seeded sampling,
  Responses and reactive peer isolation under the existing checks.
- Baseline and candidate executor diagnostics: C1/C2/C4/C8, 2048 prompt tokens,
  context 4096, TG128, warmup 1 + measured 3. These bypass job lifecycle and
  control for numerical/provider or build drift.
- Candidate direct core: replay exactly the same physical 2048-token input at
  C1/C2/C4/C8, context 4096, TG128, warmup 1 + measured 3. Jobs return credit and
  preserve output witnesses. Compare IDs to the corresponding executor lane;
  keep client wall and per-job executor time in separate columns.
- Long-context control: baseline and candidate fresh executor at 8192/131072
  physical prompt tokens, context 262144, TG128, two measured repetitions and
  no discarded warmup. Replay those exact inputs through C1 core with the same
  context/output/chunk and repetition settings. These are fresh full-prefill
  experiments, not cached incremental prefill or cold-file measurements.

Every arm uses prefill chunk 2048 and greedy AR with thinking, cache reuse, MTP
and vision off. The same existing read-only model shard/stat inventory and
runtime/DSO identities are required. An arm's first model load is not included
in its prefill/decode timing. Cold filesystem state is not controlled.

## Interpretation and gates

Preserve every sample, actual output count/EOS, physical prompt hash, output IDs,
existing low-level frontier hashes, backend/build/source identity, exit code and
telemetry. Reject failed/incomplete arms; do not replace them or average partial
samples. Fresh matching executor lanes require equal input/output and frontier
hashes. HTTP comparisons require equal request identities, output, usage and
finish for corresponding cases. Core requires matched physical input/output;
it has no independent frontier/logit API yet, so token equality alone is not a
full numerical proof.

Report medians and observed min/max. Flag a >5% median throughput loss on matched
baseline/candidate executor points, or >5% total/first-text latency increase on
matched HTTP points, for investigation. Three short repetitions and two long
repetitions cannot prove a universal no-regression bound. Different timing
scopes (core total wall, executor TG, HTTP client latency) must not be divided
into a purported reactive speedup. Native batch scheduling and kernels are
unchanged. Record sampled OS thread counts; these are not CPU utilization or
GPU lane counts. No extra application thread pool is introduced.

## Admission, ownership and closure

Wait for the Q2 thread's explicit campaign release, then perform CPU fixture
verification on `.157`. Each GPU helper reacquires the four established leases
EX|NB in the documented order with in-lease memory/device/process and identity
checks. No entry into another campaign's gaps, background admission retry or
foreign process termination. The controller starts one arm at a time and stops
on runtime/evidence failure. Retain failed attempts in their own directories.
All source, binaries and evidence use persistent LIE-owned paths. On completion,
record child retirement, KFD observations, file/model stat preservation and free
unchanged leases before returning the window. Desktop/denied-FD observations
limit exclusivity claims. This is the first core-refactor GPU gate, not cache,
MTP/vision, 1M context or independent numerical-backend qualification.
