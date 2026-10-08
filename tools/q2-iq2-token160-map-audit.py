#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit private 160-row IQ2 maps against saved, unchanged routing counts."""

import ctypes
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/iq2_token160_tiles.c"
ROUTING = ROOT / "config/q2-current-routing-v2-results.json"


class Spans(ctypes.Structure):
    _fields_ = [("wide160", ctypes.c_uint32),
                ("wide128", ctypes.c_uint32),
                ("tail64", ctypes.c_uint32)]


def audit(call, counts, tokens, used):
    experts = len(counts)
    count_array = (ctypes.c_uint32 * experts)(*counts)
    capacity = max(tokens * used, experts)
    map_array = (ctypes.c_int32 * capacity)(*([-7] * capacity))
    spans = Spans(99, 99, 99)
    assert call(count_array, experts, tokens, used,
                map_array, capacity, ctypes.byref(spans)) == 1
    total = spans.wide160 + spans.wide128 + spans.tail64
    assert all(value == -7 for value in map_array[total:])
    covered_rows = 0
    selected_rows = 0
    selected_pairs = set()
    coverage = [[0] * ((n + 15) // 16) for n in counts]
    for i, desc in enumerate(map_array[:total]):
        expert = desc & 0xffff
        offset = (desc >> 16) & 0xffff
        assert expert < experts
        if i < spans.wide160:
            start, width = offset * 16, 160
            selected_pairs.add(expert)
        elif i < spans.wide160 + spans.wide128:
            start, width = offset * 128, 128
        else:
            start, width = offset * 64, 64
        slots = coverage[expert]
        assert start < len(slots) * 16
        for slot in range(start // 16, min((start + width) // 16, len(slots))):
            slots[slot] += 1
        if i < spans.wide160:
            selected_rows += min(width, len(slots) * 16 - start)
    for slots in coverage:
        assert all(value == 1 for value in slots)
        covered_rows += len(slots) * 16
    assert sum(counts) == tokens * used
    assert selected_rows == sum(len(coverage[e]) * 16 for e in selected_pairs)
    return {"wide160": spans.wide160, "wide128": spans.wide128,
            "tail64": spans.tail64, "covered_padded_rows": covered_rows,
            "selected_padded_rows": selected_rows,
            "selected_real_rows": sum(counts[e] for e in selected_pairs),
            "selected_expert_pairs": len(selected_pairs)}


def main():
    with tempfile.TemporaryDirectory(prefix="lie-iq2-token160-") as directory:
        library = Path(directory) / "map.so"
        command = ["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-fPIC",
                   "-shared", str(SOURCE), "-o", str(library)]
        subprocess.run(command, check=True)
        call = ctypes.CDLL(str(library)).lie_iq2_token160_tiles
        call.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32,
                         ctypes.c_uint32, ctypes.c_uint32,
                         ctypes.POINTER(ctypes.c_int32), ctypes.c_size_t,
                         ctypes.POINTER(Spans)]
        call.restype = ctypes.c_int
        for n in (1, 17, 65, 145, 159, 160, 161, 223, 224, 255,
                  256, 257, 320, 321, 409, 512, 2048, 4096):
            audit(call, [n], n, 1)
        invalid_counts = (ctypes.c_uint32 * 1)(224)
        guard_map = (ctypes.c_int32 * 1)(-7)
        guard_spans = Spans(99, 99, 99)
        assert call(invalid_counts, 1, 224, 1, guard_map, 0,
                    ctypes.byref(guard_spans)) == 0
        assert guard_map[0] == -7 and (guard_spans.wide160,
              guard_spans.wide128, guard_spans.tail64) == (99, 99, 99)
        assert call(invalid_counts, 1, 225, 1, guard_map, 1,
                    ctypes.byref(guard_spans)) == 0
        assert guard_map[0] == -7 and (guard_spans.wide160,
              guard_spans.wide128, guard_spans.tail64) == (99, 99, 99)
        data = json.loads(ROUTING.read_text())
        rows = [audit(call, layer["counts"], 2048, 10)
                for layer in data["layers"]]
        assert len(rows) == 48
        summary = {"schema": "synapse-lie.q2-iq2-token160-map-audit.v1",
                   "original_routing": str(ROUTING.relative_to(ROOT)),
                   "layers": len(rows), "edge_shapes": 18,
                   "coverage_exact": True, "original_model_run": False,
                   "wide160": sum(row["wide160"] for row in rows),
                   "wide128": sum(row["wide128"] for row in rows),
                   "tail64": sum(row["tail64"] for row in rows),
                   "selected_expert_pairs": sum(row["selected_expert_pairs"] for row in rows),
                   "selected_real_rows": sum(row["selected_real_rows"] for row in rows),
                   "total_real_rows": 2048 * 10 * len(rows),
                   "selected_padded_rows": sum(row["selected_padded_rows"] for row in rows),
                   "total_padded_rows": sum(row["covered_padded_rows"] for row in rows)}
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
