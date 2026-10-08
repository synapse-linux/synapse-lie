#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Isolate measured hipBLASLt HC down algorithm 7526 for pp2048 exploration."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-affine-palette'
OUT = ROOT / '.deps/gufo-q2-bench-hc-library-down'
REL = Path('src/models/qwen38_flash_next/kernels/rocm/blaslt.cpp')
EXPECTED = 'c96c993d97baa3253190491c96dac16b6ede767eff8460fc24d7b9e0f5d0f590'


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / REL) != EXPECTED:
        raise ValueError('Measured palette library source changed')
    original = (BASE / REL).read_text()
    changed = original
    replacements = [
        ('  const auto usable = [&](hipblasLtMatmulAlgo_t& algorithm) {',
         '''  // Isolated performance exploration from the synthetic .157 sweep.
  // The unchanged F16 values use a different accumulation order; numerical
  // failures are retained. No live search, workspace or global tuning cache.
  const int preferred = type == HIP_R_16F && m == 320 && n == 2048 &&
                                k == 10240 ? 7526 : -1;
  const auto usable = [&](hipblasLtMatmulAlgo_t& algorithm) {'''),
        ('        p->algorithm = candidates[i].algo;',
         '''        if (preferred >= 0 &&
            hipblaslt_ext::getIndexFromAlgo(candidates[i].algo) != preferred)
          continue;
        p->algorithm = candidates[i].algo;'''),
        ('  const bool hc_half =\n      n >= 96 &&',
         '''  const bool hc_library_down =
      type == HIP_R_16F && m == 320 && n == 2048 && k == 10240;
  const bool hc_half =
      !hc_library_down && n >= 96 &&'''),
    ]
    for before, after in replacements:
        if changed.count(before) != 1:
            raise ValueError('Unexpected library dispatch boundary')
        changed = changed.replace(before, after)
    shutil.copytree(BASE, OUT)
    target = OUT / REL
    target.write_text(changed)
    subprocess.run(['clang-format', '-i', str(target)], check=True)
    inventory = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                       and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    if inventory != [str(REL)]:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments/q2-hc-library-down.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), target.read_text().splitlines(True),
        fromfile='a/' + str(REL), tofile='b/' + str(REL))))
    report = dict(scope='Prepared exploratory source; failed component numerical gate, model speed/quality unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', base=str(BASE.relative_to(ROOT)),
        candidate=str(OUT.relative_to(ROOT)), changed_files=inventory,
        base_sha256=sha(BASE / REL), candidate_sha256=sha(target), patch_sha256=sha(patch),
        dispatch='Only F16 M320/K10240/n2048 uses measured algorithm index 7526; other dimensions retain prior routing',
        workspace_bytes=0, numerical_limits_changed=False, model_conversion=False,
        limit='Algorithm index binds this ROCm installation; require supported zero-workspace match or fail. No automatic runtime adoption.')
    (ROOT / 'config/q2-hc-library-down-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
