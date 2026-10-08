#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate the already measured HC raw-Q8 body with bounded borrowed scratch."""
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


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected exactly one source anchor: ' + old[:100])
    return text.replace(old, new, 1)


def main():
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    assert inventory(base) == parent['files'] and len(parent['files']) == 1028
    component_path = ROOT / 'config/q2-hc-inject-reuse-component-results.json'
    component = json.loads(component_path.read_text())
    assert component['device_work_safe'] and component['command_exits'] == [0, 0, 1]
    assert not component['numerical_exact'] and len(component['output_records']) == 200
    qualified = ROOT / 'experiments/q2-hc-inject-reuse-draft-v3.inc'
    qualified_manifest = json.loads((ROOT / 'config/q2-hc-inject-reuse-component-source-v2.json').read_text())['variants']['hc-inject-reuse-draft']
    assert sha(qualified) == qualified_manifest['numerical_include_sha256']
    draft = qualified.read_text()
    # Preserve both numerical bodies and their launcher byte for byte.
    raw = draft[:draft.index('__launch_bounds__(512) __global__ void HcInjectReuseLdsDraftDeferredKernel(')]
    begin = draft.index('bool HcInjectReuseLdsDraftRaw(')
    raw += draft[begin:draft.index('bool HcInjectReuseLdsDraftDeferred(', begin)]
    raw = raw.replace('// Numerical compiler probe derived from the retained official Gufo provider.\n// No production selector, executor lifetime change or runtime acceptance.',
        '// Official-Gufo-derived numerical bodies, reused from the saved GPU component.\n// Executor admission and same-stream scratch lifetime are separately guarded.')
    changed = {}
    name = REL + 'kernels.hip.cpp'
    changed[name] = once((base / name).read_text(), '#include "q2_hc_down_bk256.inc"',
        '#include "q2_hc_inject_raw_q8.inc"\n\n#include "q2_hc_down_bk256.inc"')
    name = REL + 'kernels.hpp'
    declaration = '''// Private raw-Q8 experiment. Call only after scratch admission.
bool HcInjectReuseLdsDraftRaw(const void* up, const __half* low_rank,
                            const float* xn, const float* inject_w, float* mixed,
                            __half* mixed_half, void* mixed_q8, float* dots,
                            std::size_t dot_bytes, float* inject,
                            std::uint32_t n_tokens, hipStream_t stream);

'''
    changed[name] = once((base / name).read_text(), 'bool HcMixRawQ8F16Gemm(', declaration + 'bool HcMixRawQ8F16Gemm(')
    name = REL + 'executor.hpp'
    changed[name] = once((base / name).read_text(), '#include "lie_q2_deferred_norm_state.h"',
        '#include "lie_q2_deferred_norm_state.h"\n#include "lie_q2_hc_inject_scratch.h"')
    changed[name] = once(changed[name], '  mutable Scratch s_{};',
        '  mutable Scratch s_{};\n  lie_q2_hc_inject_scratch hc_inject_scratch_{};')
    name = REL + 'executor.cpp'
    changed[name] = once((base / name).read_text(), '  s.down_e = f32(slots * hidden);',
        '''  s.down_e = f32(slots * hidden);
  e->hc_inject_scratch_ = {s.down_e,
      lie_q2_hc_inject_capacity(T, c.num_experts_used, hidden)};''')
    old = '''    if (!HcMixRawQ8F16Gemm(m.up.data,
                           reinterpret_cast<const __half*>(s_.hc_gate), xn,
                           fused_inject ? m.inject.f32() : nullptr, mixed,
                           static_cast<__half*>(s_.x_half), s_.x_q8t, inject,
                           n_tokens, c.hidden_size, c.hc_low_rank, stream_)) {'''
    new = '''    // Combine has queued the last expert-output read on stream_. Both
    // injection launches finish on that stream before Moe can overwrite it.
    // Allocation identity rejects RowScratch views; never publish a borrow.
    const bool reuse_inject = fused_inject && lie_q2_hc_inject_can_borrow(
        &hc_inject_scratch_, s_.down_e, n_tokens, c.hidden_size,
        c.hc_low_rank, c.hc_count,
        moe_pending_ || moe_f32_pending_ || moe_q2_half_pending_);
    const bool mixed_ok = reuse_inject
        ? HcInjectReuseLdsDraftRaw(m.up.data,
              reinterpret_cast<const __half*>(s_.hc_gate), xn, m.inject.f32(),
              mixed, static_cast<__half*>(s_.x_half), s_.x_q8t, s_.down_e,
              hc_inject_scratch_.bytes, inject, n_tokens, stream_)
        : HcMixRawQ8F16Gemm(m.up.data,
              reinterpret_cast<const __half*>(s_.hc_gate), xn,
              fused_inject ? m.inject.f32() : nullptr, mixed,
              static_cast<__half*>(s_.x_half), s_.x_q8t, inject, n_tokens,
              c.hidden_size, c.hc_low_rank, stream_);
    // A failed launch is a terminal error, never a fallback/retry after writes.
    if (!mixed_ok) {'''
    changed[name] = once(changed[name], old, new)
    changed[REL + 'q2_hc_inject_raw_q8.inc'] = raw
    policy = ROOT / 'experiments/q2_hc_inject_scratch.h'
    changed[REL + 'lie_q2_hc_inject_scratch.h'] = policy.read_text()
    target = ROOT / '.deps/gufo-q2-hc-inject-raw-q8-run'
    patch_path = ROOT / 'experiments/q2-hc-inject-raw-q8.patch'
    output = ROOT / 'config/q2-hc-inject-raw-q8-source.json'
    assert not any(p.exists() for p in (target, patch_path, output)), 'Preserve existing experiment'
    shutil.copytree(base, target)
    patches = []
    for name, text in changed.items():
        before = (base / name).read_text() if (base / name).exists() else ''
        (target / name).write_text(text)
        patches += difflib.unified_diff(before.splitlines(True), text.splitlines(True),
            fromfile='a/' + name if before else '/dev/null', tofile='b/' + name)
    patch_path.write_text(''.join(patches))
    files = inventory(target)
    assert len(files) == 1030 and sorted(name for name in files if files[name] != parent['files'].get(name)) == sorted(changed)
    binding = dict(parent_manifest=parent_path, measured_parent=ROOT / 'config/q2-iq2-fixed-bounds-model-results.json',
        component_qualification=component_path, qualified_include=qualified, policy=policy,
        patch=patch_path, generator=Path(__file__))
    variant = dict(source=str(target.relative_to(ROOT)), files=files,
        changed_files=sorted(changed), numerical_include=REL + 'q2_hc_inject_raw_q8.inc',
        numerical_include_sha256=sha(target / (REL + 'q2_hc_inject_raw_q8.inc')),
        selection='Existing raw-Q8 HC route, F32 injection, n2048, H2560/rank320/streams4, full allocation identity, no pending expert output',
        borrowed_device_bytes=2048 * 2560 * 4, extra_device_or_persistent_bytes=0,
        same_stream=True, callbacks_or_streams_changed=False,
        finite_component_differences_preserved=True, component_rerun=False,
        original_model_run=False, model_gain=False, goal_met=False)
    for key, path in binding.items():
        variant[key] = str(path.relative_to(ROOT))
        variant[key + '_sha256'] = sha(path)
    output.write_text(json.dumps(dict(schema='synapse-lie.q2-hc-inject-raw-q8-source.v1',
        official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        variants={'hc-inject-raw-q8': variant}), indent=2) + '\n')
    assert inventory(base) == parent['files']
    prep = ROOT / 'evidence/q2-hc-inject-raw-q8-preparation'
    prep.mkdir(exist_ok=True)
    argv = json.loads((ROOT / 'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv = [v.replace('q2-iq2-fixed-bounds', 'q2-hc-inject-raw-q8') for v in argv]
    (prep / 'assembly-argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=len(changed),
        borrowed_bytes=variant['borrowed_device_bytes'], extra_device_bytes=0)))


if __name__ == '__main__':
    main()
