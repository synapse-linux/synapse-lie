#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check exact 64-row coverage by the private C17 IQ2 token-tile map."""

import ctypes
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Spans(ctypes.Structure):
    _fields_ = [("wide256", ctypes.c_uint32), ("wide128", ctypes.c_uint32),
                ("tail64", ctypes.c_uint32)]


def check(lib, counts, tokens, used):
    experts = len(counts)
    groups = [(c + 63) // 64 for c in counts]
    capacity = sum(groups)
    source = (ctypes.c_uint32 * experts)(*counts)
    output = (ctypes.c_int32 * max(1, capacity))(*([-1] * max(1, capacity)))
    spans = Spans(999, 999, 999)
    assert lib(source, experts, tokens, used, output, capacity,
               ctypes.byref(spans)) == 1
    widths = [(spans.wide256, 4), (spans.wide128, 2), (spans.tail64, 1)]
    assert spans.wide256 == sum(g // 4 for g in groups)
    assert spans.wide128 == sum((g % 4) // 2 for g in groups)
    assert spans.tail64 == sum(g & 1 for g in groups)
    assert sum(n for n, _ in widths) <= capacity
    coverage = [[0] * g for g in groups]
    offset = 0
    for n, width in widths:
        for descriptor in output[offset:offset + n]:
            expert = descriptor & 0xFFFF
            index = (descriptor >> 16) & 0x7FFF
            begin = index * width
            assert expert < experts and begin + width <= groups[expert]
            for row in range(begin, begin + width):
                coverage[expert][row] += 1
        offset += n
    assert all(all(value == 1 for value in rows) for rows in coverage)
    assert all(value == -1 for value in output[offset:])

    short = (ctypes.c_int32 * max(1, offset))(*([-7] * max(1, offset)))
    old = Spans(111, 222, 333)
    if offset:
        assert lib(source, experts, tokens, used, short, offset - 1,
                   ctypes.byref(old)) == 0
        assert list(short) == [-7] * len(short)
        assert (old.wide256, old.wide128, old.tail64) == (111, 222, 333)


def main():
    with tempfile.TemporaryDirectory(prefix="lie-iq2-tile-map-") as directory:
        library = Path(directory) / "tile-map.so"
        subprocess.run(["cc", "-std=c17", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC", "-o", str(library),
                        "experiments/iq2_token256_tiles.c"], cwd=ROOT, check=True)
        dll = ctypes.CDLL(str(library))
        func = dll.lie_iq2_token256_tiles
        func.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32,
                         ctypes.c_uint32, ctypes.c_uint32,
                         ctypes.POINTER(ctypes.c_int32), ctypes.c_size_t,
                         ctypes.POINTER(Spans)]
        func.restype = ctypes.c_int
        cases = 0
        for layer in json.loads((ROOT / "config/q2-current-routing-v2-results.json").read_text())["layers"]:
            check(func, layer["counts"], 2048, 10)
            cases += 1
        for n in (1, 16, 17, 49, 64, 65, 127, 128, 129, 255, 256,
                  257, 511, 512, 1023, 1024, 2048, 4096):
            check(func, [n], n, 1)
            cases += 1
        print(json.dumps({"cases": cases, "source": "iq2_token256_tiles.c",
                          "coverage_exact": True, "gpu_run": False}))


if __name__ == "__main__":
    main()
