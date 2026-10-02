# DS4 KVC interchange

The shared C17 `lie_kvc` library reads/writes KVC v1, payload ABI 2, in owned
RAM records and regular files. `LIE_KVC_INTERCHANGE=ON` builds it and the offline
`synapse-lie-kvc` tool, including in `LIE_CORE_ONLY` builds. It adds no work,
threads or storage to inference. SSD persistence still requires explicit opt-in.

This completes the wire codec, not live DS4-to-LIE model restore. The runtime
cache still uses the independently qualified LIE component representation and
native `LIEPFX1` SSD format. Neither parsing a foreign file nor a synthetic
round-trip authenticates its model or proves equivalent next-token inference.

## Offline use

```sh
build/kvc-sanitize/synapse-lie-kvc inspect /absolute/checkpoint.kv --max-mib 8192
build/kvc-sanitize/synapse-lie-kvc copy /absolute/checkpoint.kv /absolute/new-copy.kv --max-mib 8192
```

These commands open no model and run no GPU work. `inspect` prints bounded JSON
metadata, never prompt text, tensor contents or client extensions. `copy` retains
every input byte, including unknown reason/flag/reserved bytes and opaque trailers.
It creates a private temporary file beside the requested output, flushes its
contents and publishes with a hard link that refuses an existing destination.
Temporary files are removed on normal completion/failure. A crash can leave a
temporary file; directory durability across power loss is not promised by this
offline tool. No serving cache directory is created or scanned implicitly.

The default allocation budget is 256 MiB; `--max-mib` sets the explicit maximum
for descriptor plus wire bytes. Text is capped at 8 MiB and trailer at 1 MiB.
Oversized records fail before payload allocation. Exit codes are 0 for success,
1 for I/O/format/budget refusal and 2 for invalid command syntax.

For Qwen structural validation add `--qwen-geometry /absolute/geometry.txt`.
That file contains exactly these 13 decimal integers, separated by whitespace:

```text
trunk_layers mtp_layers attention_interval attention_heads_kv attention_head_dim index_dim value_heads linear_head_dim conv_rows conv_channels ple_rows hidden_width vocab
```

Values must come from the corresponding model binding. Several are absent from
the payload header and cannot safely be inferred from its family identifier.
For example, the tiny **synthetic test fixture only** uses:

```text
4 1 2 1 4 3 2 3 2 5 2 6 32
```

`qwen_layout_validated=true` means complete structural validation, including
outer/inner token and context agreement. `text_positions` distinguishes ordinary
positions from position-adjusted records; `mtp_tokens` describes retained MTP
rows. Neither field enables MTP or vision execution. `inference_qualified` remains
false. Without a geometry file the model payload is opaque and is reported as such.

## Shared API and ownership

`include/lie/kvc.h` owns envelope framing and bounded file I/O. `kvc_qwen.h`
owns the model-specific plan, parser and serializer. Neither links an executor,
HTTP, Gufo, HIP, C++ or a CPU forward implementation. OpenSSL supplies SHA-1
for the interoperable text filename; that name is not a payload checksum.

`lie_kvc_parse` returns borrowed, immutable byte spans. An owned `lie_kvc` retains
one exact wire allocation until `lie_kvc_destroy`. Success publishes complete
objects; failure leaves outputs unchanged. Allocated bytes are observable through
`lie_kvc_memory_bytes`. Caller-owned input buffers, stack/allocator overhead and
OpenSSL internals are outside that explicit allocation budget. No hidden tensor
expansion or compression occurs. Quantization metadata accepts 2/4/5/6/8; it is
not interpreted as KV precision or authorization for cross-weight reuse.

File operations preserve FD positions. Reads use an already-open regular file,
preflight length/budget checks and before/after size/time/header checks. The
caller must still keep the input immutable: KVC has no content checksum and
these checks are not authentication against concurrent malicious writers.
Writes require an empty private owned regular file and may leave partial bytes
on failure. Publication belongs to the caller. Completed I/O and memory copying
check cancellation between at most 1 MiB transfers; token scans check every
64 KiB. Filesystem syscalls are not forcibly preempted. Serving integration must
use the existing bounded I/O worker and preserve the single device owner.

Qwen spans use the existing typed component vocabulary but retain the wire
order and exact byte offsets, including unaligned sections. F16/F32 tensor bits
are never numerically converted. The serializer requires every planned span;
it refuses missing/short components and overlap with its caller-owned output.
It preserves MTP rows, full index history, pooled keys, PLE and n-gram state,
signed position delta and position tuples. This is a serialization API, not an
implicit adapter from native `lie_state`.

## Remaining live integration

Gufo currently retains an index ring/tail, two n-gram slots and lazily materialized
pooled keys. The DS4 wire layout requires additional state. A native-to-KVC live
export needs a provider capture path that actually retains that information,
with separately measured memory and transfer costs. Import also needs an audited
tensor-orientation/history mapping, strong model/tokenizer binding and a qualified
DS4-produced checkpoint. Model id, geometry and text SHA-1 alone are insufficient.
Cross-quantization reuse and frontend-specific history serialization remain open.
No additional high-ratio codec is required by this increment.

The next device gate requires a DS4-produced checkpoint with recorded upstream
revision, model/tokenizer identities, geometry and saved token frontier. The
mapping must verify GDN matrix orientation, PLE ordering and EOS history handling;
test both sides of the index-pooling boundary and context growth; and compare
restored logits plus subsequent generated tokens against independent replay.
Export additionally needs DS4 to load a LIE-produced file. Until those gates
pass, no KVC object is converted into a live-domain `lie_state` or handed to
`lie_sequence_state_write`. GPU work must first obtain the coordinated window
and leases in [COORDINATION.md](COORDINATION.md).

## Evidence and provenance

`tests/test_kvc_fixture.py` constructs an independent Python `struct` wire oracle.
The C test decodes and re-encodes it; Python compares all resulting bytes.
Tests cover every truncated prefix, invalid/overflowed lengths, budget edges,
malformed geometry/tokens/history, incomplete components, overlap, zero/partial
MTP, adjusted positions, unknown metadata preservation, cancellation, short I/O,
EINTR, ENOSPC, a changing source, sparse oversized files and 4,000 deterministic
mutations. CLI tests check JSON, exclusive publication and nonblocking refusal
of special inputs. These are explicitly **NOT-INFERENCE** fixtures.

Original first-party MIT implementation; no upstream implementation was copied.
Wire facts were inspected read-only in official
[DS4 Qwen payload code](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/ds4.c)
and [payload constants](https://github.com/antirez/ds4/blob/0aaea5a238fb41a35106a551e73c8409dfb751ac/ds4.h),
at the revision returned by official `git ls-remote` on 2026-10-02.
The outer envelope was checked in
[the pinned store](https://github.com/antirez/ds4/blob/6289c516273979173abbc062209a81dd3706b804/ds4_kvstore.c)
and the [2026-10-02 main store review](https://github.com/antirez/ds4/blob/main/ds4_kvstore.c)
for its expanded quantization list. The older pin has no Qwen payload and must
not be cited as Qwen qualification. No local DS4 source, build, cache, service,
model or qualified artifact was modified or imported.
