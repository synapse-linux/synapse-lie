#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the unselected 256-token IQ2 tile with the retained 128 tile."""

import hashlib
import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_parser():
    path = ROOT / "tools/analyze-q2-iq2-halfstage-static.py"
    spec = importlib.util.spec_from_file_location("q2_static_parser", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse


def instruction_streams(path: Path) -> dict[str, tuple[str, ...]]:
    """Ignore assembly label numbering and comments, preserve opcodes/operands."""
    source = path.read_text()
    bodies = {}
    for match in re.finditer(r"^(_Z[^\s:]+):\s*;", source, re.M):
        start, symbol = match.start(), match[1]
        end = source.index("\n\t.section\t.rodata", start)
        instructions = []
        for line in source[start:end].splitlines():
            if re.match(r"^\t[a-z][a-z_0-9]+(?:\s|$)", line):
                without_comment = line.split(";", 1)[0].strip()
                instructions.append(re.sub(r"\.LBB\d+_", ".LBB_", without_comment))
        bodies[symbol] = tuple(instructions)
    return bodies


def main() -> None:
    target = ROOT / "config/q2-iq2-token256-probe-static.json"
    if target.exists():
        raise ValueError("preserve existing static report")
    source_path = ROOT / "config/q2-iq2-token256-probe-source.json"
    source = json.loads(source_path.read_text())
    for relative, digest in source["changed_files"].items():
        if sha(ROOT / source["private_provider"] / relative) != digest:
            raise ValueError(f"private source differs: {relative}")
    if sha(ROOT / source["private_patch"]) != source["private_patch_sha256"]:
        raise ValueError("private patch differs")
    parent_static_path = ROOT / "config/q2-iq2-fixed-bounds-static.json"
    parent_static = json.loads(parent_static_path.read_text())
    parent_asm = ROOT / parent_static["candidate_assembly_path"]
    if sha(parent_asm) != parent_static["candidate_assembly_sha256"]:
        raise ValueError("retained assembly differs")
    output = ROOT / "evidence/q2-iq2-token256-probe-preparation"
    compile_result = json.loads((output / "compile.json").read_text())
    if compile_result["exit_code"] != 0:
        raise ValueError("device compilation failed")
    candidate_asm = output / "candidate.s"
    parse = load_parser()
    parent = parse(parent_asm)
    candidate = parse(candidate_asm)
    parent_instructions = instruction_streams(parent_asm)
    candidate_instructions = instruction_streams(candidate_asm)
    if set(candidate) - set(parent) != {next(s for s in candidate if "RoutedIq2FixedBoundsKernel" in s and "ELi256ELi2" in s)}:
        raise ValueError("unexpected added device body")
    if set(parent) - set(candidate):
        raise ValueError("retained device body missing")
    if any(parent[s]["resources"] != candidate[s]["resources"] or
           parent_instructions[s] != candidate_instructions[s] for s in parent):
        raise ValueError("retained device instructions, operands or resources changed")
    old = next(s for s in parent if "RoutedIq2FixedBoundsKernel" in s and "ELi128ELi2" in s)
    new = next(iter(set(candidate) - set(parent)))
    before, after = parent[old], candidate[new]
    expected = (
        (before["resources"]["next_free_vgpr"], after["resources"]["next_free_vgpr"]),
        (before["resources"]["group_segment_fixed_size"], after["resources"]["group_segment_fixed_size"]),
        (before["resources"]["private_segment_fixed_size"], after["resources"]["private_segment_fixed_size"]),
    )
    if expected != ((150, 242), (25728, 42112), (0, 0)):
        raise ValueError(f"unexpected resources: {expected}")
    report = {
        "schema": "synapse-lie.q2-iq2-token256-probe-static.v1",
        "source_manifest_sha256": sha(source_path),
        "retained_static_sha256": sha(parent_static_path),
        "retained_assembly_sha256": sha(parent_asm),
        "candidate_assembly_sha256": sha(candidate_asm),
        "compile": compile_result,
        "retained_device_instruction_operand_resource_exact": len(parent),
        "added_device_bodies": 1,
        "retained_128": {"symbol": old, **before},
        "probe_256": {"symbol": new, **after},
        "relative_vgpr_increase_percent": 100 * (242 / 150 - 1),
        "relative_lds_increase_percent": 100 * (42112 / 25728 - 1),
        "gpu_run": False,
        "model_run": False,
        "numerical_acceptance": False,
        "performance_gain": False,
        "limits": "Static device compilation only; no runtime occupancy or speed claim.",
    }
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"retained_exact": len(parent), "vgpr": [150, 242],
                      "lds": [25728, 42112], "scratch": [0, 0],
                      "gpu_run": False}))


if __name__ == "__main__":
    main()
