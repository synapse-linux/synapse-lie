#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Expose the block-uniform SSM channel partition without changing arithmetic."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ssm", ROOT / "tools/prepare-q2-ssm-row-group.py")
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def partition_check():
    """Enumerate each float4 owner at the guarded M16384/BM256 launch."""
    owners = {}
    for block in range(64):
        r_block = block * 256
        for wave in range(8):
            for half in range(2):
                for vector in range(4):
                    row = r_block + wave * 32 + half * 16 + vector * 4
                    assert row not in owners
                    owners[row] = block
                    for component in range(4):
                        assert ((row + component) < 10240) == (r_block < 10240)
    assert set(owners) == set(range(0, 16384, 4))
    return dict(float4_owners=len(owners), scalar_rows=16384,
                convolved_blocks=40, projection_only_blocks=24,
                channel_boundary=10240, block_rows=256,
                token_guards_unchanged=True, arithmetic_unchanged_in_source=True)


def main():
    parent_path = ROOT / "config/q2-ssm-fixed-bounds-source.json"
    parent = json.loads(parent_path.read_text())["variants"]["ssm-fixed-bounds"]
    base = ROOT / parent["source"]
    assert ssm.inventory(base) == parent["files"]
    original = (base / ssm.REL).read_text()
    changed = ssm.once(original,
        "          constexpr std::uint32_t channels = 10240;\n",
        "          constexpr std::uint32_t channels = 10240;\n"
        "          // No BM256 block straddles the fixed channel boundary.\n"
        "          static_assert(channels % BM == 0);\n"
        "          const bool convolved_block = r_block < channels;\n")
    changed = ssm.once(changed,
        "              if (row >= channels || tok_l < 3 || tok_l >= kOutputTokens - 3 ||\n",
        "              if (!convolved_block || tok_l < 3 || tok_l >= kOutputTokens - 3 ||\n")
    changed = ssm.once(changed,
        "              if (row < channels && tok_l >= 3) {\n",
        "              if (convolved_block && tok_l >= 3) {\n")
    wrapper = "bool DenseF16SsmGemm("
    assert ssm.function(original, wrapper) == ssm.function(changed, wrapper)
    destination = ROOT / ".deps/gufo-q2-ssm-channel-bounds-run"
    manifest_path = ROOT / "config/q2-ssm-channel-bounds-source.json"
    patch_path = ROOT / "experiments/q2-ssm-channel-bounds.patch"
    assert not any(p.exists() for p in (destination, manifest_path, patch_path))
    proof = partition_check()
    shutil.copytree(base, destination)
    (destination / ssm.REL).write_text(changed)
    patch_path.write_text("// SPDX-License-Identifier: MIT\n" + "".join(
        difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                            fromfile="a/" + ssm.REL, tofile="b/" + ssm.REL)))
    files = ssm.inventory(destination)
    assert len(files) == 1027
    assert [p for p in files if files[p] != parent["files"][p]] == [ssm.REL]
    measured = ROOT / "config/q2-ssm-fixed-bounds-model-results.json"
    variant = dict(source=str(destination.relative_to(ROOT)), files=files,
        parent_manifest=str(parent_path.relative_to(ROOT)),
        parent_manifest_sha256=ssm.sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),
        measured_parent_sha256=ssm.sha(measured),
        patch=str(patch_path.relative_to(ROOT)), patch_sha256=ssm.sha(patch_path),
        mechanism="Replace per-row convolution channel predicates with the equivalent block-uniform predicate at the unchanged guarded SSM launch.",
        symbolic_partition=proof,
        numerical_contract="All weight conversion, ordered WMMA, transpose, convolution expressions and token/history tails remain unchanged in source. Generated arithmetic and actual outputs require device validation.",
        additional_allocations=0, additional_streams=0, additional_launches=0,
        parent_rebuilt=False, gpu_run=False, model_inference=False,
        numerical_acceptance=False, performance_gain=False)
    with manifest_path.open("x") as stream:
        json.dump(dict(schema="synapse-lie.q2-ssm-channel-bounds-source.v1",
                       variants={"ssm-channel-bounds": variant}, goal_met=False),
                  stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(provider_files=1027, partition=proof, gpu_run=False)))


if __name__ == "__main__":
    main()
