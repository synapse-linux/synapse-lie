#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare only the GPU-qualified ordinary owner route in a private provider."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}


def main():
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    assert inventory(base) == parent['files'] and len(parent['files']) == 1027
    qualification_path = ROOT / 'config/q2-hc-norm-owner-component-results.json'
    qualification = json.loads(qualification_path.read_text())
    assert qualification['numerical_exact'] and qualification['device_work_safe']
    assert len(qualification['output_records']) == 120
    ordinary_timing, moe_timing = qualification['summaries']
    assert ordinary_timing['wall_cycle_time_change_percent'] < 0
    assert moe_timing['wall_cycle_time_change_percent'] > 0
    include_path = ROOT / 'experiments/q2-hc-norm-owner-draft.inc'
    source = include_path.read_text()
    ordinary = source.split('\n__global__ void HcNormOwnerDraftMoeKernel(', 1)[0] + '\n'
    assert ordinary.count('__global__ void') == 1
    assert 'HcNormOwnerDraftOrdinaryKernel' in ordinary
    kernel_path = base / (REL + 'kernels.hip.cpp')
    kernel = kernel_path.read_text()
    anchor = '}  // namespace\n\n'
    assert kernel.count(anchor) == 1
    changed = kernel.replace(anchor, anchor + '#include "q2_hc_rms_owner_ordinary.inc"\n\n', 1)
    launch = '''  hipLaunchKernelGGL(HcCombineF32HalfKernel, dim3(n_tokens), dim3(kThreads), 0,
                     stream, res, block_out, inject, inject_parts, gamma, xn,
                     norm_half, hidden, eps);
'''
    assert changed.count(launch) == 1
    replacement = '''  // Keep scalar/decode and small ragged dispatch unchanged. The complete
  // ordinary owner kernel is qualified at n97/129 and the fixed n2048 point.
  if (n_tokens >= 96) {
    hipLaunchKernelGGL(HcNormOwnerDraftOrdinaryKernel, dim3(n_tokens),
                       dim3(kThreads), 0, stream, res, block_out, inject,
                       inject_parts, gamma, xn, norm_half, hidden, eps);
  } else {
    hipLaunchKernelGGL(HcCombineF32HalfKernel, dim3(n_tokens), dim3(kThreads), 0,
                       stream, res, block_out, inject, inject_parts, gamma, xn,
                       norm_half, hidden, eps);
  }
'''
    changed = changed.replace(launch, replacement, 1)
    target = ROOT / '.deps/gufo-q2-hc-rms-owner-ordinary-run'
    assert not target.exists(), 'Preserve existing provider'
    shutil.copytree(base, target)
    (target / (REL + 'kernels.hip.cpp')).write_text(changed)
    with (target / (REL + 'q2_hc_rms_owner_ordinary.inc')).open('x') as stream:
        stream.write(ordinary)
    files = inventory(target)
    assert len(files) == 1028
    changed_files = [name for name, digest in parent['files'].items() if files[name] != digest]
    assert changed_files == [REL + 'kernels.hip.cpp']
    patch_path = ROOT / 'experiments/q2-hc-rms-owner-ordinary.patch'
    with patch_path.open('x') as stream:
        stream.write(''.join(difflib.unified_diff(kernel.splitlines(keepends=True),
            changed.splitlines(keepends=True), fromfile='a/' + REL + 'kernels.hip.cpp',
            tofile='b/' + REL + 'kernels.hip.cpp')))
    prep = ROOT / 'evidence/q2-hc-rms-owner-ordinary-preparation'
    prep.mkdir()
    argv = json.loads((ROOT / 'evidence/q2-hc-norm-owner-component-preparation/assembly-argv.json').read_text())
    old_include = '-I' + str(base)
    assert argv.count(old_include) == 1
    argv[argv.index(old_include)] = '-I' + str(target)
    argv[argv.index('-S') + 1] = str(target / (REL + 'kernels.hip.cpp'))
    argv[argv.index('-o') + 1] = str(prep / 'candidate.s')
    with (prep / 'assembly-argv.json').open('x') as stream:
        json.dump(argv, stream, indent=2)
        stream.write('\n')
    report = dict(schema='synapse-lie.q2-hc-rms-owner-ordinary-source.v1',
        official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        variants={'hc-rms-owner-ordinary': dict(source=str(target.relative_to(ROOT)),
            files=files, parent_manifest=str(parent_path.relative_to(ROOT)),
            parent_manifest_sha256=sha(parent_path),
            measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
            measured_parent_sha256=sha(ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'),
            component_qualification=str(qualification_path.relative_to(ROOT)),
            component_qualification_sha256=sha(qualification_path),
            qualified_include=str(include_path.relative_to(ROOT)),
            qualified_include_sha256=sha(include_path),
            patch=str(patch_path.relative_to(ROOT)), patch_sha256=sha(patch_path),
            generator='tools/prepare-q2-hc-rms-owner-ordinary.py',
            generator_sha256=sha(Path(__file__)),
            selection='Existing valid HcCombineF32Half, n>=96 only; MoE/scalar/decode unchanged',
            changed_parent_files=changed_files, new_source_files=[REL + 'q2_hc_rms_owner_ordinary.inc'],
            extra_device_or_persistent_bytes=0, executor_lifetimes_changed=False,
            new_host_callbacks_or_streams=0, parent_source_unchanged=True,
            component_rerun=False, controls_rebuilt_or_rerun=False,
            original_model_run=False, independent_quality=False,
            production_adopted=False, numerical_promotion=False,
            new_model_rate=None, goal_met=False)})
    with (ROOT / 'config/q2-hc-rms-owner-ordinary-source.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(source_files=1028, changed_parent_files=1,
        MoE_changed=False, decode_changed=False, original_model_run=False)))


if __name__ == '__main__':
    main()
