<!-- SPDX-License-Identifier: MIT -->
# Development progress

The [current roadmap](BACKEND.md#current-roadmap--2026-10-05-utc) records completed
r11 OpenAI AR/MTP controls and six open tasks: Terminal Bench, full 1M acceptance, requested
benchmark methods, DS4 directional steering and sampling temperatures, and the
identified C17 sampling extractions. Assigned platform/weight-format work and
undefined future features are excluded. Earlier platform and long-context
matrices remain explicitly historical; raw receipts and failures are unchanged.

## C17 string and Unicode-DFA runtime; host parity — 2026-10-05 UTC

Root continues task 7 from `4aa7478` in the persistent context/OpenAI worktree.
`lie/grammar_regex.h` and `src/grammar_regex.c` own copied scalar classes/raw DFA
tables, unique successor/predecessor construction, shortest accepting distances,
edge pruning, range lookup, bounded length reachability and Brent cycle skipping.
`lie/grammar_string.h` and `src/grammar_string.c` own UTF8, JSON escapes,
surrogate pairs, pending ranges, decoded lengths, completion, copied mask-key
canonicalization and the 32-byte formatting-whitespace predicate.

Eleven exact regex and three string edits route the pinned provider through
storage/JSON/error glue under the existing default-ON/OFF selection. After C
sealing the adapter retires temporary C++ state/alphabet vectors. The strict
receipt binds 21 owned source/header/glue files and both new recipes. The direct
legacy reference now compiles regex methods too; its original-weight build/link
and continuation remain unqualified. Regex derivative/schema compilation and
vocabulary trie/transition/cache still need extraction in the same grammar task.

Independent C checks cover 5,832 automata, 507,384 finite-language queries and
all 1,112,064 scalar codepoints in patterned/scalar modes with literal and escaped
spellings: 4,448,256 full quoted-string checks. Constructor/query/work/capacity
faults, malformed phases/shift states, copied tables and mask-key isolation pass.
Complete pristine/ON/OFF witnesses match 14 admitted string policies, 2,018 byte
steps, 10,090 canonical keys, 423,424 byte branches and 756 DFA query pairs.
All seven prior probability/history/byte/numeric witnesses keep their exact hashes.
Final 21 Debug, 21 ASan/UBSan/LeakSanitizer and 19 sanitizer reference-project
tests, 38 public C++ headers and strict C17/symbol checks pass. No failed build
or test command occurs in this slice; the older closed-stderr abort remains open.
[Commands, sources, witnesses and limits](development/validation/c17-grammar-unicode-host-2026-10-05.json).

Local Strix Halo CPU peak is 90.625 C, with no guard trip or tuning. Regex queries
allocate at most 12 bytes per state only when their minimum requires reachability
scratch; scalar decoding needs no additional allocator. This is not provider
allocation-exact cost, memory-fit or a speedup measurement. One inference device
owner remains, and no model operation, runtime thread, RNG or DS4 format changes.

Fresh `.161` read-only witness at 09:34:11.650086 UTC still observes foreign Gemma
PID 29223/start 2470351 and router PID 29377/start 2474081 in actual/kernel KFD;
GPU 100%, remote CPU 91.875 C. Original lease/boot/filesystem/four model stats
remain unchanged. No root GPU build/run/hash/conversion, service mutation,
foreign signal, waiter or standing lease follows. All six owned tasks remain open.

## C17 exact-decimal numeric grammar; host parity — 2026-10-05 UTC

Root continues task 7 in `feature/context-million-openai` from `39b237e`.
`lie/grammar_number.h` and `src/grammar_number.c` now own canonical decimal
parsing/comparison, exact division/product, strongest bounds, empty interval/grid
refusal, integer `multipleOf` reduction, prefix interval intersection and exact
LCM. Four source-bound edits route the pinned provider through storage/JSON/error
glue with the existing default-ON selection; OFF retains the numerical reference.
Schema-number representability remains a JSON-adapter responsibility.

Independent C checks pass 7,413 fixed-point/integer value oracles and 1,600 LCM
pairs, allocator/work/buffer refusal, copied policy and 4096-byte scalar limits.
Complete pristine/ON/OFF witnesses agree for 49 admitted policies, 16,954 prefix
checks, 539 values and 196 intersections. All six previous complete
probability/history/byte-state/mask witness hashes remain unchanged. Final
20 Debug, 20 ASan/UBSan/LeakSanitizer and 18 sanitizer reference-project checks
pass, plus 36 public C++ headers and strict C17/symbol checks. Matching final
provider/number contract rechecks pass 2 Debug and 2 sanitizer tests.

CPU peak is 91.875 C, with no guard trip or tuning. The measured host policy is
24,680 bytes; each numeric call owns/retires 114,856 bytes of scratch, copying
only live digits. Original-weight allocation/cost remains unqualified. The first
strict compiler warning and sandbox-only socket failures are retained with their
actual exits in the [source-bound receipt](development/validation/c17-grammar-number-host-2026-10-05.json).
The older closed-stderr abort remains unresolved; no numerical/GPU speedup is claimed.

The read-only `.161` witness at 08:51:41.633432 UTC still observes foreign Gemma
PID 29223 and router PID 29377 in actual/kernel KFD, GPU 100%, CPU 89.25 C.
Original lease, boot/filesystem and four model stats remain unchanged. No root
GPU build/run/hash/conversion, service mutation, foreign signal, waiter or standing
lease follows. All six owned tasks remain open. String/Unicode-DFA/regex
predicates, schema compilation and vocabulary trie/transition/cache extraction
remain within the same grammar task, alongside its original-weight gates.

## C17 byte-grammar runtime; complete host state/mask checks — 2026-10-05 UTC

Rule expansion, byte branching, stack/lexeme ordering, canonical snapshots and
completion now use C17, together with dense/compact logit mask application.
Programs deep-copy immutable tables; snapshots own bounded state, and allocation
refusals preserve input/output ownership. Provider glue seals independent
programs after schema/reasoning/tool composition. ON/OFF layouts agree; matched
source/archive/application rebuilds are required. Reactive owner, request/RNG
semantics and DS4 RAM/SSD framing remain unchanged.

Final 19 Debug, 19 ASan/UBSan/LeakSanitizer and 17 pristine/ON/OFF host checks pass,
with 35 public headers and strict C17/symbol checks. Independent C fixtures cover
134,402 transitions. Full witnesses compare 13,700 byte states and 7,089 masks
across 20 grammars/23 texts; older probability/history witness hashes agree.
CPU peak is 90.75 C, without guard trips. [Source-bound commands and limits](development/validation/c17-grammar-runtime-host-2026-10-05.json)
retain the older unresolved closed-stderr abort without claiming a fix.

Schema compiler, primitive exact-decimal/string/Unicode-DFA predicates and
vocabulary trie/cache algorithms still need extraction within the same grammar
task. New original-weight continuation/resources/cost remain unqualified. At 08:12:22.016655 UTC,
the read-only `.161` witness still observes foreign Gemma PID 29223 and router
PID 29377 in KFD. No root GPU build/run/hash, service mutation, foreign signal,
waiter or standing lease occurs. All six owned tasks remain open.

## C17 compact distributions and host MTP arithmetic — 2026-10-05 UTC

Ordered/compact normalization, mapped penalties, p-q residual correction and
exact host proposal/verification arithmetic now belong to the shared C17
sampler. Caller-owned storage and refusal checks preserve published results and
RNG. The default-ON provider recipe uses storage/options/error glue; OFF retains
Gufo numerical behavior and the same layouts. Reactive device/controller
ownership and DS4 RAM/SSD framing are unchanged.

Final 18 Debug, 18 ASan/UBSan/LeakSanitizer and 16 pristine/ON/OFF host checks pass,
with 34 public C++ headers and strict C17/symbol checks. Complete 1,728-profile /
6,912-decision witnesses agree byte-exactly. CPU peak is 88.375 C; no guard trips.
[Source-bound commands, full witnesses and limits](development/validation/c17-distribution-host-2026-10-05.json)
retain the tooling failure and the older unexplained closed-stderr abort.

Original-weight continuation/resources/cost remain unqualified. Grammar/masking
is still the remaining source extraction in the identified three-component task;
model/controller and GPU-resident numerical kernels remain transitional. The
fresh `.161` witness at 07:28:56.951902 UTC still observes Gemma training PID 29223
and router PID 29377 in descriptor/kernel KFD. No root remote GPU build/run/hash,
service mutation, foreign signal, waiter or reservation starts. All six owned
tasks remain open.

## C17 sampler history; host checks only — 2026-10-05 UTC

Prompt-tail repetition and committed generated-token counts now use the owned
C17 history contract, selected with the existing default-ON sampler option.
Construction/reset/acceptance/free-distribution bookkeeping is wired through
storage-only provider glue; OFF retains Gufo. Inputs are borrowed, growth is
caller-controlled and refusals preserve published state. The owner/reactive
path and DS4 prefix framing remain unchanged.

Seventeen Debug and seventeen ASan/UBSan/LeakSanitizer checks pass, plus fifteen
pristine/ON/OFF sanitizer checks and 33 public C++ headers. The independent
FIFO/count oracle covers 14,400 transitions; complete history witnesses cover
1,728 transitions and 48 profiles. The failed sandbox run and unsupported root
schema fixture remain in the [host receipt](development/validation/c17-history-host-2026-10-05.json).
Local CPU peak is 90.875 C; no thermal guard trips or tuning occurs. The older
closed-stderr abort remains unexplained.

History GPU continuation and cost are still unqualified. Grammar/masking and
compact speculative distributions remain delegated. The fresh `.161` witness
at 06:24:10.934843 UTC observes the external training PID29223 and router PID29377
in descriptor/kernel KFD. No remote build/run/hash, service change, waiter or
reservation starts. All six owned roadmap tasks remain open.

## HTTP steering plans and independent choices — 2026-10-05 UTC

Both HTTP APIs now accept `dir_steering_plan`, copied into the shared C17 core
before protocol storage is freed. Multi-choice admission gives every child an
independent plan with existing seed offsets and rollback. Stored controls use
`/steering/{choice}` for one selected child; GET retains tickets, actual policy
and attempted/applied plan steps after the foreground closes. Additional stored
choice references are charged only with a direction bank and released on disposal.
The network loop still performs admission/snapshots only; no inference thread,
JSON dependency in core contracts or Python product/default-test dependency is added.

Final 24 Debug and 24 ASan/UBSan/LeakSanitizer checks pass, with three build-off
tests and 32 public C++ headers. Coverage includes concurrent AR/MTP schedules,
both creation routes, exact prompt/decode positions, malformed/duplicate plans,
early-EOS unreached steps, live choice isolation, deletion and no-bank retirement.
The initial suites exposed release of a null extra-choice reference when the
bank was absent; the guard fixes that regression without changing assertions.
Both failed exit-8 commands remain in the
[host receipt](development/validation/steering-http-plan-host-2026-10-05.json).
Local CPU peak is 71.875 C. The older closed-stderr abort remains unexplained.

Original-weight GPU continuation, quality and cost remain pending. The fresh
read-only `.161` witness at 05:43:05.088403 UTC still observes external
PID29223/start2470351 and router PID29377/start2474081 in descriptor/kernel KFD
inventories. No remote build/run/hash, service mutation, waiter or reservation
starts. The six open tasks and frozen GPU/task-evaluation evidence remain.

## Scheduled steering and HTTP controls — 2026-10-05 UTC

The shared C17 core now copies an immutable steering plan and applies it at
declared retained token positions. Prefill chunks, AR rows and MTP bursts stop at
each boundary; prefix lookup cannot skip the first unapplied change. The native
bench accepts `--dir-steering-plan`, reports actual application positions and
history, and rejects incomplete plans or comparisons with different steering.
Stored single-choice Chat and Responses requests expose asynchronous GET/POST
`/steering` controls through the same inference owner. No inference thread or
Python product/default-test dependency is added.

Final checks pass: 21 Debug, 21 ASan/UBSan/LeakSanitizer, three build-off tests and
32 public C++ headers. They cover exact boundaries, concurrent policies, RAM/SSD
reuse, cancellation, provider failures, strict report identities and both HTTP
routes. Local CPU peak is 75 C. The initial boundary-crossing failure, compiler
failures and corrected EOS fixture remain recorded with actual exit codes in
the [host receipt](development/validation/steering-schedule-host-2026-10-05.json).
The previous closed-stderr sanitizer abort remains unexplained; subsequent
passing checks do not establish its cause or a fix.

Original-weight GPU continuation, numerical quality, graph/correction behavior
and cost remain unqualified. HTTP multi-choice control and creation-time plans,
and replay-based lookup of later mixed-history checkpoints, remain open. The
fresh `.161` witness at 05:01:54.702189 UTC still observes external
PID29223/start2470351 and router PID29377/start2474081 in descriptor/kernel KFD
inventories. No remote build/run/hash, service mutation, waiter or reservation
starts. All six open roadmap tasks and frozen GPU/evaluation receipts remain.

## Live steering on the existing inference owner — 2026-10-05 UTC

The shared C17 core now admits one copied scale change per job and returns an
asynchronous ticket. The owner applies it at a scheduling boundary, preserving
past retained tensors/logits, history and separate image identity. Snapshots
retain completion through retirement. Scope refresh after each completed forward
prevents mixed steering history from reusing a uniform prefix. Mutating failure
poisons the shared model; pure refusal preserves the job. No inference thread or
Python product/default-test dependency is added, and absent-bank dispatch keeps
its ordinary path.

The provider source invalidates private graphs and MTP controller/proposal
scratch while preserving an already sampled residual correction for unchanged
boundary logits. Nine ON/OFF/unavailable provider syntax checks pass; this is not
GPU proof. Final host checks pass: 16 Debug, 16 ASan/UBSan/LeakSanitizer, three
build-off and 32 public headers. They include concurrent isolated policies,
AR/MTP/vision RAM/SSD capture, copied inputs, saturation, cancellation and failure.
Local CPU peak is 80.875 C.

One sanitizer native-bench run aborted in its deliberate broken-stderr case.
The original failure remains; its cause is unresolved. The fixture now retains
sanitizer diagnostics on file without disabling checks. A diagnostic native rerun,
32 isolated fault repetitions and the final suites pass; these do not prove the
previous abort fixed. Compiler/fixture failures and a stale-binary check excluded
from qualification are retained in the [host receipt](development/validation/steering-live-host-2026-10-05.json).

Dynamic HTTP/bench controls and original-weight live continuation, graph,
deferred-correction, quality and cost gates remain open. The `.161` read-only
witness at 04:06:49.060745 UTC still observes external PID29223/start2470351 and
router PID29377/start2474081 in actual/kernel KFD inventories. No GPU admission,
remote build/run/hash, service mutation, waiter or reservation starts. All six
open roadmap tasks and the frozen GPU/task-evaluation limits remain unchanged.

## Shared core steering and initial server/bench controls — 2026-10-05 UTC

The additive core constructor copies bank options/path before return and admits
them on the existing inference owner. READY snapshots project bank hashes and
host/device vector data without calling the provider from a client thread.
Complete steering/image scope is composed before RAM/SSD text or token lookup,
then checked by capture/restore. Zero-scope legacy reads and unused-bank state
remain compatible. Executor/request/generation/state ABIs and unversioned core
options/info layouts are unchanged; no inference thread or Python dependency is added.

Server and native core bench share DS4's initial file/FFN/attention controls.
Native reports validate actual admission against requested scales and refuse
matched comparisons whose bank or scales differ. Sixteen Debug and sixteen
ASan/UBSan/LeakSanitizer checks pass, covering synthetic AR/MTP/vision and joint
RAM/SSD process restart, copied option lifetimes, both HTTP APIs in JSON/SSE,
and native reports. Three build-off checks and 32 public C++ headers pass.
Local CPU peak is 78.5 C. Retained failures comprise the sandbox socket refusal,
an integer accessor for fractional scale, a missing strict-client fingerprint
and missing requested Chat SSE usage; fixture corrections preserve protocol behavior.

Live scale transitions and actual GPU continuation/numerical quality/cost remain
open. The read-only `.161` witness at 03:20:53.768099 UTC still observes external
PID29223/start2470351 and restored router PID29377/start2474081 in actual/kernel
KFD lists. No remote GPU build/run/hash, service change, waiter or reservation
starts. The six open roadmap tasks and frozen GPU/evaluation results remain.
[Commands, source/artifact hashes and failures](development/validation/steering-core-host-2026-10-05.json).

## Steering model-prefix RAM/SSD binding — 2026-10-05 UTC

The model-neutral C17 state binding plans and validates steering metadata tails
without copying the tensor payload again. The provider source revalidates the
actual model prefix, admits policy/scales/combined semantic scope before transfer,
and commits exactly its observed restored position before suppressing cancelled
delivery. Model codecs still independently validate geometry, image positions
and predictor/controller content. Native Gufo snapshots retain their active
steering refusal; the LIE path uses its owned typed state contracts.

Active or earlier-steered state retains explicit policy metadata. An admitted but
unused bank preserves exact legacy layout, scope and filenames. Existing MTP
and vision auxiliary components remain in place; the DS4 tensor body and leading
client extension are unchanged. A previously steered prefix switched off later
cannot be reused as initially unsteered state. Existing RAM/SSD accounting charges
the tail; no runtime thread, tensor scratch copy or Python product dependency is added.

Ten Debug and ten ASan/UBSan/LSan tests pass, with 32 public C++ headers and
complete-adapter syntax enabled/disabled/without state access. The native tests
exercise actual shared RAM/SSD and C Qwen AR/MTP/vision codecs with synthetic
tensors. Local CPU peak is 65.125 C. Initial build exit 2 from a fixture field-name
typo and test exit 8 from requiring INVALID for an unsupported magic are retained;
production codec behavior is unchanged. These results do not qualify actual
GPU continuation, numerical steering, quality or cost.

Shared-worker resource admission/scoped text lookup, live scale changes and
HTTP/bench exposure remain open. At 01:49:21.180644 UTC `.161` still shows foreign
PID29223/start2470351 and restored router PID29377/start2474081 in actual/kernel
KFD inventories. Root starts no GPU window, build, service mutation, waiter or
reservation; all frozen GPU/evaluation results and the seven-item queue remain.
[Commands, hashes and scope](development/validation/steering-binding-host-2026-10-05.json).

## Direct steering admission and retained-forward binding — 2026-10-05 UTC

The C17 model contract now validates direction options against actual model
geometry before GPU upload. The provider source owns the bank and per-sequence
policy, applies initial scales and confirms only the actual retained frontier
after prefill, AR and batch AR/MTP. Completed work commits before cancelled client
delivery is suppressed; rejected drafts and predictor work are excluded. Failed
post-mutation confirmation poisons the model. No thread or Python product
dependency is added; existing executor/request/generation ABIs are unchanged.

Nine Debug and nine ASan/UBSan/LSan host checks pass, as do all 31 public C++
headers and complete-adapter syntax with steering enabled, disabled and without
state access. The new native fixture uses host files and synthetic positions;
it does not execute a model. Local CPU peak is 67.375 C. No GPU linking or
original-weight numerical/quality/cost qualification exists for this increment.

Shared-worker admission/accounting, model-cache binding, live changes and
HTTP/bench controls remain open. Direction-enabled state transfer refuses even
at zero scales until complete history-aware restore exists. Existing opens
without directions retain their RAM/SSD path. The fresh read-only `.161` witness
at 01:26:22.453930 UTC still finds external PID29223/start2470351 and restored
router PID29377/start2474081 holding KFD. No GPU window is started. The seven
owned tasks and frozen GPU/evaluation results remain unchanged.
[Commands, hashes and scope](development/validation/steering-admission-host-2026-10-05.json).

## Steering metadata and staged RAM/SSD restore — 2026-10-05 UTC

The C17 policy now encodes explicit little-endian, checksummed 192-byte metadata
instead of native structure padding. A pristine destination validates bank,
history/scales and an independently confirmed target frontier before staging.
The immutable plan supplies its combined semantic scope before transfer and
commits only the exact completed restored position. Refusals preserve live state;
plans retain their policy/bank. Capacity and revision remain destination-local.
Absent metadata admits only unsteered legacy state with zero scales.

The additive state role requires an existing cache-scope section and stays after
the KVC auxiliary boundary. Eight Debug and eight ASan/UBSan/LSan host tests pass,
including full independent wire oracles, checksummed malformed frames, scale
history continuation, bank/geometry/frontier incompatibility, owner/stale/discard
lifetimes and actual shared RAM/SSD framing with synthetic model bytes. The
DS4 model payload and leading client extension remain byte-identical. All 31
public C++ headers and complete-adapter syntax pass. Local CPU peak is 75 C.
Two Debug exit-8 fixture failures remain retained: an incorrectly transcribed
oracle length and prematurely unlinking the private file before SSD admission.

This is host protocol qualification, not original-weight or GPU steering. Live
model/session admission, resource metrics, scale transitions, provider/cache and
HTTP/bench wiring remain pending. At 00:52:53.054202 UTC `.161` still has external
PID29223/start2470351 and router PID29377/start2474081 as actual/kernel KFD
clients. No GPU build/run, service change, retry, waiter or reservation follows.
The seven-item roadmap and all frozen GPU/evaluation failures remain unchanged.
[Commands, hashes and scope](development/validation/steering-state-host-2026-10-05.json).

## Directional activation operators and provider hooks — 2026-10-05 UTC

The owned C17 activation descriptor validates row/branch spans, scale and byte
arithmetic. An independently written HIP operator applies DS4's projection edit
to the target attention block before HC combine and every FFN residual branch
after combine, in scalar prefill/decode/verification and native batches. Active
FFN edits invalidate fused normalization and cached F16/Q8 views. The separate
MTP predictor is unchanged; no inference/scheduling thread is added.

The provider's immutable initial bank/scales are private hooks. Public model and
session policy admission, live transitions, history-aware cache compatibility,
HTTP/bench controls and original-weight numerical/quality/cost gates remain open.
Active steering refuses native/provider snapshots and LIE state transfers until
that history is integrated. Unsteered DS4 payload formats are unchanged. The
compile selection is on by default and requires new matching verified archives.

Six Debug and six ASan/UBSan/LSan host tests pass. All 1,019 pristine source hashes
and the exact composed changes verify. Enabled/disabled provider/adapter syntax,
both HIP target syntax checks and all 31 public C++ headers pass without producing
device objects. CPU maximum is 82 C. The first sanitizer run exits 8 under ptrace;
the first executor syntax checks exit 1 on a missing actual provider define.
Both failures remain retained; corrected checks pass without weakening oracles.
At the read-only `.161` witness, external PID29223/start2470351 still owns KFD
alongside the restored router; no GPU admission/build/run or reservation follows.
[Commands, hashes and scope](development/validation/steering-provider-host-2026-10-05.json).

## Original-weight automatic AR budgets qualified; MTP interrupted — 2026-10-04 UTC

The device-free `.161` r12 build verifies all 2,457 capsule files and the 1,019
official Gufo files, compiles `a3066a7`, exits 0 and closes its lease. The separately
admitted AR window passes **37/37** checks: the previous 34 controls plus model
limit agreement and actual automatic output in both APIs. Chat and Responses
each produce 327 tokens with omitted JSON and null SSE limits, with identical
complete constrained text, usage and resolved budget 4,096. All runtime/controller
exits are 0; collection verifies seventeen artifacts. CPU/GPU/NVMe maxima are
61.25/64/62.85 C. Router and original lease are restored at 23:11:50.074654 UTC.

The subsequent MTP window completes the 21 controls sidecar but is interrupted
at 23:16:24 UTC by external Python 3.12 PID29223/start2470351 in `session-424`.
Supervisor/controller exit 1, owned child exit 137 and container-init exit 143
are retained; OOM is false. Sixteen artifacts verify and the actual owned GPU
PID29140/start2464442 is absent. Models are unchanged, router PID29377 is active
and the original lease is free. The new MTP37 gate remains unqualified; the
historical r11 AR/MTP34 gates are unchanged. No automatic retry or standing
root GPU ownership remains. [Combined receipt](development/validation/automatic-output-point-gpu-2026-10-04.json).

Terminal Bench's unchanged official source is separately staged for the existing
Harbor 0.20.0/Docker client. The smoke image is cached; only 4/19 Core-19 images
are present. No dependency is installed and no task is executed. Inference still
targets `.161` over HTTP8000 after a newly admitted server window.

## Automatic shared-core output budgets implemented — 2026-10-04 UTC

The subsequent optional GPU protocol requires actual output past 128 tokens
with omitted JSON and null SSE budgets in both APIs, plus matching advertised
model limits. Its 58 supervisor and five wire-oracle host tests pass; an initial
malformed-JSON exception is retained and normalized without weakening rejection.
This adds no dependency to the product, native graphs or default tests.
[Protocol receipt](development/validation/automatic-output-gpu-protocol-host-2026-10-04.json).

The pinned Terminal Bench runner omits `max_tokens`; the existing Harbor client
raises an output-length error on a length-truncated response. LIE previously
silently selected 128 tokens. Omitted/null HTTP limits now reach the C17 core as
an automatic budget, resolved after prompt preparation to the smaller of the
remaining physical context and the existing 4,096-token ceiling. Explicit
positive budgets retain exact admission; numeric zero remains invalid in HTTP.
The C initializer retains its explicit 128-token default. Admission reserves
bounded storage without a mutable shared request or an extra worker thread.

Request ABI 8 requires callers to rebuild; executor/generation ABI 3 are unchanged.
Prepared job snapshots and Chat timings expose the resolved limit; Responses
and stored replay use `max_output_tokens`. Both model routes advertise context
and output limits. EOS, stop strings and the declared output ceiling still apply.

Nine focused Debug and nine ASan/UBSan/LSan tests pass, covering past-128 output,
near-full context, independent concurrent budgets, immutable admission, exact
positive overflow, natural EOS, MTP's final burst, JSON/SSE and stored replay.
The first Debug run exits 8 on two HTTP assertions: the diagnostic initially
failed to expose the resolved Responses budget. The correction uses its standard
field, and the failed run remains preserved. Local CPU maximum is 74 C.
[Commands, hashes and retained failures](development/validation/automatic-output-host-2026-10-04.json).

These host fixtures do not establish a Terminal Bench score. The subsequent
r12 AR37 GPU window is recorded above; the newer MTP gate remains interrupted.
The frozen r11 receipts are unchanged. No task has run and no harness output
cap or product dependency is added by this slice.

## Original-weight OpenAI MTP controls completed — 2026-10-04 UTC

After the unrelated training process retires, fresh `.161` inspection verifies
the original boot/FS/lease, sole authorized router, temperatures and memory.
The separately admitted `context-r11-openai-controls-mtp-r3` window runs the
frozen `abb69d5` server with the original UD weights and explicit Q8 predictor.
All 34 checks pass, matching the earlier AR set: both JSON/SSE APIs, function
arguments/results/replay, allowed tools, 2/8 choices, seeded replay,
probabilities/bias, stop strings, constrained JSON, storage, disconnected
background jobs, cursor/input pagination, cancellation, deletion and truncation.

Server/client/controller/supervisor exits are 0; collection exits 0 and verifies
all fifteen artifacts. Original model/predictor stats stay unchanged. Owned
processes and KFD clients retire, router PID23248 is restored and the original
lease is free at 22:22:10.325729 UTC. The subsequently stopped Distrobox init's
exit 143 is preserved separately from the successful inference child. Across
97 samples, CPU/GPU/NVMe maxima are 61.5/66/66.85 C, maximum GTT is 87.775 GiB
and minimum available RAM is 25.289 GiB. CPU98/NVMe85 guards remain active;
GPU temperature is observed only.
[Validation receipt](development/validation/openai-controls-mtp-point-gpu-2026-10-04.json).

Roadmap item 1 is complete for this runtime and these wire/lifecycle paths.
The earlier foreign-client refusal and all old receipts remain unchanged.
This is not task evaluation, independent numerical quality or performance,
nor GPU qualification of the later top-k/min-p, fixed-EOS or steering increments.
Root retains no GPU job, waiter or reservation on `.161` or `.157` at closure.

## Owned C17 steering policy/history implemented — 2026-10-04 UTC

The shared library now owns per-session scale transactions and history/cache
identities in separate policy ABI 1, retaining the immutable bank. Preparing
before device work and committing only its completed retained-target frontier
keeps failed, deferred and rejected speculative work out of cache history.
At most two plans are outstanding; policy/staged byte accounting is explicit.
Uniform policy identity is independent of prefill chunks and accepted bursts;
turning steering off preserves earlier steered history. Unused toggles preserve
legacy text/image identities. Owner checks, pins and locked snapshots add no
runtime thread. Executor/request/generation ABIs remain 3/7/3.

Five focused Debug and five ASan/UBSan/LSan checks pass. Native fixtures retain
independent SHA oracles, partial/discard/stale/zero updates, wrong-owner refusal,
plan capacity, image composition, source/bank lifetime and concurrent snapshots.
Both the full adapter and public header compile in C++; these checks are not
model inference. Maximum local CPU is 70.5 C. The initial compiler exit 2 from
a formatting warning is preserved and corrected without suppressing warnings.
[Validation receipt](development/validation/steering-policy-host-2026-10-04.json).

Policy primitives are not yet attached to actual provider/session/cache calls.
HIP attention/FFN edits, normalized-view refresh, MTP/graph invalidation, encoded
history persistence and HTTP/bench controls remain roadmap item 5. No existing
state or DS4 KVC framing changes. Read-only `.161` inspection at 21:31:58 UTC
confirms training PID19916/start1073961 still holds KFD/renderD128 and is present
in the kernel client list. Root admits no GPU window or standing reservation.

## Fixed-token EOS benchmark method implemented — 2026-10-04 UTC

The independently verified official Gufo TG benchmark calls decode with
`stop_at_eos=false`. LIE previously always selected `true`, explaining a method
difference for fixed-output measurements. The native core bench now accepts
explicit `--ignore-eos`, with a per-sequence shared-core policy in AR/batch/MTP.
EOS remains a sampled confirmed token, including its actual ID and possibly
empty text. No masking or replacement draw is added. Normal HTTP serving keeps
EOS; chat, tool, vision, constraint and stop-string combinations refuse ignore.

Request ABI 7 appends the policy; executor ABI 3 and generation ABI 3 stay
unchanged. A violated provider policy poisons the shared result under the
existing failure contract. The native CLI, report and optional Point supervisor
retain full output oracles; result/comparison identity records `eos_policy`,
with historical absence meaning `stop`. No thread or product dependency is added.

Eight focused Debug and eight ASan/UBSan/LSan checks pass, with 56 optional
supervisor fixtures and a complete adapter header check. EOS C2 repetitions,
zero-byte text, MTP bursts, immutable admission, late setter refusal, malformed
policy, mismatched reports and deliberate provider policy violation are covered.
The local CPU maximum is 83.5 C. An initial documentation context-patch refusal
is retained; no test or compiler fails in this slice.
[Commands, hashes and scope](development/validation/fixed-eos-host-2026-10-04.json).

Original-weight fixed TG128, physical 1M and quality/performance remain open.
The prior physical PP1,048,448/EOS43 gate is unchanged, not retrospectively
qualified. Read-only `.161` inspection at 21:08:01 UTC still sees the unrelated
training process PID19916/start1073961; root admits no GPU job or standing lease.

## Owned C17 steering bank implemented — 2026-10-04 UTC

The shared core library now provides a model-neutral direction-bank loader with
exact flat f32 values, explicit geometry/budget, immutable references and separate
file/geometry identities. Invalid files, nonfinite directions, ABI mistakes,
overflow and over-budget input refuse without changing the output handle.
No HTTP types, GPU work, extra runtime thread or new dependency enters this API.

Four focused Debug tests and four ASan/UBSan/LSan tests pass, including concurrent
reference lifetime, source unlink/mutation, multichunk values and independent
SHA oracles; local CPU maximum is 66.625 C. The loader does not activate steering
in the model. HIP edits, shared admission/session scales, cache binding and
HTTP/bench flags remain roadmap item 5.
[Contract and exact binding requirements](development/STEERING.md) ·
[Validation receipt](development/validation/steering-bank-host-2026-10-04.json).

Read-only DS4 source audit at `0aaea5a` confirms attention's projected-block
edit and FFN's post-combine per-HC-residual edit. The Gufo provider's fused
normalization must be refreshed after an FFN edit; editing only the MoE block
would implement different behavior. DS4 source/workspaces remain untouched.

## Terminal Bench source and client prerequisites prepared — 2026-10-04 UTC

An independently downloaded official Terminal Bench Mini archive at
`07034484346dc724d0e2c47c821fd196add1d6fb` matches all 231 recorded reference
file hashes. The persistent private source keeps the upstream Apache-2.0
license/notice and unchanged tasks; the official loader verifies Core-19 1.0.0
content and its one-task smoke tier. This adds no product/build dependency.
Read-only client checks find existing Harbor 0.20.0 and Docker 29.7.2 on `.157`;
root job directories will be separate from Q2's environment and results.

Actual model inference remains on `.161`, over ordinary HTTP port 8000. No task
is executed, no GPU admission or dependency installation occurs, and the
20:19:42 UTC read-only check still sees the unrelated `.161` training process.
Full task-image/runtime prerequisites must also pass before a long evaluation.
[Pinned source, unchanged task verification and scope](development/validation/terminal-bench-source-preparation-2026-10-04.json).

## DS4 sampling GPU profile admission prepared — 2026-10-04 UTC

The optional Point supervisor accepts an explicit, complete seven-control
`generation` profile, forwards it to the native core bench and verifies the
returned identity. Invalid profiles refuse before model verification/load;
unknown, null, wrongly typed or mismatched result controls cannot qualify.
Historical absent/five-control identities still mean disabled candidate filters.
All 78 optional Point CPU fixtures pass; maximum CPU is 54.75 C. No runtime,
GPU thread or product dependency is added.
[Receipt](development/validation/ds4-sampling-point-supervisor-2026-10-04.json) ·
[AR/exact-MTP sampling protocol](development/protocols/DS4-SAMPLING-GPU-PROTOCOL.md).
Actual inference/profile cost remains pending on a freshly admitted `.161`.

## DS4 candidate filters exposed in the shared core — 2026-10-04 UTC

Top-k and min-p now pass through generation ABI 3/request ABI 6, Chat and
Responses, and the native core benchmark to the transitional sampler. Both
APIs enforce strict numeric types and bounds; Responses retains supplied filter
values in stored objects. Greedy defaults and disabled filters remain unchanged.
Native reports record all seven sampling controls, refuse mismatched or malformed
filters, and normalize missing historical top-k/min-p settings to zero.

All eight focused native Debug checks and the same eight ASan/UBSan/LSan checks
pass. Existing mathematical sampler oracles pass; adapter object and full
state/cache/MTP/vision syntax checks use independently verified pinned source.
The initial null-normalization test failure (exit 8) and a stale-header check
(exit 1) remain preserved. The maximum local CPU reading is 81.25 C, during
source composition. No model or GPU inference runs in this slice.
[Commands, hashes, retained failures and scope](development/validation/ds4-sampling-controls-2026-10-04.json).

Original-weight qualification of the DS4 sampling profile and its AR/exact-MTP
cost remains open. The read-only `.161` check at 20:01:31 UTC still sees the
unrelated training process; no new root GPU lease or job is started. Directional
steering remains a separate task, and DS4-owned files are unchanged.

## Roadmap ownership and DS4 controls — 2026-10-04 UTC

At the owner's request, the active queue excludes separately assigned DGX
Spark/CUDA, Antirez weight-format/quantization and Strix Point port work. Future
weight persistence, further model families and new clients are not active tasks.
General MTP/vision campaign expansion and a complete executor rewrite are not
used as unspecified backlog items; their recorded qualification limits remain.

Two concrete DS4-derived capabilities are added: per-layer directional steering
with FFN/attention scales, and sampling-temperature/filter coverage. Existing
temperature support is not claimed as absent; top-k/min-p client exposure and
AR/exact-MTP profile qualification need completion. The steering task includes
validated `.f32` banks, session/cache behavior, baseline-off equivalence and
original-weight cost/quality checks. DS4's documented Qwen implementation uses
Metal; its existence does not qualify LIE HIP. All GPU tests in this queue use
`.161` under fresh admission. Only LIE-owned code is modified.

## Native progress GPU qualification prepared — 2026-10-04 UTC

The optional Point supervisor now forwards a declared `progress_interval_ms`
to regular core benchmark clients and checks matching result identity. A bounded
streaming reader verifies live observations and retired final jobs against the
actual measured counters/times, preserving raw stderr hashes. A final metadata
flag cannot replace successful inference or a complete fixed-output sample.
Quiet historical runs remain compatible; reactive probes keep progress disabled.

All 75 optional Point CPU fixtures pass, including adversarial progress tests
for synthetic records, missing/fake retirement, wrong counts, duplicate users,
clock/counter regression, interval drift, oversized lines and missing snapshots.
Local maximum CPU is 57.125 C. No C core, inference thread or product dependency
changes; actual GPU exercise remains pending while the foreign `.161` process
uses the device. [Receipt](development/validation/core-progress-point-supervisor-2026-10-04.json).

## Corrected OpenAI AR controls pass on Point — 2026-10-04 UTC

The sealed `abb69d5` r11 runtime passes all **34 original-weight AR HTTP checks**
on `.161`: thirteen model/function checks and twenty-one additional controls.
Disconnected background generation retains all 64 requested output tokens and
its LENGTH completion; cursor replay, cancellation after a witnessed output
delta, storage, truncation, choices, probabilities, bias, stops and structured
JSON all pass. This qualifies wire behavior and lifetimes, not independent
quality or performance. The original r10 retirement failure remains failed.

Controller, child, server, supervisor and collection exit 0. Fifteen artifacts
hash-verify, model stats stay unchanged, owned processes retire, the router is
restored and the lease releases at 19:21:29.872800 UTC. Across 111 resource
observations, CPU/GPU/NVMe maxima are 61.375/63/65.85 C; sampled GTT peaks at
89,905,623,040 bytes and minimum available RAM is 30,831,460,352 bytes.

The first r11 build attempt refuses its unfinished source stage before compiling;
the separately admitted r2 build passes. The first AR r11 attempt stops during
loading on its conservative 112 GiB projected-memory budget, without OOM.
The successful 16K/eight-row AR gate uses a measured-workload budget of 96 GiB
and retains its 1 GiB RAM floor and CPU98/NVMe85 guards. Those failures remain
preserved. MTP r2 then refuses foreign GPU PID19916/start1073961 before model
load, restores the router and releases at 19:27:37.908694 UTC. Four artifacts
hash-verify; no model or container child starts. MTP remains unqualified by
this new gate and requires fresh available-host admission.
[GPU receipt](development/validation/openai-controls-point-gpu-2026-10-04.json).

## Background terminal-demand retirement race corrected — 2026-10-04 UTC

The first original-weight AR OpenAI-control gate passes all thirteen existing
checks and fourteen of the twenty-one additional controls, then fails when a
disconnected background Responses stream becomes cancelled. Child, supervisor
and controller exits are 1; server shutdown and collection exit 0. Fifteen
artifacts hash-verify, model stats are unchanged, owned processes are absent,
the router is restored and the lease released at 18:55:10.267458 UTC.

A deterministic CPU sequence-close barrier reproduces the same shared-record
failure: final output closes demand while numerical teardown and `retired`
metadata are still pending. `lie_record_pump` now treats CLOSED demand as a
normal boundary and continues until semantic TURN_END, preserving the output
and its completion reason. Invalid credit operations still fail. No HTTP type,
additional thread or provider call enters this shared C17 fix.

The original regression exits 8. After correction, seven focused headless,
flow, semantic and AR/MTP HTTP tests pass in Debug and with ASan/UBSan/LSan;
maximum local CPU is 66.25 C during builds and 60 C during checks. These are
CPU fixtures. The separately admitted corrected AR GPU gate now passes above;
the MTP gate still needs an available host and fresh admission.
[Receipt](development/validation/background-retirement-2026-10-04.json).

## Physical 1M prefill completed; TG128 gate failed — 2026-10-04 UTC

The original-weight `.161` C1 AR YaRN4 chunk256 run completes all
**1,048,448 physical prefill tokens** across 4,096 calls. Prefill takes
7,398.225 s (141.72 token/s); generation stops naturally at EOS after 43 tokens,
with 44 decode calls and 5.403 s decode time (7.96 output token/s). The benchmark
footer and child exit are 0. The declared fixed TG128 oracle correctly rejects
43 output tokens: supervisor/controller exits remain 1 and state remains FAILED.
The original predicate is not weakened after observing the result.

Collection exits 0 and all eleven artifacts verify against their recorded
SHA-256. Model stat witnesses remain unchanged; owned supervisor/GPU/container
processes retire, the named router is restored and the lease is released at
18:38:51.721369 UTC. Across 7,155 resource observations, CPU/GPU/NVMe maxima are
78.625/79/66.85 C and minimum available RAM is 6.03 GiB. No OOM or thermal stop
is reported. The repeated tokenizer-ID corpus is stress evidence, not recall
quality, a repeated performance comparison or a successful TG128 qualification.
[Receipt](development/validation/gtt112-boot-capacity-2026-10-04.json).

## Native live prefill observations — 2026-10-04 UTC

The regular shared-core benchmark now accepts `--progress-ms 100..60000` and
emits native JSONL metadata snapshots on stderr. The default is zero. Snapshots
expose completed prefill tokens, cache reuse, target-confirmed output and
consumer-observed output, with per-job timing and global execution phase.
They use the existing locked C17 counters. No provider call, output credit,
additional inference thread or Python dependency is introduced.

An explicit final observation is retained before releasing jobs on success,
failure or deadline. Its `retired` field remains separate from `final_snapshot`;
unfinished or failed prefill contributes no successful-input count. A closed
progress pipe produces a failed result and owned cleanup. Native paired reports
require equal declared intervals; historical records without the field mean zero.

The three native benchmark/report/HTTP contracts pass in Debug and with
ASan/UBSan/LeakSanitizer, using CPU fixtures and an interpreter-free child PATH.
Cases include two jobs, cache reuse, pending calls, injected prefill failure,
deadline, broken pipe, quiet default and historical comparison compatibility.
The first sandbox socket refusal and the missing target in the headless ASan
build remain preserved with actual exits 8 and 2. Maximum local CPU is 67.875 C.
These are client/metadata checks, not new GPU numerical or performance evidence.

The validation receipt retains the live physical1M observation made before
that run terminated. The run used its frozen r10 binary, without the new
progress option; its collected terminal result is recorded above. The new
progress client still needs a separately admitted GPU build and run.
[Validation receipt](development/validation/core-progress-2026-10-04.json).

## OpenAI control qualification prepared — 2026-10-04 UTC

The optional GPU supervisor now stages a hash-bound control gate alongside the
existing HTTP/tool gate. Its 21 checks cover 2/8 Chat choices in JSON and SSE,
prompt usage counted once, seeded replay, token probabilities, positive/negative
bias, cross-token stops, JSON/schema output, stored Chat operations and Responses
disconnect/replay/pagination/cancellation/deletion/truncation. Unsupported APIs
must return an explicit error. The server and shared C17 runtime are unchanged;
the helper adds no product build or benchmark dependency.

All **54 CPU-only protocol/supervisor fixtures pass** (8 controls and 46 campaign
checks), with device visibility masked and a 57.875 C maximum CPU temperature.
The initial fixture-placement failure remains preserved with exit 1. These are
qualification-control checks, not model inference.

Separate AR and MTP manifests pin the previously built `e6f537f` ROCm 10
`gfx1150` runtime, the postboot filesystem binding and exact helpers. Both remain
**prepared at this checkpoint** while the physical 1M window owned `.161`. Its
collected closure is recorded above; fresh admission is required for each gate. Original
weight qualification of these controls and Terminal Bench tasks remains open.
[Preparation receipt](development/validation/openai-controls-preparation-2026-10-04.json).

## GTT112 boot verified; 1M capacity passes — 2026-10-04 UTC

Following the owner's explicit reboot authorization, `.161` returns with a new
boot ID, the same qualified kernel and **112 GiB effective GTT**. GRUB identity,
syntax, lease inode and filesystem UUID verify. The router and both monitor
containers return automatically. The earlier rejected reboot remains historical
evidence of a command that did not execute.

The first capacity attempt refuses the filesystem device renumbering before
model launch; supervisor/controller/collection exits remain 1, with five files
retained and successful ownership closure. Optional staging binding now verifies
the witnessed boot ID, filesystem UUID and exact old/new device numbers while
preserving SOURCE.json and all other stat fields. All 44 CPU control fixtures
pass. No runtime dependency is added.

The separately admitted C1 AR YaRN4 chunk256 capacity-1,048,576 gate passes
PP1500/TG32. Controller, child and collection exit 0; eleven files hash-verify,
model stats stay unchanged, the router is restored and the lease released at
16:31:43.810798 UTC. Peak GTT is 109.18 GiB, minimum available RAM 7.98 GiB,
and CPU/GPU/NVMe maxima 67.75/70/64.85 C. All 32 output IDs equal the 512K gate.
The single cold sample records PP50.21/TG10.47 token/s; prefill is slower than
the short 512K gate and has not been diagnosed or qualified as performance parity.

The subsequent physical PP1,048,448 run completes prefill, then stops at 43
output tokens. The required TG128 gate remains failed; collection and ownership
closure pass, as recorded above. Its repeated tokenizer-ID corpus tests extended
positions, not recall quality or canonical Gufo/Halogen performance.
[Boot and capacity receipt](development/validation/gtt112-boot-capacity-2026-10-04.json).

## Current integration and remaining gates — 2026-10-04 UTC

| Work | Current result | Remaining work |
| --- | --- | --- |
| Strix Point integration | Owner checkpoint `40b2ac7` merged into `develop` as `30598a3`; merge Debug 48/48. | No implicit publication. |
| OpenAI native functions | Corrected runtime `e6f537f` passes all thirteen original-weight HTTP checks on `.161`. Chat/Responses each stream five argument fragments, accept correlated results, and retained Responses replay byte-identically. | Full task evaluation of this runtime; hosted cloud tools remain outside the local API. |
| Context profiles | Native/YaRN2/YaRN4 implemented in shared C17 core; short original-weight gates pass. Capacity accepts 1,048,576 tokens; physical PP1,048,448 completes. | Fixed-output extended-context qualification, recall quality and generic attention performance above 256K. |
| Reduced scratch | C1 chunk256 passes short 4K/512K/1M capacity gates at 78.33/93.68/109.18 GiB GTT with exactly equal output IDs. | Diagnose the cold short-prompt prefill slowdown at capacity 1M; no replicated performance parity claim. |
| Physical 1M fit | GTT112 capacity allocation passes. Physical PP1,048,448 completes with 43 output tokens and 6.03 GiB minimum available RAM. | Required TG128 gate fails on natural EOS; recall quality and canonical comparisons remain open. |

The active work is isolated in `feature/context-million-openai`. Native Debug
passes 51/51 and focused ASan/UBSan/LSan passes 4/4. Build, HTTP and reduced
scratch/capacity windows have collected successful closure. The separate physical
1M window is retired with collected closure and a failed TG128 oracle; there is
no standing GPU ownership or publication.
Earlier failed gates remain failed evidence.
[GPU receipt](development/validation/tool-context-point-gpu-2026-10-04.json) ·
[Context configuration and memory budget](guides/CONTEXT.md).

## Strict JSON function frames and scratch admission — 2026-10-04 UTC

The first original-weight HTTP gate passes complete strict function output but
fails incremental SSE: the provider emits JSON frames, which the first parser
buffered. That exit 1, server exit 0 and successful collected closure remain
preserved. The shared C17 preview now streams exact JSON argument bytes after
the complete function name, ignoring nested names and quoted closing tags.
Independent every-byte prefix oracles and XML/JSON HTTP fixtures pass; Debug
passes 51/51 and focused ASan/UBSan/LSan passes 4/4. The subsequent r10 GPU
gate passes, as recorded above; the failed r9 gate is not reclassified.
[Host receipt](development/validation/tool-json-streaming-2026-10-04.json).

A short original-weight chunk256 gate passes at the prior numerical checkpoint,
but shows no GTT reduction: scratch still allocated 2048 rows. The new adapter
passes the existing C17 prefill bound to model creation, retaining a floor for
admitted decode and MTP rows; indexer score scratch follows that capacity.
The default 2048 allocation is unchanged. Exact source edits and adapter/engine
headers verify. The r10 GPU gate samples a 1.21 GiB GTT reduction and exactly
equal output IDs; PP1500/TG32 records 266.94/10.52 token/s. This single sample
uses capacity 4096, no warmup, AR and both cache tiers off. It is not physical
1M or a replicated performance qualification. The subsequent boot and capacity
gate are recorded above.

## Incremental native functions — 2026-10-04 UTC

The shared C17 core now publishes provisional function starts and append-only
argument fragments (event ABI 2). Chat and Responses project those events into
SSE; successful full-turn validation still commits complete calls. The bounded
record journal owns fragment copies for replay after retirement. Loan retention,
credit accounting and cancellation stay in the shared core, without another
inference thread. `allowed_tools` supports the native function subset shapes
for both APIs, filtering prompt declarations and refusing unknown/duplicate names.

Native Debug passes 51/51. Focused ASan/UBSan/LSan covers parser prefixes,
held/cancelled/abandoned loans, final validation and exact retired HTTP replay;
the seven-test initial suite and four-test final suite both pass. CLI/client and
benchmark dependencies stay native C; optional campaign supervision uses Python.
The corrected GPU HTTP function/result/replay gate subsequently passes all
thirteen checks under a fresh build and admission. The [agent guide](guides/AGENT-CLIENTS.md) gives
actual client requests and distinguishes native tools from the audited Terminus
text command protocol. [Host receipt](development/validation/tool-streaming-2026-10-04.json).

## GPU context profiles and memory budget — 2026-10-04 UTC

The verified r8 HIP build and three original-weight `native`/`yarn2`/`yarn4`
PP1500/TG32 gates pass on `.161`. They use total capacity 4096, C1 and no prefix
retention. Each controller/model child exits 0 and collected closure verifies
router restored, owned processes absent and private lease free. They qualify
short-profile integration only. The r7 hash refusal, private source-copy mistake,
preserved drift and independently verified restoration remain explicit in the
[GPU receipt](development/validation/context-point-gpu-2026-10-04.json).

The initial source-formula estimate for C1 AR capacity 1M is 110.60 GiB GTT at chunk
2048. Extending the present 96 GiB ceiling to 112 GiB is technically possible,
but the observed baseline predicts only 0.72 GiB available RAM left. Host tuning
and reboot have not occurred. The subsequent measured scratch-bound baseline
reduces the estimate to 109.16 GiB. The next actual 512K capacity gate samples
93.68 GiB against the 93.65 projection; rebasing at that gate estimates 109.18
GiB for 1M and 3.15 GiB remaining RAM. The physical prompt is still only 1500
tokens. Fresh RAM admission still precedes physical 1M qualification; the
[context guide](guides/CONTEXT.md#gtt-on-the-point-test-host) records the exact
proposed boot argument and rollback. Long-context recall and generic attention
performance above 256K remain open.

## Context 1M implementation and Point merge — 2026-10-04 UTC

The completed Point checkpoint `40b2ac7` is merged into `develop` as `30598a3`;
48/48 native Debug tests pass on the merge. `feature/context-million-openai`
continues from that integration and carries the native conversation benchmark.

Shared C17 plans now expose explicit native/YaRN2/YaRN4 profiles. HTTP and direct
clients accept total capacity up to 1,048,576. The verified provider variant
uploads the plan for both attention and indexer, preserves mRoPE positions,
grows session/scratch bounds, and binds scaled SSD identity. Defaults remain
native, RAM retention enabled and SSD persistence opt-in. The profile changes
executor ABI to 3; old callers must rebuild.

CPU tests check independent frequency/rotation formulas and an actual 1,048,575
token fixture prefill plus one output. ASan/UBSan/LSan focused tests pass after
rerunning outside the ptrace sandbox; the sandbox failure remains preserved.
State-access adapter headers compile against the fully derived, hash-verified
official source variant. These checks are NOT-INFERENCE: original-weight 1M
memory fit, quality and throughput are not qualified. The larger sparse mask
currently selects generic attention above the 256K WMMA bound.

The owner prefers `.161` for new GPU qualification. Metadata shows 96 GiB GTT
and approximately 123.44 GiB visible physical RAM; increasing GTT requires
separate host-driver configuration, not an inference capacity flag. No host
tuning is performed by this code checkpoint. Commands, initial compiler and
sandbox failures and exact exits remain under `evidence/point-merge-20261004`.
See [usage and limits](guides/CONTEXT.md).

## Native canonical conversation benchmark — 2026-10-04 UTC

`synapse-lie-bench --suite http-curve` implements the independently fetched
Gufo `f783fedb` single-user cached-conversation protocol in C17. Exact seeded
prose/tasks, tokenizer calibration, real prefix replies, carried recalibration
and four-attempt tolerance remain distinct from the simplified direct suite.
Requests, retries, usage, raw responses and physical cache counts are retained.
Offline C reports reconstruct the protocol before exporting statistics and
four separately scaled PP/TG/HTTP-wall/TTFT panels. Comparisons expose dynamic
history/count differences instead of inferring numerical equivalence.

Focused native contracts pass 3/3 in Debug and 3/3 with ASan/UBSan/leak checking.
The new contract checks 22 upstream prompt goldens, a 35-request oracle through
128K with two repetitions and forced recalibration, and independent traces for
thinking, early prefix EOS, four failed retries and a 1M client boundary.
Benchmark/report subprocesses run with a PATH containing no interpreter or
external tools. Synthetic timing/chart values stay private and NOT-INFERENCE.
The standalone Release client also passes the independent wire fixture. Across
the device-masked commands, CPU peaks at 75.25 C under the CPU98 guard, with
separate SSD bounds and observe-only GPU temperatures.
The server/provider/executor ABI and inference scheduler are unchanged.
The provider ceiling remains 262,144; declaring 1M client capacity does not
enable 1M inference. No GPU/model access, remote build, dependency installation
or publication occurs in this implementation window.

The [benchmark guide](guides/BENCHMARKS.md#canonical-gufo-conversation-curve)
contains build/run/report commands. Static oracle provenance is recorded in
[the upstream port receipt](../third_party/gufo-bench-source.json).
Commands, actual failure/success exits, source and binary hashes and temperature
bounds are recorded in the
[host validation receipt](development/validation/bench-curve-native-2026-10-04.json).

## Point cold HTTP AR/MTP through near 256K complete — 2026-10-04 UTC

Sixteen fresh-server original-weight ROCm 10 `gfx1150` windows on `.161`
compare LIE with independently pinned official Gufo in AR and MTP at
8K/32K/128K/near-256K. Each C1 window uses context 262,144, no cross-request
KV prefix reuse, two measured complete 128-token outputs, and server-reported
prefill/decode plus client TTFT/wall timing. All 16 child/controller exits are
0, model stats unchanged, owned GPU processes retired, the named router
restored and the private lease released. The initial LIE timeout-bound pilot
remains a failed historical window with exit 1. The offline release checks
361 archived members and regenerates all eight matched comparisons with
byte-identical CSV/JSON/SVG outputs.

At 258,788 physical prompt tokens, AR LIE/Gufo median prefill is
386.128/384.685 token/s and decode 9.706/9.638. MTP prefill is
378.945/378.643 and decode 14.293/12.097; LIE/Gufo accept 85/65 draft
tokens per measured request. MTP improves the decode phase but increases
median end-to-end wall time by 8.51/8.09 seconds at this cold context. From
8K to near 256K, AR prefill declines 20.3%/19.3% on LIE/Gufo. The C1 curves
are close, so they do not identify the C17 reactive flow as the cause of the
high-context decline. All eight cross-engine output pairs differ in text;
performance matching is not a quality-equivalence claim. Sampled CPU/GPU/NVMe
maxima are 86.125/88/73.85 °C, with GPU temperature observed only. The
[full report](benchmarks/2026-10-04/strix-point/http-depth/README.md) has
per-sample values, draft counts, graphs, raw archives and offline reproduction.
Long-context multi-client HTTP, cold-file loading, allocation-exact HIP peaks
and 1M context remain open; the current server cap is 262,144 tokens.

## Point served HTTP AR/MTP comparison complete — 2026-10-04 UTC

The `128f490` LIE C17 server/native HTTP client and independently pinned
official Gufo `f783fedb` full server now have a matched original-weight
ROCm 10 `gfx1150` comparison on `.161`. Forty performance windows pass:
eight fixed eight-session runs and 32 fresh server runs with sessions equal
to C1/2/4/6/8. Each uses one excluded warmup and three measured 128-token
cohorts. All 16 native pairwise comparisons have complete identical output;
the two initial failed windows remain excluded and archived. The offline
release verifies 725 files, including 682 remote files by SHA-256, and
retains actual child/supervisor exits, model stat witnesses, thermal records,
restored router and released lease. The
[complete HTTP report](benchmarks/2026-10-04/strix-point/http-multi/README.md)
contains all decode/prefill/latency values, graphs, CSV/JSON, three sealed raw
archives and regeneration instructions.

Fresh-server LIE/Gufo AR prose summed decode reaches 32.984/33.316 token/s
at C8. MTP repetition at C1 reaches 21.037/21.496 versus the matched AR
10.423/10.504; MTP prose gains at C1 but is below AR at C8 for both engines.
Measured prefill is all-hit and has no executed PP rate; isolated cold warmup
rates are reported separately. This 4K HTTP campaign does not extend the
previous direct-engine 128K/near-256K qualification to long-context serving;
the separate [cold HTTP depth report](benchmarks/2026-10-04/strix-point/http-depth/README.md)
does that for C1.
The setup notes below preserve the historical sequence and failures.

## Point prepared HTTP qualification setup — 2026-10-04 UTC

The Point branch now includes the integrated native `http-multi` client at
`128f490`. A sealed `gfx1150` r6 source capsule from that commit has 2,302
file hashes verified on `.161`; its device-free Fedora 43/ROCm 10 build passes
with exit 0. The build restores `llama-router.service` and releases its private
lease. The new qualification helper runs that client against a supervised LIE
or separately pinned Gufo server on API port 8000. It fixes context 4,096,
eight active sessions, prefix caching, TG128 and one excluded warmup plus three
measured cohorts. Server, client, corpus and partial failure evidence are kept
separately. This setup is not yet an original-weight HTTP performance result.

The pristine Gufo CMake configuration at the recorded pin accepts only
`gfx1151`. A Point `gfx1150` full-server control therefore needs its own
explicitly recorded architecture/dependency port and GPU smoke qualification;
the existing LIE adapter build does not establish that control.

The first `.161` LIE C1 AR prose run completes all four prepared HTTP cohorts
with native client/server/container exit 0, but its supervisor exits 1 during
GPU PID retirement. The final sampled `/proc/fd` list is empty while kernel
KFD still lists the same earlier owned PID for one sample. Its 16 remote files
are collected by SHA-256; the router and free lease are verified. The supervisor
now accepts this gap only when the PID start tick and container cgroup still
match its previously recorded owned identity. A reused or foreign PID fails.
This failed window remains excluded from performance reporting; a fresh run is
required.

Fresh C1 AR prose r2 passes under the corrected supervisor: one excluded warmup
and three measured cohorts, 2,040 physical input tokens and all 128 output
tokens per request. The measured preparations each reuse all 2,040 tokens, so
their executed PP rate is null; the cold warmup executed 2,040 tokens in
3.97694 s. The native report records median server decode 10.4340 token/s,
common HTTP wall 10.4083 token/s and TTFT 0.116828 s. Client, server,
Distrobox and supervisor exit 0; 16/16 collected file hashes agree, original
model identities are unchanged, router restored and lease free. Sampled
CPU/GPU/NVMe maxima are 63.875/66/65.85 C. This C1 smoke is not the paired
C1–C8 Gufo comparison.

For that control, the Point build recipe verifies all 1,019 files of separately
fetched official Gufo `f783fedb` before copying them into an isolated port
directory. Its only planned source edit admits `gfx1150` in the top-level CMake
architecture guard and is emitted as an exact patch. Private rocWMMA 2.2.0
headers come independently from official commit `48b7db1`, which announces
`gfx1150` support; 116 staged files and the generated version header verify
by SHA-256. No package is installed. The full-server build and GPU control
remain unqualified until their own fresh leased runs.

The first full-server Point build verifies the sources and passes CMake
configuration and 235/236 object compilations, then fails at the final HIP
executable link with Fedora's default PIE and non-PIC upstream static archives
(`R_X86_64_32`). Its compiler child/supervisor exit 1, 13 collected files,
restored service and free lease are preserved. A subsequent build selects an
explicit non-PIE executable link in the private recipe; it does not change
upstream Gufo source or install packages.

## Point reactive/vision evidence integrated — 2026-10-04 UTC

Root integrates Point `c3e9916`, preserving the native prepared HTTP client,
sampling controls and all previous source-bound results. Offline audit verifies
79/79 archived remote files across seven r4/r5 runs, both exit-1 failures, and
exact 92-input/13-output-ID vision AR/MTP parity. The final r5 AR and 8K MTP
held-loan gates pass; short MTP with zero accepted drafts remains failed. All
recorded models/sidecars stay unchanged and every window restores its named
router and releases its lease. These are functional gates, separate from
independent vision quality and statistical performance.

The merged native C files remain byte-identical to the already sanitizer-tested
`74aa208` checkpoint. New supervisor/SSD/thermal fixtures pass 37/37 on `.155`
without GPU/model access, peaking at CPU82.875 C under CPU98/GPU observe-only.
All nine archive-index entries verify; three Point artifacts remain byte-identical
to their checkpoint. Merge conflicts and an initial wrong-directory SHA command
remain recorded with exit1. Fresh `.157` observation at 04:19:51 UTC finds the
shared lease held by live PID3401659/start165253067; root acquires no lease and
continues offline. [Integration receipt](development/validation/point-r5-integration-2026-10-04.json).

## Native prepared HTTP cohorts — 2026-10-04 UTC

The new `http-multi` suite uses a single C event loop for C1/2/4/6/8, stable
per-participant session IDs and a completed preparation barrier. It ships the
pinned Gufo prose/repetition prompts with exact upstream prompt hashes. Reports
keep summed individual server decode rates, common-wall throughput, preparation
PP and HTTP TTFT distinct; native four-panel graphs and CSV/JSON require complete
usage, phase timings, payloads, session identities and full output budgets.
Failed streams and cache-reuse failures retain partial evidence and fail export.
The [benchmark guide](guides/BENCHMARKS.md#prepared-http-multi-user-cohorts)
provides complete commands for LIE/Gufo AR and separately configured MTP.

Focused HTTP sanitizer CTest passes 6/6; final native contracts pass 2/2 with
ASan, UBSan and LeakSanitizer. Native fixtures include 19 corrupt-evidence cases,
actual truncated SSE, bounded positive sub-millisecond deadlines, interrupted
cohort retirement and all-hit PP graphs. The synthetic core client passes 20/20;
its two reactive probes pass 20 repeated invocations. Point `c07bb95`'s bounded
counter wait is integrated without changing the worker: job and aggregate
retirement publication are distinct. Product CLI execution with an empty PATH
confirms the new suite needs no Python. CPU peaks at 88.625 C under CPU98,
GPU observe-only and NVMe85 policies; no model/GPU forward occurs.

The initial fixture compile exit1 and a read-only `.157` debugfs denial exit1
remain recorded. A corrected sysfs observation sees the earlier Q2 PID retired
and KFD empty; root requests canonical handover rather than entering a campaign
gap. Original-weight paired performance for this new client remains pending.
[Source, commands, exits and provenance](development/validation/http-multi-native-2026-10-04.json).

## Point HTTP/SSD and direct-core probe integration — 2026-10-04 UTC

Root integrates Point `080177b`, keeping sampling controls and the optional
native `--reactive-probe`. The probe checks peer progress while a borrowed
output block holds its credits, then cancellation and retirement. Root strengthens
the snapshot check to compare every borrowed byte and covers MTP bursts of 8/13
tokens plus early-EOS/failure cleanup. It adds no inference worker and changes
no executor ABI, provider or model implementation.

Focused ASan/UBSan/LeakSanitizer CTest passes 19/19; the strengthened synthetic
client suite passes 20/20 and the repeated native contract passes 1/1. Mocked
Point supervision/SSD/thermal fixtures pass 34/34. Local CPU peaks at 84.875 C;
CPU guard is 98 C and GPU temperature is observe-only. These are host checks,
with GPU visibility masked and no model forward.

Offline root verification confirms all 34 HTTP and 42 SSD archived SHA entries,
short original-weight AR/MTP JSON/SSE exchanges, four exact cold/hot output
streams, 8,192 restored SSD tokens and zero hot prefill/errors. Native C reporting
accepts the matched SSD comparison. Seven retained Point artifacts stay byte
identical. Original GPU evidence remains bound to `9b109998`; the strengthened
probe still needs its own GPU qualification. Projector-copy bookkeeping retains
the retired temporary SSH agent's exit 2 separately from successful transfer
commands. The [integration receipt](development/validation/point-functional-integration-2026-10-04.json)
binds actual exits, merged source and scope; the [Point page](benchmarks/models/qwen3.8-flash-next/strix-point/README.md)
keeps results, archives and usage together.

## Seeded shared-core GPU comparison complete — 2026-10-04 UTC

Frozen `5a377aa` completes 18/18 original-weight `.157` arms across greedy,
unfiltered and top-p/penalty profiles. Each variant/profile has nine measurements
in three processes; 54 measured jobs plus 18 warmups complete, and 36 paired output
streams match exactly. C17/control median decode is 26.650/26.643, 25.220/25.593
and 23.837/23.877 tok/s. Slow samples stay visible; stable performance parity,
independent quality and exact allocation gates remain open.

CPU/GPU/NVMe peaks are 86/89/71.85 C, with CPU 98 C guard, GPU observe-only and no
thermal stops. Release at 02:43:25 UTC verifies 37 identities and 36 groups retired,
empty KFD, four unchanged/free original leases, model stats and capsules.
All 233 collected artifacts verify. Root remains offline; Point completes its
separate projector copy and returns `.157` to Q2. The post-run native renderer
now separates coincident markers at every category; a focused ASan/UBSan/LSan
CTest passes and pooled statistics remain byte-identical.
See the [complete results and graph](benchmarks/models/qwen3.8-flash-next/strix-halo/README.md#seeded-shared-core-sampler-comparison--october-4)
and [source-bound receipt](development/validation/sampled-core-gpu-2026-10-04.json).

## Core benchmark phase validation — 2026-10-04 UTC

The native report now rejects zero-time executed phases, inconsistent dispatch
counts and combined phase durations beyond the individual job's wall time,
including warmups. Eight malformed timing cases pass the focused CTest with
ASan, UBSan and LeakSanitizer. Six retained Point comparisons reproduce their
metrics and CSVs unchanged; cache-hit prefill remains unavailable rather than zero.

Both new `gfx1151` provider/client variants compile locally with GPU visibility
masked. Seeded greedy, unfiltered and top-p/penalty comparisons are prepared;
GPU admission stays disabled until Q2 releases `.157`. Checker/refusal fixtures
pass, and initial validation/preparation failures remain preserved. CPU guard
98 C, GPU observe-only and separate SSD bounds apply. See the
[host validation receipt](development/validation/core-phase-timing-2026-10-04.json).

## Point RAM and SSD follow-up integrated — 2026-10-04 UTC

Point checkpoint `b58394e` adds four completed original-weight AR/MTP cache
arms at P8192/TG32: RAM and explicit SSD reuse. Every cold/hot output stream
matches; the hot request restores all 8192 tokens with zero new prefill,
one corresponding cache hit and no SSD error. These are one-repetition,
same-process functional checks on source `9b109998`, separate from a restarted
process or independent quality qualification. SSD remains opt-in.

Root verifies the published subset: 46 archived members match their remote SHA
records; 16 container-home records remain outside the portable archive. Both
native CSVs reproduce exactly. Root's earlier single-category marker correction
moves only SVG x coordinates by +/-8 pixels; labels, scales and y coordinates
are unchanged. The initial byte-equality verifier refusal is retained, and no
published graphic or original evidence is rewritten. The focused supervision
and thermal fixtures pass 31/31 without a real GPU or model.
See the [integration receipt](development/validation/point-kv-cache-integration-2026-10-04.json)
and the [Point results](benchmarks/models/qwen3.8-flash-next/strix-point/README.md).

## Strix Point integration into the shared branch — 2026-10-04 UTC

The shared branch integrates Point checkpoint `618d9478` while preserving the
sampler CLI controls and the CPU-only thermal stop policy. `gfx1150` and
`gfx1151` provider targets are explicit and verified before model admission.
The retired LZ4 reader/dependency is removed; Zstandard stays default-ON and
DS4 runtime payloads retain their existing format.

The merged source passes 13/13 focused native CTest checks with ASan, UBSan and
LeakSanitizer, 34 synthetic supervision/build controls and the synthetic HIP
probe's error paths. No real GPU or model is opened by this integration check;
the local CPU peaks at 81.25 C. The integrated native reporter also reproduces
all four retained Point MTP/AR comparisons with exact input/output IDs and
unchanged phase metrics. Published artifacts stay byte-identical to their
recorded Point checkpoint; original logs retain their original whitespace.
Two initial verification command errors remain in local evidence.

The [integration receipt](development/validation/point-integration-2026-10-04.json)
binds source, actual exits and the distinction between offline checks and
historical GPU execution. The [Point platform page](benchmarks/models/qwen3.8-flash-next/strix-point/README.md)
remains the entry point for results. New GPU performance, target HTTP/vision
qualification and independent quality gates remain open.

## Integrated sampler/vision GPU qualification — 2026-10-04 UTC

The frozen `032d847` composition completes all **12/12** intended original-weight
functional arms on `.157`. AR ON/OFF each pass 32 assertions; MTP HTTP passes 12
and combined HTTP 20. Fifteen matched AR JSON generations retain exact outputs,
usage and logprobs after transport-ID normalization. MTP ON/OFF state streams
match; seven RAM/SSD probes verify **312** fresh/restored dispatch pairs and
**168** complete 248320-logit greedy AR frontiers. The direct-core probe confirms
stalled-loan peer progress, stable cancelled loans, no late publication and
in-flight PP/TG cancellation, with one device owner.

The initial old-checker `prompt_tokens_details` failure remains raw; the server
exits 0 and the failed supervisor/controller exit 1. Corrected R2 consumers come
from the exact historical arms that passed, without a runtime source change.
Nine continuation arms and controller/SSH exit 0. Independent quality, exact GPU
allocation peaks, live RNG-session resume and sampled/MTP/vision performance
remain open. The new parametrized benchmark below is outside these GPU binaries.

Closure at **00:47:22.850674 UTC** verifies 28 retired identities, empty KFD,
unchanged/free original leases, six unchanged model stats and both capsules.
All 129 collected remote artifacts hash-verify. Sampled peaks are CPU84.75/GPU86/
NVMe70.85 C, without CPU/SSD stop or observed crash; OS model-child threads range
1–52 including HIP/runtime workers. Full source/exit/state evidence is in the
[integrated receipt](development/validation/integrated-gpu-functional-2026-10-04.json)
and the [single platform page](benchmarks/models/qwen3.8-flash-next/strix-halo/README.md#integrated-runtime-functional-checks--october-4).
Root returns `.157` to Q2; the Point thread continues independent `.161` work.


## Reproducible sampled core benchmark — 2026-10-04 UTC

The native C shared-core benchmark now accepts temperature, top-p, a fixed seed
and frequency/presence penalties through the existing generation ABI. Nonzero
temperature requires an explicit seed; defaults remain greedy. JSON identities
and reports preserve all controls, and comparisons reject mismatched sampling
settings. Historical greedy streams retain their actual defaults.

The focused native benchmark contract passes **1/1** with ASan, UBSan and
LeakSanitizer. Its synthetic provider verifies all five options arrive unchanged,
including `INT64_MAX`; invalid/duplicate CLI arguments, a comparison between
identical outputs with different seeds and unsigned seed overflow are refused.
Local CPU peaks at 69.125 C with no thermal stop. These are NOT-INFERENCE checks;
matched original-weight sampler performance remains pending. Commands and source
witnesses are bound by the
[host receipt](development/validation/core-sampling-benchmark-2026-10-04.json).


## Clocked GPU follow-up complete — 2026-10-03 UTC

Frozen `15c6082` completes ten arms on `.157`: the missing 12288-depth pair,
then balanced fresh 1500 no-warmup and two-warmup process orders. All fifteen
measured pairs and five warmup pairs match physical inputs, confirmed output,
complete logit hashes and dispatch counters. At 12K, C17/control median PP is
1451.67/1454.54 and TG 25.814/25.827 token/s. Native reporting validates phase
bounds and forty sample durations; 90 collected remote artifacts hash-verify.

The 1500 slowdown appears in both builds: process medians split near 23 and
26.6 token/s. Lower measured GPU clocks accompany the slow band, including
after two warmups; this is correlation, not a causal diagnosis. Balanced pooled
TG is 25.55/25.03 without warmup and 25.19/25.17 after two warmups. Wide variation
keeps the stable performance gate open. Greedy GPU argmax excludes dense host
sampling from this measurement; the newer optimized/vision composition remains
separately pending. Full values, PP wait times, source maps and original attempts
are on the [platform benchmark page](benchmarks/models/qwen3.8-flash-next/strix-halo/README.md#clocked-follow-up-12k-depth-and-first-1500-tokens)
and [source-bound receipt](development/validation/clocked-gpu-followup-2026-10-03.json).

R3 records 1027 telemetry samples with CPU 95.75/GPU 98/NVMe 74.85 C peaks,
no CPU/SSD guard stop and no observed hardware crash. The old-policy R2 GPU 101
stop is retained. Closure at 23:30:28.038945 UTC verifies 26 retired identities,
empty KFD and unchanged/free original leases, model stats and capsules. Root
hands `.157` to Point for its separately coordinated predictor copy; no
restart/waiter remains.

The native C renderer offsets comparison markers at a single shared category
so matching series remain visible. Existing charts stay unchanged. Focused
ASan/UBSan/LeakSanitizer benchmark CTest 1/1 and three final exports pass; graphs
retain the same values, zero-based separate PP/TG scales and observed ranges.

## Integrated HIP compositions linked — 2026-10-03 UTC

The `.155` host builds three source-bound `gfx1151` providers and their clients:
sampler/decoder ON/ON, OFF/ON and ON/OFF. All nine configure/build steps exit 0,
and twelve masked identity/help commands pass without opening a model. Fifteen
linked client hashes and provider archives are bound by the
[link receipt](development/validation/c17-vision-link-2026-10-03.json).
These are NOT-INFERENCE checks; no new original-weight runtime qualification
is inferred. The private receipt assembler's incorrect completion-enum failure
is preserved and corrected; actual provider builds remain successful.

Five focused sensor/lifetime tests also pass. Legacy observation manifests remain
readable but their flag cannot remove the CPU guard in new helpers. GPU readings
remain observation-only. Build/test peaks are CPU92/GPU63/NVMe37.85 C, without
thermal stop. The separate `.157` clocked campaign still uses frozen `15c6082`,
and Point's newer-runtime qualification remains in its own target thread.

## CPU-only thermal stop policy — 2026-10-03 UTC

At the owner's correction, new qualification helpers stop at the selected CPU
ceiling and retain the independent SSD bounds; GPU temperatures are observed
without a software temperature stop. Three synthetic sensor/lifetime checks
pass, including GPU 101 C continuation, CPU98 C refusal, SSD separation and
owned-child retirement. No firmware, fan, power or clock setting changes.
The [guard receipt](development/validation/cpu-thermal-guard-2026-10-03.json)
binds the changed helpers, synthetic checks and actual command exits.

The first clocked 12288-depth C17 arm passes on `.157`, but the matched C++ arm
stops at GPU 101 C under the previous GPU98 policy, with CPU96.125 C. Its actual
failure remains preserved; no hardware crash is observed. The separately
prepared R3 continuation repeats all ten arms from unchanged frozen `15c6082`
binaries, with the corrected CPU98/GPU-observed policy and CPU<=60 C preflight.
This continuation remains in progress and is not a completed performance gate.

## Optimized sampler and vision decoder integrated — 2026-10-03 UTC

`feature/c17-sampling` combines sampler checkpoint `ba054bd` with vision
checkpoint `d42ac47`, preserving both histories and their qualified evidence.
The shared C17 sampler, weight decoder and reactive core remain separate from
HTTP. No model kernel, device ownership or scheduling policy changes in this
merge. Default-ON sampler and projector decoding retain explicit build controls.

The resulting source passes **44/44** native ASan/UBSan/LeakSanitizer tests and
**1/1** independently pinned decoder reference test: all 63,488 finite F16 and
16,252,928 Q8 values match at the BF16 rounding boundary. Exact inherited
sampler/glue/fixture hashes preserve the earlier 17-suite host result; it is
not rerun here. Six configure/build/test commands exit 0, with CPU/GPU/NVMe
peaks of 73.375/51/33.85 C and no thermal stop. The
[integration receipt](development/validation/c17-vision-integration-2026-10-03.json)
binds source, raw commands, sanitizer checks and their NOT-INFERENCE scope.
HIP compilation/linking and GPU retesting of this composition remain pending.

The existing Point thread reports the old-source ROCm10 fresh256 LIE arm closed
on `.161`: 2/2 samples, PP382.8545/TG9.7330 token/s, unchanged model stats,
21 verified remote-file hashes and restored router. Gufo fresh256 then starts
under a new target lease. Modern runtime qualification follows separately;
root performs no GPU work on either remote host during this integration.

## Dense-loop sampler follow-up — 2026-10-03 UTC

Mask-free greedy uses its own finite argmax loop; probability normalization now
divides independent entries before stable underflow compaction. This lets the
compiler optimize those loops without an optional mask branch or a moving output
cursor. API, ABI, allocation shape, reactive flow and GPU operations are unchanged.

ASan/UBSan/LeakSanitizer passes 17/17 host-reference suites, 1/1 native C contract
and three cost smokes. All 54 measured distributions/draws/RNG witnesses match
both controls and the original baseline; all 162 allocation scopes retire, and
all twelve measurement processes exit 0 and retire. Worst CPU case ratio versus
Gufo improves from 2.00 to **1.20**; median ratio stays **1.07**. Full-vocabulary
sine greedy measures 53.43/49.94 µs, unfiltered sampling 1549.44/1354.22 µs.
The cost gate remains open; these generated-logit CPU measurements do not
qualify original-weight GPU throughput. Measurement CPU/GPU/NVMe peaks are
84.125/55/33.85 C; no software thermal stop occurs. Original and both optimized
results remain separately bound in the
[sampler guide](development/C17-SAMPLING.md#first-cost-optimization),
[receipt](development/validation/sampling-dense-loops-2026-10-03.json) and full CSV.

Strix Point's ROCm10 old-source fresh128 pair now finishes 10/10 samples per
arm, with matching output IDs and full PP/TG frontiers. At 128K LIE/Gufo medians
are PP401.949/402.066 and TG10.061/10.062 token/s. The Point thread verifies
21 remote-file hashes per arm, exits 0 and owned closure, then starts a separately
admitted old-source fresh256 LIE arm. This is baseline `1877b03`, not qualification
of the newer integrated core or this sampler follow-up.

## First sampler cost optimization — 2026-10-03 UTC

The C17 ranked selector replaces full heapsort with bounded introsort, preserving
its deterministic logit/token order and heap fallback. Linear selection tracks
the maximum while preparing candidates; ordinary host greedy checks improvement
before eligibility. No API, ABI, reactive scheduling, worker or device change.

ASan/UBSan/LeakSanitizer passes **17/17** host-reference tests, **1/1** native
C contract and three cost smokes. The expanded full-vocabulary matrix contains
24 cases, including adversarial orderings. All 54 measured distribution/draw/RNG
witnesses match controls and the original baseline; all 162 allocation scopes
retire, twelve measurement processes exit 0 and retire. New control-relative
median case cost falls from **1.71 to 1.07**, but the worst ratio remains **2.00**.
The performance acceptance gate stays open, with original-weight sampled GPU
qualification still pending. Complete retained baseline/current values are in
the [optimization report](development/C17-SAMPLING.md#first-cost-optimization)
and [source-bound receipt](development/validation/sampling-optimization-2026-10-03.json).
Measurement CPU/GPU/NVMe peaks are 77.875/52/34.85 C, with no guard stop.

The existing Strix Point thread runs its missing ROCm10 fresh128 baseline on
`.161` using the old qualified source `1877b03`; this is not qualification of
the newer runtime. Separately it commits current core/MTP/vision/gfx1150
integration at `b8a3c73` and frozen `bea50d3` phase-clock/QA integration at
`a049bcc`, retaining target-specific receipts and the central benchmark page.
Point's next runtime GPU window remains separately admitted; root accesses
neither remote GPU during this CPU increment.

## Dense sampler host cost measured — 2026-10-03

The editing Strix Halo `.155` completes the host-only 54-case sampler matrix:
three generated-logit vocabulary sizes, three shapes and six configurations.
Pristine official Gufo, C17 and the same-layout OFF control use three balanced
process orders, seven measured repetitions each. All distributions, draws and
RNG witnesses match. Expanded ASan/UBSan/LeakSanitizer CTest passes **17/17**;
three additional cost-probe sanitizer smokes pass. All twelve measurement
children exit 0 and retire, and all 162 counted allocation scopes reach zero.

The **cost acceptance gate fails**: C17/reference per-call time ratios range
from 0.55 to 3.43, with a median across cases of 1.71. Several full-vocabulary
filters regress; top-k often reduces allocations. Complete values, exact scope
and reproducible native commands are in the
[sampler cost section](development/C17-SAMPLING.md#host-cost-and-temporary-allocations)
and its [receipt](development/validation/sampling-cost-2026-10-03.json).
These CPU operator measurements perform no model forward or GPU execution.
They do not attribute the earlier 1500-token GPU regression, whose ordinary
greedy path retains device argmax. Runtime source is unchanged in this checkpoint.

Measurement peaks are CPU82.5/GPU55/NVMe34.85 C; the sanitizer suite peaks at
CPU94.5 C. No thermal stop or hardware shutdown occurs. The failed preparation
argument and initial compiler warnings remain retained; corrected builds and
all validation commands exit 0. No GPU run/staging on `.157` occurs: its Q2
reservation remains in force. The owner separately resumes the existing Strix
Point thread for `.161` qualification and current-core integration; historical
target results remain bound to their original binaries.

## Clocked performance follow-up prepared — 2026-10-03

Ten arms are prepared locally at frozen runtime checkpoint `15c6082`: the
missing 12288-token depth pair at capacity 133760, then balanced C17/control
orders for fresh PP1500/TG128 at capacity 262144. Four arms use no model warmup
and four use two warmups, with three measured samples each. First and later
samples remain distinct; OS file cache is uncontrolled, so these are not
cold-file measurements.

The private supervisor adds read-only optional GPU clock/power and CPU-frequency
snapshots with monotonic bounds, correlated with the new native PP/TG clocks.
GPU-masked build-info/help exits are zero and all ten capsule manifests verify.
**No GPU run, model load/hash or remote staging occurs; admission remains
disabled until a new Q2 handover.** The
[preparation receipt](development/validation/performance-followup-preparation-2026-10-03.json)
binds source, binaries, commands and the planned acceptance checks. The earlier
1500-token slowdown remains unresolved.

The combined published CSV duration headers now correctly say `seconds` rather
than `ns`. All 17 rows and their data bytes remain unchanged; 204 duration cells
match the native summaries. Raw measurements and figures remain unchanged.

## Benchmark phase clocks and durations — 2026-10-03

Native direct benchmarks now record monotonic prefill/decode bounds and a
wall-clock sample start for correlation with supervised telemetry. They exclude
prefix construction, frontier copies and flow setup from the timed calls. The
C report exports duration distributions in seconds to JSON/CSV, validates full
ordered clock tuples and exact duration differences, and retains support for
older raw data without a clock declaration. This is host timing, not a GPU
kernel timeline or preemption claim.

Focused ASan/UBSan/LeakSanitizer `native-benchmark-contract` passes, including
four malformed clock cases, old-evidence compatibility and existing HTTP/SSD
fixtures. Both pinned HIP compositions link with GPU visibility masked. The
first build's incorrect helper name/exit 1 is preserved and corrected. Re-export
of all three original-weight datasets adds duration columns without changing
any existing witness, comparison or SVG/PNG hash. The
[source-bound receipt](development/validation/bench-phase-clocks-2026-10-03.json)
records CPU-only validation; this does not resolve the 1500-token GPU slowdown.

## Local GPU thermal benchmark — 2026-10-03

At the owner's request, the editing ASUS ROG Flow Z13 `.155` completes eight
consecutive rocBLAS FP16 GEMM4096 trials, each with five warmups and 4000 timed
iterations. All child/supervisor exits are 0. The campaign lasts **201.79 s**,
including **185.99 s** in the timed GEMM loops. Median throughput is
**23.766 TFLOP/s**; the last trial is **0.79%** below the first. Sampled peaks
are **CPU93.5/GPU97/NVMe38.85 C**, with no 98 C guard stop, hardware shutdown
or deterioration observed. The last trials generally remain around 92–94 C
under load, with brief GPU peaks. Both existing fan curves select PWM255 from
60 C; loaded fans run at 8700–8900 RPM. No settings change during the benchmark.

This is a **synthetic matrix workload**, not LIE inference or a model token-rate
comparison. Eight short processes do not qualify longer steady-state operation;
there is no controlled comparison with earlier fan settings. The independent
local lease is acquired afresh for each arm. All sixteen owned process identities
retire, KFD is empty and the original lease inode is unchanged/free afterwards.
The [thermal receipt](development/validation/local-thermal-155-2026-10-03.json)
binds every trial, 380 sensor samples, OS thread counts (up to five), raw hashes
and temperature/fan/throughput plots. Raw files stay under local `evidence/`.

## Strix Point core integration checkpoint — 2026-10-03/04

The sealed `.161` ROCm 10 r5 binary now passes original-weight direct C-core
reactive gates in AR (1,500 physical tokens/TG32) and MTP (8,192/TG128).
In each, a borrowed output loan and its credits remain held while a peer
completes its full budget; the held job then cancels and all borrowed bytes
stay unchanged. MTP drafts 100 and accepts 64 at 8K. The retained short MTP
gate fails its accepted-draft condition with zero accepted despite completed
and cancelled counters both equalling one. The same r5 binary passes direct
Q8-projector vision AR and MTP+vision on `.161`: both use the same 92 physical
input tokens and 13 output IDs; MTP accepts 8 drafts. These are functional
GPU checks, not an internal-forward or statistical throughput claim. The
[full Point gate report](benchmarks/models/qwen3.8-flash-next/strix-point/README.md#direct-reactive-core-and-q8-vision-gates)
retains all seven r4/r5 windows, real failures, prefill/decode values,
79/79 fresh remote SHA checks and raw evidence. All windows restore the
authorized router, preserve model/sidecar stat and release their lease.

The original Q8 vision projector was copied directly from `.157` to `.161`
after the coordinated root release, with no source transfer or WAN download.
The destination's complete 616,703,104 bytes match the pinned SHA-256; source
stat identity is unchanged. The copy controller, sender and receiver exit 0,
and the temporary SSH agent is retired. Final `.157` postflight finds KFD
empty and all four established leases unchanged/free; `.161` has only its
restored router PID 108508 in KFD, no LIE container and its private lease
free. The [copy receipt](development/validation/point-projector-copy-2026-10-04.json)
and [destination plan](../config/models-161-projector.plan.json) bind the
source, destination and release. Ownership was returned to Q2/WMMA; the
later r5 vision inference gates are reported above.

The native C17 core benchmark now has an opt-in `--reactive-probe` functional
mode: a direct client keeps one output loan and its credits withheld while a
second row completes, then cancels the held row and verifies the borrowed text
and retirement counters. It uses no HTTP and reports no speedup. The focused
synthetic contract passes in normal and ASan/UBSan builds; the sandboxed first
CTest attempt was blocked by loopback permissions and is retained in ignored
evidence. The later r5 version compares the entire borrowed text, waits for
worker-wide counters after semantic terminals and has passed the original-
weight GPU gates above.

The Point `modern-http` GPU gate now passes for both AR and explicit MTP in
separate lease-supervised ROCm 10 Distrobox windows. It starts the
original-weight server with fresh requests, verifies `/v1/models`, Chat
Completions and Responses in JSON/SSE and records each wire exchange.
Both paths return `4` across both APIs and projections. The backend reports
`synthetic=false`, with `mtp=false` for AR and `mtp=true` for the predictor
run. All 34 collected remote files hash-verify; both servers, children and
supervisors exit zero, model/predictor identities are unchanged and each
window restores the named service and releases the lease. The
[Point HTTP receipt](benchmarks/models/qwen3.8-flash-next/strix-point/README.md#original-weight-http-ar-and-mtp-gates)
includes the raw requests/responses, temperatures and postflight. These are
short loopback functional requests inside the container: external Pi-agent
access, long-context HTTP, tools, and served performance remain untested on
`.161`.

The separate opt-in SSD restart gate now passes AR and MTP with original
weights. Each arm starts a cold direct-core process at 8,192 physical prompt
tokens, persists its KV and exits; a distinct process in the same admitted
Distrobox reads the same SSD directory. Both hot processes restore all 8,192
tokens with zero prefill, one SSD hit, zero SSD errors and exact cold/hot
output IDs. AR and MTP physical/output IDs also match each other; MTP accepts
18 drafts in both processes. Both windows preserve model identities and
restore/release service and lease. The [SSD restart report](benchmarks/models/qwen3.8-flash-next/strix-point/README.md#ssd-kv-reuse-across-inference-processes)
contains 42/42 remote-file SHA checks, raw archive, telemetry and one-sample
decode/wall values. Final `.161` postflight finds only the restored router
PID 106168 in KFD, no LIE container and the private lease free. This qualifies
cross-process persistence, not crash recovery or statistical performance.

`feature/strix-point-ud` integrates the `feature/vision-q8` C17 core, MTP and
vision contracts while retaining explicit `gfx1150` build receipts and HIP
device admission. The provider build now selects and records one HIP target;
the server verifies the receipt, cache and target-policy hash before link.
The local full C/HTTP build passes. Headless CTest passes 25/25 and focused
ASan/UBSan tests pass 26/26. The legacy HTTP suite passes 69/71 on its first
unrestricted run; its two stale expectations rejected supported OpenAI options.
After updating those expectations, both focused tests pass. The initial
sandboxed 21 HTTP failures were loopback-denied fixtures, not serving results.
The first long-context ROCm 10 `.161` baseline remains a separately pinned
pre-integration binary; new runtime/device qualification is pending.
Its paired fresh-prompt ROCm 10 LIE/Gufo arms now pass 10/10 samples each from
1,500 through 131,072 physical tokens, with identical physical input IDs,
outputs and full prefill/decode frontiers at every pair. Both child/supervisor
exits are 0; 21/21 files per arm match remote SHA-256, models are unchanged,
`llama-router.service` is restored and the private lease released. At 128K,
LIE/Gufo median prefill is 401.949/402.066 tok/s and decode is
10.061/10.062 tok/s. The [Point results page](benchmarks/models/qwen3.8-flash-next/strix-point/README.md)
contains full values, charts, raw bundles and the offline verifier.
The subsequent frozen `bea50d3` merge adds validated prefill/decode phase
clocks to the native benchmark and report. On the Point branch, the C/HTTP
rebuild and five focused native/HTTP/provider tests pass; the ASan/UBSan
native/provider subset passes 2/2. The
[Point benchmark page](benchmarks/models/qwen3.8-flash-next/strix-point/README.md)
links the complete already-published direct results and keeps new-runtime
measurement pending.
The additional CPU-qualified C17 sampler commits `ff91544` and `ba054bd`
are now merged for the future Point runtime. The Point full C/HTTP rebuild and
five focused CTest cases pass; the corresponding ASan/UBSan subset passes 4/4.
These host checks do not qualify the optimized sampler on `gfx1150`. The
`fresh-256k` paired baseline on the unchanged `1877b03` binary passes 2/2
samples per arm from 258,794 physical tokens through 128 output tokens.
LIE/Gufo physical IDs, output IDs and full prefill/decode frontiers match.
Median LIE/Gufo prefill is 382.855/380.717 tok/s and decode is
9.733/9.715 tok/s. The [Point results page](benchmarks/models/qwen3.8-flash-next/strix-point/README.md)
contains min/max, durations, charts, verified raw bundles and native C17
reproduction commands. Both leases, service states and 21/21 remote files
per arm were verified after collection.
The new ROCm 10 build path is prepared as a CMake helper under the existing
`.161` lease runner. It seals a separate persistent source capsule, selects
`gfx1150` with target-bound provider receipts, leaves GPU devices and network
out of the compiler container, and records configure/link exits. The local
campaign control fixture passes 24/24; a direct host invocation correctly
refuses without the admitted build window. Its first actual device-free `.161`
build completed the gfx1150 provider stage, then failed CMake configure on
missing `lz4.h` in the pinned Fedora image. Child/supervisor exit 1, exact
configure error and source remain in ignored persistent evidence; the service
was restored and lease released at 23:24:26.943766 UTC. LZ4 belonged to a
removed reader, so current source removes codec 1 and the LZ4 build/link
requirement while retaining default-ON Zstandard compression. A clean core
ASan/UBSan build has no LZ4 cache or direct dynamic dependency; focused
checkpoint/store/reactive CTest passes 3/3 with leak detection disabled in
this ptrace sandbox. The first LeakSanitizer attempt failed because LSan
cannot operate under ptrace, not because of a test assertion.
The predictor has since been copied directly from `.157` to `.161`: all
2,786,568,256 bytes match the recorded SHA-256, the source inode/stat is
unchanged, both private leases were released, and both services restored.
The second modern build (with LZ4 removed) again passed its provider stage;
configure failed with exit 1 solely because the pinned Fedora image lacks
`zstd.h`. Its remote logs were copied and SHA-256 checked locally; child and
supervisor both exited 1, `llama-router.service` was restored, and the lease
released at 23:46:01.238465 UTC. The next isolated capsule will stage the
host's Zstandard 1.5.7 header pair and BSD license against the image's
matching 1.5.7 runtime library, preserving compression ON. Modern GPU MTP/AR
qualification was pending that build.

The sealed ROCm 10 modern r3 build from `9b109998` then passed the `gfx1150`
provider, configure and link stages with matching staged Zstandard 1.5.7
headers/license and checkpoint compression ON. Its child/supervisor exits are
zero, binary and remote-file SHA-256 inventories match, the named service was
restored and the lease released at 00:01:00.364029 UTC on 2026-10-04. The
resulting `synapse-lie-bench` needs `libzstd.so.1` and has no ELF dependency on
LZ4. On `.161`, four matched original-weight GPU MTP/AR pairs now pass at
P1500/C1/TG32, P8192/C1/TG128, P131072/C1/TG128 and P8192/C2/TG128. All
eight qualified children and supervisors exit zero, every pair has equal
physical input IDs and full output IDs, all model/predictor stat identities
remain unchanged, and each window restores the authorized service and frees
the private lease. The [Point MTP GPU report](benchmarks/models/qwen3.8-flash-next/strix-point/README.md#modern-c17-core-mtp-vs-ar-on-the-gpu)
contains full prefill/decode/complete-wall values, native C17 graphs, a
collection receipt and raw archives. An initial AR control inference completed
but its supervisor failed on a stale KFD PID; that failure is retained, and a
bounded ownership-aware retirement fix passes 26/26 campaign fixtures before
the fresh successful AR rerun. The native C17 reporter now exports core decode
rates, with focused normal and ASan/UBSan tests passing. Final `.161` postflight
finds the service active, only its PID in KFD, no LIE container and the private
lease free. These are one-repetition direct-core results; served HTTP and
statistically replicated MTP performance remain open.

Four further `.161` original-weight gates pass the modern C17 core's MTP and
AR paths with one cold and one hot 8,192-token/32-output request each. Both
RAM-cache arms restore all 8,192 tokens from RAM; both explicitly enabled
SSD-cache arms restore all 8,192 tokens from SSD, with no new prefill and zero
SSD errors. Every cold/hot output sequence matches across MTP and AR. The
[Point cache report](benchmarks/models/qwen3.8-flash-next/strix-point/README.md#ram-and-opt-in-ssd-kv-reuse-with-mtp)
includes exact decode/wall values, graphs, raw receipts and offline replay.
All four remote inventories pass 62/62 SHA-256 checks in total; all
children/supervisors exit zero, models remain unchanged and each private GPU
window restores the named service and releases its lease. The last `.161`
postflight sees only the restored router PID 101236 in KFD, no LIE container
and the private lease free. SSD remains opt-in; one hot sample per arm does not
establish steady-state performance.

## Original-weight vision, MTP and reactive continuation — 2026-10-03

Frozen checkpoint `bec0955` passes all seven declared functional arms on `.157`:
combined HTTP, combined RAM state, MTP SSD write/read, combined SSD write/read
and direct-core backpressure/cancellation. HTTP passes **20 assertions**, including
red/blue semantics, image-scope isolation, same-image reuse and controlled AR
fallback. The five state arms compare **228 paired dispatches** with full logits,
confirmed tokens and counters; **120 greedy frontiers** also match a fresh forced
target-AR control from the same provider. Sampled text includes three rejected
drafts. SSD reads run in new processes with freshly admitted model identities.

The direct-core arm completes a peer while another row is stalled at eight
confirmed tokens, preserves its borrowed output through cancellation, and
observes in-flight prefill/decode cancellation without late output. It has one
device owner, no HTTP layer and no additional inference worker. This is
functional evidence, not a speedup measurement or independent quality oracle.

Three first attempts fail in private verification code: an omitted optional
zero-cache usage field, missing required DS4 prompt-text metadata, and demand
renewal after producer closure. Corrected consumers also retain cancellation
offsets after a borrowed block. An untraced ASan/UBSan/LeakSanitizer fixture
qualifies the consumer correction; the frozen runtime/numerical source is
unchanged. Failed commands, exits and original artifacts remain preserved.

The window closes at **20:44:19.723712 UTC**: 50 collected files hash-verify,
20 owned PID/start identities retire, KFD is empty, the four original leases
are unchanged and released, and six model file identities and all capsules
remain unchanged. Sampled peaks are CPU80.625/GPU82/NVMe66.85 C; no thermal stop
occurs. The [GPU receipt](development/validation/vision-mtp-gpu-2026-10-03.json)
binds source, commands, exact comparisons and release. Independent quality,
image cancellation/fault handling, allocation-exact fit and matched MTP/vision
performance remain open.

## Vision projector storage admission — 2026-10-03

`feature/vision-q8` starts from `develop` and advances to checkpoint `b72f4e8`
in a persistent worktree. The initial original-weight combined arm refuses the
available Q8 projector before READY: pinned vision requires BF16 dense tensors.
Metadata-only inspection finds 83 Q8_0, 27 F16 and 224 F32 tensors; the F16
feed-forward down-projections have a 4304-wide input, not a Q8 block multiple.
No original model values were converted or changed during this inspection.

The shared C17 decoder now handles both storage types during the first GPU
upload, one bounded staging tensor at a time. It synchronizes each borrowed
buffer before retirement; GPU kernels, reactive device ownership and the DS4
state format remain unchanged. `LIE_VISION_WEIGHT_DECODE` defaults ON with an
explicit BF16-only OFF control. New provider receipts bind the exact edits,
owned source, selected option, recipe and archives.

ASan/UBSan/LeakSanitizer native tests pass **44/44**. An independently fetched
official Gufo control matches all **63,488** finite F16 values and **16,252,928**
Q8 values at the BF16 rounding boundary. Providers ON/OFF and HIP clients build;
these are **NOT-INFERENCE** checks. The first failed admission remains preserved
in `gpu-functional-f0-r4/combined-http` on the sampling worktree. Original-weight
vision/state/cache/SSD/resource qualification remains open, while the separate
sampling performance campaign continues on `.157` from its frozen checkpoint.
The [host receipt](development/validation/vision-weight-decode-2026-10-03.json)
binds source, providers, command exits and CPU thermal observations.

## Dense-loop sampler follow-up — 2026-10-03 UTC

Mask-free greedy uses its own finite argmax loop; probability normalization now
divides independent entries before stable underflow compaction. This lets the
compiler optimize those loops without an optional mask branch or a moving output
cursor. API, ABI, allocation shape, reactive flow and GPU operations are unchanged.

ASan/UBSan/LeakSanitizer passes 17/17 host-reference suites, 1/1 native C contract
and three cost smokes. All 54 measured distributions/draws/RNG witnesses match
both controls and the original baseline; all 162 allocation scopes retire, and
all twelve measurement processes exit0 and retire. Worst CPU case ratio versus
Gufo improves from 2.00 to **1.20**; median ratio stays **1.07**. Full-vocabulary
sine greedy measures 53.43/49.94 µs, unfiltered sampling 1549.44/1354.22 µs.
The cost gate remains open; these generated-logit CPU measurements do not
qualify original-weight GPU throughput. Measurement CPU/GPU/NVMe peaks are
84.125/55/33.85 C; no software thermal stop occurs. Original and both optimized
results remain separately bound in the
[sampler guide](development/C17-SAMPLING.md#first-cost-optimization),
[receipt](development/validation/sampling-dense-loops-2026-10-03.json) and full CSV.

Strix Point's ROCm10 old-source fresh128 pair now finishes 10/10 samples per
arm, with matching output IDs and full PP/TG frontiers. At 128K LIE/Gufo medians
are PP401.949/402.066 and TG10.061/10.062 token/s. The Point thread verifies
21 remote-file hashes per arm, exits0 and owned closure, then starts a separately
admitted old-source fresh256 LIE arm. This is baseline `1877b03`, not qualification
of the newer integrated core or this sampler follow-up.

## First sampler cost optimization — 2026-10-03 UTC

The C17 ranked selector replaces full heapsort with bounded introsort, preserving
its deterministic logit/token order and heap fallback. Linear selection tracks
the maximum while preparing candidates; ordinary host greedy checks improvement
before eligibility. No API, ABI, reactive scheduling, worker or device change.

ASan/UBSan/LeakSanitizer passes **17/17** host-reference tests, **1/1** native
C contract and three cost smokes. The expanded full-vocabulary matrix contains
24 cases, including adversarial orderings. All 54 measured distribution/draw/RNG
witnesses match controls and the original baseline; all 162 allocation scopes
retire, twelve measurement processes exit0 and retire. New control-relative
median case cost falls from **1.71 to 1.07**, but the worst ratio remains **2.00**.
The performance acceptance gate stays open, with original-weight sampled GPU
qualification still pending. Complete retained baseline/current values are in
the [optimization report](development/C17-SAMPLING.md#first-cost-optimization)
and [source-bound receipt](development/validation/sampling-optimization-2026-10-03.json).
Measurement CPU/GPU/NVMe peaks are 77.875/52/34.85 C, with no guard stop.

The existing Strix Point thread runs its missing ROCm10 fresh128 baseline on
`.161` using the old qualified source `1877b03`; this is not qualification of
the newer runtime. Separately it commits current core/MTP/vision/gfx1150
integration at `b8a3c73` and frozen `bea50d3` phase-clock/QA integration at
`a049bcc`, retaining target-specific receipts and the central benchmark page.
Point's next runtime GPU window remains separately admitted; root accesses
neither remote GPU during this CPU increment.


## Dense sampler host cost measured — 2026-10-03

The editing Strix Halo `.155` completes the host-only 54-case sampler matrix:
three generated-logit vocabulary sizes, three shapes and six configurations.
Pristine official Gufo, C17 and the same-layout OFF control use three balanced
process orders, seven measured repetitions each. All distributions, draws and
RNG witnesses match. Expanded ASan/UBSan/LeakSanitizer CTest passes **17/17**;
three additional cost-probe sanitizer smokes pass. All twelve measurement
children exit0 and retire, and all 162 counted allocation scopes reach zero.

The **cost acceptance gate fails**: C17/reference per-call time ratios range
from 0.55 to 3.43, with a median across cases of 1.71. Several full-vocabulary
filters regress; top-k often reduces allocations. Complete values, exact scope
and reproducible native commands are in the
[sampler cost section](development/C17-SAMPLING.md#host-cost-and-temporary-allocations)
and its [receipt](development/validation/sampling-cost-2026-10-03.json).
These CPU operator measurements perform no model forward or GPU execution.
They do not attribute the earlier 1500-token GPU regression, whose ordinary
greedy path retains device argmax. Runtime source is unchanged in this checkpoint.

Measurement peaks are CPU82.5/GPU55/NVMe34.85 C; the sanitizer suite peaks at
CPU94.5 C. No thermal stop or hardware shutdown occurs. The failed preparation
argument and initial compiler warnings remain retained; corrected builds and
all validation commands exit0. No GPU run/staging on `.157` occurs: its Q2
reservation remains in force. The owner separately resumes the existing Strix
Point thread for `.161` qualification and current-core integration; historical
target results remain bound to their original binaries.

## Clocked performance follow-up prepared — 2026-10-03

Ten arms are prepared locally at frozen runtime checkpoint `15c6082`: the
missing 12288-token depth pair at capacity 133760, then balanced C17/control
orders for fresh PP1500/TG128 at capacity 262144. Four arms use no model warmup
and four use two warmups, with three measured samples each. First and later
samples remain distinct; OS file cache is uncontrolled, so these are not
cold-file measurements.

The private supervisor adds read-only optional GPU clock/power and CPU-frequency
snapshots with monotonic bounds, correlated with the new native PP/TG clocks.
GPU-masked build-info/help exits are zero and all ten capsule manifests verify.
**No GPU run, model load/hash or remote staging occurs; admission remains
disabled until a new Q2 handover.** The
[preparation receipt](development/validation/performance-followup-preparation-2026-10-03.json)
binds source, binaries, commands and the planned acceptance checks. The earlier
1500-token slowdown remains unresolved.

The combined published CSV duration headers now correctly say `seconds` rather
than `ns`. All 17 rows and their data bytes remain unchanged; 204 duration cells
match the native summaries. Raw measurements and figures remain unchanged.

## Benchmark phase clocks and durations — 2026-10-03

Native direct benchmarks now record monotonic prefill/decode bounds and a
wall-clock sample start for correlation with supervised telemetry. They exclude
prefix construction, frontier copies and flow setup from the timed calls. The
C report exports duration distributions in seconds to JSON/CSV, validates full
ordered clock tuples and exact duration differences, and retains support for
older raw data without a clock declaration. This is host timing, not a GPU
kernel timeline or preemption claim.

Focused ASan/UBSan/LeakSanitizer `native-benchmark-contract` passes, including
four malformed clock cases, old-evidence compatibility and existing HTTP/SSD
fixtures. Both pinned HIP compositions link with GPU visibility masked. The
first build's incorrect helper name/exit1 is preserved and corrected. Re-export
of all three original-weight datasets adds duration columns without changing
any existing witness, comparison or SVG/PNG hash. The
[source-bound receipt](development/validation/bench-phase-clocks-2026-10-03.json)
records CPU-only validation; this does not resolve the 1500-token GPU slowdown.

## Local GPU thermal benchmark — 2026-10-03

At the owner's request, the editing ASUS ROG Flow Z13 `.155` completes eight
consecutive rocBLAS FP16 GEMM4096 trials, each with five warmups and 4000 timed
iterations. All child/supervisor exits are 0. The campaign lasts **201.79 s**,
including **185.99 s** in the timed GEMM loops. Median throughput is
**23.766 TFLOP/s**; the last trial is **0.79%** below the first. Sampled peaks
are **CPU93.5/GPU97/NVMe38.85 C**, with no 98 C guard stop, hardware shutdown
or deterioration observed. The last trials generally remain around 92–94 C
under load, with brief GPU peaks. Both existing fan curves select PWM255 from
60 C; loaded fans run at 8700–8900 RPM. No settings change during the benchmark.

This is a **synthetic matrix workload**, not LIE inference or a model token-rate
comparison. Eight short processes do not qualify longer steady-state operation;
there is no controlled comparison with earlier fan settings. The independent
local lease is acquired afresh for each arm. All sixteen owned process identities
retire, KFD is empty and the original lease inode is unchanged/free afterwards.
The [thermal receipt](development/validation/local-thermal-155-2026-10-03.json)
binds every trial, 380 sensor samples, OS thread counts (up to five), raw hashes
and temperature/fan/throughput plots. Raw files stay under local `evidence/`.

## Original-weight GPU continuation — 2026-10-03

After the Q2 thread's verified release at 17:37:05 UTC, root takes the `.157`
window under fresh four-lease admission for each arm. Checkpoint `f0f58b3`
passes **32 AR HTTP assertions** with the original UD weights: new sampling
controls, strict schemas/functions, correlated tools, retained Chat/Responses,
stream/replay/cursors, cancellation, truncation and RAM reuse. Child/helper
exit 0. Sampled peaks are CPU74.375/GPU76 C. This is same-provider functional
evidence, not an independent numerical or performance qualification.

The first two attempts preserve verifier failures: nullable logprobs when a
stop hides every token, and the deliberately rejected over-context request
incrementing `failed`. Their servers retire cleanly; no runtime change masks
these outcomes. The successful AR arm is `gpu-functional-f0-r3/ar-http`.

The following MTP arm confirms completed TG128, 95 proposed/accepted tokens
and controlled target-AR fallback, then fails on long-prefix capture. The UD
metadata declares **48 trunk blocks and no nextn field**, while a separate Q8
predictor is actually admitted. The adapter inferred zero predictor layers
from trunk metadata. Its state geometry now binds the admitted predictor;
the C17 codec, cache policy and DS4 payload framing remain unchanged. The
original failed request/exit remain in `gpu-functional-f0-r3/mtp-http`.

The corrected MTP HTTP/cache arm passes **12 assertions**, including actual
2669-token prefix reuse. A C17 probe compares all 248320 logits and confirmed
tokens/counters across fresh/restored predictor state: greedy 24 dispatches,
47/47 accepted proposals; sampled 18 dispatches, 32/35 accepted. All restored
frontiers match exactly, including three rejected proposals and cancellation.
The destination sampler is fresh; this is prefix continuation, not live RNG
session restoration. Peak CPU71.625/GPU61 C for the state probe.

The legacy C++ sampler HTTP control also passes **32 assertions**; fifteen
matched JSON cases have identical output, usage and logprobs. Client timings
from these functional arms are not a paired performance result. Combined
vision refuses the available Q8 projector before READY because the pinned
encoder requires BF16 dense weights. The failed admission is retained; a
separate `feature/vision-q8` checkpoint `bec0955` prepares C17 upload decoding.

The [functional receipt](development/validation/c17-gpu-functional-2026-10-03.json)
binds all eight passed/failed arms, observed OS threads, temperatures and raw
artifact hashes. The [declared protocol](development/protocols/C17-GPU-PROTOCOL.md)
keeps matched performance, process-restarted MTP/vision SSD, real reactive peer
progress and independent numerical/quality gates separate. All six declared
C17/C++ performance arms finish with child/helper exits 0 through full fresh
prefill at 258794 tokens. Their thirty collected result files SHA-verify. All
46 measured and 12 warmup pairs have identical physical IDs, outputs, counters
and full frontier hashes. Native C figures, CSV/JSON and raw compressed JSONL
are now in the single [Strix Halo benchmark page](benchmarks/models/qwen3.8-flash-next/strix-halo/README.md).
TG differs by less than 1% except the retained un-warmed 1500-token point,
which loses 16.64% and keeps the performance gate open. The missing 12288 depth
and exact Gufo HTTP/MTP protocols remain explicit. The `.157` window releases
at **19:41:04 UTC**: all 28 owned process identities retire, KFD is empty, the
four original leases are unchanged/free, and six model stat witnesses and all
used source capsules are unchanged. The controller exits 0; there is no observer,
queued restart or waiter. The prepared vision/SSD/reactive continuation has not
run. No source in `/tmp`, DS4 modification, remote build, installation or tuning
occurs.

## C17 dense sampling extraction — 2026-10-03

`feature/c17-sampling` starts from `develop` in a persistent worktree and
incorporates checkpoint `8992c0b`. The shared C17 library now owns dense greedy
selection, penalties/bias, top-k/top-p/min-p, normalization and random draws.
The verified provider enables it by default; `LIE_C17_SAMPLING=OFF` retains the
C++ control. HTTP and direct clients use the same core. Reactive demand,
cancellation, batching, MTP and the one device-owner worker are preserved.
Sampler ABI is **1**; existing executor/request/generation/state ABIs are unchanged.
History, grammar compilation, compact speculative distributions and model
forward remain delegated; this is the first slice of the autonomous C executor.
See [ownership and build instructions](development/C17-SAMPLING.md).

Final ASan/UBSan/LeakSanitizer suites pass **43/43** native tests, **18/18**
headless MTP/vision-OFF tests and **14/14** host reference tests. Complete
distribution/draw/RNG witnesses agree for **1200** configurations against the
independently fetched official Gufo pin and the legacy control, another **1200**
biased configurations against the prior C++ bias variant, and **12** complete
248320-logit synthetic rows. The pinned HIP provider and server/bench compile
and link. A symbol/metadata audit confirms the direct Gufo reference excludes
the C selector while server and LIE bench include it. These checks are
**NOT-INFERENCE**; no original weights or GPU execution were used.

Read-only admission found `.157` reserved by an enclosing Q2 campaign, so this
turn took the owner's development fallback without a lease or GPU/model access.
The [source-bound receipt](development/validation/c17-sampling-2026-10-03.json)
preserves final identities, actual failures/exits and thermal evidence. Two
owned build children were stopped by a **95 C software guard**; no hardware
shutdown or deterioration was observed. Later serialized provider builds used
the owner's 98 C CPU allowance and stayed below it; there was no fan/clock/power
tuning. Original-weight continuation/cache correctness and matched performance
qualification on `.157` remain open. No speedup is claimed.

## OpenAI generation and retained responses — 2026-10-03

`feature/openai-completion` starts from `develop` and incorporates semantic core
checkpoint `a399052` in a persistent worktree. The C17 core now owns stop matching,
probability normalization, structured-output validation, multiple-choice job
admission, bounded response records/history, oldest-turn context truncation and
an immutable semantic journal. Chat and Responses add token bias/logprobs,
JSON/schema output, strict functions, stored CRUD/pagination, conversation
continuation, background cancellation and Responses stream replay from a cursor.
[Usage](guides/USAGE.md#generation-controls-and-stored-responses) gives HTTP
commands on port 8000; [API coverage](reference/OPENAI-REACTIVE.md) records limits.
Request ABI is **5**, generation ABI **2**, executor ABI remains **2**.

The native ASan/UBSan/LeakSanitizer suite passes **42/42**. Final focused HTTP,
semantic and native-bench checks pass **3/3** after preserving ordinary wire fast
paths; a final headless quota/ownership check also passes. The protocol-independent
MTP/vision-OFF configuration passes **17/17**, then passes the final changed
headless test. The headless build discovers/links no HTTP libraries; the default
HTTP and core builds require no Python. Native fixtures cover split-token stops, suppressed stop logprobs, bias, nested function
schemas, strict canonical calls, multiple choices and aggregate SSE usage,
retention quotas/TTL, metadata filters, stored history, automatic truncation,
live/replayed/resumed response streams and idempotent cancellation. The OpenAI
HTTP campaign runs both AR and a synthetic MTP13 provider; background streams
continue after the creating client disconnects, including credit handover when
a write finishes after that disconnect.

The official Gufo pin was fetched independently and rebuilt with the exact
`sampling-edits.json` state variant. HIP server and bench compile/link; host-only
sampler/grammar and template checks pass **2/2**. Constraint compilation/masking
remain delegated C++ through neutral C controls; this is not an autonomous C
model executor. No inference thread was added. Explicit stop/bias/logprob requests
use target AR steps; ordinary requests preserve MTP and bias-free sampler/wire
fast paths. No measured performance gain or parity is claimed.

The [source-bound receipt](development/validation/openai-completion-2026-10-03.json)
preserves command exits, failures, source/provider identities and local thermal
telemetry. The observed CPU peak is **93.375 C** under a 95 C owned-child guard;
there was no shutdown, deterioration or fan/clock/power tuning. No original-weight
model load/hash/conversion, GPU execution, remote build or performance campaign
occurred. Original-weight controls, strict-output/MTP numerical behavior and
resource/performance qualification on `.157` remain pending under coordination.
Audio/video/embedding executors, hosted tools, named Conversations and compaction
are outside the implemented serving surface; unknown fields fail explicitly.

## Shared core semantic events — 2026-10-03

`feature/core-semantic-events` imports MTP/vision checkpoint `01ff720` into a
persistent Git Flow worktree from `develop`. Text, confirmed-token progress,
validated complete tool calls and typed turn completion now use the shared
C17 [event contract](reference/EVENTS.md). HTTP, Responses and the direct core
benchmark consume it; model-output grammar and UTF-8 decoding belong to the
core. Request ABI 4 owns parallel-tool policy. No inference thread was added.

Native ASan/UBSan/LeakSanitizer tests pass **39/39**, including AR/two MTP
geometries, byte-split UTF-8, complete/invalid/truncated tool turns, forbidden
parallel calls, credit starvation with peer progress, retained loans, cancellation
before pending calls and terminal retirement during prefill. Native Chat and
Responses JSON/SSE fixtures verify calls, failure terminals and full-size burst
pieces. The protocol-independent build with MTP/vision OFF passes **16/16**;
it discovers/links no libuv, llhttp or json-c. Existing raw clients remain usable
but a job refuses mixed raw/semantic consumption.

The official pinned Gufo provider was fetched and rebuilt independently in this
worktree. HIP server and benchmark compile/link, and metadata-only `--build-info`
passes with GPU visibility masked. These are **NOT-INFERENCE** checks. The
[source-bound receipt](development/validation/core-events-2026-10-03.json)
preserves actual failures/exits and thermal evidence. No shutdown/deterioration,
model load/hash/conversion, GPU run, remote build or performance campaign occurred.

Semantic parsing runs in the core consumer API. Confirmed-token demand and device
owner scheduling are preserved; this change makes no measured speedup claim.
Original-weight tool behavior and GPU qualification remain open, as do incremental
argument events, constrained generation, scoring/logits and chat/eval clients.

## MTP and vision integration — 2026-10-03

`feature/mtp-vision-integration` combines the complete MTP checkpoint `7d85b2f`
and semantic vision checkpoint `806a790` in a persistent worktree created from
`develop`. The shared C17 core admits target, predictor and projector together;
HTTP and the direct benchmark use that same lifecycle and reactive dispatcher.
A joint checkpoint includes the unchanged DS4 tensor payload, MTP controller,
residual/hidden rows and the prepared vision scope. Prepared positions, scope and
controller are checked before numerical restore; the destination sampler is fresh.
RAM remains default-on and SSD opt-in. No new inference worker was added.

Native ASan/UBSan/LeakSanitizer tests pass **36/36**. Coverage includes combined
burst demand/cancellation, two fixture geometries, equal-token/different-image
isolation, RAM reuse, SSD process restart and Chat/Responses JSON/SSE cache reuse.
The option combinations MTP-OFF, vision-OFF and both-OFF pass **30/30**,
**29/29** and **26/26** tests. Five focused changed identity/cache tests also pass.
The combined synthetic core client exports native JSON/CSV/SVG/PNG.
The official pinned provider was fetched and rebuilt independently with the
combined source manifest; HIP server and benchmark compile and link. These are
host/fixture checks, **not original-weight inference or performance evidence**.
See [configuration](guides/USAGE.md#mtp-with-images) and the
[source-bound receipt](development/validation/mtp-vision-integration-2026-10-03.json).

Original-weight image/text MTP, numerical cache parity, sampled target behavior,
rejection/rollback, resource fit and GPU measurements remain open. No GPU run,
model hash/conversion/load, remote build, deployment or publication occurred.

## Earlier feature checkpoints

The entries below describe their dated branches before integration.

## Complete MTP RAM/SSD binding — 2026-10-03

The C17 codec and shared cache now connect to live predictor transfers, residual
and kept hidden rows, and the adaptive controller. Missing hidden catch-up rows
refuse in both the C codec and device admission. The independently rebuilt Gufo
variant materializes completed MTP pooled keys in scalar/batch paths. SSD identity
pins the actual admitted target/predictor readers and includes the draft policy;
RAM-only startup performs no weight hash. Default RAM retention is preserved.
Unsupported models refuse readiness unless caches are explicitly disabled.

CPU ASan/UBSan/LeakSanitizer checks pass **29/29**, including two synthetic model
families, prompt/verified-frontier clones, budgets, cancellation, SSD process
restart, predictor/draft identity changes and Chat/Responses JSON/SSE cache reuse.
The MTP-OFF lifecycle/cache checks pass **3/3**. HIP libraries and server/bench
compile/link; the synthetic core client also checks default RAM hits and native
CSV/SVG/PNG export. These are **NOT-INFERENCE** results. The source/evidence-bound
[cache receipt](development/validation/mtp-cache-2026-10-03.json) preserves the
initial stale HTTP assertion and every thermal interruption/refusal.

No original-weight model load, GPU execution, heavy model hash, conversion or
`.157` performance run occurred. The CPU build peak was 94.625 C under a 95 C
child-only guard; GPU functional preparation retains its separate 85 C guard.
Original-weight MTP/cache continuation and sampled correctness remain required.
Vision semantic cache identity and device binding are the next separate branch
integration task; the current vision checkpoint remains `3434504`.

## Shared auxiliary KV state and MTP codec — 2026-10-03

The C17 RAM/SSD store now retains typed auxiliary state with complete budget
accounting and SHA-256 admission, preserving original DS4 payload offsets and
version-1 AR files. Two unrelated fixture schemas exercise the same storage path.
The Qwen codec adds predictor K/V, index/pooled keys, residual/kept hidden
rows and adaptive-controller state. Device binding, complete predictor pooling
and stable predictor identity remain pending; live MTP KV reuse stays refused.

Local CPU ASan/UBSan/LeakSanitizer checks pass **28/28**; HIP provider linking
also passes. No model load, GPU run or performance campaign is claimed. Current
functional-GPU authorization and metadata-only USB findings are recorded in
[coordination](COORDINATION.md). Raw failures and actual exits remain under local
`evidence/`; see the [source-bound state receipt](development/validation/mtp-state-2026-10-03.json).


## MTP model-neutral development slice — 2026-10-03

Verified output bursts, per-row credits, explicit predictor admission and draft/acceptance metrics now run through the shared C17 core, HTTP and core benchmark client. The Qwen limit stays inside its provider; fixtures admit both 8- and 13-token bursts.

Native CPU ASan/UBSan/LeakSanitizer checks pass **27/27**, including both APIs,
JSON/SSE, exact output budgets and early EOS. Final focused feature/dispatcher
checks and the feature-OFF headless lifecycle also pass. The HIP adapter and
clients compile/link against the independently verified Gufo pin. No model
was loaded; .157 and GPU performance campaigns were not used. Direct synthetic
core-client runs also produce JSON/CSV/SVG/PNG successfully. These are
NOT-INFERENCE checks, not performance results.

The feature is compiled ON by default but requires explicit model admission.
Its complete extra state is not yet serializable: the development configuration
requires both KV caches explicitly off, with unsupported state advertised as
such. AR's RAM default is unchanged. Original-weight correctness, extended
state/identity and combined MTP+vision integration remain open. Benchmarks are
postponed while these separate feature branches advance. See
[usage and remaining gates](development/MTP.md) and the
[validation receipt](development/validation/mtp-2026-10-03.json).


## Vision semantic RAM/SSD cache binding — 2026-10-03

The shared C17 cache now keys images separately from tokens. RAM lookup,
deduplication, retention/protection and SSD filenames/index/restart use a typed
semantic scope; equal tokens with different images produce a pre-upload miss.
The Qwen binding validates prepared MRoPE positions and the actual loaded
model/projector files. DS4 tensor payload and old AR framing remain unchanged.
RAM keeps its normal default; SSD is opt-in. Clients resupply images after
restart; full-prompt scope conservatively limits earlier-prefix reuse.

Native ASan/UBSan/LeakSanitizer passes **30/30**. Tests cover two fixtures,
KVC/aligned process restart and both HTTP APIs in JSON/SSE. The independently
materialized provider and HIP server/bench compile/link. No model load, GPU
run, weight hash or performance result is claimed. Earlier compiler errors and
fixture assertions remain in local evidence with their actual exits. See
[usage and limits](development/VISION.md) and the
[source-bound receipt](development/validation/vision-cache-2026-10-03.json).


## Shared auxiliary KV state and vision positions — 2026-10-03

The C17 RAM/SSD store now retains typed auxiliary state with complete budget
accounting and SHA-256 admission, preserving original DS4 payload offsets and
version-1 AR files. Two unrelated fixture schemas exercise the same storage path.
The Qwen codec adds MRoPE delta/physical rows and compares them against prepared
input positions. Live vision KV reuse stays refused until image identity also
covers lookup, deduplication, device layout and restart ownership.

Local CPU ASan/UBSan/LeakSanitizer checks pass **28/28**; HIP provider linking
also passes. No model load, GPU run or performance campaign is claimed. Current
functional-GPU authorization and metadata-only USB findings are recorded in
[coordination](COORDINATION.md). Raw failures and actual exits remain under local
`evidence/`; see the [source-bound state receipt](development/validation/vision-state-2026-10-03.json).


## Vision model-neutral development slice — 2026-10-03

Owned PNG/JPEG inputs, model-specific physical token expansion and encoder admission now run through the shared C17 core, Chat/Responses and core benchmark client. Fixtures use distinct image limits and expansion geometry; no Qwen positions or tensor types enter the public C contract.

Native CPU ASan/UBSan/LeakSanitizer checks pass **27/27**, including both APIs,
JSON/SSE, exact output budgets and early EOS. Final focused feature/dispatcher
checks and the feature-OFF headless lifecycle also pass. The HIP adapter and
clients compile/link against the independently verified Gufo pin. No model
was loaded; .157 and GPU performance campaigns were not used. Direct synthetic
core-client runs also produce JSON/CSV/SVG/PNG successfully. These are
NOT-INFERENCE checks, not performance results.

The feature is compiled ON by default but requires explicit model admission.
Its complete extra state is not yet serializable: the development configuration
requires both KV caches explicitly off, with unsupported state advertised as
such. AR's RAM default is unchanged. Original-weight correctness, extended
state/identity and combined MTP+vision integration remain open. Benchmarks are
postponed while these separate feature branches advance. See
[usage and remaining gates](development/VISION.md) and the
[validation receipt](development/validation/vision-2026-10-03.json).


## Native build, benchmark clients and reports — 2026-10-03

Python is no longer required for the normal build, provider verification,
benchmark clients, graph exports or default tests. CMake fetches and verifies
the independently pinned provider and builds its existing state variant.
The HTTP and KV disk benchmark clients, JSON/CSV reports and SVG/PNG renderer
now run in C17; libpng is a documented full-build dependency. Historical Python
oracles remain optional through `LIE_LEGACY_PYTHON_TESTS=ON` (default OFF).

The native tests cover KVC bytes and state mapping, malformed evidence,
request replay, Chat/Responses JSON/SSE, disk restart, C2 consumers and owned
I/O-barrier cancellation/peer witnesses. Report comparisons align physical
workloads even when reference files reorder them. Separate zero-based axes
preserve prefill/generation scale; absent metrics are not plotted as zero.

Local ASan/UBSan/LeakSanitizer checks pass **25/25** with Python discovery
disabled and **44/44** with historical oracles enabled; the final graph fix
passes **3/3** focused checks. Official source fetch, complete provider build
and final HIP link also pass without Python helpers. All are CPU checks or
compilation: no model execution, GPU performance claim or change to inference
scheduling. Initial HTTP failure-marker and relative KVC fixture-path failures
are retained with their exit codes and corrected. [Validation receipt](development/validation/native-tools-2026-10-03.json).

## KV option names and future weight storage — 2026-10-03

Server and shared-core/state benchmark CLIs now use `--kv-*` for inference
checkpoints: `--kv-cache-ram-mb`, `--kv-disk-dir`, `--kv-disk-space-mb` and
`--kv-disk-staging-mb`. Disk and boundary names follow the official DS4 server
CLI. Old names remain aliases in a shared C normalizer, preserving existing
qualified recipes. The HTTP benchmark uses `--server-kv-cache` for its remote
configuration declaration, distinct from `--kv-cache-policy ds4|legacy`.
Future weight persistence/streaming belongs to `--model-*`; it is not implemented
by these cache controls. RAM remains enabled and disk persistence opt-in.

Local CPU ASan/UBSan/LeakSanitizer checks pass **5/5**, including RAM reuse,
KV disk restart across new/old spellings, core/state clients and HTTP benchmark
declarations. Build exit 0, tests exit 0; observed peaks 76.625 C and 72.875 C.
The initial sandboxed test attempt exited 8 because private sockets and
LeakSanitizer were restricted; the failure is retained. Receipts are under
`evidence/kv-cli-names-{build,test,test-unsandboxed}-20261003/`. No GPU run or
performance claim. The separate Python dependency removal remains in progress.

## Complete prompt retention — 2026-10-02

The owner authorizes publication to `https://github.com/synapse-linux/synapse-lie`.
Configured `origin` and pushed only `feature/openai-reactive-api` at `89b1620`;
no other branch, merge, release or deployment was published.

The shared C17 core now captures the complete prompt before generation. Under
RAM/SSD pressure, generated captures preserve the longest prefix reusable by
that input; sufficient budgets still retain conversation continuations. The
guard follows original visibility-key flags separately from generated metadata,
and is local to a capture, not a permanent pin. SSD refusal precedes eviction
and counts as a skip. Numerical kernels, KVC representation, thread count and
reactive credit/cancellation remain unchanged. [Contract and GPU protocol](development/CACHE-PROMPT-RETENTION.md).

Full ASan/UBSan/LeakSanitizer suite **39/39**; headless utility/compression/
interchange-OFF suite **10/10**. Tiny native/KVC fixtures qualify one-record
pressure, unaligned complete prompts, oversized fallback, continuation, key
isolation, independent SSD process restart and RAM promotion. Existing held-I/O
peer/cancellation tests pass. Local receipts retain four failed focused attempts:
fixture chunk misuse and stale BPE expectations, fixture EOS count, the original
visibility-key guard omission, and an SSD quota below the retained-state staging
admission. Corrections pass without disabling sanitizers. No new original-weight
performance claim is made until the separately coordinated GPU comparison.

## DS4 runtime GPU qualification and cost — 2026-10-02

Frozen `a4008b9` completes 15/15 original-weight GPU arms on .157, all child/helper
exits 0. There are 24 exact full-logit/token replay/restore pairs and 12 exact pairs
across the legacy/KVC provider variants, including generated frontiers and SSD
restart at 131072 tokens with context 139264→262144. Core C1/C4 outputs and cache
accounting match. [Full report, values and plots](archive/KVC-GPU-RESULT.md).

At 128K, retained state grows 3.205→3.957 GiB (+23.46%); median RAM-hit TTFT grows
224.815→267.929 ms (+19.18%) and restore 42.195→52.149 ms (+23.59%). Those exceed
the predeclared 5% latency gate. PP/TG and complete-window throughput remain
approximately unchanged in these samples. The requested DS4 format stays ON by
default and its compile-time OFF control remains available. No overall performance
promotion, high-ratio codec or improvement attributable to reactive scheduling is
claimed. The existing default capture-policy retention regression is separate.

Fresh closure 19:18:19.131870 UTC verifies 30 owned identities, controller and
observer absent, KFD empty and four original leases free; 152 artifacts SHA-verify.
Q2 and Point received explicit release. Independent 1747-sample thermal evidence
records CPU 98.25 C / GPU 100 C peaks and their durations, without crash or disconnect.
No model/DS4 mutation, remote build, tuning, deployment or publication. Foreign
DS4-produced import/export and other real model families still need their own
bindings and independent qualification.

## DS4 runtime payload replacement — 2026-10-02

Default-ON `LIE_DS4_RUNTIME_CACHE` now selects exact DS4 Qwen AR payloads in RAM
and optional SSD, through state ABI 2 and the shared C17 core. The model binding
captures directly into wire offsets; the generic store writes KVC `.kv` files
with an opaque trailing LIE stable-identity/integrity extension. Foreign files
without an authenticated binding remain offline. Qwen geometry stays in its
model codec; an additional synthetic family exercises the generic lifecycle.

The independently materialized Gufo variant keeps complete raw index history
and pools completed keys before sparse selection, with full device allocation
included in session admission. Existing kernels are reused; changed scheduling
and memory cost require GPU qualification. Legacy runtime remains compile-time
selectable. SSD remains default-off; KVC bypasses additional Zstandard packing.
Reactive ownership stays one device worker and one optional bounded I/O worker.

ASan/UBSan/LeakSanitizer: full **37/37**, headless interchange/compression OFF
**8/8**, final report/supervisor contract **1/1**. Independent tiny wire fixtures
cover 1/3/4/2048/2049/131072 tokens, exact payload, restart, client trailers,
identity/integrity refusal and budget/cancellation boundaries. These are
NOT-INFERENCE. Both DS4 and legacy HIP compositions compile and link locally.
Retained failures: store-name compiler warning (exit2), old report ABI/event
expectations (35/36, exit8), and invoking the Release all-target build on assert-
based test fixtures (exit2); corrected focused builds/tests pass. Peak local
CPU was95.125 C during provider compilation and93.375 C during the full suite.
Source/binary-bound [CPU receipt](benchmarks/2026-10-02/kvc-runtime/cpu-receipt.json).

Next is the [paired GPU campaign](development/protocols/KVC-GPU-PROTOCOL.md) on .157 after Q2's verified
release. No GPU numerical/performance result is yet claimed for this variant.
DS4-produced import/export, cross-quantization reuse and other real model families
remain separate gates. [Runtime format and precise boundaries](reference/KVC.md).

## Multi-model cache requirement — 2026-10-02

The owner confirms that KV/prefix caching must also serve other model families.
Recorded an explicit [multi-model contract](reference/STATE.md#multi-model-requirement):
shared C17 RAM/SSD policy, resource and reactive lifecycle; model-specific
component geometry, complete frontier capture and exact KVC payload codecs.
The loaded-model binding must select and authenticate a codec before restore;
Qwen-specific history must not enter generic cache/storage policy. Second-family
RAM/SSD lifecycle and numerical qualification are acceptance gates, not existing
support. Different models do not share otherwise incompatible checkpoints.

Source review confirms separate generic state/store/envelope and Qwen model
modules. This checkpoint changes documentation only; no runtime, ABI, model or
GPU work, and no new test execution is needed.

## C17 Qwen KVC/native component mapping — 2026-10-02

Added shared `lie_qwen_kvc`: allocation-free projection of validated text AR
KVC records into native QF1 components, plus exact reverse serialization when
the caller supplies missing index/pool history. It preserves GPU GDN orientation,
PLE order and tensor bits, translates EOS/unset n-gram history and handles both
sides of the index-pooling threshold. Generic layout helpers were extracted
unchanged from device capture/restore, so this library links without a provider.

Independent Python wire and native byte oracles pass thirteen complete
wire→native→wire pairs, including 2047/2048/2049 and 131072 tokens with tiny
synthetic geometry. These are NOT-INFERENCE checks, not full-model memory or
performance measurements. The suite also checks cancellation, budgets, aliasing,
malformed state and refusal of incomplete auxiliary history. Initial headless
suite: 9/9; final full composition: 35/35; interchange-OFF: 7/7. All use ASan/UBSan
with LeakSanitizer enabled; all nine configuration/build/test commands exit 0.
Persistent receipts: `evidence/kvc-map-*`. Local sampled CPU peak 84.625 C
during the OFF build; full-suite peak 78.875 C. No GPU/model work or window request.

Projected layouts deliberately have domain zero and cannot be restored into a
live model. Provider capture of discarded history, model/tokenizer identity
binding and bilateral GPU qualification using a DS4-produced checkpoint remain
open. Runtime RAM/SSD formats, reactive scheduling and inference work are
unchanged. The mapper is built by default under optional `LIE_KVC_INTERCHANGE`;
SSD remains opt-in. [Contracts, source audit and next gates](reference/KVC.md).

## C17 KVC envelope and Qwen payload codecs — 2026-10-02

Added default-ON, independently optional `LIE_KVC_INTERCHANGE`: a shared C17
wire library and `synapse-lie-kvc inspect/copy`, also available without HTTP.
Owned RAM records and file I/O retain KVC v1/ABI2 bytes, bounded text/extensions
and interoperable text filenames. The typed Qwen codec validates and serializes
complete payload components, including full index history, MTP rows and position
metadata, without inventing missing data or changing numerical precision.

An independent Python wire oracle checks C decode/re-encode byte equality.
The suite covers truncation at every byte, size/geometry/token corruption,
4,000 deterministic mutations, cancellation, short I/O/EINTR/ENOSPC, source
mutation, budgets and exclusive output publication. Headless ON: 8/8; complete
HTTP/core composition: 34/34; headless interchange OFF: 7/7, all ASan/UBSan with
LeakSanitizer enabled. All build/configuration/test child exits are 0. Persistent
receipts: `evidence/kvc-*`; local CPU peak 74.875 C. No GPU or model work.

This is wire-format support, not a qualified live-state converter. Native RAM
and `LIEPFX1` SSD serving remain unchanged; there is no new inference thread or
prefill work. Gufo's discarded index history and differing state layout still
require a provider bridge, an independently produced DS4 checkpoint and a
coordinated numerical GPU test. Cross-quant reuse and frontend-specific history
serialization remain open. High-ratio compression beyond reviewed upstream
capability stays deferred. [API, tool, provenance and next gates](reference/KVC.md).

## High-ratio compression deferred to upstream capability — 2026-10-02

The owner explicitly permits skipping high-ratio compression for now when it
is absent from antirez's implementation. The reviewed DS4 Qwen path uses F16/F32
state without an additional high-ratio codec; developing a new one is removed
from the active parity scope. The requirement for DS4-compatible RAM/SSD state
and KVC files remains. KVC conversion, cross-quant reuse and frontend history
serialization retain their separate implementation/qualification gates.

Existing optional packing and the measured raw fallback remain available.
This is a documentation/scope checkpoint; no runtime changes or new GPU tests.

## DS4 policy GPU qualification and retention regression — 2026-10-02

Frozen `f11ab7f` completes 15 GPU child arms across R9/R10/R11 on `.157`:
six exact full-logit/token state pairs, five matched legacy/DS4 core comparisons,
and automatic SSD producer/restarted-reader output equality. Capture after
128 generated tokens and restoring a checkpoint from capacity 131072 into 262144
pass. The later `fffaabb` cache-disabled shortcut retains its separate CPU check.

At 128K/4 GiB, DS4 scheduling keeps only 28672 reusable tokens and recomputes 102400;
warm TTFT is 79.195 s versus legacy 0.227 s. At 8 GiB it keeps 122880 tokens, with TTFT
6.738 s versus matched legacy 0.231 s, retaining 7.524 GB. No high compression or
reactive speedup is claimed. Default-ON features remain independently optional;
runtime `--cache-policy legacy` is available. [Tables, graphs and limits](archive/CACHE-DS4-GPU.md).

R9 retains FAILED controller status for the mistaken 122880-token expectation
under 4 GiB pressure; all nine device children exit 0 and offline outputs match.
R10 retains its mistaken 8231-token expectation for a legacy aligned 8192-token
checkpoint, child exit 0. R11 runs only missing arms and completes successfully.
R8's original adapter refusal and every actual exit remain in the archive.

Final R11 closure 14:56:30.025088 UTC confirms ten owned identities absent,
empty KFD and four unchanged/free leases. Controller is absent; observer exits 0
at 14:56:45.219419 UTC; all 58 collected files verify. Root returns the window
to Q2 and notifies Point, with no GPU job or waiter remaining. Whole-process
inference observations are 36 threads for RAM and 37 with SSD, including provider
threads. `.157` supervisor peaks CPU 98.25/GPU 100 C; no observed crash/reboot.
Independent sampled thermal durations are preserved separately. DS4 binary KVC
conversion, cross-quant reuse and DS4-specific frontend history serializers
remain unimplemented; this is shared policy parity, not full format parity.

## DS4 policy GPU refusal and repair — 2026-10-02

R8 passes native-v3 SSD producer and context131072→262144 reader, with three
exact full-logit/token pairs, then the 8K legacy core control. The first DS4
core arm fails at end-of-generation capture: the adapter still rejected
`sampling_started` sources. Its exit 1 and empty surfaced job error are retained.
The repair allows completed capture after decode while restore still requires
an empty unstarted destination, and publishes capture failure before waking a
flow consumer. A zero-frontier shutdown edge is also corrected. The state bench
adds `--capture-decode` to qualify exact live generated frontiers independently.

R8 closes at 14:06:00.539460 UTC with eight owned identities absent, empty KFD,
four unchanged/free leases. Observer retires at 14:06:16.094468, exit 0; all 49 collected
files verify. Root retains the coordinated window for a freshly admitted R9
following local CPU qualification. The incomplete R8 is not a policy pass.

## Shared DS4 cache policy — 2026-10-02

Implemented persistent six-hour utility, bounded dynamic indices, startup quota
eviction, text-prefix/suffix retokenization, owned opaque extensions and
progressive cold/continued/retirement/shutdown captures in the shared C17 core.
One busy SSD operation parks the affected row; peers remain schedulable.
The server and core bench expose matching options and accounting. Request ABI
is now 2. The adapter admits smaller saved contexts after shape validation.

Complete CPU sanitizer suite: 33/33, including failed-write preservation and
shutdown captures; optional-feature OFF checks also pass. Peak CPU in the full
run was 75.25 C on .155, no GPU work in those tests. Retained failed attempts
and successful receipts live in `evidence/ds4-policy-*`. GPU qualification is
prepared after Q2 release at 13:37:03.673156 UTC, with fresh per-arm leases.
**DS4 KVC import/export and cross-quant reuse remain pending.** Native v3 files
persist policy metadata but are not DS4-compatible files.
[Implementation, controls and remaining gates](reference/CACHE-DS4-POLICY.md).

## DS4 format constraint for RAM and SSD — 2026-10-02

The owner requires DS4's compression representation in both memory and SSD,
with higher savings and restore latency close to raw state. The earlier idea
of a separate lossy Q4/Q8 format is therefore not pursued as an equivalent.
Read-only upstream tracing confirms RAM snapshots share the Qwen persistence
serializer; the inspected path retains F16 KV/F32 recurrent tensors without an
extra high-ratio stream. The exact alternative DS4 function/version remains
unidentified. [Source trace and constraint](reference/STATE.md#requested-ds4-representation-parity--clarification-2026-10-02).
No runtime code or numerical precision changes, model reads, new GPU jobs or
DS4 mutations in this clarification. Q2 still owns its separately admitted work.


## Compression cost measured; strict admission qualified — 2026-10-02

R6 passes all six GPU arms, including restarted compressed SSD state at 128K
with three exact full-logit/token pairs. The codec saves 15.35% at 8K and 15.71%
at 128K, but 128K warm restore rises 42.46 to 1228.78 ms and output/wall falls 24.38
to 19.87 tok/s. The owner rejects that tradeoff; this is retained negative evidence.

R7 source `71a4599` passes 4/4 matched ON/OFF arms. Both tested Qwen states fail
the stricter benefit gate and remain raw. At 128K, warm restore 42.41 ms and
output/wall 24.36 tok/s match the OFF control closely; no high compression is
claimed. One cold capture 129.15 versus 118.00 ms remains visible. All 16 jobs
reach 128 identical tokens across matched builds. [Full tables and graphs](archive/CACHE-COMPRESSION-GPU.md).

R6 CPU/GPU peaks 97.875/99 C; R7 peaks 98/100 C, with the 100 C GPU reading confined
to one sampled point bracketed within 2.018 s. No observed crash/reboot/device
failure. R7 closure 12:37:26.556477 UTC confirms eight owned identities absent,
KFD empty, four unchanged/free leases; controller and observer retire, all 50
collected files verify. Root releases the coordinated window to Q2 and informs
Point. Sources, evidence, CSV and graph artifacts remain persistent and local.


## Reject low-benefit checkpoint compression — 2026-10-02

The owner rejects the measured 15–16% checkpoint saving as insufficient for its
capture/restore cost. New default admission requires at least 50% saving of the
complete retained allocation, including its descriptor. A deterministic probe
of at most 48 KiB rejects likely low-benefit data before candidate allocation;
the full result still has to meet the strict size gate. The probe may skip useful
packing but never changes the state or permits lossy conversion. Existing v1/v2
readers remain compatible. Both cache build options remain ON; SSD remains opt-in.

Thirteen focused ON suites and six OFF suites pass ASan/UBSan; local Release
variants link against the unchanged numerical engine. Tests include modest
savings rejected and misleadingly compressible samples that fail final admission.
[CPU source-bound receipt](benchmarks/2026-10-02/cache-benefit-cpu/receipt.json).
The new GPU comparison is pending a fresh per-arm admission after R6 closes.

The upstream Qwen payload audit corrects the earlier architectural generalization:
DS4 supports Qwen, but its reviewed Qwen path writes live F16 KV and F32 recurrent
state without a generic high-compression stream. LIE's independent host codec is
not the same algorithm. High-ratio compression of real Qwen state and low-bit
active KV are not achieved by raising the admission threshold. See the precise
[model/policy boundary](reference/STATE.md#retention-policy-and-compression-boundary).


## Numeric-byte codec follow-up after R5 — 2026-10-02

R5 closes 9/9 original-weight arms at 11:57:08 UTC: six ON/OFF core comparisons,
three exact 8K state pairs, and HTTP SSD producer/restarted reader with 30
samples, three C2 cohorts, natural read cancellation and slow-client isolation.
All states remain raw: LZ4 does not provide an admitted 12.5% payload saving.
At 128K, capture increases 119.638 to 205.906 ms without memory savings; warm
aggregate throughput stays near 24.04 tok/s. [Full R5 result](archive/CACHE-FEATURES-GPU.md).

The follow-up groups numeric byte positions before Zstandard level-1 compression,
using fixed static contexts inside the workspace budget. It preserves every bit,
keeps legacy LZ4 decoding, names the selected codec in metrics/reports and remains
behind default-ON `LIE_CHECKPOINT_COMPRESSION`. Thirteen focused ON suites, six
OFF headless suites and the final report check pass ASan/UBSan; Release variants
link locally. [CPU receipt](benchmarks/2026-10-02/cache-features-zstd-cpu/receipt.json).
Original-model compression benefit is pending a distinct R6 admission. This is
checkpoint storage, not an active KV precision/kernel change. R6 declares 8 GiB
workspace for the 128K packing comparison and lower context capacity 133120 to
bound active-session allocation; matched ON/OFF settings and exact SSD restart
will be checked separately from R5's default-budget result.


## Default-on utility and lossless checkpoint compression — 2026-10-02

Implemented independent CMake switches `LIE_CACHE_UTILITY` and
`LIE_CHECKPOINT_COMPRESSION`, both ON by default. Shared C17 RAM/SSD utility
retention ages reuse and scores saved tokens per stored byte, distinguishes
anchors/continuations and deterministically breaks ties. OFF selects LRU.
The C-owned checkpoint codec preserves every byte with bounded 1 MiB LZ4/raw
blocks, a 12.5% minimum saving, raw fallback and explicit working-memory
admission. Tokens remain directly readable. Raw v1 persists; compressed SSD
files use separately validated v2 framing. SSD alone remains runtime opt-in.

Metrics and benchmark JSON/CSV distinguish expanded/retained memory and build
features. An explicit `--compare-cache-build` enables matched ON/OFF reports;
ordinary comparisons reject those differences. State qualification applies the
same codec before full-logit/token checks. No kernel, active KV format, thread
count or HTTP-owned engine policy was introduced. Host packing/expansion can
add owner latency; active Qwen KV remains F16 and DS4's learned architectural
compression is not claimed.

Thirteen focused ASan/UBSan CPU suites pass with features ON; all six headless
suites pass with both OFF and without LZ4. The first reporting attempt selected
Python without matplotlib and failed two suites; that evidence is preserved.
Using the already installed system interpreter fixes both. Release ON/OFF
executables link the unchanged pinned numerical engine locally; no local GPU
inference. The next `.157` campaign follows Point's verified 11:11:58 UTC
handover, fresh root checks and independent four-lease admission per arm.
GPU performance of these new defaults is not yet claimed at this checkpoint.


## SSD HTTP consumer suite and explicit cache boundary — 2026-10-02

Added `synapse-lie-bench --suite http-ssd`: producer/restarted-reader output
comparison, Chat/Responses JSON/SSE, repeated C2 cohorts, cache-aware PP/TG,
first-text latency and text-event gap distributions, CSV/JSON and SVG/PNG.
Natural disk-wait cancellation and slow-client checks require observed states;
missed windows are INCONCLUSIVE. A test-only held pread proves peer progress
and cancellation deterministically through the real C core and HTTP stack.
The production core/model/ABI are unchanged.

The existing four-lease supervisor now owns the HTTP server and retires its
checker, binds corpus and restarted producer/store/summary identities, and
retains resource/thermal admission. Four focused ASan/UBSan CTest suites pass
(including 16 core-bench, six HTTP-client and two thermal-guard checks), followed
by a passing expanded supervisor/client fixture. R3 tests peak at CPU80.25/GPU57 C;
R4 at CPU71.75/GPU55 C. Commands exit 0. [Protocol and receipt](development/protocols/SSD-HTTP-PROTOCOL.md).
The final R5 source repeats the four focused suites with leak detection and
halt-on-error sanitizer settings: 4/4 pass, CPU75.625/GPU54 C, exit 0.
No original-model HTTP SSD result is claimed; `.157` is coordinated for the
owner's direct model copy to `.161` following Q2, with no core interleaving.

The owner clarified `antirez/ds4` as the cache reference. LIE's current LRU
retention and F16 KV checkpoints do not implement DS4's disk utility priorities
or a generic high-compression active KV codec. These are explicitly separate
remaining core/model/provider work in [STATE.md](reference/STATE.md#retention-policy-and-compression-boundary).

## Completed SSD GPU continuation and thermal timeline — 2026-10-02

R4 completes 10/10 arms, closing 128K exact SSD restart and core C1 off/RAM/SSD
at 8K/128K. All 24 core jobs (four warmups) emit 128 identical tokens across
policies; three state pairs each match every logit frontier and 16 output tokens.
R2's exact 8K and 4K-to-8K extension passes remain separate from its failed
128K reader. R1/R2/R3 failures and actual exits are retained without rewriting.

At 128K, median core TTFT is 98.583 s off, 0.226 s RAM, 2.186 s restarted SSD;
fresh PP is 1332.098 tok/s and native C1 TG about 25 tok/s. Full hits execute no
PP; startup hashing and write durability have separate measurements. The bench
graphs/CSV expose complete samples and min/max, not just headline rates.

The 1 Hz observer retains 1743 samples: CPU peak 98.125 C, GPU peak 100 C in three
isolated samples. GPU episodes at/above 98 C are bracketed within 3.036 s, while
95 C plateaus last longer. No crash/reboot/device error was observed. Matched
128K fresh PP falls about 2.08% across three samples; there is no controlled
thermal A/B to attribute that variation solely to temperature. No hardware
settings changed. The core adds one optional I/O worker; C1 does not establish
reactive concurrency speedup. [Full result and reproducible evidence](archive/SSD-GPU-COMPLETION.md).

Closure at 09:39:08.072 UTC confirms twenty owned helper/child identities absent,
KFD empty and four unchanged/free leases. Controller and observer retired;
all 106 collected files SHA-verify. The window was returned to Q2 and Point was
notified after collection. HTTP/concurrent SSD GPU tests, fault injection,
256K checkpoint fit, 1M, MTP and vision remain separate roadmap items.

## Owner requested transient-temperature observation — 2026-10-02

R2 closes with five successful SSD state arms and a software thermal stop at
GPU99 C on the 128K reader. R3 stops its first 8K core arm at GPU98 C; neither
is a hardware crash, and its chunk512 alternative never launches. The owner
clarified the dynamic-fan behavior and explicitly requested recording transient
peaks and any performance deterioration/shutdown. An opt-in supervisor policy
now observes CPU/GPU temperatures without the earlier software ceiling, retains
reported hardware bounds and SSD guards, and leaves hardware settings untouched.
Both focused CTest suites pass (15 core-bench and 2 thermal checks), all exits 0,
with ASan/UBSan fixture binaries. [Receipt](benchmarks/2026-10-02/ssd-qualification/thermal-observation.json).
The resumed R4 protocol uses the original chunk2048 and a 1 Hz observer that
persists received samples on the editing host. No R4 result is claimed yet.

## Documentation navigation and benchmark scope — 2026-10-02

Added a documentation index and benchmark navigation by model, platform and
weight format. Current UD Strix Halo campaigns link their original reports and
artifacts; other platform/format work is explicitly not integrated evidence.
Corrected stale current-contract statements about RAM/SSD, shared-core ownership,
actual-model tools, Crypto dependencies and local non-performance checks. Dated
result files and hash-bound assets retain their original scope and contents.
The Gufo-style multiuser result remains a simplified direct-executor measurement;
it does not reproduce the published HTTP corpus and per-request-rate aggregation.

## User-authorized Strix Halo temperature revision — 2026-10-02

The 85 C R1 ceiling was an assistant-selected precaution. Following the user's
98 C clarification and AMD's 100 C CPU Tjmax specification, helpers now support
an explicit 98 C CPU/GPU ceiling on the verified 395 host. Lower hardware limits
remain enforced, NVMe stays at 85 C or lower and defaults remain 85 C elsewhere.
No numerical/core source or hardware policy changes. Both focused ASan/UBSan
CTest suites pass, including 14 bench checks and two guard tests, at CPU91.875 /
GPU65 C. The preceding sandbox attempt retains its LeakSanitizer/loopback
restrictions and exit 8. [Thermal revision receipt](benchmarks/2026-10-02/ssd-qualification/thermal-revision.json).

The remaining 14 SSD arms are prepared for a separate continuation; Q2 owns
`.157`, so no new GPU run or heavyweight hash starts before its release.

## First original-weight SSD restart — 2026-10-02

`ssd-gpu-r1` records two successful arms: 512-token durable write and a separate
restart reader with three exact fresh/restored logit/token pairs. Early EOS
limits each pair to two decode calls and one emitted token. File read takes
61.517 ms, median owner upload 4.388 ms; median fresh PP 627.892 ms. Startup model
load and 52.770–60.059 s full-content hashing remain separate, not request latency.

The next 8K producer stops during PP at GPU86/CPU84 C under the initial 85 C
policy, child/supervisor exits 1/1, without forced kill. The campaign remains
FAILED/INCOMPLETE; 13 arms never launched, so there is no long-prefix SSD or core
performance result. All 39 collected files verify. Closure 07:39:00.622 UTC:
six owned identities/controller retired, KFD empty, four unchanged/free leases.
The window was returned to Q2. [Complete timings, failure and scope](archive/SSD-GPU-RESULT.md).

## SSD restart qualification harness — 2026-10-02

`synapse-lie-bench --suite state` now has explicit `--state-ssd-mode write|read`
with independent directory/quota/staging options. Write requires a new empty
store and a durable commit; a separate read process requires the exact frontier
and compares all logits/tokens with fresh recomputation in three pairs. Missing,
shorter and corrupted checkpoints cannot pass through a fallback. The shared
store implementation is unchanged. Reporting separates hashing/write/read/upload.

The leased benchmark supervisor binds new stores or sealed preceding producers,
checks explicit full-content hashing and RAM/staging/disk admission, and records
thermal telemetry with an 85 C or lower sensor ceiling. Q2's persistent release
at 07:13:11.718 UTC was verified read-only: no KFD clients, CPU48.125/GPU46 C;
the next GPU run still needs fresh leases. The [predeclared protocol](development/protocols/SSD-GPU-PROTOCOL.md)
covers exact restart/extension through 128K followed by core off/RAM/SSD timings.

Local [CPU receipts](benchmarks/2026-10-02/ssd-qualification/cpu-receipt.json):
14/14 focused checks, full ASan/UBSan 30/30 (CPU77.75/GPU58 C), HIP server/bench
compile/link exit 0 (CPU73/GPU58 C). All commands exit 0. No original-model SSD
result is claimed by this preparation checkpoint.

## Strix Point fork — 2026-10-02

The ROCm 10 Distrobox `multi` comparison on `.161` now passes LIE reactive,
direct Gufo and LIE serial at C1/2/4/6/8: 60/60 full-output samples, with
child/supervisor exit 0 in each arm. At C8, aggregate decode medians are
32.837, 32.872 and 10.425 token/s, respectively; LIE reactive is 3.15× its
serial control. All C2–C8 LIE measurements show 128 GPU batch calls and zero
single-row decode calls. Same-stack inputs, outputs and frontiers match all
three arms; ROCm 10 and ROCm 7.2 inputs match, but their outputs and frontiers
differ. The [full multi-user report](benchmarks/2026-10-02/strix-point/rocm10-distrobox-multi/README.md)
has prefill/decode values and graphs. All 63 remote files were verified by
SHA-256; router active, no LIE Distrobox, lease free. This is direct engine
concurrency, not served HTTP clients.

The Docker-managed Distrobox ROCm 10 `single` benchmark on `.161` now passes
all eight occupied-prefix depths 0–128K with 16/16 full 128-token outputs.
At 128K, LIE measures 357.117 prefill and 9.227 decode tokens/s for a 2,048
new-token tail. CPU/GPU peaks were 91.125/90 C; supervisor and child exited 0,
model files stayed unchanged, and final postflight found `llama-router.service`
active and the private lease free. A failed Distrobox network-entry attempt is
retained separately. The [raw report and graphs](benchmarks/2026-10-02/strix-point/rocm10-distrobox-single/README.md)
include all eight points and 27 remote-file hashes. Physical inputs match the
earlier ROCm 7.2 run, but output IDs and numerical frontiers differ at every
depth; the kernel and container mode also changed. `fresh-128k` and
`fresh-256k` remain pending for ROCm 10; the later `multi` comparison above
has now completed.

The operator-requested `.161` Pop!_OS kernel update installed
`7.1.5-76070105-generic` and kept `6.16.3-76061603-generic` in GRUB. With
the same pinned ROCm 10 images and binaries, AlmaLinux native and Python HIP
diagnostics and the Fedora 43 LIE HIP/rocBLAS probe now pass. A bounded original
UD model run also passes. Matched ROCm 10 LIE and direct Gufo tests at 0/4K
return identical 128-token outputs and prefill/decode frontier hashes; these
frontiers differ from the earlier ROCm 7.2 results, and output IDs diverge at
both depths. Those bounded tests qualified the runtime gate and same-stack
parity, not cross-stack numerical equivalence or full performance. The
[updated report](STRIX-POINT-ROCM10.md) records the six clean passes, one
preserved supervisor race failure, 80 verified files and restored .161 state.

The official AlmaLinux 10.2 minimal image plus AMD's signed ROCm 10.0.0-4
`gfx1150` RPMs built on `.161` with exit 0. Its in-image `hipcc` compiled a
native HIP probe, which fails on the same 48-byte memset and host/device copy
operations as a separate Python diagnostic in the same image and the Fedora
variants. Both failed campaigns retained all HIP codes, restored the named
service, released their fresh leases and passed remote/local source-result hash
checks. The [ROCm 10 report](STRIX-POINT-ROCM10.md) has image ID, binary hash,
thermal and closure evidence from the original 6.16.3-kernel tests.

The ROCm 10 follow-up found the `.157` Strix Halo image originates from Kyuz0's
Docker Hub repository: its local digest is recorded, with Fedora Minimal 44 and
AMD's signed RHEL 10 `gfx1151` RPMs. A separate LIE Fedora Minimal 44 image
using AMD `gfx1150` RPMs built on `.161` with exit 0. Primitive HIP memset and
copies fail in that image under three container profiles, and also fail with the
Fedora 43 ROCm 10 tarball; a byte-identical ROCm 7.2 control passes on the same
host. All one-shot runs release their lease and restore the named service.
The [ROCm 10 report](STRIX-POINT-ROCM10.md) records exact image IDs, HIP codes,
temperatures and evidence from those original 6.16.3-kernel tests. The Fedora 43 `gfx1150` LIE probe
was compiled and linked with ROCm 10 before execution; Fedora 44 has only a
runtime diagnostic so far. Upstream gfx1150 issues #6191 and amdgpu #213 cover
similar first-use failures, but neither matches our ROCm 10 errors and kernel.

The fresh operator-approved 100 C `single` campaigns on .161 now pass **8/8
occupied depths each** for LIE reactive C1 and direct Gufo C1, PP2048/TG128,
one warmup and one measured sample per depth. All 16 samples in each arm
complete 128 output tokens; physical inputs, outputs and PP/TG frontiers match
at every depth. At 128K, LIE measures 389.786 PP / 9.862 TG token/s and Gufo
388.395 PP / 9.869 TG token/s. Sampled CPU/GPU maxima are 91.5/90 C for LIE
and 92/92 C for Gufo, below the authorized limit. Both child and supervisor
exit0 with unchanged model files, restored service, released lease and fresh
collection proving owned processes absent. The [complete direct report](STRIX-POINT-BENCHMARK-RESULT.md)
and [portable raw/graph bundle](benchmarks/2026-10-02/strix-point/full-single/README.md)
retain all values and receipts. These are direct C1 occupied-prefix tests;
fresh full-prompt and multi-user suites use separate methods. The earlier
85 C failure is preserved unchanged.

The subsequent `.161` C1/2/4/6/8 `multi` suites each passed for LIE reactive,
direct Gufo and LIE serial control with one warmup and three measured samples
per point. All 60 samples returned the complete 128-token output per user;
physical prompts, generated outputs and PP/TG frontier hashes match among all
three arms. At C8, aggregate decode medians are 32.184/32.146/10.316 token/s.
Every measured reactive C2–C8 sample records zero scalar decode calls and 128
native batch calls, with 128 × users rows. The direct reactive path therefore
gains 3.12× over serial at C8 and closely matches direct Gufo; C1 and PP
speedups are not established. All arms retire their child and supervisor,
preserve model stats and restore the service. Exact raw data, counters,
telemetry, CSV/JSON and reproducible plots are in the
[three-arm bundle](benchmarks/2026-10-02/strix-point/multi/README.md).

The later `.161` paired `fresh` campaigns also pass for 1500, 8000, 8192,
32768 and 131072 **entirely new physical prompt tokens** at capacity 262144,
with no warmup and two measured repetitions per point. All 20 samples finish
the 128-token output budget; LIE and Gufo physical IDs, output IDs and PP/TG
frontier hashes match at all five points. At 128K, fresh PP medians are
413.264/412.584 token/s and TG medians 9.894/9.875 token/s; this is a
different metric from a 2048-token tail after a live 128K prefix. Both runs
retire cleanly with sampled CPU/GPU peaks below 92 C. Raw receipts, exact
min/max and reproducible graphs are in the
[fresh-128K bundle](benchmarks/2026-10-02/strix-point/fresh-128k/README.md).

The further `.161` `fresh-256k` direct pair passes **258794 actual physical
prompt tokens** at capacity262144, two measured repetitions per arm and 128
generated tokens in all four samples. LIE/Gufo PP medians are 384.647/384.154
token/s and TG medians 9.4485/9.4192 token/s; full inputs, outputs and PP/TG
frontiers match exactly. Each original-weight campaign exits0 without OOM,
preserves model stats, restores `llama-router.service` and frees the .161
lease. Sampled CPU/GPU peaks stay under 92/92 C. The
[fresh-256K bundle](benchmarks/2026-10-02/strix-point/fresh-256k/README.md)
retains raw receipts, observed min/max, temperature/GTT plots and process
thread snapshots. This qualifies direct inference with a near-256K prompt;
HTTP, MTP, vision and 1M remain different gates.

The operator now authorizes a fresh 100 C ceiling for the complete .161 run.
The campaign supervisor requires that explicit override in the manifest and
still applies lower published sensor limits, including NVMe max 89.85 C.
AMD publishes 100 C Tjmax for the target HX 370 CPU; the previous run stopped
on CPU Tctl at the conservative 85 C setting. Focused CPU campaign controls
pass 11/11, including refusal of an unquoted or above-100 C override. The
two full GPU campaigns subsequently obtained fresh admission and evidence.

`synapse-lie-bench` now has supervised fixed .161 profiles for the same direct
`single`, `fresh`, `multi`, `memory` and `loading` workload families used on
.157; a separate direct Gufo reference arm is supported. The first full
eight-depth `single` run exited1 at CPU85 C during the 8K warmup. Completed
0/4K samples and 114 telemetry records are retained as failed-campaign
diagnostics, not promoted to a passing sweep. Its owned child/supervisor and
lease retired; the named service was restored, model stats unchanged.
Subsequent short, cooled **matched** LIE/Gufo runs at depths0/4096 each exit0
and agree exactly on physical prompts, generated output IDs and complete
prefill/decode frontier hashes. PP and TG values, resource peaks and graphics
are in [the direct-benchmark result](STRIX-POINT-BENCHMARK-RESULT.md).
Both LIE and direct Gufo `--suite loading` arms at capacity262144 exit0 with
13.750589557/13.695302901 s under uncontrolled OS file-cache conditions,
without a 256K prompt prefill. No
additional long-context or concurrency claim was made from that thermal stop;
later, separately admitted passing campaigns are reported above.

The [full Strix Point report](STRIX-POINT-RESULT.md) now consolidates the completed
build/runtime/tuning/copy qualification and original-weight C1 smoke. All four
samples, exact nanoseconds, RAM counters, decode versus complete-wall throughput,
27 resource observations and individual temperature sensors are exported as
portable CSV/JSON with SVG/PNG plots. An offline reproducer validates the
previously committed receipt hashes, complete benchmark accounting, repeated
output IDs, successful exits and retirement before deriving metrics. Mean decode
is 10.555678 token/s; mean output/complete-wall is 10.495151 token/s. Fresh PP is
only the first 9-token warmup; three measured samples reuse all nine tokens.
The report keeps missing long-context, concurrency, numerical-reference and HTTP
qualification explicit. Report generation is local CPU work only; no new model
run, remote access or runtime implementation change is implied.

The latest operator instruction replaces WAN download with a **copy** of the
existing official .157 UD shards, keeping the source intact. WAN R3 retired at
10:27:42 UTC; its verified first shard and 31.584 GB second-shard partial are
retained. After Q2's release and core's handover, the direct .157-to-.161 copy
started at 10:36:05 under both hosts' admitted leases. The source controller
streams to the destination directly, using a temporary destination-constrained
SSH agent; model bytes do not pass through the editing host, and no remote SSH
account configuration changes. **Copy complete:** all 111334654784 bytes and
four official SHA-256 digests are verified, with all source file identities
unchanged. R1 delivered the data but exposed an EOF/ACK deadlock; its failed
control exit is retained. The corrected helper has a real-pipe regression test;
R2 reverified existing destination files without recopying payload and passed
at 11:11:58 UTC. Processes and temporary agents are retired, leases free; core
and Q2 received the .157 handover. No WAN fallback is scheduled.

**First original-weight GPU smoke passes** on .161 at 11:14:40 UTC: shared
reactive core, context capacity4096, actual prompt9 tokens, AR32 output tokens,
one warmup and three measured repetitions. Load-to-ready13.440 s, first fresh
prefill377.705 ms, measured warm decode mean10.556 token/s, warm TTFT112.853 ms.
All four output ID sequences match. The warm samples restore all9 prompt tokens
from RAM cache and do no prefill; do not interpret them as long-context PP.
CPU/GPU/NVMe peaks74.25/58.00/63.85 C, below85 C; process threads observed
1/28/44 include runtime threads, not configured inference-worker counts.
Child/supervisor exit0, model stats unchanged, owned container removed, llama
restored and private lease free. Independent numerical parity, long contexts,
HTTP and comparative reactive benefit remain separate gates.

Operator-authorized TTM tuning **passes** on .161: after reboot, actual HIP
reports 103079215104 bytes (96 GiB), up from 61.72 GiB. HIP allocation/copies
and rocBLAS SGEMM pass, child/supervisor exit 0, owned container retired and
llama restored. Initramfs backup and scoped rollback are retained. Post-boot
COSMIC reports no display output; greeter and gpu-manager reached their start
limits, while compute is operational. The initial KFD-retirement refusal is
retained and its bounded wait is fixture-tested.
The read-only .157 LAN attempt held all four established leases but was
deliberately stopped after the Wi-Fi relay proved slow; its partial data and
failure exits are retained. The temporary WAN R3 phase is superseded by the
completed direct copy above. The transfer's seven tiny CPU integrity/pipe
fixtures pass; focused CTest 4/4 includes
the existing core contract under ASan/UBSan. Core bench now
preserves model-load errors; focused ASan/UBSan tests pass and the new R3
candidate passes no-device startup. See [the evolving target report](STRIX-POINT.md).

Follow-up: added a C17 HIP/rocBLAS diagnostic with explicit actual-device
execution, separate from automatic tests. Its twenty synthetic error/lifetime
cases pass ASan/UBSan locally and on .161; focused local CTest passes 2/2.
The HIP-linked diagnostic loads with `--help` on .161, without device access.
The first local LeakSanitizer sandbox failure is retained. Four official shard
identities are independently verified via small upstream metadata and recorded
in `config/models-161.plan.json`; no payload download/hash has run. The router
is still active at the 08:36:57 UTC check; explicit temporary-stop/restore
handover remains pending. No GPU SGEMM, model inference or fit claim follows.

`feature/strix-point-ud` starts from the qualified shared-core checkpoint
`02a9464`. Explicit gfx1150 selection, archive/cache target binding and runtime
architecture/wave validation are implemented without numerical source changes.
The C17 core and reactive scheduling remain shared. On `pop@192.168.5.161`,
host target/admission fixtures pass ASan/UBSan and four Python receipt checks;
headless core CTest passes 6/6 under ASan/UBSan, CPU peak47.625 C. The initial
container sensor failure and local thermal preflight refusals are retained.
The complete local ASan/UBSan suite passes 34/34. All 38 gfx1150 numerical build
steps and server/bench/reference links pass; ten device ELF headers confirm
gfx1150. No-model startup on .161 works with the existing runtime and isolated
DSOs, without installing the missing target SDK. Loader failures are retained.

At initial checkpoint `123ea23`, GPU qualification had not run: the foreign
`llama-router.service` held KFD, and the requested Flash Next UD shards were not found in known model directories,
and no model was substituted. The target's native SDK is incomplete, but the
prepared cross-host/container path passes its no-model checks. No foreign process stop,
package install, weight download, tuning or
publication occurred. [Port boundary and staged device gates](STRIX-POINT.md).

## Optional SSD prefix persistence — 2026-10-02

Implemented the version 1 component codec, conservative full-file identity,
private quota-limited store, immutable reference pins, bounded staging and one
asynchronous I/O worker in C17. The shared core integrates disk waits through its
existing event loop while runnable inference peers retain their flow credits.
RAM remains default-on; SSD is opt-in with explicit directory, quota and staging
limits. Server and direct core bench expose the same facility and separate disk /
owner transfer timings. See [SSD-PREFIX.md](reference/SSD-PREFIX.md).

Local non-performance tests are now explicitly user-authorized. Headless R5
passes 5/5 and full Debug R9 passes 29/29, including actual synthetic-process
restart, HTTP/Responses and bench graphs. Raw commands, actual exits and
per-second temperature samples are retained under `evidence/ssd-local-r*/`.
R1 keeps its strict-compiler indentation error; R7 keeps 12 failed suites caused
by the loopback sandbox and a selected Python without Matplotlib. R9 uses the
already installed system Python and permitted private loopback sockets; no
packages were installed. Thermal R4/R10/R11 refused before spawning a build at CPU
89/89.625/91.625 C. The successful full suite's observed peak was CPU84.375/GPU61 C.
Subsequent passive readings reached CPU92.625 C with no owned test running.

Runtime checkpoint `9b6c937` includes the final file-length/timer arithmetic and
Release reference-count checks, expanded identity environment inputs and the
thermal guard fixture. On that source, R12 rebuild and focused Debug checks pass
4/4; R13 ASan/UBSan passes **30/30**, with leak detection and halt-on-error enabled.
All five configure/build/test commands exit 0; the sanitizer suite's observed
peak is CPU79.75/GPU57 C. The HIP adapter and both executables compile/link in
`ssd-linked-r2`, exit 0, CPU74.625/GPU53 C, against the existing qualified numerical
archives. The preceding linked build remains a recorded thermal stop at CPU86.5 C
(owned child SIGTERM, child exit -15, guard exit 125). No numerical archive was
rebuilt. [Source and command receipts](benchmarks/2026-10-02/ssd-prefix-cpu/receipt.json)
bind these completed checks to the committed source; earlier fixtures remain
historical evidence rather than final-source acceptance.

Original-weight SSD restart, fit and performance remain unqualified; no new
model run or heavyweight hash occurred. The Q2 thread retains the coordinated
`.157` window. This completes the local contract/build checks, not the SSD device
acceptance gate. No push, deployment or DS4 mutation.

A separately requested fork, **Synapse LIE — DGX Spark**, was initialized in
`worktrees/dgx-spark`, branch `feature/dgx-spark`, at qualified checkpoint
`07427b1`. That thread owns platform/TensorFold investigation and `.158` read-only
inventory; this thread owns the shared SSD core. Active KV paging and PLE/weight
streaming remain distinct from persisted hybrid prefix checkpoints.


## C17 component state and default RAM retention — 2026-10-02

The user's clarification is implemented: RAM retention defaults on (4 GiB,
lazy allocation), SSD remains off and pending. State layout/allocation and
prefix lookup/budgets/LRU are extracted into C17; Qwen AR component geometry
is a C model module. HTTP and `--suite core` share the same engine cache.
No opaque Gufo serializer is used. The explicit friend-access variant changes
three declarations in two pinned headers, rebuilt separately; active numerical
execution remains delegated. Exact-generation resume, SSD, MTP and vision remain
pending. [State contract](reference/STATE.md), [ABI](reference/ABI.md) and [provenance](../third_party/README.md)
record this boundary.

New coverage includes headless capture/restore, domain/layout rejection,
independent clones, budget eviction, cancellation, fail-closed mutating faults,
cache-aware Chat/Responses and default-on/off bench graphs. `.157`
`reactive-cpu-r12` passes headless 3/3, Debug 26/26 and ASan/UBSan 26/26; all nine
configure/build/CTest commands exit 0. R11 also passed. R10 retains two failed
HTTP assertions that assumed cold/warm usage equality or selected usage from
the timing SSE frame; both expectations were corrected, without hiding failure.
Local compile failures R1/R3/R4 are retained alongside corrected R2/R5/R6 and
the successful HIP link receipts; no test or model ran on the editing host.

`--suite state` adds paired full-logit qualification (greedy, seeded sampling,
independent clone) with completed capture/restore/tail timings. GPU campaign
`state-gpu-r1` now passes **16/16 arms** under the [predeclared protocol](development/protocols/STATE-GPU-PROTOCOL.md).
Exact logits/output pass at 512/8192/131072 tokens and 4096-to-8192 extension;
cache-off frontiers match the pristine historical provider. Core warm-cache
TTFT falls from 98384.31 to 224.93 ms at 128K; whole-request throughput rises
from 1.24 to 24.08 tok/s. C8 aggregate complete-wall throughput rises from 51.14
to 106.02 tok/s, with effectively unchanged per-job TG and no added threads.
These are repeated identical-prefix savings, not faster fresh PP. Default-on
HTTP passes on port 8000. [Full values, cold samples, graphs and limits](archive/STATE-GPU-RESULT.md)
are retained; SSD/MTP/vision remain pending.

Runtime checkpoint `4fe6231`; 153 GPU evidence files SHA-verified. Final postflight
at 04:06:08.842 UTC records 32 owned child/supervisor identities absent, KFD empty,
and four unchanged/free leases. Controller retirement was observed separately;
the window was returned to Q2 before offline analysis. No permanent listener,
publication or DS4 mutation.

## First core GPU regression passed — 2026-10-02

`core-gpu-r2` completes all 13 declared arms on `.157`, all exits 0, with the
successful baseline HTTP arm explicitly retained from failed R1. Baseline
`2ba01ed` and candidate engine `81c2f60` use identical official Gufo archives;
helpers are at `04a0642`. Tokens and executor PP/TG frontier hashes match;
core physical replay and HTTP request/output/usage/finish comparisons also pass.

Matched executor median changes stay within 1%. At 131072 fresh tokens, PP is
1347.00 -> 1342.70 tok/s; C8 pure TG is 106.98 -> 107.09 tok/s. The largest HTTP
first-text median increase is 0.35%. Direct C8 core records 128 eight-row batches
and 51.09 output tok/s over total wall, including prefill. These timing scopes
remain distinct; extraction does not introduce a new numerical/reactive gain.
Actual inference thread samples are 35 executor / 36 core-or-HTTP, with loader
totals 51/52. C8 adds no per-request owner threads.

CPU headless/Debug/ASan checks already pass on `.157` (`reactive-cpu-r9`). All
121 collected GPU files verify against their hashes. Closure at 02:13:52 UTC:
owned identities retired, empty KFD, four unchanged/free leases; the controller
and port 8000 are also retired. The window was returned to the Q2 thread.
Full tables, ranges, thread census, retained preflight failure and graphs:
[GPU result](archive/CORE-GPU-RESULT.md). Pi itself was not rerun; numerical ownership,
RAM/SSD reuse, MTP/vision and 1M remain open. Earlier entries below are historical.

## First core GPU regression campaign prepared — 2026-10-02

The operator authorized the first extraction's original-weight GPU test. New
Release builds compare baseline `2ba01ed` and core `81c2f60`, with identical
verified official Gufo archives. `run-bench.py` now binds core input basename,
size and hash to the staged manifest; `smoke-model.py` accepts explicit private
ports and both supervisors record process thread/RSS observations. New fixture
checks cover malformed, ambiguous, changed and symlinked input declarations.

`.157` receipt `reactive-cpu-r8` passes headless 1/1, Debug 23/23 and ASan/UBSan
23/23; all nine configure/build/test exits are 0. The core benchmark suite now
has seven checks. No new engine/provider code changed after `81c2f60`.
The predeclared [GPU protocol](development/protocols/CORE-GPU-PROTOCOL.md) covers HTTP lifecycle and
latency, C1/2/4/8 and fresh 8192/131072-token prefill with exact physical replay.
GPU results are pending; source-bound CPU evidence is not GPU qualification.

`core-gpu-r1` completed the baseline HTTP performance/lifecycle arm, then the
candidate preflight refused port 8000 before model load. Both owned processes
retired, KFD was empty and all four locks were free. The preflight socket lacked
address reuse after server-side TCP close; a new private-port regression fixture
checks both active-listener refusal and retired TIME_WAIT reuse. The corrected
helper uses SO_REUSEADDR (not SO_REUSEPORT). R1 remains FAILED; its successful
baseline arm is retained with explicit hashes for the continuation.
`reactive-cpu-r9` passes headless 1/1, Debug 23/23 and ASan/UBSan 23/23,
including eight core-benchmark checks and the TCP regression. All exits are 0.

## Shared C17 core and direct benchmark implemented — 2026-10-02

`lie_core` now owns the existing reactive worker independently of the HTTP parser:
neutral deep-copied messages/tools, raw text/physical-token inputs, model/job
lifecycle, bounded admission, ready-row batching, demand, cancellation, snapshots
and retirement. The protocol library translates/frees parsed requests; no JSON
object or SSE state owns a core job. `lie/core.h` is experimental client API 1;
executor ABI 2 and the numerical Gufo pin remain unchanged.

`synapse-lie-bench --suite core` directly consumes those jobs and exports physical
input/output witnesses, per-job PP/decode call times, client first-token/total
latency and cohort throughput over total wall time, with optional plots. Historical
executor and HTTP modes retain their separate timing meanings. No new GPU rate is
claimed. Input copy and retained token witnesses add host cost that still needs
measurement. Tool-output semantic events, cache/MTP/vision and evaluation logits
remain open; the library extraction does not complete those engine features.

Coordinated `.157` receipt `reactive-cpu-r7`: headless build 1/1, full Debug 23/23,
ASan/UBSan 23/23; all nine commands exit 0. The six core benchmark tests include
actual graph export. Original-weight execution did not run; Pi/node were not
available to the private CPU runner. Full logs, exact source SHA-256 inventory
and runner remain under local `evidence/reactive-cpu-r7/`. See
[scope, limitations and next gates](development/CORE-EXTRACTION.md).

Next: bind the core input manifest in the coordinated supervisor, qualify the
refactor with the GPU, then implement RAM prefix reuse and complete hybrid state,
optional SSD, MTP/vision and measured model/numerical extraction. No deployment,
push, merge or dependency installation occurred. The earlier design-only entries
below describe their historical checkpoints, before this implementation.

## Reactive core invariant and historical thread audit — 2026-10-02

The shared-core extraction must retain reactive inference: bounded demand/output
credit, immediate ready-row scalar/native-batch dispatch, one device owner,
bounded prefill, cooperative cancellation and completed-work retirement for
every client. Synchronous provider calls remain a separate internal boundary;
moving ownership out of HTTP must not turn generation into an unbounded blocking
loop or duplicate scheduling in clients.

Source and archived harness inspection confirms one direct-benchmark model
caller, or one server device worker plus its HTTP main loop. C1/2/4/6/8 count
sequences, not CPU model threads. The earlier `performance-http-r1` process
observer contains 693 samples, all with 36 OS threads after warm-up. Gufo has
a separate PLE reader pool capped at 32; exact per-TID attribution was not
recorded. Later reactive/full-prefill campaigns did not record process thread
totals, so their application roles and measured older OS count stay distinct.
[Thread scope and receipt](INFERENCE-REACTIVE.md#thread-topology-of-the-retained-tests).
This is a read-only evidence audit and documentation update, with no new GPU
run, runtime change or performance result.

## Shared engine core required before cache implementation — 2026-10-02

The owner clarified that HTTP is a client/protocol layer; engine features must
live in one C17 core reusable by `synapse-lie-bench` and future `lie-chat` and
`lie-eval`. Corrected the architecture diagram, ownership contract and next-step
order accordingly. The core owns lifecycle, scheduling, state/cache, MTP/vision,
model semantics and typed execution observability. HTTP owns parsing and wire
projection. Direct physical-token input preserves benchmark/evaluation semantics.

Source audit confirms partial sharing today: `lie_inference` and `lie_flow` are
common, while `lie_runtime` combines worker and protocol files. The worker owns
`lie_chat_request`, including `json_owner` and transport options; the direct
benchmark independently manages sequences. A shared dispatcher does not yet
establish shared engine lifecycle/cache. The first implementation step is now
the extraction plus an actual direct-core benchmark consumer, before RAM/SSD
features. The executor diagnostic path remains a separately labelled scope.

This checkpoint updates requirements and documented boundaries only. No new
`lie_core` library, client, runtime API or cache implementation is claimed.
Validation: local documentation links/anchors and Git whitespace checks; no
runtime tests or GPU run in this increment. The ensuing ownership refactor
requires direct and HTTP tests plus ASan/UBSan on `.157`.

## C17 separation and cache/MTP/vision assessment — 2026-10-02

Documentation-only assessment: start separating engine policy, model-family
semantics and device/numerical capabilities now, before adding more session-state
features. The present C boundary still delegates model loading/binding,
tokenization, sampling, hybrid state and forward to Gufo C++ classes. Target
C17 ownership of these responsibilities in measured slices; complete removal
of retained C++/HIP kernels and runtime dependencies is a separate explicit gate.
No replacement, ABI symbol, cache flag, MTP or vision capability is implemented
by this assessment.

The first runtime deliverable is C-owned RAM prefix lifecycle/budgets and complete
version-qualified hybrid capture/restore, then optional default-off SSD storage
with explicit directory/quota and bounded staging/I/O. Contracts now include
verified MTP output bursts, rollback/RNG/predictor identity, image identity and
multimodal restart inputs. Existing Gufo snapshot support alone does not include
the external sampler or serialize image pixels. Model-family, weight packing
and platform support remain independent qualification axes; the parallel format
audit does not require a simultaneous engine rewrite.

Updated [backend assessment](BACKEND.md#separation-assessment--2026-10-02),
[architecture](reference/ARCHITECTURE.md), [planned ABI](reference/ABI.md#planned-state-mtp-vision-and-owned-execution-contracts),
[state design](reference/STATE.md), metrics and README. Corrected stale one-row/no-batching
and pending-Pi statements against existing evidence. Validation is documentation
consistency and Git whitespace/link checks only; no source/build/model/GPU work,
new CPU fixture result or numerical/performance claim in this increment.

## Extended-context benchmark client and closure audit — 2026-10-02

The new HTTP `long-context` preset supplies varied deterministic numeric records
at 258794/524288/786432/1004581 prompt targets, output64, physical-count checks,
corpus export/replay, graphs and an hour socket timeout. Capacity and RoPE are
recorded operator declarations; they do not enable backend support. Comparisons
reject different declarations. Current LIE inference remains native 262144;
the pinned provider lacks YaRN and rejects greater capacities in two layers.
No new GPU run, model access, provider change or host tuning occurred.

Fresh `.157` fixtures in `reactive-cpu-r6` pass **21/21 debug and 21/21 ASan/UBSan**,
all six commands exit 0. The client contract includes a synthetic million-token
usage case, exact corpus replay, output-room rejection and scaling mismatch.
[CPU receipt](benchmarks/2026-10-02/long-context-cpu-receipt.json).
These are wire/accounting fixtures, not real million-token inference.

The [closure matrix](development/TEST-COVERAGE-LONG-CONTEXT.md) lists missing repetitions,
HTTP/cache protocols, MTP/quality/vision/loading/memory tests and the real 1M
implementation gates. It also explicitly distinguishes the measured 4.11x gain
over scalar interleaving from the unproven benefit over existing native batching.

## Full-prefill and HTTP campaign completed

`reactive-suite-r5` on `.157` passed 21:57:54–22:19:05 UTC, 2026-10-01.
Twelve direct samples (six sizes, n=2, no discarded warm-up) reach 258794
physical prompt tokens with TG128; each point preserves exact repeat output
and full PP/TG frontiers. Median full PP is 1531.83 at 8192, 1457.88 at 32768,
1354.82 at 131072 and 1270.51 at 258794 tok/s; corresponding TG at the last two
points is 24.73/23.89 tok/s. All actual outputs have 128 tokens.
HTTP adds six full-prefill observations, ten 256-token shape observations
(mean 25.88 output/complete-wall tok/s) and a two-turn 100K conversation.
The latter takes 69.76/71.79s, confirming full-history re-prefill without cache.
Three calibration requests per applicable HTTP preset stay outside averages.
All helper/model/client exits 0; controller/children absent, KFD empty, four
unchanged leases free. Thirty-three collected files match their hashes.
[Full values, times, plots and limits](archive/FULL-PREFILL-HTTP-RESULT.md).


## HTTP 256K and direct Pi acceptance — completed with retained harness failures

Server and worker now admit context through 262144 total tokens, with a dedicated
context CLI parser rather than the 16-bit port parser. HTTP/parser body bounds
are 8 MiB, history bounds 1024 messages, default request deadline 600 seconds;
physical prompt plus requested output must fit, without truncation. The isolated
Pi profile advertises the same limits and a 630-second provider timeout.
`reactive-cpu-r4` on `.157` passed 20/20 debug and 20/20 ASan/UBSan, all six
command exits 0. New fixtures cover >1MiB Chat/Responses, exact byte/message
bounds, 256K chunk accounting and rejection before forward. These are CPU fixtures.
The HIP-linked `http256-r1` server now passes original-weight Chat/Responses at
262075 prompt tokens. Pi 0.87.1 on `.155` passed real read/edit/read over direct
HTTP `.157:8000` in 24.02 s, without a tunnel. Pi/Node remain absent on `.157`.
The firewall-blocked 19879 attempt and a later SCP-marker collection race are
retained as failed campaigns despite their separately passed capacity/Pi checks.
Both servers retired with exit 0, empty KFD and four unchanged free leases.
See [HTTP-256K-PI.md](archive/HTTP-256K-PI.md) for exact evidence and limits.


## Reactive inference GPU comparison passed and persistent checkpoint

The source now lives at
`/home/paperboy/workspace/projects/synapse-linux/synapse-lie/worktrees/openai-reactive-api`.
The old `/tmp/synapse-lie-pi-tools` copy was removed only after all 1608 files
matched and Git worktree registration was repaired across the filesystem move.
The prior benchmark/report/graph checkpoint is `ad02a01`.

The shared C17 `lie_inference` dispatcher now reserves output credit for ready
sequences and calls scalar or native batch decode immediately. It is used by
both the production worker and `synapse-lie-bench`; `--execution serial` keeps
the previous direct path for A/B. Server admission supports up to eight active
sequences, while one remains the default. ABI-2 layouts remain unchanged;
explicit additive admission and per-row completed-outcome entry points carry
no upstream types. New counters distinguish batch calls and selected rows.

Final `reactive-cpu-r3` passed 19/19 debug and 19/19 ASan/UBSan on `.157`,
including error-terminal metadata ordering; fixtures remain NOT-INFERENCE.
After the operator renewed the free GPU window, `reactive-suite-r2` passed
19:24:01–19:59:02 UTC on 2026-10-01 using code checkpoint `0e2bd45`.
Original-weight HTTP lifecycle, Responses, native tools and the seeded
heterogeneous serial/concurrent pair pass; the pair observes 32 native batches.
Direct serial/reactive comparisons use one warm-up and three measured samples
per point at C1/2/4/6/8 and occupied context 0/16K/128K. All physical/output IDs
and full PP/TG frontier hashes match. C8 decode is 107.15 versus 26.08 token/s
(4.11×); all C1 decode medians differ by at most 0.35%. Prefill remains sequential,
and no PP gain or new HTTP speedup is claimed.

All five helpers and GPU children exit 0; final postflight observes unchanged/free
leases, absent owned processes and empty KFD. All 43 archived files and 67 bound
source files verify. The earlier `reactive-suite-r1` refusal at 18:51:29 UTC
(occupied pipeline lease, exit 1, no model attempt) remains preserved.
See [REACTIVE-INFERENCE-RESULT.md](archive/REACTIVE-INFERENCE-RESULT.md).

## Earlier simplified 128K and concurrency comparison

The reusable C17 `synapse-lie-bench` implements AR depth, concurrency, loading
and memory-estimate suites, JSONL evidence and optional SVG/PNG/CSV/JSON exports.
On `.157`, matched original-weight direct-executor single runs passed all eight
depths through physical prefix 131072 (133120 total prompt tokens). At that depth
LIE TG is 24.67 token/s versus direct Gufo 24.71; all physical/output IDs and full
frontier hashes match. Matched concurrency 1/2/4/6/8 passed: at eight users LIE
aggregates 26.07 versus native Gufo batch 107.03 token/s. That measured adapter
used single-row decode; the shared-dispatcher increment above addresses this gap.

Fresh CPU fixtures passed 18/18 debug and 18/18 ASan/UBSan, including the
small-context calibration regression and graph exports. The initial suite retains
its FAILED root and actual exit 1 before any multi sample; the corrected follow-up
ran only missing arms and completed PASS (all six helper/child exits 0).
Final owned PIDs are absent and no known lease holder is observed. These are
simplified direct AR measurements, not HTTP
128K/cache support, MTP or independent numerical qualification. See
[BENCHMARK-RESULTS.md](archive/BENCHMARK-RESULTS.md) and
[CONTEXT-COMPARISON.md](archive/CONTEXT-COMPARISON.md).

## Earlier serial-runtime performance and DS4 coverage

The `.157` GPU performance matrix passed on 2026-10-01: nine direct C1
measurements, 110 measured HTTP requests plus 22 warm-ups across 16 configurations,
24-client admission burst (8 completed, 16 capacity refusals), and the real-model
cancellation/backpressure/isolation suite. CPU fixtures passed 17/17 in debug
and 17/17 with ASan/UBSan on `.157`. Runtime binary remains the earlier API-qualified
`213c91e` build; harness changes add measured clients and prompt metadata.
All four leases were free/unchanged and owned processes absent at final postflight;
KFD was empty. No deployment or publication.

Direct PP medians are 999.65 / 1648.11 / 1608.97 token/s for physical prompt
counts 502 / 2042 / 8191; TG medians 26.87 / 26.07 / 25.98 token/s. C2 serving
roughly doubles request latency with similar aggregate throughput: no reactive
inference speedup is demonstrated. Full timings, sampled resources and limitations
are in [PERFORMANCE-RESULT.md](archive/PERFORMANCE-RESULT.md).

[DS4-COVERAGE.md](development/DS4-COVERAGE.md) records the read-only comparison. Coverage is
not equivalent: vision, MTP, native batching, prefix/snapshot state, extended
sampling and long-context qualification remain among LIE's missing capabilities.
Neither API completeness nor DS4 historical numerical qualification is inherited.

## API implementation

Worktree `/home/paperboy/workspace/projects/synapse-linux/synapse-lie/worktrees/openai-reactive-api`, branch `feature/openai-reactive-api`, created
from `develop`, then fast-forwarded to the existing native-tools base `e3d0c7a`.
The original worktree remains untouched; no merge, push or deployment.
On 2026-10-01 the linked worktree moved out of `/tmp` at the operator request;
all 1608 transferred files matched before removing the old copy. Benchmark
checkpoint: `ad02a01`. Historical evidence retains its original paths.

User direction: general OpenAI functionality, compatible clients through their
ordinary protocol; C reactive execution, tests on `.157` with GPU. New Responses
normalization/wire and sequence sampling build on the typed native tool API and
existing bounded flow. General API coverage remains incomplete; see
[the exact capability matrix](reference/OPENAI-REACTIVE.md).

Remote `openai-reactive-cpu-r3`: all 16 CTest suites pass in debug and with
ASan/UBSan. Local HIP link succeeds against the pinned LIE-owned upstream build.
The earlier compile type mismatch (`int32` prompt versus upstream unsigned
sampler history) and its actual exit code are retained under
`evidence/openai-reactive-build-r2`; the adapter now explicitly copies the typed
history. Original-weight GPU runs `openai-reactive-gpu-r2/r3` passed lifecycle, Responses
JSON/SSE, seeded sampling and a native function round trip. Final server/helper
exits are 0; all four unchanged leases are free and KFD empty at postflight.
See [the precise result and limits](archive/OPENAI-GPU.md).
These statements do not qualify independent numerics, performance or deployment.

# Resumption — original-weight serving smoke and C1 baseline, numerical gate open

Owner: synapse-lie fork; DS4 remains the other agent's project.
Repository: `/home/paperboy/workspace/projects/synapse-linux/synapse-lie` on `.155`.
Branch: `feature/initial-runtime`, from `develop` seed `ce3ce59`.
The runtime increment starts at `79625ce`; the resumed smoke/runner fix starts
at `b7de609`. No workflow or independent review is claimed.

## Current direction — Q2 withdrawn; operate Unsloth with Pi

The owner requested cancellation/replanning of the Q2 work, then prioritized
making the current Unsloth-backed runtime usable from Pi. Active implementation
was restored to **`4307486`**, removing Q2 overlays, fixtures and build helpers.
C17 runtime/server and the original UD adapter are retained unchanged. Historical
reports/evidence and qualified builds are preserved, not active Q2 support.
The [replacement plan](archive/REPLAN.md) puts Pi tool operation first and any future Q2
reference measurement before another port. No new GPU result is implied by rollback.

Rollback is committed as **`ffca17e`**. A proportional baseline check passed 13
CPU suites with ASan/UBSan. A deferred Q2-restart task is in the Synapse backlog;
that capture does not authorize another port or GPU run.

## Server tools — implemented; native Pi CPU round trip passed

The owner rejected a Pi-specific bridge and required completion of the server.
The unexecuted client draft was withdrawn into `pi-client-bridge-rejected-r1`;
no global Pi configuration was changed. New C17 input/output parsing supports
OpenAI tool declarations, structured calls, correlated results, tool choices,
JSON/SSE results and bounded complete-turn validation. The original native Qwen
template is used through an additive C ABI entry point. No numerical kernels,
weights, source dependency or DS4 artifact changed.

`server-tools-final-cpu-r1`: **15 CPU suites pass with ASan/UBSan**, including
nested nonfinite-value rejection and buffered-tool cancellation/error accounting.
The new production candidate `build/server-tools-linked-r2/synapse-lie-server` links unchanged pinned
provider archives; **16 CPU suites pass**, including the actual Qwen formatter.
All compilation/tests are serial/local and GPU-masked. `server-tools-pi-cpu-r4`
proves the installed Pi's **standard OpenAI provider** consumed a structured call,
executed its real `read`, returned the file content and received a final reply
from the synthetic server. It is not model inference. The earlier Pi fixture
failed because 4096 context equaled Pi's fixed safety margin, reducing the output
budget to one token; raw trace/exit and diagnosis remain. The normal profile now
uses matching server/client context 32768, without changing Pi itself.

The actual Unsloth tool session, 32768-context memory/correctness and updated
serving/PP/TG behavior remain untested. No model/GPU run, remote staging, permanent
listener or new lease was started. Current coordination is required before that
next gate. [Exact scope and setup](archive/SERVER-TOOLS.md).

The Q2 sections below are dated records of the now-withdrawn experiment.

## Historical first real Q2 model test — matched performance never established

`q2-model-first-gpu-r1` completed at **2026-10-01 10:15:04 UTC** on `.157`.
The actual antirez Q2 loaded in **11.638 s**, answered exactly `4`, and generated
128 tokens counting from 1 through 46, with finite checked frontier logits.
The second fresh session had **458 physical prompt tokens**, **368.18 PP tok/s**
and **19.79 TG tok/s**. No benchmark warmup/repetitions or matched comparison:
these results do not prove preserved performance versus the historical UD ~26.

Only an isolated test overlay/executable was enabled. Production upload/link
refusals are unchanged. After the operator dedicated the machine to the model,
the proposed 53.5 GB cumulative allocation cap and 32 GiB reserve were removed
before execution. PLE stays disk-addressed with direct-I/O-only test readers;
reported/cumulative bytes are not an independent resident peak. No CPU forward.

Actual binary: `q2-model-first-relink-r1`, using unchanged HIP archives from
`q2-model-first-build-r2`. Both retain Git base `c0d6c6d` plus their source diffs;
no source-SHA inventory was added. All four leases, current preflight and start/end
registration were used; child/supervisor exited 0 and model stat/artifacts stayed
unchanged. At **10:18:10 UTC** both identities were retired, KFD empty and the four
unchanged leases free. No pending GPU job or standing authorization remains.
See [scope, timings and evidence](archive/Q2-FIRST-MODEL.md). Next is matched UD/Q2
performance and independent quality, not another synthetic-only model verdict.

## Earlier Q2 preflight change closed — local build/tests only

The private `Executor::Create` now validates the entire Q2 descriptor profile
before construction or HIP calls. All gate/up/down expert counts and nonempty
storage must match, alongside geometry, layer count and workspace capacity;
up-only mixed formats are also detected. The C17 planner has 720 single-field
rejection fixtures. No kernel arithmetic, `RowScratch`, upload refusal or
production provider change is included.

`q2-admission-linked-r1`: serial masked HIP build/link and host checks pass.
`q2-admission-close-r1`: all 17 CTest suites pass under GCC, Clang and ASan/UBSan;
source identity uses base commit `82df5dd` plus `source.patch`. Earlier RED logs
remain in `q2-admission-dev-r1`. Closure is deliberately limited to the existing
change: no additional memory subsystem or qualification campaign was started.

At that preflight closure, Q2 model loading and PP/TG were **NOT RUN**;
executor/model integration and necessary memory admission remained unfinished. The previous 24+64 GPU results
belong to their recorded binaries, not this newly compiled candidate. No remote
work, GPU run, model access, DS4 change or publication occurred in this closure.
Details: [Q2-HIP.md](archive/Q2-HIP.md#latest-source-closure--executor-profile-preflight).

## Q2 extended operators — two fixes, 24 + 64 controls pass

The renewed GPU window exposed two genuine arithmetic losses: IQ2 vector
integer division discarded fractional eighths; Q2 MMA rounded scale/minimum
products back to half. Both RED failures and raw outputs are retained. The
private, hash-guarded fixes preserve the original tolerance, bounds, workspace
allocation and production refusal.

`q2-operator-extended-green-r3` passes **24/24** (15 IQ2, 9 Q2), including all IQ2
grid entries, varied weight half mantissas, 640/2560 output widths, last expert
511, requested tile widths 16–80, capacity extremes and workspace reuse.
The offline audit checks **1,725,239 raw outputs**, zero mismatches, maximum
absolute error **3.0517578125e-5**. `q2-operator-legacy-green-r1` additionally
passes the **64 original grid-zero controls** on the corrected candidate.
These are operator fixtures, not original-UD model regression or model inference.

A stale source-receipt SHA field in three cloned manifests is explicitly retained
and documented, with additive verified build/source bindings; the audit is not
an unqualified manifest-consistency PASS. See [Q2-EXTENDED.md](archive/Q2-EXTENDED.md).
At 08:14:28 UTC the four GPU attempts' process identities were retired, KFD empty
and all four unchanged leases free. No model payload, benchmark, deployment,
remote build, tuning or DS4 change occurred. Executor integration, arbitrary
activations, memory admission and independent full-model numerics still block
Q2 model loading; antirez and updated-server PP/TG remain NOT RUN.

## Earlier Q2 initial GPU operators — 64/64 pass, model admission still closed

After the fresh `hai la finestra libera` handover, `.157` passed the fixed
`q2-operator-gpu-r1` synthetic suite at **2026-10-01 07:03:42–07:03:46 UTC**
(supervisor scope, not timing/throughput). All four existing leases were held
nonblockingly. The unchanged r5 probe from `dc5ef28` completed 36 IQ2 and 28 Q2
cases with maximum reported absolute errors 4.76837158e-7 and 0 respectively,
within the predeclared tolerance. Padding/output guards pass; no retries.

Raw case records, empty stderr, nine telemetry samples and start/end registration
are retained and pass offline audit. Child/supervisor exit 0, binary/DSOs/power
settings unchanged; owned PIDs absent/KFD empty at 07:04:44, known leases free at
07:07:03 UTC. Desktop clients/denied FD observations remain visibility limits,
not proof of universal exclusivity. No model access, remote build, deployment,
install, tuning or DS4 changes. Full GPU output arrays were not emitted.

**Scope is limited:** grid-zero IQ2, synthetic power-of-two scales/activations,
small ragged output shapes and tiled width 16. Full codebook/shape qualification,
Executor/RowScratch integration, matched UD regression, role-aware memory
admission and independent full-model parity remain. Model upload/runtime gates
stay closed; antirez and new-server PP/TG remain not run. See [Q2-HIP.md](archive/Q2-HIP.md).

## Earlier Q2 HIP implementation — compiled, before the GPU run

The private candidate now routes IQ2_XXS gate/up (vector, paired/grouped and
prefill tiled) and Q2_K down (vector/tiled). Logical 640-float rows are read with
stride 640 directly into zero-padded quantized storage, while weight stride
remains physical 768. No additional FP32 padded copy/kernel is introduced.
C17 planning reserves one executor-owned workspace for quantization, ID maps,
rank/count and grouped-vector scratch; the new projections do not grow a pool
or global ID-map allocation during forward. Shape/format choices stay on the
host, with specialized dot-product kernels and necessary GPU tail guards.

`q2-route-linked-r5` passes HIP compile/link, the shared upstream formatting
script and masked host refusal/scalar-golden checks. The MMQ TU retains the
upstream C++17/gfx1151/NO_VMM flags. The host recipe received formatting-only
changes; eight host cases still pass all compiler/sanitizer variants.
Seventeen default CPU suites pass in `q2-route-cpu-r2`. Delivery audit r2 checks
all final hashes, production refusal and saved-header GCC/Clang binding again.
Its earlier diff-rendering error on an unchanged binary fixture is retained.
All original sources/builds remain intact.

At this implementation receipt, GPU work was still **not run**. The later
64-case run above advances only the initial operator gate; its scalar expression
covers Q2 affine blocks and IQ2 grid-zero sign/scale cases, not the full codebook.
Runtime admission remains disabled pending broader format/shape checks,
full-model memory admission/reference qualification and PP/TG. See
[Q2-HIP.md](archive/Q2-HIP.md). No reactive speedup or cache capability is claimed.

## Q2 compatibility started — private host path passes, GPU path remains closed

The requested Q2-first implementation now has a private, hash-guarded
transitional provider variant: IQ2_XXS/Q2_K storage and binding, F16 HC inject,
physical 768/logical 640 down-input separation, and MXFP4 descriptor recognition
for the unused stored predictor. No `.deps`, model or qualified build was changed.
This extends delegated Gufo; it is not an autonomous LIE C17 model executor.

A full actual-header-derived binder test uncovered another concrete blocker:
missing `rope.dimension_sections`. The failure is preserved. A narrowly identified
text-AR Q2 rule uses canonical [11,11,10,0] sections from the independently fetched
official pinned Qwen config, without replacing malformed explicit metadata or
editing weights. Source/configuration licenses and identities remain separate.

The same actual **11025350 header bytes / 1256 descriptors** now bind all **48 AR
layers** through `ModelWeights::Bind` with GCC and Clang. Declared payload regions
are PROT_NONE in an anonymous virtual view: no weight values or model forward.
Eight synthetic host contract cases also pass GCC/Clang/ASan/UBSan; the source
materializer has seven contract tests. The original source remains pristine.

**This is not yet GPU Q2 compatibility, full-model loading, numerical
qualification or a benchmark.** Runtime linkage is expressly forbidden for this
host variant and device upload has a pre-allocation Q2 refusal. The subsequent
HIP candidate above implements the routing/padding; GPU qualification,
role-aware memory admission and numerical/model/performance gates remain. See
[Q2-COMPATIBILITY.md](archive/Q2-COMPATIBILITY.md). Cache work stays behind this path.

## Antirez prefill/decode benchmark — format admission work

The operator explicitly requires **full prefill and decode benchmarks for the
antirez model**, not substituted UD-Q4_K_XL numbers. Both protected Q2/Q4 files
were inspected read-only at 2026-10-01 03:35/03:42 UTC, bounded to 24 MiB of
metadata/descriptors per file. All inherited stat identities match; no tensor
payload, model load, GPU execution, weight hash/conversion or DS4 modification.

Concrete layout: Q2 has 96 IQ2_XXS AR gate/up tensors and 48 Q2_K down tensors
with physical input 768 versus logical 640. Q4 has Q4_K gate/up and MXFP4 down,
not uniform Q4_0. Both carry one predictor layer and a 102400491520-byte BF16
PLE table; file size is not a measured all-resident GPU budget. MXFP4 geometry was
identified from independently fetched official upstream source, not a sibling
project import. Initial unknown-type observations are preserved.

The pristine pinned Gufo reader rejects MXFP4 in a CPU in-memory fixture probe;
it occurs in both actual files. Binder restrictions (including F16 HC inject),
padded geometry and routed PP/TG dispatch need additional implementation and
qualification. **Antirez LIE PP/TG remains NOT RUN / blocked**, not zero and not
inherited from a DS4 run. No GPU attempt was made against a known parser blocker.
The [per-format benchmark gate](archive/ANTIREZ-BENCHMARKS.md) specifies full fresh PP
512/2048/8192 targets and TG128, C1 direct-ABI and separate HTTP/server lanes,
matched references, numerical/admission gates and all-sample retention.

The formerly untested `tools/gguf-layout.py` draft now has fifteen synthetic
storage/parser tests and a registered CTest suite. RED reproduced invalid bool/
alignment acceptance and FIFO blocking; the corrected reader is bounded,
regular-file-only, identity checked and explicit about incomplete unknown-type
geometry. `antirez-layout-green-r1/r2`: fourteen suites pass GCC/Clang/ASan/UBSan
and Gufo header checks. These are not inference. Native provider/server numerics
and the C17 executor benchmark were not changed by this discovery increment.
RAM prefix reuse and optional/default-off SSD persistence remain unimplemented.

## Latest GPU result — original-weight lifecycle passed

`t0-model-lifecycle-r1`, **23:01:13–23:01:44 UTC**, used source `efcb7fb` and the
HIP-linked `t0-lifecycle-linked-r1` server. All four actual leases, DSO/model/
binary preflight, start/end registration and owned shutdown passed. It is
`MODEL_HTTP_LIFECYCLE_PASS_NOT_NUMERICAL_QUALIFICATION`.

Six JSON/SSE cases preserve READY/4/caffè 🙂, usage and EOS, with valid per-request
PP/TG timings and one timing finish per SSE. Additional cases observed first
cancellation in prefill/decode dispatch, clean retirement, an unread TCP client
stalled at 65 generated tokens for at least 0.511 s, an unaffected arithmetic peer
and matching post-cancellation recovery. Final: **9 completed, 3 cancelled,
0 failed, 79 generated**, no queued/active/blocked jobs; 12 prefill and 89 decode
calls all returned. Server/helper exit 0; binary and five model stat identities
unchanged; no full weight hash. No foreign client observed, KFD empty after exit.
At 23:05:36 UTC, owned processes were absent and all known leases had no holders.

All 228 lifecycle events, raw responses and 29 telemetry samples are retained;
offline audit exit 0. This is a scoped real-model server result, **not** kernel
preemption, native batching, independent numerical equivalence, capacity testing
or a fresh performance baseline. Neither RAM prefix reuse nor SSD is implemented.
Details/identities: [T0-LIFECYCLE.md](archive/T0-LIFECYCLE.md). No deployment or retry left.

## Source increment — executor guards and lifecycle protocol

A fresh read-only target check at **22:09 UTC** observed an active DS4 Q4 benchmark
campaign, KFD activity and all four leases occupied, including the enclosing
pipeline lease. No formal ACK was present. Receipt: `t0-lifecycle-activity-r1`.
No LIE GPU attempt, staging, lock acquisition, heavyweight I/O or foreign process
intervention followed; no background wait/retry. This is a dated observation,
not permission to enter gaps in that campaign.

The C worker now validates returned positions, token/count/stop ranges and text
sizes before publication. Unexpected provider errors or malformed successful
returns fail the runtime and its peers without retry, rather than allowing
uncertain state to remain ready. Controlled CPU fixtures expose the old invalid-
position bug (RED runtime exit -6, `t0-worker-frontier-red-r1`), then test thirteen
fault modes and prefill/decode cancellation with consumer release before return.
Dispatch counters/phase and output-credit stalls are now visible via management;
these are owner intervals, not proof of GPU-kernel preemption.

`tools/serving_checks.py` is intermediate Python qualification tooling, not the
planned C17 benchmark. The explicit `http-lifecycle-v1` suite in the existing
lease-gated supervisor validates JSON/SSE timings, disconnects during observed
prefill/decode dispatch, sustained TCP backpressure, matching fresh/interleaved
peer responses and clean recovery/accounting. Missed windows are INCONCLUSIVE;
all observations and failures are retained. Hash/settings gates precede model
launch. CPU synthetic coverage passes; the subsequent real-model result is
recorded separately above. Protocol and exact boundaries: [T0-LIFECYCLE.md](archive/T0-LIFECYCLE.md).

The default-off optional SSD requirement is retained in commit `7f6a32`, with
RAM reuse independent of persistence. Neither prefix reuse nor SSD is implemented
by this server-hardening increment. Antirez Q2/Q4 and the independent pristine
numerical comparator remain open. The GGUF inspector was an untested draft at
this lifecycle source commit; its later validation is recorded above.

Initial local receipts: `t0-worker-frontier-green-r1` (twelve suites) and
`t0-lifecycle-helper-r1` (initial thirteen suites), GCC/Clang/ASan/UBSan/header only.
Final CPU closures `t0-lifecycle-closure-r1/r2` pass all thirteen suites;
`t0-lifecycle-linked-r1` links HIP and passes masked/no-model/synthetic checks.
Server SHA256: `f71dbe74f95415bbfe1880a2de1804b73adc3ea24eaab371a6308eaaf8b5db0a`.
The second CPU closure additionally covers exact-verified-byte helper loading.
All of these remain separate from GPU qualification.

At **22:42 UTC**, the operator supplied a new GPU window (`hai a disposizione
gpu`). A fresh read-only probe `t0-lifecycle-activity-r2` observed empty KFD,
GPU busy 0%, no inference/model handles and no holders of the four known leases.
No formal ACK was present. This permits preparing a one-shot attempt, not bypassing
nonblocking lease acquisition/admission or claiming global exclusivity.

## Previous source increment — request timing, no new GPU run

User direction: definitive `synapse-lie-bench` in C17; Python may serve intermediate
development/graphs while server functionality takes priority. Pinned Gufo method
review: `fd1710b5fd090880722e0681a868df2006595c73`, separate from the unchanged
provider pin. [BENCHMARKING.md](archive/BENCHMARKING.md) records exact experiment semantics
and current gaps. No upstream benchmark script was run; the complete named tool
is not implemented. Antirez Q2/Q4 discovery remains unqualified and separate;
the previously written `tools/gguf-layout.py` is still an untested draft.

C worker snapshots and JSON/SSE now expose versioned per-request PP/TG executor-
call timing. Physical input deltas are counted once; EOS detection consumes time
but not an output token. Queue, other-session and credit stalls are not phase
compute time. Invalid clocks latch null duration/rates without retrying inference.
Timing/accounting precedes terminal publication; failure/cancellation cannot
produce a successful timing record. No numerical/adapter/executor ABI changes,
new GPU barriers, prefix reuse, MTP, native batching or aggregate latency metrics.

The HTTP regression failed against the prior qualified CPU fixture binary with
`KeyError: 'lie_timings'` (`t0-request-timings-red-r1`, exit 1). Initial eleven-suite
GCC/Clang/ASan/UBSan/header verification passed (`t0-request-timings-green-r1`).
Final eleven-suite GCC/Clang/ASan/UBSan/header closure passed, additionally checking
partial prefill failure and zero-output rates (`t0-request-timings-closure-r1`).
The new private `t0-request-timings-linked-r1` also passed HIP adapter linking,
build-info, no-model and all synthetic tests, with GPU visibility masked.
Server SHA256: `cf6da02e33b6f8c840bbd5693daf9ec74d8cbb2b287e9cead4f9857f194a16f5`.
Test-only link-time clock wrapping
covers completed counts, queue/credit exclusion, in-flight cancellation, EOS,
clock failure/regression/overflow and zero-resolution division. No model access
or GPU execution; previous measured binaries/baselines remain unchanged. This
source-only increment had no new GPU run at its commit. The later lifecycle
run above exercises these timings on the GPU; a new performance baseline remains
unmeasured.

## Latest target result — C1 baseline, 2026-09-30 20:52 UTC

The user's explicit prefill/decode request produced a new C17 direct-executor
harness and leased supervisor, without changing the adapter or numerical sources.
`t0-c1-perf-r2` completed one warmup and three measured fresh-session runs for each
actual prompt size 502/2042/8191, all TG128, common context9216/chunk2048. Median
PP: **988.68 / 1642.65 / 1607.13 tok/s**. Median TG: **26.851 / 26.049 / 25.965 tok/s**.
Full finite PP/TG frontier logits and outputs matched warmup exactly. All nine
measured samples are retained; no profile/tuning/HTTP or outlier removal.

Child/helper exit 0, original stats and artifact hashes unchanged, no foreign GPU
client observed, KFD empty after retirement. Existing governor `powersave`, EPP
`balance_performance`, GPU DPM `auto` were retained. This is a C1 embedded-provider
baseline, not independent numerical qualification or a reactive speedup. Exact
scope, ranges and all conditions: [C1-BASELINE.md](archive/C1-BASELINE.md).

`t0-c1-perf-r1` had failed before model launch on an absent optional sysfs power
attribute, not a GPU/model error. Its failure and the focused CPU RED/GREEN are
preserved; unavailable telemetry is now explicit null/error. No workload or
admission control was weakened. Code commits `cbb06fc` (harness) and `7f85ef8`
(supervisor fix); ten CPU suites pass, including eleven benchmark contract cases,
with GCC/Clang/ASan/UBSan (`t0-perf-cpu-r3`). HIP/no-model receipt:
`t0-perf-linked-r1`; final documentation/source CPU closure: `t0-perf-closure-r1`.

## Previous target result — serving smoke, 2026-09-30 20:07 UTC

A fresh operator handover (machines free, resume LIE) and read-only observation
preceded successful acquisition of all four existing leases. `t0-model-smoke-r3`
passed target binary/DSO preflight but hit a Python runner name collision directly
after server launch; no inference was observed, helper exit 1/child exit -15.
That failure is retained. `http_client` now avoids the collision, with four
CPU-only HTTP regression cases added as the ninth CTest suite. Focused RED/GREEN
and GCC/Clang/ASan/UBSan/header checks passed (`t0-smoke-runner-fix-r1`).

`t0-model-smoke-r4` then passed **all six original-weight requests**: READY, 4 and
`caffè 🙂`, each nonstream and SSE with identical content/usage/stop, one DONE,
clean retirement and server/helper exit 0. Totals: six completed requests, ten
emitted tokens, zero failed/cancelled. No foreign GPU clients were observed;
KFD was empty after shutdown, and binary/model identities were unchanged.
Executed build remains `t0-linked-r4`; no C/C++ runtime source changed.
See [T0-SMOKE.md](archive/T0-SMOKE.md) and its exact receipts. No pristine numerical,
broad quality, concurrency, cancellation-in-flight or performance qualification follows.

## Previous target admissions — 2026-09-30 18:53 UTC

Following the operator's explicit go-ahead after the idle-node inspection,
`tools/smoke-model.py` and the unchanged `t0-linked-r4` binary were staged under
private LIE run directories on `.157`. Two attempts at 18:49 and 18:51 refused
admission on a busy DS4 download lock, exit 1, **before any LIE model open**.
No target model/DSO smoke or inference was performed. At 18:53 a DS4 `native-perf`
warm-up was using the GPU at 98%, with download/qualification/shared locks held.
Do not enter between its benchmark phases. No background retry is scheduled.

See [T0-SMOKE.md](archive/T0-SMOKE.md) for the exact operator-window scope, predeclared
requests, observations and preserved `t0-model-smoke-r1/r2` receipts. Staging a
private test binary is not a service installation or a working-model result.

## Policy and actual status

The user permits embedded Gufo for T0, followed by requirement-driven T1/T2
refactoring toward an autonomous C backend. The older reference-only prohibition
is superseded, not the autonomy goal. See BACKEND.md and INFERENCE-REACTIVE.md.

**The HIP-linked executable has now performed bounded original-weight GPU
inference through C HTTP/SSE, worker, flow and provider binding.** The first real
serving smoke passed, while the complete T0 acceptance gate (including pristine
numerical comparison and real cancellation/backpressure) remains open. Separate
synthetic tests are still distinct from this actual-model evidence.

## Implemented in this increment

- `src/worker.c`: one pthread device owner, eight bounded admissions, one active
  sequence by default or two explicitly configured interleaved single-row
  sequences. Round-based chunk/step scheduling; never native batching by claim.
- Independent worker and consumer references keep jobs alive after disconnect.
  Short metadata gates protect publication and cancellation-latch versus
  sequence detachment. No GPU wait is held under these gates or on the HTTP loop.
- Eight token slots per job, 256 bytes each. Decode reserves/begins before work;
  SSE releases/replenishes credits only after uv_write completion. Nonstream
  reserves a bounded aggregate sink. Active admission is not a measured RAM fit.
- Text request validation and copied ownership; pinned Qwen renderer, thinking
  disabled, context admission before session creation/forward, greedy AR only.
  Streaming UTF-8 replacement decoding is independent of token boundaries.
- Real nonstream JSON and SSE formatting, usage/finish/error terminals, queue
  refusal, disconnect, request deadline and shutdown lifetime handling.
- ABI 2 adds chat preparation and provider metadata/selection. Gufo types remain
  inside the adapter. The neutral worker opens the selected composition binding;
  `lie_gufo_open` remains explicitly Gufo, not renamed into an ownership claim.
- For loaded-runtime backend failure, adapter drains device work before returning
  failure/allowing retirement. Undrainable device failure exits 70 without retry
  or core dump. This exceptional hardware path is compile/link checked, not GPU
  fault-tested. Successful calls have no added device-wide barrier.
- Diagnostics disclose engine, source pin, build label, delegated/synthetic/none
  ownership and unsupported capabilities. `--build-info` opens no model.
  Hardware qualification is false. Worker counters are not remote-delivery ACKs.
- Opt-in `LIE_GUFO_RUNTIME`; real libraries from independently fetched upstream.
  A LIE-owned Qwen-only CMake scope uses the upstream model target and unchanged
  source. It is not the full upstream release build. No numerical port exists.

No tools, native batching, MTP, vision, prefix reuse, RAM/SSD restore or CUDA is
exposed. Unknown memory/latency/throughput/cache metrics remain null. Default
no-model startup still has readiness 503, empty models and chat 503. The synthetic
provider is only in test executables and reports `NOT-INFERENCE`.

## Preserved build/verification evidence

All paths below are local `evidence/` directories; labels are occupied. Receipts
record actual process exit codes, logs and source/binary identities.

| Label | Observed result / scope |
|---|---|
| `gufo-host-r1` | Full upstream configure failed, exit 1: missing rocWMMA header. No install or fake header. |
| `gufo-qwen-host-r1` | Qwen subset archives built, no execution. |
| `t0-runtime-r1` | Eight CPU/synthetic suites passed with GCC, Clang, ASan/UBSan; Gufo header object passed. Before final cancellation/error refinements. |
| `t0-linked-r1` | Link failed, exit 1: omitted upstream sample/argmax translation unit and curl link dependency. Failure preserved. |
| `gufo-qwen-host-r2` | New private subset build includes real upstream sampling unit and curl dependency; original source unchanged. |
| `t0-linked-r2` | Real HIP adapter linked; eight CPU/synthetic suites and no-model smoke passed. No weight/model/GPU execution. Before final refinements. |

`t0-runtime-r2` passed all eight suites in GCC/Clang/ASan/UBSan at
18:11:53–18:12:10 UTC, including the final binding/error/lifetime refinements.
`t0-linked-r3` passed real linking, `--build-info`, no-model and synthetic tests at
18:12:19–18:12:26 UTC, with no model access/GPU execution. Its binary SHA256 is
`b7b42150d070bf91915d2859ce66b71fed2d386f4a7f12682d5e1736309fd1d6`.

The runtime closure labels are **`t0-runtime-r3`** and **`t0-linked-r4`**.
The resumed runner/documentation closure is **`t0-smoke-closure-r1`** (CPU only).
Their `result.json` and delivery receipts, not a label or build target, establish
success and exact source identity. Label-owned build directories preserve earlier artifacts. Local link verification
masks GPU visibility, isolates HOME/cache/temp, records ELF dependencies and
never supplies `--model` to the real server.

Seventeen current default CPU suites: `chat-parser-wire`, `worker-synthetic`, `worker-timing-contract`,
`worker-executor-contract`, `reactive-flow`, `metrics`, `monitor-parser`,
`executor-c-layout`, `http-monitor`, `http-synthetic`, `model-smoke-helper`,
`serving-lifecycle-helper`, `executor-bench-contract`, `gguf-layout-contract`,
`q2-source-contract`, `q2-route-plan`, `q2-hip-source-contract`.
The eight Q2 host C++ cases are a separate optional suite,
not part of the linked production provider. All contract/helper checks
use CPU clock/HTTP/executor fixtures only, never GPU/model execution.
The synthetic suites exercise in-flight cancellation with a barrier, owner-thread
checks, context refusal, queue saturation, a stalled peer, real TCP backpressure,
UTF-8 split/invalid bytes, JSON/SSE equivalence, deadline, poison, error terminal,
FD cleanup and shutdown. They are not GPU/numerical/quality evidence. ASan/UBSan
covers first-party CPU paths and the fixture, not the GPU kernels.
No TSan, independent review or promtool pass is claimed.

Earlier `cpu-closure-r1/r2`, `reactive-closure-r1`, `backend-scope-r1`,
`backend-evolution-r1`, guard refusals and their delivery receipts remain historical
and unchanged. The old policy/guard result is not reinterpreted retrospectively.

## Coordination: resumed window

The 20:01 UTC observation (`t0-node-activity-r2`) followed the operator's fresh
handover. No DS4 ACK was present; none was written for its owner. Both r3 and r4
held pipeline/download/qualification/shared leases, with actual start/end records.
The successful serving r4 exited at 20:07:42 UTC and released its leases.
A later explicit measurement request admitted `t0-c1-perf-r2`, with its own
start/end records and clean exit at 20:52:07 UTC. No foreign process, DS4
source/build/cache/service/profile, model or qualified artifact was modified.
No deployment or background retry is left running.

This operator window is not permanent shared-runner adoption. Further GPU work
requires a current handover/lease, fresh preflight and register entries; idle
hardware or SSH alone is not authorization. See COORDINATION.md.

## Next work under a fresh admitted run

1. Fresh identity/memory/storage preflight; stat the original five read-only files
   against inventory, without assuming old values are live or rehashing weights.
2. Build a private independently pinned pristine comparator; retain compiler,
   flags, source, binary and target DSO identities. Prefer local serial compilation;
   remote GPU compilation needs separate coordination. Full upstream configure's
   missing rocWMMA dependency remains a blocker, not permission to install it.
   Local workspace visibility on `.157` must not be assumed.
3. Original-weight C1 short-context AR: validate physical prompt IDs, completed
   frontiers and output against the independent reference. Bounded HTTP/SSE,
   UTF-8, cancellation, pressure/isolation and retirement now pass in the lifecycle
   run above; this does not replace the numerical comparator or GPU failure gates.
   Define any extended protocol and oracle before execution. No rollout.
4. Only with a correct baseline, collect separate pure-inference traces and test
   a falsifiable internal-reactive change. Completed PP/TG, concurrency and serving
   improvements remain separate; no benefit has been measured yet.
5. T1/T2 refactoring, native C2/4/8, tool continuity, complete RAM/SSD state and
   MTP remain separate gates; CUDA follows qualified AMD work. SSD save/restore is
   a required **optional, default-off** feature with explicit enable, private
   directory and quota controls; RAM prefix reuse must work independently. The
   clarified [state contract](reference/STATE.md) is design only, not a working CLI flag.

Do not reintroduce the historical assistant-imposed 32 GiB reserve as a user
requirement, call the DS4 300K stop an OOM, or import DS4's benchmarks/quality into
LIE. The monitor/UI is still development en_US; v0.1 is not release-ready.

## Full-prompt and served benchmark increment — 2026-10-01

Added C17 `fresh` suite at capacity 262144, all-new PP sizes through 258794 and
actual TG128; report comparison keys/graphs now distinguish full prompt sizes.
Added `synapse-lie-bench --suite http`, an explicitly separate Python client
harness with calibrated full-prefill, ten original prompt shapes, actual
multi-turn history, exact corpus export/replay, usage/TTFT/wall timings and plots.
No server/cache/MTP configuration or tool execution is performed by this client.
`.157` `reactive-cpu-r5`: 21/21 debug and 21/21 ASan/UBSan; six command exits 0.
Raw source hashes/receipts: `evidence/bench-comparable-cpu-r1/`. The subsequent Pi
profile port-only edit selects 8000 at the user's request. The full-prefill and
HTTP benchmark GPU qualification follows these CPU checks, not implied by them.
Detailed reactive attribution is in `docs/INFERENCE-REACTIVE.md`.

## Reactive and long-prefill audit

`docs/INFERENCE-REACTIVE.md` maps reactor, flow credits, worker, shared inference
dispatcher and synchronous adapter boundaries to code and actual evidence.
The C8 4.11x result is attributed to ready-row dispatch plus native batching;
C1 stays within 0.35%, PP remains sequential and no matched HTTP tail-latency
improvement is claimed. `docs/PREFILL-ANALYSIS.md` records actual pinned-source
candidates, including causal block scoring and repeated host prefix scans,
without claiming a profile or implementing speculative optimizations. The
user-requested external comparison research is retained privately in
`evidence/prefill-research-r1/`; public product documentation stays independent.

## 2026-10-02 — Documentation, published charts and bundled libuv

The README now introduces the project, dependencies, build and first request.
Separate [build](guides/BUILD.md), [usage](guides/USAGE.md) and
[benchmark](guides/BENCHMARKS.md) guides replace the previous scattered setup
instructions. [CHANGELOG.md](../CHANGELOG.md) records user-visible changes.
Contracts live under `reference/`, development protocols under `development/`,
and historical implementation reports under `archive/`. Ten small legacy-path
pointers preserve links from immutable dated measurement records.

The [Qwen/Strix Halo page](benchmarks/models/qwen3.8-flash-next/strix-halo/README.md)
contains the eight-depth AR table, concurrent PP/TG and full fresh prefill through
258,794 tokens, with embedded figures and full-precision CSV. Throughput axes
start at zero. The LIE serial control, later reactive result and earlier Gufo
reference are explicitly identified; 4.11× refers to LIE batching versus its
serial control. No new GPU measurement or matched-current-Gufo claim is made.
`tools/render-published-benchmarks.py` regenerates the page and figures from
hash-bound retained summaries. Dated evidence files remain byte-identical.

Official libuv 1.52.1 is bundled at commit
`1cfa32ff59c076ffb6ed735bbc8c18361558661f`, with 127 unmodified files, full retained
license notices and a SHA-256 acquisition inventory. The default static link
removes the server's `libuv.so` dependency. `LIE_SYSTEM_LIBUV=ON` selects system
libuv. The shared headless core still does not link libuv. No package was
installed, no service deployed, and the Gufo provider and model files were not
changed. Python remains a build/test/HTTP-benchmark/plot helper, with no server
runtime dependency; `libsynapse-core` is not linked by this branch.

The pending core-benchmark accounting work is complete: skipped RAM captures,
SSD evictions/skips/errors and final drained allocation/entry counters are now
exported. CPU fixtures reject negative admission counters and check drained
store values. Existing graph-dependent fixtures now skip only their plot checks
when Matplotlib is absent.

Validation: 39/39 CTests pass with ASan, UBSan and LeakSanitizer against bundled
libuv; six focused HTTP tests pass with system libuv. The release server and
benchmark link successfully against the existing verified HIP provider, with
GPU visibility masked for help-only checks. No model is opened. Documentation
checks cover all local Markdown links/fragments and 19 shell examples; source
hashes, CSV rows and graph axes were verified. Local peak CPU temperature was
92.625 °C, below the configured 98 °C ceiling.

Preserved failed attempts: the first vendor configure omitted `configure.ac`,
which upstream CMake reads for its version; two initial CTests found accidental
mandatory Matplotlib use; the first fixture correction missed a dependent CSV
assertion. All were corrected and rechecked. The earlier wrong-target bench
build failure is retained as well. The [CPU receipt](development/validation/docs-libuv-2026-10-02.json)
records commands, actual exits and artifact hashes; raw logs remain under local
`evidence/docs-*`. GPU prompt-retention performance qualification remains pending;
the `.157` preparation window was released before this documentation work.
