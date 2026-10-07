#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an unselected 160-row IQ2 kernel from the retained provider."""

import difflib
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT_MANIFEST = ROOT / "config/q2-iq2-fixed-bounds-source.json"
INC = "src/models/qwen38_flash_next/kernels/rocm/q2_iq2_fixed_bounds.inc"
HIP = "src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp"
OUT = ROOT / ".deps/gufo-q2-iq2-token160-probe"
PATCH = ROOT / "experiments/q2-iq2-token160-probe.patch"
MANIFEST = ROOT / "config/q2-iq2-token160-probe-source.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f"expected one occurrence: {before[:80]}")
    return source.replace(before, after, 1)


def main():
    parent = json.loads(PARENT_MANIFEST.read_text())["variants"]["iq2-fixed-bounds"]
    base = ROOT / parent["source"]
    for relative, digest in parent["files"].items():
        if sha(base / relative) != digest:
            raise ValueError(f"retained provider differs: {relative}")
    if any(path.exists() for path in (OUT, PATCH, MANIFEST)):
        raise ValueError("private probe already exists; preserve its evidence")

    old_inc = (base / INC).read_text()
    new_inc = replace_once(
        old_inc,
        "bool kPacked = false, bool kScaled = false>",
        "bool kPacked = false, bool kScaled = false, bool kOffset16 = false>",
    )
    new_inc = replace_once(
        new_inc,
        "static_assert(BM == 128 && (BN == 64 || BN == 128) && BK == 2);",
        "static_assert(BM == 128 && (BN == 64 || BN == 128 || BN == 160) && BK == 2);",
    )
    new_inc = replace_once(
        new_inc,
        "static_assert(BN % 16 == 0 && BN / 16 <= 8);",
        "static_assert(BN % 16 == 0 && BN / 16 <= 10);\n"
        "  static_assert(!kOffset16 || BN == 160);",
    )
    new_inc = replace_once(
        new_inc,
        "const int t_local = (tile >> 16) * BN;",
        "const int t_local = (tile >> 16) * (kOffset16 ? 16 : BN);",
    )
    new_inc = replace_once(
        new_inc,
        "constexpr int kActFetch = BN <= 64 ? 2 : 4;",
        "constexpr int kActFetch = BN <= 64 ? 2 : BN <= 128 ? 4 : 5;",
    )
    old_hip = (base / HIP).read_text()
    anchor = '#include "q2_scaled_input.inc"'
    probe = """// Private experiment only. Production dispatch never calls this symbol.
void ProbeRoutedIq2Token160(const void* gate, const void* up, const __half* x,
                            const std::int32_t* tiles, std::uint32_t n_tiles,
                            const std::int32_t* bounds,
                            const std::int32_t* rows_token,
                            const std::int32_t* rows_slot, float* out,
                            hipStream_t stream) {
  const dim3 grid(10, n_tiles);
  hipLaunchKernelGGL(
      (RoutedIq2FixedBoundsKernel<WeightType::kIQ2_XXS, 128, 160, 2,
                                 true, false, false, true>),
      grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,
      rows_slot, nullptr, out, nullptr, 640, 2560, up);
}

"""
    new_hip = replace_once(old_hip, anchor, probe + anchor)
    shutil.copytree(base, OUT)
    (OUT / INC).write_text(new_inc)
    (OUT / HIP).write_text(new_hip)
    for relative, digest in parent["files"].items():
        if sha(base / relative) != digest:
            raise ValueError(f"retained provider changed during copy: {relative}")
        if relative not in (INC, HIP) and sha(OUT / relative) != digest:
            raise ValueError(f"unrelated provider file changed: {relative}")
    chunks = []
    for relative, before, after in ((INC, old_inc, new_inc), (HIP, old_hip, new_hip)):
        chunks.extend(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True),
            fromfile="a/" + relative, tofile="b/" + relative))
    PATCH.write_text("".join(chunks))
    result = {
        "schema": "synapse-lie.q2-iq2-token160-probe-source.v1",
        "retained_manifest": str(PARENT_MANIFEST.relative_to(ROOT)),
        "retained_manifest_sha256": sha(PARENT_MANIFEST),
        "private_provider": str(OUT.relative_to(ROOT)),
        "private_patch": str(PATCH.relative_to(ROOT)),
        "private_patch_sha256": sha(PATCH),
        "changed_files": {INC: sha(OUT / INC), HIP: sha(OUT / HIP)},
        "unchanged_files": len(parent["files"]) - 2,
        "selected_by_production": False,
        "gpu_run": False,
        "model_run": False,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
