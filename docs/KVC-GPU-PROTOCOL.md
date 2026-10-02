# DS4 runtime checkpoint qualification

The owner requests DS4 format as the runtime cache representation, with shared
C17 policy for all models. This campaign qualifies the first Qwen binding,
comparing `LIE_DS4_RUNTIME_CACHE=ON` against OFF from the same LIE source and
independently verified Gufo provider variants. It does not execute DS4 or import
its source/cache. Exact envelope/payload compatibility and bilateral inference
interoperability are separate claims.

Run on .157 after the explicit Q2 PLE-cache release recorded in COORDINATION.
Every arm reacquires the four established leases nonblockingly, verifies model
stat witnesses, executable/DSO identities, current resources and foreign GPU
clients. Immutable source capsule, CPU receipt and exact argv accompany each
run. Only owned children receive signals. Any failure stops the campaign and
is retained; repair requires a new exclusive attempt. No builds on the target.

`ssd-gpu-r12` declares:

- Paired legacy/KVC RAM state captures at 3 and 2049 tokens, plus 8192 tokens
  followed by 16 generated tokens. Require all three replay/restore pairs to
  match complete logits and token sequences exactly. Compare the complete
  frontier hashes between provider variants as well.
- A 131072-token legacy RAM control and KVC SSD writer/restarted reader.
  Write at context 139264 and read at 262144; require the same three exact
  pairs, matching stable identity and cross-variant frontier hashes. Explicit
  private quota 8 GiB and staging 4 GiB; heavyweight hashing only under leases.
- Matched shared-core C1 at 8192 tokens with retention off; C4 at 8192 and C1
  at 131072 with 4 GiB RAM retention. Use chunk2048, TG128, one warmup and three
  measured cohorts. Use identical legacy capture policy in both variants to
  isolate representation/provider costs from the previously measured policy
  regression. Require output IDs and executed/reused token counts to match.

Inputs are preserved physical token IDs from LIE's prior workload, with short
prefix slices for boundary cases. The user-facing model is the original
UD-Q4_K_XL Qwen Flash Next. No synthetic fixture serves as model evidence.
The 128K case and sparse boundary are mandatory before calling this runtime
qualified. Report fresh PP, decode, TTFT, capture/read/upload durations, retained
bytes, first cold request, startup/hash time and sampled thermals separately.
Any median slowdown over5% in matched core timings is an explicit regression,
not silently averaged away; sample size and observed spread limit conclusions.

Preserve reactive output credit and single device ownership; optional SSD still
uses the existing bounded worker. CPU tests separately hold disk I/O to verify
peer progress and cancellation. No C1 gain is attributed to reactive scheduling
or thread count. These runs do not qualify a second model family, MTP, vision,
cross-quant reuse, foreign DS4 checkpoint import or device-fault recovery.

The user-requested thermal observation policy records CPU/GPU peaks without a
software98C operating stop; exposed hardware bounds and the NVMe guard remain.
An independent read-only observer persists1Hz samples on .155. Connection loss
alone is not a hardware shutdown or evidence of a particular crash temperature.
Closure requires all owned controller/child identities and the observer retired,
empty KFD and four unchanged/free leases, followed by verified evidence collection
and explicit handover to the next thread.
