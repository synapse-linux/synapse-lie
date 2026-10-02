<!-- SPDX-License-Identifier: MIT -->
# Q2 scheduling performance exploration

The owner explicitly authorized measuring performance before resolving the
small numerical differences found by the previous exact replay checks.
The earlier failures and their original protocol remain unchanged. This new
campaign treats speed and numerical behavior as separate observations; it does
not promote either candidate into the qualified runtime.

Two isolated source trees reproduce all 1019 files of the previously tested
operator capsules exactly: bounded K unrolling and the token-tile barrier for
widths 32 and above. `--source-variant bounded-k|wide-barrier` selects only those
experimental trees for `q2-bench`; the default source and runtime patch remain
qualified original Q2. The fixed remote runner, leases and process ownership
rules are unchanged.

`config/q2-performance-exploration.json` fixes the workload before execution:
C1, physical prompts 512/2048/8192, prefill chunk 2048, session capacity 9216,
MTP off, one warmup and three measured repetitions per size, 128 emitted tokens
with 127 timed decode calls. Sessions are fresh; loading is excluded. The
campaign includes fresh qualified-Q2 and pristine-UD controls on `.157`.

For every arm, retain command exits, telemetry, full final and prefill logits,
input/output token IDs and artifact hashes. Report exact replay, token agreement,
finite-logit KL/error and observed timing ranges separately. Numerical acceptance
is not inferred from speed. GPU/resource faults and incomparable workloads still
stop or invalidate an arm. No deployment, merge or publication is authorized.

Status: core explicitly handed over the window; fresh reference measurement
is running under the existing four leases.

The candidate trees can be reproduced without fetching new source: prepare two
copies of the qualified Q2 patch from the recorded official archive, then apply
`experiments/q2-bounded-k.patch` to `.deps/gufo-q2-bench-bounded-k` and
`experiments/q2-wide-token-barrier.patch` to `.deps/gufo-q2-bench-wide-barrier`,
both with `patch --batch --fuzz=0 -p1`. Source identity checks against the earlier
operator capsules are recorded in the exploration configuration.

The four model arms use the existing fixed remote tool:

```sh
python3 tools/q2-remote.py q2-bench q2-explore-reference-r1
python3 tools/q2-remote.py q2-bench q2-explore-bounded-r1 --source-variant bounded-k
python3 tools/q2-remote.py q2-bench q2-explore-barrier-r1 --source-variant wide-barrier
python3 tools/q2-remote.py ud-base q2-explore-ud-r1
```

Labels are exclusive. These commands require a current coordinated window;
retained completed labels must not be reused. Collect and verify each arm's
results before deriving comparisons.
