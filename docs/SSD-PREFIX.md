# Optional C17 SSD prefix persistence

This increment implements disk persistence of the same complete hybrid AR
frontiers used by the RAM cache. It is shared by HTTP and `--suite core` through
`lie_core`; the provider supplies bound model files, geometry and completed
device transfers. The codec, identity hashing, store, budgets, I/O scheduling and
ownership are C17. [Original-weight restart and core C1 comparisons now pass
through 128K](SSD-GPU-COMPLETION.md): full-logit/token equivalence after restart,
4K-to-8K extension, and matched off/RAM/SSD timings. The completed continuation
retains the earlier software thermal stops and includes 1 Hz temperature/clock
observations. HTTP/concurrent SSD device checks remain separate.
The [HTTP SSD benchmark client](SSD-HTTP-PROTOCOL.md) now has passing CPU
restart/C2/held-read/cancellation/slow-client fixtures and percentile exports;
its original-weight campaign is still NOT RUN.

RAM remains enabled by default, with its independent lazy 4 GiB budget.
SSD remains disabled by default. Enable it explicitly with all three options:

```text
--prefix-ssd-dir /absolute/private/lie-prefix-directory
--prefix-ssd-quota-mib 16384
--prefix-ssd-staging-mib 4096
```

Both `synapse-lie-server --model ...` and `synapse-lie-bench --suite core` accept
these options. `--prefix-cache-mib 0` can independently disable RAM retention for
an SSD-only comparison. No environment switch, automatic spill or cache-directory
discovery enables disk I/O. An absent directory option means no store scan,
creation, identity hashing, read, write or I/O thread. Turning the option off
leaves previously committed files intact.

All ancestors must exist. The final directory is created with mode 0700 or must
already have that exact mode and belong to the current user. Paths are walked
through directory FDs without symlinks. Files use 0600, one link, regular-file
checks and FD-relative operations. The dedicated directory must contain only
this store's entries, temporary entries and lock. An exclusive nonblocking lock
rejects a second simultaneous store owner. These are private conversation-derived
bytes without encryption at rest; the directory is not a boundary against an
adversarial process with the same UID.

## Identity and version 1 framing

The live model domain is never written to disk. An enabled core obtains a stable
identity and its new live domain before READY. For the transitional HIP provider,
the identity hashes every complete bound GGUF shard in C, with before/after stat
checks, then the executable and loaded library files, kernel/architecture,
device/runtime policy and relevant numerical environment. The model's original
file descriptors/stat witnesses are retained across load; changed files refuse
SSD admission. Model/configuration/tokenizer/template/quantization metadata is
included in full GGUF content; context, chunk, batch width, text-only AR and
thinking policy are explicit. Immutable weights remain a prerequisite during
model execution. No stat-only digest cache or guessed publisher hash is used.

This is deliberately conservative: a different executable, library, kernel,
device policy or execution configuration can miss even when a looser future
contract might prove compatibility. No cross-HIP/CUDA or cross-build portability
is claimed. Full weight hashing can be expensive and is counted in load-to-READY,
not in request prefill. Shared GPU host admission must authorize that read too.
The lease supervisor admits SSD only with an explicit campaign manifest for
full-content hashing, separate RAM/staging/disk reserves and a new private store
or a sealed preceding producer. See the [device protocol](SSD-GPU-PROTOCOL.md).

The wire representation is **not a C struct dump**. Integers are little-endian;
version 1 requires a little-endian IEEE binary32 host. F16 tensor bits are
preserved. The fixed 160-byte header is:

| Offset | Length | Meaning |
|---|---:|---|
| 0 | 8 | `LIEPFX1` plus NUL; prefix-checkpoint kind |
| 8 | 4 | Envelope version 1 |
| 12 | 4 | Header length 160 |
| 16 | 4 | Model representation version |
| 20 | 4 | Component count, 1..256 |
| 24, 28, 32 | 4 each | Token count, context capacity, prefill chunk |
| 36 | 4 | Reserved zero |
| 40, 48 | 8 each | Payload bytes, entire file bytes |
| 56 | 32 | Stable model/build/execution SHA-256 identity |
| 88 | 32 | SHA-256 checksum |
| 120 | 32 | Eight model frontier uint32 values |
| 152 | 8 | Reserved zero |

The header is followed by `component_count` 64-byte records: role, layer, dtype,
rank (four uint32 values); four uint64 dimensions; uint64 byte count and payload
offset. The payload uses the already owned component layout, with canonical
zero alignment padding. Physical int32 tokens are one required component;
logits are another. SHA-256 covers the header with its digest field zeroed,
the entire component table and all payload bytes. It detects corruption; it is
not an authentication signature. Trailing bytes, truncation, invalid lengths,
duplicate roles/layers, inconsistent shapes, unsupported dtypes, bad padding,
negative token IDs and identity mismatches are refused before GPU mutation.

Filenames are SHA-256 of a versioned domain separator, stable identity, count
and exact physical token IDs, followed by `.lie`. Each tier selects its longest
eligible exact frontier. The core currently prefers any usable RAM prefix and
consults SSD only on a RAM miss; it does not search disk for a longer alternative
after a partial RAM hit. An unaligned checkpoint can serve only an exact prompt;
longer recurrent state is never trimmed. Complete payload validation precedes a
provider geometry check, rebinding to the new live domain and owner-thread upload.
Missing/corrupt/incompatible files cause ordinary prefill; failures after admitted
mutating upload poison the core, as with RAM restore.

## Reactive ownership and resource bounds

An enabled store has one I/O worker and **one admitted operation**, including a
completed result awaiting collection. There is no additional inference pool.
The device owner submits immutable state references or copied token queries and
polls an eventfd. A job awaiting disk does not run prefill until its lookup
completes; other runnable rows continue prefill/decode under the existing flow
credits. The HTTP loop never waits for a disk syscall or transfer.

Only one completed prompt frontier is offered for persistence per request, never
one write per token. A busy writer slot skips optional persistence. When no RAM
copy exists, the owner checks the separate staging cap before capturing. A RAM
copy can be retained by reference, without a second tensor copy. RAM eviction
cannot free a pinned writer. The RAM and staging budgets conservatively account
such a shared payload in both pools. Reads reserve the staging cap, including
the bounded query token copy, before allocating a payload; no unbounded queue or
staging allocation is hidden behind async submission. Fixed metadata, thread
stack, OpenSSL internals and allocator overhead are outside payload accounting.

The index has at most 64 files. Logical and allocated entry bytes are recorded;
admission checks both against the quota, including reserved temporary-file space.
Physical reservation uses the filesystem allocation unit and is checked again
before commit; this is not a bound on filesystem journal/metadata or transient
allocation beyond that unit. Successful file bytes exclude failed partial I/O.
One worker serializes reader pins, writes and eviction. Idle least-recently-used
entries are evicted before admitting a write; recency restarts in scan order
after reopening. A pre-existing store above the requested quota refuses startup.
Lock/directory filesystem metadata is not included in the payload quota.

Writes use an exclusive same-directory temporary file, bounded transfers,
file fsync, rename and directory fsync. Only completed durable commits increment
`writes`. Safely recognized abandoned temporary files are removed on reopening.
Failures retain an error counter and never change inference into a successful
cache hit. Cancellation is observed between bounded transfers; a blocking
filesystem syscall is not preempted. Normal core shutdown drains the single
writer before STOPPED. Request completion alone does not acknowledge durability.

Metrics distinguish RAM hits, checksum-valid SSD file hits and actual per-job
SSD reused tokens. `ssd_read_ns` covers lookup/read/validation, while
`cache_restore_ns` covers owner restore work. Async write time is store-wide;
it cannot be attributed to a request that may already have retired. The bench
emits a final `ssd_drained` record after shutdown, plus separate job timings and
SSD fields in JSON/CSV. Cache policies and both SSD budgets are comparison keys;
full-hit PP throughput remains unavailable because no prefill executed.

## Validation and remaining device qualification

New synthetic cases cover the disk codec, malformed data, identity changes,
private paths, hardlinks/symlinks, exclusive locks, budget/eviction, write/fsync/
rename faults, process restart, RAM promotion, HTTP/Responses usage, bench export,
read cancellation and poison after a mutating upload fault. The reactive fixture
holds an SSD pread while an already active peer consumes credits and finishes
generation. These are contract checks, not GPU speed or numerical evidence.

Local tests are now user-authorized on `.155` as well as `.157`. Builds use at
most two compiler processes; `tools/thermal-run.py` records sensor readings and
actual exits and stops only its owned child group at 85 C or a lower sensor
max/critical limit. No fan, power or clock changes. The local R4 attempt was
refused before spawn at CPU 89 C; retain that evidence separately from failures.
At runtime checkpoint `9b6c937`, final focused Debug checks pass 4/4 and the full
ASan/UBSan suite passes 30/30, including leak detection. The sanitizer run peaks
at CPU79.75/GPU57 C. The HIP adapter and server/bench compile/link pass against
existing qualified numerical archives, without executing a model or rebuilding
those archives. The successful linked continuation peaks at CPU74.625/GPU53 C;
the earlier attempt stopped at CPU86.5 C, preserving child exit -15 and guard
exit 125. [Receipts](benchmarks/2026-10-02/ssd-prefix-cpu/receipt.json) retain source
hashes, commands, exits and raw telemetry/log hashes. These functional and build
checks do not qualify original-weight SSD inference or performance.

The [completed GPU continuation](SSD-GPU-COMPLETION.md) qualifies exact SSD state
through 128K and C1 off/RAM/SSD request timings at 8K/128K, with startup hashing,
capture/write/read/upload, output equality and temperature telemetry separated.
Every restarted SSD request reuses its full prompt; all core outputs reach TG128.
HTTP with SSD enabled, concurrent GPU peer progress/cancellation, device-side
fault injection and independently measured HIP peak allocation still need
separate admitted work. File corruption, quota and write failures retain their
synthetic contract scope. 256K checkpoint retention/fit and 1M remain
unqualified/unsupported respectively.
This version persists hybrid checkpoints. Active KV paging, PLE/weight streaming,
exact resumable sampling/tool sessions, MTP and vision require distinct contracts.
