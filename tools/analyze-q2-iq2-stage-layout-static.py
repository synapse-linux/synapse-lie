#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify that the IQ2 layout probe adds one body and preserves production ISA."""

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/q2-iq2-stage-layout-source.json"
PARENT = ROOT / "config/q2-iq2-fixed-bounds-static.json"
ASSEMBLY = ROOT / "evidence/q2-iq2-stage-layout-host-r1/candidate.s"
FIXTURE = ROOT / "run/q2-iq2-stage-layout-hip-build/cmake/hip/q2_iq2_stage_layout_check"
REPORT = ROOT / "config/q2-iq2-stage-layout-static.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parser():
    path = ROOT / "tools/analyze-q2-iq2-token256-probe.py"
    spec = importlib.util.spec_from_file_location("iq2_token256_parser", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_parser(), module.instruction_streams


def main() -> None:
    if REPORT.exists():
        raise ValueError("preserve existing static report")
    source = json.loads(SOURCE.read_text())
    provider = ROOT / source["private_provider"]
    assert sha(ROOT / source["private_patch"]) == source["private_patch_sha256"]
    for relative, digest in source["changed_files"].items():
        assert sha(provider / relative) == digest, relative
    parent = json.loads(PARENT.read_text())
    parent_assembly = ROOT / parent["candidate_assembly_path"]
    assert sha(parent_assembly) == parent["candidate_assembly_sha256"]
    parse, instructions = parser()
    original = parse(parent_assembly)
    candidate = parse(ASSEMBLY)
    old_isa = instructions(parent_assembly)
    new_isa = instructions(ASSEMBLY)
    renamed = {}
    for symbol in original:
        new_symbol = (symbol.replace("ELb1ELb0ELb0EEE", "ELb1ELb0ELb0ELb0EEE")
                      if "RoutedIq2FixedBoundsKernel" in symbol else symbol)
        assert new_symbol in candidate, symbol
        assert original[symbol]["resources"] == candidate[new_symbol]["resources"], symbol
        assert old_isa[symbol] == new_isa[new_symbol], symbol
        renamed[symbol] = new_symbol
    additions = set(candidate) - set(renamed.values())
    assert len(original) == 164 and len(additions) == 1, additions
    added = additions.pop()
    assert "RoutedIq2FixedBoundsKernel" in added and "ELb1ELb0ELb0ELb1EEE" in added
    resources = candidate[added]["resources"]
    assert resources["group_segment_fixed_size"] == 25728
    assert resources["private_segment_fixed_size"] == 0
    assert resources["next_free_vgpr"] == 153
    assert FIXTURE.is_file()
    report = {
        "schema": "synapse-lie.q2-iq2-stage-layout-static.v1",
        "source_manifest_sha256": sha(SOURCE),
        "retained_assembly_sha256": sha(parent_assembly),
        "candidate_assembly_sha256": sha(ASSEMBLY),
        "linked_fixture_sha256": sha(FIXTURE),
        "retained_device_instruction_operand_resource_exact": len(renamed),
        "added_device_bodies": 1,
        "added_symbol": added,
        "added_resources": resources,
        "gpu_run": False,
        "model_run": False,
        "performance_gain": False,
        "limit": "Static compilation and C17 byte-layout tests do not establish GPU time or model memory fit.",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"retained_exact": len(renamed),
                      "added_resources": resources, "gpu_run": False}))


if __name__ == "__main__":
    main()
