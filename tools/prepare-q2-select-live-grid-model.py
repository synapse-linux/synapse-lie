#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate the measured selector grid bound in eager prefill only."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('prior', ROOT/'tools/prepare-q2-iq2-tail16.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, inventory, once = prior.sha, prior.inventory, prior.once


def main():
    parent_path = ROOT/'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT/parent['source']
    assert inventory(base) == parent['files']
    qualification_path = ROOT/'config/q2-select-live-grid-results.json'
    qualification = json.loads(qualification_path.read_text())
    assert qualification['numerical_pass'] and qualification['exact_pairs'] == 62
    assert qualification['oracle_passes'] == 62 and qualification['commands'] == [0, 0, 0]
    target = ROOT/'.deps/gufo-q2-select-live-grid-model'
    manifest = ROOT/'config/q2-select-live-grid-model-source.json'
    patch = ROOT/'experiments/q2-select-live-grid-model.patch'
    prep = ROOT/'evidence/q2-select-live-grid-model-preparation'
    assert not any(p.exists() for p in (target, manifest, patch, prep))
    names = [REL+n for n in ('executor.cpp', 'kernels.hpp', 'kernels.hip.cpp')]
    original = {n: (base/n).read_text() for n in names}
    changed = dict(original)
    changed[names[0]] = once(changed[names[0]],
        'mask_words_, max_blocks, stream_);',
        'mask_words_, max_blocks, stream_,\n'
        '                   prefill_phase ? (start_pos + t0 + n) / c.compress_ratio : 0U);')
    for name, suffix in ((names[1], ';'), (names[2], ' {')):
        text = changed[name]
        a = text.index('void SelectBlocks(')
        b = text.index('void Attention(', a)
        body = text[a:b]
        body = once(body, 'std::uint32_t max_blocks, hipStream_t stream)' + suffix,
            'std::uint32_t max_blocks, hipStream_t stream,\n'
            '                  std::uint32_t live_blocks' + (' = 0' if name == names[1] else '') + ')' + suffix)
        if name == names[2]:
            body = once(body,
                '  // Grids are sized by max_blocks so a captured decode graph replays at any\n'
                '  // position; blocks past the live range return at once.\n'
                '  const dim3 grid(n_tokens, (max_blocks + kThreads - 1) / kThreads);',
                '  // Eager prefill knows the live extent. Captured decode keeps the full\n'
                '  // capacity grid so replay remains valid as the device position advances.\n'
                '  // The allocated score pitch and mask stride never change.\n'
                '  const auto grid_blocks = live_blocks ? std::min(live_blocks, max_blocks) : max_blocks;\n'
                '  const dim3 grid(n_tokens, (grid_blocks + kThreads - 1) / kThreads);')
        else:
            body = '// live_blocks is a host-known eager-prefill bound; zero preserves graph replay.\n'+body
        changed[name] = text[:a]+body+text[b:]
    shutil.copytree(base, target)
    for name, text in changed.items():
        (target/name).write_text(text)
    files = inventory(target)
    assert len(files) == 1028 and set(files) == set(parent['files'])
    assert {n for n in files if files[n] != parent['files'][n]} == set(names)
    with patch.open('x') as stream:
        for name in names:
            stream.write(''.join(difflib.unified_diff(original[name].splitlines(True),
                changed[name].splitlines(True), fromfile='a/'+name, tofile='b/'+name)))
    prep.mkdir()
    argv = json.loads((ROOT/'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv = [x.replace(str(base), str(target)) for x in argv]
    argv[argv.index('-S')+1] = str(target/names[2])
    argv[argv.index('-o')+1] = str(prep/'candidate.s')
    (prep/'assembly-argv.json').write_text(json.dumps(argv, indent=2)+'\n')
    bindings = dict(parent_manifest=str(parent_path.relative_to(ROOT)),
        component_qualification=str(qualification_path.relative_to(ROOT)),
        patch=str(patch.relative_to(ROOT)), generator=str(Path(__file__).relative_to(ROOT)))
    report = dict(schema='synapse-lie.q2-select-live-grid-model-source.v1',
        official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        candidate=str(target.relative_to(ROOT)), files=files,
        **bindings, **{k+'_sha256': sha(ROOT/v) for k, v in bindings.items()},
        changed_parent_files=names, numerical_device_code_changed=False,
        score_pitch_changed=False, mask_stride_changed=False, captured_decode_changed=False,
        extra_device_or_persistent_bytes=0, new_callbacks_or_streams=0,
        parent_source_unchanged=True, controls_rebuilt_or_rerun=False,
        model_inference=False, production_adopted=False)
    with manifest.open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    assert inventory(base) == parent['files']
    print(json.dumps(dict(provider_files=len(files), changed_parent_files=names)))


if __name__ == '__main__':
    main()
