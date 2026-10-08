<!-- SPDX-License-Identifier: MIT -->
# Held-out steering response check

This protocol checks a learned conciseness direction on original weights. It is
separate from bank construction, general model quality and throughput. Its
checker and native-client HOST fixtures are implemented; original-weight
execution and campaign integration remain pending.

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
At +2, require a median ratio of at least1.2 and longer explanations in at
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

Passing establishes arithmetic-answer preservation and a response-length
effect on this held-out corpus. It does not establish semantic explanation
quality, broad instruction following, another model/platform or performance.
Those steering roadmap gates remain open.
