#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the new channel predicate against retained1585 source and assembly."""
import importlib.util
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/q2-ssm-channel-bounds-preparation"


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


group = module("analyze-q2-ssm-row-group-compose-static.py")
generator = module("prepare-q2-ssm-channel-bounds.py")
ssm, old = group.ssm, group.old


def main():
    source_path = ROOT / "config/q2-ssm-channel-bounds-source.json"
    source = json.loads(source_path.read_text())["variants"]["ssm-channel-bounds"]
    for key, value in source.items():
        if key.endswith("_sha256"):
            assert ssm.sha(ROOT / source[key[:-7]]) == value, key
    parent = json.loads((ROOT / source["parent_manifest"]).read_text())["variants"]["ssm-fixed-bounds"]
    for provider in (source, parent):
        assert ssm.inventory(ROOT / provider["source"]) == provider["files"]
    proof = generator.partition_check()
    assert proof == source["symbolic_partition"]
    metadata_path = ROOT / "config/q2-ssm-fixed-bounds-static.json"
    metadata = json.loads(metadata_path.read_text())
    before_path = ROOT / metadata["candidate_assembly_path"]
    assert ssm.sha(before_path) == metadata["candidate_assembly_sha256"]
    after_path = OUT / "candidate.s"
    a, b = old.isa.parse(before_path), old.isa.parse(after_path)
    before, after = before_path.read_text(), after_path.read_text()
    assert set(a) == set(b) and len(a) == 162
    changed = [name for name in a
               if old.instructions(before, name) != old.instructions(after, name)
               or a[name]["resources"] != b[name]["resources"]]
    assert len(changed) == 1
    symbol = changed[0]
    assert "ILi256ELi128ELi2ELi8ELi1ELi1ELb0ELb1" in symbol
    assert a[symbol]["resources"] == b[symbol]["resources"]
    retained_mnemonics = ("v_wmma_f32_16x16x16_f16", "s_barrier",
                         "global_load_b128", "global_store_b128",
                         "ds_load_b128", "ds_store_b128")
    for name in retained_mnemonics:
        assert a[symbol]["mnemonics"].get(name, 0) == b[symbol]["mnemonics"].get(name, 0), name
    original = (ROOT / parent["source"] / ssm.REL).read_text()
    changed_source = (ROOT / source["source"] / ssm.REL).read_text()
    assert ssm.function(original, "bool DenseF16SsmGemm(") == ssm.function(
        changed_source, "bool DenseF16SsmGemm(")
    with TemporaryDirectory(dir=OUT, prefix="reconstruct-") as temporary:
        destination = Path(temporary) / ssm.REL
        destination.parent.mkdir(parents=True)
        destination.write_text(original)
        result = subprocess.run(["patch", "--batch", "-p1", "-i", str(ROOT / source["patch"])],
                                cwd=temporary, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert ssm.sha(destination) == source["files"][ssm.REL]
    commands = {name: json.loads((OUT / (name + "-command.json")).read_text())
                for name in ("generation", "assembly", "fixture-host", "fixture-device")}
    assert all(command["exit_code"] == 0 for command in commands.values())
    saved_flags = json.loads((before_path.parent / "assembly-argv.json").read_text())
    candidate_flags = json.loads((OUT / "assembly-argv.json").read_text())
    assert [item.replace("q2-ssm-channel-bounds", "q2-ssm-fixed-bounds")
            for item in candidate_flags] == saved_flags
    mnemonics = sorted(set(a[symbol]["mnemonics"]) | set(b[symbol]["mnemonics"]))
    delta = {name: [a[symbol]["mnemonics"].get(name, 0), b[symbol]["mnemonics"].get(name, 0)]
             for name in mnemonics
             if a[symbol]["mnemonics"].get(name, 0) != b[symbol]["mnemonics"].get(name, 0)}
    counts = [a[symbol]["instructions"], b[symbol]["instructions"]]
    report = dict(schema="synapse-lie.q2-ssm-channel-bounds-static.v1",
        source_manifest_sha256=ssm.sha(source_path), provider_files=1027,
        parent_static_metadata_sha256=ssm.sha(metadata_path),
        parent_assembly_path=str(before_path.relative_to(ROOT)),
        parent_assembly_sha256=ssm.sha(before_path),
        candidate_assembly_path=str(after_path.relative_to(ROOT)),
        candidate_assembly_sha256=ssm.sha(after_path),
        parent_recompiled=False, compiler_arguments_match_except_paths=True,
        source_patch_reconstruction_exact=True, launch_wrapper_exact=True,
        other_kernels_instruction_operand_resource_exact=161,
        symbolic_partition=proof,
        parent_kernel=dict(symbol=symbol, **a[symbol],
                           compiler_comments=group.static.compiler_comments(before, symbol)),
        candidate_kernel=dict(symbol=symbol, **b[symbol],
                              compiler_comments=group.static.compiler_comments(after, symbol)),
        instruction_counts=counts, instruction_count_change_percent=100 * (counts[1] / counts[0] - 1),
        changed_mnemonics=delta,
        unchanged_mnemonic_counts={name: a[symbol]["mnemonics"].get(name, 0)
                                   for name in retained_mnemonics},
        commands=commands,
        limits="Static counts include compiler scheduling and paired instructions. Changes in packed F32 arithmetic are visible in the mnemonic delta: source expressions and equivalent predicates do not establish compiled numerical equivalence. The syntax-checked existing fixture contains the older1580 control, not a new device comparison with retained1585. No device or model execution, throughput, active occupancy or independent quality is established.",
        gpu_run=False, model_inference=False, numerical_acceptance=False,
        performance_gain=False, goal_met=False)
    output = ROOT / "config/q2-ssm-channel-bounds-static.json"
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(instructions=counts,
        change_percent=report["instruction_count_change_percent"],
        other_kernels_exact=161, resources_unchanged=True,
        source_patch_exact=True, gpu_run=False)))


if __name__ == "__main__":
    main()
