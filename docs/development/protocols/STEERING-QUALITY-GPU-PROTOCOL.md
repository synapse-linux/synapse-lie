<!-- SPDX-License-Identifier: MIT -->
# Held-out steering response check

This protocol checks a learned conciseness direction on original weights. It is
separate from bank construction, general model quality and throughput. Its
checker, serial server/client supervision, campaign body and native-client HOST
fixtures are implemented. The coordinator now selects
`bench_profile: "modern-steering-quality"` and executes exactly the bounded,
SHA-checked profile bytes before its full input/model provenance checks.
Original 100-pair FFN learning is now
[independently verified](../validation/steering-conciseness-original100-point-2026-10-08.json);
held-out original response execution remains pending. The dispatch
hook was applied after the admitted near-512K recall window was collected,
strongly closed, released to all four peers and independently sealed.

The owned [corpus](../../../tests/fixtures/steering-conciseness-v1.json) contains
100 unique training questions and ten disjoint held-out arithmetic problems.
Each training question receives the same two instructions: concise target and
detailed contrast. Collect FFN residuals from the last physical prompt token,
average branches, learn target-minus-contrast and normalize each trunk layer
with the existing C17 builder. Keep the complete successful journal, raw rows,
physical IDs, exact prompt bytes and independently reconstructed bank. A file
hash alone does not qualify learning.

Freeze corpus, prompt, bank, runtime and helper hashes before admission. Use
native RoPE, context 8192, chunk/scratch 256, seed 77, greedy AR, output budget 256,
C1, zero warmups, one repetition and RAM/SSD prefix caching off. MTP, vision,
graph/fault checks and matched cost require separate cohorts. The existing
[coordination protocol](../../COORDINATION.md) applies to training and serving;
do not inherit a previous window or run alongside another owner.

Run two serial owned server lifetimes. First load no bank and answer all ten
held-out questions. Then load the SHA-bound FFN bank with both initial scales
zero. Answer each question at FFN scales -1, -0.5, 0, 0.5, 1 and 2; attention
stays zero. Each request declares a single position-zero steering step and
`store:true`. Use the existing native `synapse-lie-bench --suite http --requests`
client. Require the stored steering endpoint to prove actual application at
position zero and the final policy; configured scales alone are insufficient.
Keep all seventy full SSE observations, exact requests, actual native exits,
stored snapshots and executor phases. Stop and retire only owned children.

Each answer must be a complete JSON object containing exactly `answer` and
`explanation`. The answer string must match the predeclared integer. Explanation
must contain countable words. All outputs must stop naturally; a budget stop
remains a quality failure. The no-bank and zero-scale controls must match text,
physical prompt/output counts and stop reason for every question. This checks
observed HTTP output parity, not unobserved token-ID parity.

Count explanation words with the checker's locale-independent Unicode word
expression. Negative scale amplifies the concise target-minus-contrast
direction; positive scale removes it. At -1, require a median word-count ratio
of at most 0.8 against scale 0 and shorter explanations in at least 8/10 cases.
At +2, require a median ratio of at least 1.2 and longer explanations in at
least 8/10 cases. Report every intermediate scale without assuming monotonicity.
Only score this effect after all arithmetic, natural-stop and parity controls
pass. No effect, wrong answers or truncation produce `QUALITY_FAILED`, retaining
all observations. Transport, identity, lifecycle or incomplete-evidence errors
remain separate failures; never tune thresholds or rewrite questions after
seeing model output.

The optional [independent development checker](../../../tools/strix-point-steering-quality-gate.py)
reconstructs saved SSE rather than trusting assembled text or green summaries.
Its `prepare` operation writes paired prompt files and both native request
cohorts into a new directory; `review` consumes actual supervised exit codes,
exported requests, measurements and stored snapshots. These development tools
are outside the Python-free native product and default CMake build.

The optional [own-child supervisor](../../../tools/strix-point-steering-quality-run.py)
launches the two servers serially, waits for the selected model, runs the native
client and fetches each stored steering observation. It preserves raw HTTP
status/text and partial native files on failure. The second server cannot start
before both first-phase children retire. Timeout and signals retire only its
own children; process identities and actual exits are retained. The outer
campaign still owns GPU admission, thermal/resource guards, original model
provenance, container retirement and release notifications.

The optional [campaign body](../../../tools/strix-point-steering-quality-profile.py)
checks all five helper hashes before importing staged code. It binds settings,
corpus, the independently qualified training receipt and the FFN bank to the
same model and runtime. Admission requires 100 original training pairs with the
exact paired prompt bytes, complete model-derived geometry, actual successful
native/review/control exits and whole-container closure with all four peer
releases. The earlier eight-pair formal/casual receipt cannot replace this
training. Future 100-pair receipts must include `source_model`, `training_corpus`,
the complete `closure` and `actual_exits.independent_review`. Bank rows must be
finite and normalized. No Qwen geometry is hard-coded in the profile.

After supervision, the campaign body independently reconstructs all 70 saved
SSE observations, requests and stored snapshots. Actual container/native exits
and both serial lifetimes must agree with the review. Complete quality failures
retain their scores even when the container exits 1; launch or partial-read
failures preserve available artifacts and still run model postflight. All
admitted input identities must remain unchanged, including byte-identical inode
replacement. These checks execute inside the existing owned campaign; they do
not acquire a lease or replace outer admission and closure.

Response storage is bounded to 128 records/64 MiB, with TTL covering the complete
workload deadline so early responses do not expire while later scales run.
The deadline is two model-load bounds plus 70 request bounds and 600 seconds
for 70 three-second snapshot reads, two client margins, four owned retirements
and setup/I/O. The earlier 180-second allowance omitted these costs. Configurations
exceeding one day refuse before any process is launched. Seventeen campaign-body
and twelve supervision HOST checks pass per normal/sanitizer mode, plus two
focused native CTests per mode
([receipt](../validation/steering-quality-profile-host-2026-10-08.json)).
Across the two suites, four actual C clients consume 140 synthetic responses per
mode. Model servers, snapshots and training metadata are simulated. These checks
do not qualify GPU admission, model loading, applied numerical steering or
original-weight response quality. The earlier eleven-case supervisor
[receipt](../validation/steering-quality-supervision-host-2026-10-08.json)
retains its original sources and deadline; it is historical evidence.

Eight dispatch checks pass per normal/native-sanitizer mode, including two
actual C clients consuming 70 synthetic replies per mode, and all 89 existing
ownership/restore coordinator checks pass
([receipt](../validation/steering-quality-campaign-host-2026-10-08.json)).
Symlink/FIFO/directory/hash failures refuse before a model opens. A source swap
after hashing cannot execute unchecked bytes; the full profile detects the
remaining content drift. This is HOST checking-code evidence, without GPU
admission or an original learned bank.

After actual terminal state and original lease release, the optional
[response collector](../../../tools/strix-point-steering-quality-collect.py)
copies both phases' full wire, exported requests, server/client logs, stored
snapshots and execution identities. It binds all frozen helpers and inputs,
hashes bounded regular files in 1 MiB reads, refuses overwrite and rechecks the
complete local inventory. Remote paths refuse traversal before local directory
creation. Complete quality failures and infrastructure partial files remain
distinct; a transfer timeout never restarts inference. Twelve
[HOST checks](../validation/steering-quality-collection-host-r2-2026-10-08.json)
pass without any model, GPU or remote access. This proves transfer boundaries,
not original response quality or container retirement. The separate closure
must verify both actual GPU server identities, both native clients, supervisor,
launcher and init, the whole cgroup, both API/management ports, unchanged model
stats and original lease, followed by all four release notifications.

Passing establishes arithmetic-answer preservation and a response-length
effect on this held-out corpus. It does not establish semantic explanation
quality, broad instruction following, another model/platform or performance.
Those steering roadmap gates remain open.
