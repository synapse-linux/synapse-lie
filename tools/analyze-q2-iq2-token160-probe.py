#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify that a private 160-row IQ2 body leaves retained GPU bodies intact."""

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    source_path = ROOT / "config/q2-iq2-token160-probe-source.json"
    source = json.loads(source_path.read_text())
    provider = ROOT / source["private_provider"]
    for relative, digest in source["changed_files"].items():
        assert sha(provider / relative) == digest
    assert sha(ROOT / source["private_patch"]) == source["private_patch_sha256"]
    old_path = ROOT / "config/q2-iq2-fixed-bounds-static.json"
    old = json.loads(old_path.read_text())
    old_asm = ROOT / old["candidate_assembly_path"]
    assert sha(old_asm) == old["candidate_assembly_sha256"]
    preparation = ROOT / "evidence/q2-iq2-token160-probe-preparation"
    compile_result = json.loads((preparation / "compile.json").read_text())
    assert compile_result["exit_code"] == 0
    new_asm = preparation / "candidate.s"
    parser = load("q2_static_parser", ROOT / "tools/analyze-q2-iq2-halfstage-static.py")
    streams = load("q2_stream_parser", ROOT / "tools/analyze-q2-iq2-token256-probe.py")
    before, after = parser.parse(old_asm), parser.parse(new_asm)
    before_ops = streams.instruction_streams(old_asm)
    after_ops = streams.instruction_streams(new_asm)
    matched = set()
    renamed = 0
    for symbol, metadata in before.items():
        candidate = symbol
        if candidate not in after and "RoutedIq2FixedBoundsKernel" in candidate:
            candidate = candidate.replace("ELb1ELb0ELb0EE", "ELb1ELb0ELb0ELb0EE")
            renamed += 1
        assert candidate in after
        assert metadata["resources"] == after[candidate]["resources"]
        assert before_ops[symbol] == after_ops[candidate]
        matched.add(candidate)
    assert len(before) == 164 and renamed == 2
    added = set(after) - matched
    assert len(added) == 1
    private_symbol = next(iter(added))
    assert "RoutedIq2FixedBoundsKernel" in private_symbol and "ELi160ELi2" in private_symbol
    old_symbol = next(s for s in before if "RoutedIq2FixedBoundsKernel" in s and "ELi128ELi2" in s)
    old_resources = before[old_symbol]["resources"]
    new_resources = after[private_symbol]["resources"]
    assert old_resources["next_free_vgpr"] == 150
    assert old_resources["group_segment_fixed_size"] == 25728
    assert new_resources["private_segment_fixed_size"] == 0
    report = {
        "schema": "synapse-lie.q2-iq2-token160-probe-static.v1",
        "source_manifest_sha256": sha(source_path),
        "retained_assembly_sha256": sha(old_asm),
        "candidate_assembly_sha256": sha(new_asm),
        "compile": compile_result,
        "retained_device_instruction_operand_resource_exact": len(matched),
        "retained_symbols_renamed_by_private_template_parameter": renamed,
        "added_device_bodies": 1,
        "retained_128_resources": old_resources,
        "private_160_resources": new_resources,
        "gpu_run": False,
        "model_run": False,
        "numerical_acceptance": False,
        "performance_gain": False,
    }
    output = ROOT / "config/q2-iq2-token160-probe-static.json"
    if output.exists():
        raise ValueError("preserve existing static report")
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"retained_exact": len(matched),
                      "vgpr": [old_resources["next_free_vgpr"],
                               new_resources["next_free_vgpr"]],
                      "lds": [old_resources["group_segment_fixed_size"],
                              new_resources["group_segment_fixed_size"]],
                      "gpu_run": False}))


if __name__ == "__main__":
    main()
