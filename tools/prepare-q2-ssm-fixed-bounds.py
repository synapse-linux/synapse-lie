#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Remove only SSM row/K bounds already proved by its unchanged launch guard."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm', ROOT / 'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def main():
    previous_path = ROOT / 'config/q2-ssm-fixed-shape-source.json'
    previous = json.loads(previous_path.read_text())['variants']['ssm-fixed-shape']
    assert ssm.inventory(ROOT / previous['source']) == previous['files']
    source = (ROOT / previous['source'] / ssm.REL).read_text()
    prefix = 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,'
    body = ssm.function(source, prefix)
    changed_body = body
    replacements = [
        ('    a_live[p] = idx < kAUnits && r < m_i;',
         '    // SSM launches64 full output-row blocks and two full K32 blocks.\n'
         '    a_live[p] = kSsmConv || (idx < kAUnits && r < m_i);'),
        ('      const bool live = a_live[p] && kb < num_kb;',
         '      const bool live = kSsmConv || (a_live[p] && kb < num_kb);'),
        ('      if (b_ptr[p] != nullptr && kb < num_kb) {',
         '      if (b_ptr[p] != nullptr && (kSsmConv || kb < num_kb)) {'),
        ('              if (row >= m)\n                continue;\n',
         '              // Every float4 row fits the SSM M16384 grid.\n'),
    ]
    for before, after in replacements:
        changed_body = ssm.once(changed_body, before, after)
    changed = ssm.once(source, body, changed_body)
    # The removed predicates are universally true for this guarded grid.
    fetches = 0
    for block in range(64):
        for p in range(2):
            for tid in range(256):
                idx = p * 256 + tid
                assert idx < 512 and block * 256 + idx // 2 < 16384
                fetches += 1
    k_fetches = 0
    for kb0 in range(0, 80, 2):
        for tid in range(256):
            assert kb0 + tid % 2 < 80
            k_fetches += 1
    stores = 0
    for block in range(64):
        for wave in range(8):
            for lane in range(32):
                for v in range(4):
                    row = block * 256 + wave * 32 + (lane % 2) * 16 + v * 4
                    assert row + 3 < 16384
                    stores += 1
    assert ssm.function(source, 'bool DenseF16SsmGemm(') == ssm.function(changed, 'bool DenseF16SsmGemm(')
    assert body.count('tok < batch') == changed_body.count('tok < batch')
    assert body.count('t < static_cast<int>(batch)') == changed_body.count('t < static_cast<int>(batch)')
    destination = ROOT / '.deps/gufo-q2-ssm-fixed-bounds-run'
    manifest_path = ROOT / 'config/q2-ssm-fixed-bounds-source.json'
    patch_path = ROOT / 'experiments/q2-ssm-fixed-bounds.patch'
    assert not any(p.exists() for p in (destination, manifest_path, patch_path))
    shutil.copytree(ROOT / previous['source'], destination)
    (destination / ssm.REL).write_text(changed)
    parent = json.loads((ROOT / previous['parent_manifest']).read_text())['variants']['down-register-scatter']
    original = (ROOT / parent['source'] / ssm.REL).read_text()
    with patch_path.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True),
            fromfile='a/' + ssm.REL, tofile='b/' + ssm.REL)))
    files = ssm.inventory(destination)
    assert len(files) == 1027 and [p for p in files if files[p] != parent['files'][p]] == [ssm.REL]
    variant = dict(previous)
    variant.update(source=str(destination.relative_to(ROOT)), files=files,
        patch=str(patch_path.relative_to(ROOT)), patch_sha256=ssm.sha(patch_path),
        preceding_local_manifest=str(previous_path.relative_to(ROOT)),
        preceding_local_manifest_sha256=ssm.sha(previous_path),
        mechanism='Expose fixed SSM M/K and omit only row/K predicates implied by its unchanged full-row grid and even80 K32 blocks. Preserve all token-tail checks and other dense specializations.',
        symbolic_bounds=dict(weight_fetch_owners=fetches, k_fetch_owners=k_fetches,
                             float4_store_owners=stores, token_tail_guards_retained=True),
        numerical_contract='Original WMMA, rounded operands and convolution formulas retained; row/K bounds are proven for the unchanged wrapper. Compiler arithmetic equivalence and actual device memory safety still require GPU checks.')
    with manifest_path.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-ssm-fixed-bounds-source.v1',
                       variants={'ssm-fixed-bounds': variant}, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=1027, bounds=variant['symbolic_bounds'], gpu_run=False)))


if __name__ == '__main__':
    main()
