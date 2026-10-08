#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Expose the existing SSM M/K guard to the compiler; keep other shapes generic."""
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
    parent_path = ROOT / 'config/q2-down-register-scatter-pair-source.json'
    parent = json.loads(parent_path.read_text())['variants']['down-register-scatter']
    assert ssm.inventory(ROOT / parent['source']) == parent['files']
    original = (ROOT / parent['source'] / ssm.REL).read_text()
    prefix = 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,'
    body = ssm.function(original, prefix)
    changed_body = ssm.once(body,
        'float* __restrict__ y, std::size_t batch, std::size_t m, std::size_t k,',
        'float* __restrict__ y, std::size_t batch, std::size_t runtime_m,\n'
        '    std::size_t runtime_k,')
    changed_body = ssm.once(changed_body,
        '    AttentionProjectionOutput attention = {}) {\n',
        '    AttentionProjectionOutput attention = {}) {\n'
        '  // DenseF16SsmGemm already requires this M/K shape before launch.\n'
        '  // Keep batch dynamic, including ragged token tiles and history tails.\n'
        '  const std::size_t m = kSsmConv ? 16384 : runtime_m;\n'
        '  const std::size_t k = kSsmConv ? 2560 : runtime_k;\n')
    changed = ssm.once(original, body, changed_body)
    wrapper = ssm.function(original, 'bool DenseF16SsmGemm(')
    assert wrapper == ssm.function(changed, 'bool DenseF16SsmGemm(')
    assert 'm != 16384 || k != 2560' in wrapper
    assert original.count('DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>') == 1
    destination = ROOT / '.deps/gufo-q2-ssm-fixed-shape-run'
    manifest_path = ROOT / 'config/q2-ssm-fixed-shape-source.json'
    patch_path = ROOT / 'experiments/q2-ssm-fixed-shape.patch'
    assert not any(p.exists() for p in (destination, manifest_path, patch_path))
    shutil.copytree(ROOT / parent['source'], destination)
    (destination / ssm.REL).write_text(changed)
    files = ssm.inventory(destination)
    delta = [name for name, digest in files.items() if parent['files'][name] != digest]
    assert len(files) == 1027 and delta == [ssm.REL]
    with patch_path.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
            original.splitlines(True), changed.splitlines(True),
            fromfile='a/' + ssm.REL, tofile='b/' + ssm.REL)))
    measured = 'config/q2-down-register-scatter-model-results.json'
    control = 'experiments/q2-ssm-row-group-control.inc'
    oracle = 'experiments/q2-ssm-row-group-oracle.inc'
    fixture = 'tests/q2_ssm_row_group.hip'
    variant = dict(source=str(destination.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=ssm.sha(parent_path),
        measured_parent=measured, measured_parent_sha256=ssm.sha(ROOT / measured),
        parent_prefill_tok_s=1580.226725, parent_decode_steps_s=25.10411864,
        patch=str(patch_path.relative_to(ROOT)), patch_sha256=ssm.sha(patch_path),
        control_include=control, control_include_sha256=ssm.sha(ROOT / control),
        oracle=oracle, oracle_sha256=ssm.sha(ROOT / oracle),
        fixture=fixture, fixture_sha256=ssm.sha(ROOT / fixture),
        mechanism='Constant M16384/K2560 only in the existing SSM template specialization; all other dense specializations use their original runtime dimensions.',
        dispatch_unchanged=True, batch_dynamic=True, row_group=1,
        numerical_contract='Original weight decoding, WMMA source/K order, convolution, guards and boundary kernel remain literal. Constant propagation may change compiled arithmetic; GPU replay and independent operators remain required.',
        additional_allocations=0, additional_streams=0, additional_launches=0,
        ssm_row_group_composed=False, current_frozen_campaign_changed=False,
        parent_recompiled=False, gpu_run=False, model_inference=False,
        numerical_acceptance=False, performance_gain=False, goal_met=False)
    with manifest_path.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-ssm-fixed-shape-source.v1',
                       variants={'ssm-fixed-shape': variant}, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=1027, changed_files=delta,
                          wrapper_unchanged=True, row_group=1, gpu_run=False)))


if __name__ == '__main__':
    main()
