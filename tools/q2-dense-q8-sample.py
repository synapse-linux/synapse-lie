#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read a bounded Q8_0 code sample; never rewrite or hash model payload."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys


TENSOR_NAMES = (
    "output.weight",
    "blk.0.attn_qkv.weight",
    "blk.0.attn_gate.weight",
    "blk.0.ssm_out.weight",
)
SAMPLE_BLOCKS = 32768
GGUF_BLOCK_BYTES = 34
GGUF_CODES_PER_BLOCK = 32


def identity(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
            stat.st_ctime_ns)


def sample(fd, metadata, tensor, tensor_bytes):
    assert tensor["type_name"] == "Q8_0"
    assert tensor_bytes % GGUF_BLOCK_BYTES == 0
    blocks = tensor_bytes // GGUF_BLOCK_BYTES
    take = min(SAMPLE_BLOCKS, blocks)
    codes = Counter()
    widths = Counter()
    offsets = []
    for fraction in (1, 2, 3):
        first = (blocks - take) * fraction // 4
        offset = metadata["data_offset"] + tensor["offset"] + first * GGUF_BLOCK_BYTES
        payload = os.pread(fd, take * GGUF_BLOCK_BYTES, offset)
        if len(payload) != take * GGUF_BLOCK_BYTES:
            raise ValueError("Incomplete bounded Q8 sample")
        offsets.append(offset)
        for pos in range(0, len(payload), GGUF_BLOCK_BYTES):
            values = [value if value < 128 else value - 256
                      for value in payload[pos + 2:pos + GGUF_BLOCK_BYTES]]
            codes.update(values)
            span = max(values) - min(values) + 1
            widths[max(1, (span - 1).bit_length())] += 1
    count = sum(widths.values())
    probabilities = [n / (count * GGUF_CODES_PER_BLOCK) for n in codes.values()]
    entropy = -sum(p * math.log2(p) for p in probabilities)
    # A hypothetical per-block range codec needs the old 2-byte scale,
    # a minimum, and a width header. It can always retain the original block.
    packed_bytes = sum(min(GGUF_BLOCK_BYTES, 4 + 4 * width) * n
                       for width, n in widths.items()) / count
    return {
        "name": tensor["name"],
        "tensor_bytes": tensor_bytes,
        "sample_offsets": offsets,
        "sampled_blocks": count,
        "code_min": min(codes),
        "code_max": max(codes),
        "marginal_code_entropy_bits": entropy,
        "block_range_widths": {str(width): widths[width] for width in sorted(widths)},
        "range_codec_bytes_per_block_with_original_fallback": packed_bytes,
        "original_bytes_per_block": GGUF_BLOCK_BYTES,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--parser-tools", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.parser_tools))
    from gufo.gguf import parse_gguf, tensor_bytes  # pylint: disable=import-outside-toplevel

    plan = json.loads(args.plan.read_text())
    model = plan["model_stats"][0]
    path = Path(model["path"])
    expected = tuple(model[name] for name in
                     ("device", "inode", "bytes", "mtime_ns", "ctime_ns"))
    if identity(path) != expected:
        raise ValueError("Recorded model identity differs")
    kfd = Path("/sys/class/kfd/kfd/proc")
    if kfd.exists() and list(kfd.glob("[0-9]*")):
        raise ValueError("GPU client present during read-only sample")
    metadata = parse_gguf(path)
    tensors = {tensor["name"]: tensor for tensor in metadata["tensors"]}
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        rows = [sample(fd, metadata, tensors[name],
                       tensor_bytes(metadata, tensors[name])) for name in TENSOR_NAMES]
    finally:
        os.close(fd)
    if identity(path) != expected:
        raise ValueError("Model identity changed during sample")
    if kfd.exists() and list(kfd.glob("[0-9]*")):
        raise ValueError("GPU client appeared during read-only sample")
    output = {
        "schema": "synapse-lie.q2-dense-q8-sample.v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "official_gufo_pin": "f783fedb9bea2ec7de941f6da4e02f4a4596b29e",
        "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        "model_path": str(path),
        "model_stat_identity_unchanged": True,
        "gpu_client_absent_before_after": True,
        "sample_bytes_upper_bound": len(TENSOR_NAMES) * 3 * SAMPLE_BLOCKS * GGUF_BLOCK_BYTES,
        "total_model_q8_bytes_from_metadata": sum(
            tensor_bytes(metadata, tensor) for tensor in metadata["tensors"]
            if tensor["type_name"] == "Q8_0"),
        "tensors": rows,
    }
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
