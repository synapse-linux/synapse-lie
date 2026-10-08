#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate the GPU-qualified scalar HC kernel into a private provider copy."""

import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected unique source anchor: ' + old)
    return text.replace(old, new, 1)


def main():
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    base = ROOT / parent['source']
    for name, digest in parent['files'].items():
        if sha(base / name) != digest:
            raise ValueError('Retained parent changed: ' + name)
    component_path = ROOT / 'config/q2-hc-scalar-up-mix-results.json'
    component = json.loads(component_path.read_text())
    if not (component['eligible_for_original_model_trial'] and
            component['exact_pairs'] == 64 and component['independent_oracle_checks'] == 50):
        raise ValueError('Component is not qualified')
    source_binding = json.loads((ROOT / 'config/q2-hc-scalar-up-mix-source.json').read_text())
    kernel = ROOT / 'experiments/q2-hc-scalar-up-mix.inc'
    if sha(kernel) != source_binding['bindings'][str(kernel.relative_to(ROOT))]:
        raise ValueError('Qualified numerical kernel changed')
    out = ROOT / '.deps/gufo-q2-hc-scalar-up-mix-run'
    manifest = ROOT / 'config/q2-hc-scalar-model-source.json'
    patch = ROOT / 'experiments/q2-hc-scalar-model.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Preserve existing model integration')
    edits = {}
    executor = (base / REL / 'executor.cpp').read_text()
    executor = once(executor, '  const auto deferred = deferred_norm_;', '''  const bool fused_scalar_projection =
      !xn_half_ && n_tokens == 1 && !MatrixRows(n_tokens) && c.hc_count == 4 &&
      c.hidden_size == 2560 && c.hc_low_rank == 320 &&
      m.down.type == GgmlType::kF16 && m.down.rows == c.hc_low_rank &&
      m.down.cols == c.HcDim() && m.up.type == GgmlType::kF16 &&
      m.up.rows == c.HcDim() && m.up.cols == c.hc_low_rank &&
      (inject == nullptr || m.inject.empty() ||
       m.inject.type == GgmlType::kF32);
  const auto deferred = deferred_norm_;''')
    executor = once(executor,
        '    } else if (!Dense(m.up, s_.lo, s_.hc_gate, n_tokens, error_msg)) {',
        '''    } else if (!fused_scalar_projection &&
               !Dense(m.up, s_.lo, s_.hc_gate, n_tokens, error_msg)) {''')
    executor = once(executor, '''  q8t_src_ = nullptr;
  half_src_ = nullptr;
  if (xn_half_) {
    if (fused_projection) {''', '''  q8t_src_ = nullptr;
  half_src_ = nullptr;
  if (fused_scalar_projection) {
    // Preserve the scalar F32 gate/mix and ten-slice injection arithmetic.
    // The gate plane is dead; downstream input-cache identities stay invalid.
    HcScalarUpMix(static_cast<const __half*>(m.up.data), s_.lo, xn,
                  fused_inject ? m.inject.f32() : nullptr, mixed, inject,
                  stream_, nullptr);
  } else if (xn_half_) {
    if (fused_projection) {''')
    edits[REL + 'executor.cpp'] = executor
    header = (base / REL / 'kernels.hpp').read_text()
    header = once(header, 'void HcMixEpilogue(const float* xn,', '''// Original scalar F16 up projection and F32 mix/injection, fixed2560/320/4.
// Caller owns ten partial injection sums per stream and supplies no witness.
void HcScalarUpMix(const __half* w, const float* lo, const float* xn,
                   const float* inject_w, float* mixed, float* inject,
                   hipStream_t stream, float* gate_witness);
void HcMixEpilogue(const float* xn,''')
    edits[REL + 'kernels.hpp'] = header
    source = (base / REL / 'kernels.hip.cpp').read_text()
    source = once(source, '}  // namespace\n\nvoid EmbedTokens(',
                  '}  // namespace\n\n#include "q2_hc_scalar_up_mix.inc"\n\nvoid EmbedTokens(')
    edits[REL + 'kernels.hip.cpp'] = source
    edits[REL + 'q2_hc_scalar_up_mix.inc'] = kernel.read_text()
    shutil.copytree(base, out)
    patches = []
    for name in sorted(edits):
        content = edits[name]
        previous = (base / name).read_text() if (base / name).exists() else ''
        (out / name).write_text(content)
        patches.append(''.join(difflib.unified_diff(
            previous.splitlines(True), content.splitlines(True),
            fromfile='a/' + name if previous else '/dev/null', tofile='b/' + name)))
    patch.write_text(''.join(patches))
    files = {name: sha(out / name) for name in sorted(set(parent['files']) | set(edits))}
    changed = sorted(name for name, digest in files.items()
                     if digest != parent['files'].get(name))
    if changed != sorted(edits) or len(files) != 1029:
        raise ValueError('Unexpected integration scope')
    report = {
        'schema': 'synapse-lie.q2-hc-scalar-model-source.v1',
        'official_gufo_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        'source': str(out.relative_to(ROOT)), 'files': files, 'changed_files': changed,
        'parent_manifest': str(parent_path.relative_to(ROOT)),
        'parent_manifest_sha256': sha(parent_path),
        'component_result_sha256': sha(component_path),
        'qualified_include_sha256': sha(kernel),
        'patch': str(patch.relative_to(ROOT)), 'patch_sha256': sha(patch),
        'generator_sha256': sha(Path(__file__)),
        'counting_harness_sha256': sha(ROOT / 'experiments/counting-baseline/q2_model.cpp'),
        'scalar_only': True, 'new_precision_boundary': False,
        'additional_runtime_allocations': 0, 'streams_changed': False,
        'cache_invalidation_preserved': True, 'injection_parts_preserved': True,
        'inherited_parent_task_quality_qualified': False, 'model_run': False,
        'prefill_phase_excluded': True,
    }
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'source_files': len(files), 'changed_files': changed,
                      'numerical_include_exact_to_component': True}))


if __name__ == '__main__':
    main()
