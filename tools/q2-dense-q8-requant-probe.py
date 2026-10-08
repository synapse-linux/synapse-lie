#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Estimate bounded Q8_0-to-narrower error without converting model files."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys


NAMES = ("output.weight", "blk.0.attn_qkv.weight",
         "blk.0.attn_gate.weight", "blk.0.ssm_out.weight")
BLOCK_BYTES = 34
SAMPLE_BLOCKS = 8192


def identity(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def rounded_half(value):
    return struct.unpack("<e", struct.pack("<e", value))[0]


def probe(fd, metadata, tensor, size):
    if tensor["type_name"] != "Q8_0" or size % BLOCK_BYTES:
        raise ValueError("Expected complete Q8_0 blocks")
    blocks = size // BLOCK_BYTES
    take = min(SAMPLE_BLOCKS, blocks)
    sums = {bits: [0.0, 0.0, 0] for bits in (5, 6, 7)}
    first_blocks = []
    for fraction in (1, 2, 3):
        first = (blocks - take) * fraction // 4
        first_blocks.append(first)
        offset = metadata["data_offset"] + tensor["offset"] + first * BLOCK_BYTES
        payload = os.pread(fd, take * BLOCK_BYTES, offset)
        if len(payload) != take * BLOCK_BYTES:
            raise ValueError("Incomplete bounded Q8_0 read")
        for position in range(0, len(payload), BLOCK_BYTES):
            scale = struct.unpack_from("<e", payload, position)[0]
            if not math.isfinite(scale):
                raise ValueError("Nonfinite Q8_0 scale")
            values = [code if code < 128 else code - 256
                      for code in payload[position + 2:position + BLOCK_BYTES]]
            original = [scale * code for code in values]
            energy = sum(value * value for value in original)
            peak = max(abs(code) for code in values)
            for bits, aggregate in sums.items():
                bound = (1 << (bits - 1)) - 1
                new_scale = rounded_half(scale * peak / bound) if peak else scale
                if new_scale == 0:
                    estimate = [0.0] * 32
                else:
                    quantized = [max(-bound, min(bound, round(value / new_scale)))
                                 for value in original]
                    estimate = [new_scale * code for code in quantized]
                aggregate[0] += sum((a - b) ** 2 for a, b in zip(original, estimate))
                aggregate[1] += energy
                aggregate[2] += 1
    return {
        "name": tensor["name"],
        "tensor_bytes": size,
        "first_blocks": first_blocks,
        "sampled_blocks": take * 3,
        "relative_rms_error": {
            str(bits): math.sqrt(error / energy) if energy else 0.0
            for bits, (error, energy, _) in sums.items()
        },
        "hypothetical_fixed_bytes_per_block": {
            str(bits): 2 + 4 * bits for bits in sums
        },
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
    expected = tuple(model[key] for key in
                     ("device", "inode", "bytes", "mtime_ns", "ctime_ns"))
    if identity(path) != expected:
        raise ValueError("Recorded model identity differs")
    kfd = Path("/sys/class/kfd/kfd/proc")
    if kfd.exists() and list(kfd.glob("[0-9]*")):
        raise ValueError("GPU client present")
    metadata = parse_gguf(path)
    tensors = {tensor["name"]: tensor for tensor in metadata["tensors"]}
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        rows = [probe(fd, metadata, tensors[name], tensor_bytes(metadata, tensors[name]))
                for name in NAMES]
    finally:
        os.close(fd)
    if identity(path) != expected or (kfd.exists() and list(kfd.glob("[0-9]*"))):
        raise ValueError("Read-only model/GPU state changed")
    print(json.dumps({
        "schema": "synapse-lie.q2-dense-q8-requant-probe.v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "official_gufo_pin": "f783fedb9bea2ec7de941f6da4e02f4a4596b29e",
        "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        "model_stat_identity_unchanged": True,
        "gpu_client_absent_before_after": True,
        "max_payload_bytes": len(NAMES) * 3 * SAMPLE_BLOCKS * BLOCK_BYTES,
        "quantizer": "symmetric signed, per-32 code maximum, F16 rounded scale, nearest-even codes",
        "limitation": "weight-only sample, not an operator, model-output, quality, or throughput result",
        "tensors": rows,
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
