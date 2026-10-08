#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a phase-scoped scalar Q2 down provider, without running a model."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Nonunique source anchor: ' + old)
    return source.replace(old, new, 1)


def main():
    parent_path = ROOT / 'config/q2-hc-scalar-isolated-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT / parent['source']
    for name, digest in parent['files'].items():
        if sha(base / name) != digest:
            raise ValueError('Changed parent: ' + name)
    component = ROOT / 'config/q2-decode-down-rows-results.json'
    result = json.loads(component.read_text())
    if result['oracle_checks'] != result['oracle_passes'] or not all(
            x < 0 for x in result['measured']['4']['paired_changes_percent']):
        raise ValueError('Four-row component gate differs')
    binding = json.loads((ROOT / 'config/q2-decode-down-rows-source.json').read_text())
    candidate = ROOT / 'experiments/q2-decode-down-rows.inc'
    if sha(candidate) != binding['files']['experiments/q2-decode-down-rows.inc']:
        raise ValueError('Measured component source changed')
    out = ROOT / '.deps/gufo-q2-decode-down-rows-run'
    manifest = ROOT / 'config/q2-decode-down-rows-model-source.json'
    patch = ROOT / 'experiments/q2-decode-down-rows-model.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Preserve existing provider')
    edits = {
        REL + 'q2_decode_down_rows.inc': candidate.read_text(),
        REL + 'q2_decode_down_rows.hip':
            (ROOT / 'experiments/q2-decode-down-rows-model.hip').read_text()}
    name = REL + 'executor.cpp'
    edits[name] = once((base / name).read_text(),
        '''  if (!tiled) {
    rc = qfn_mmq_moe_vec''',
        '''  if (!tiled && !prefill_phase && n_tokens == 1 && n_rows == 10 &&
      n_used == 1 && w.type == GgmlType::kQ2_K && M == 2560 && K == 768 &&
      config().expert_ff == 640 && E == 512) {
    rc = Q2DecodeDownRows4(w.data, x, ids, out, stream_);
  } else if (!tiled) {
    rc = qfn_mmq_moe_vec''')
    name = REL + 'kernels.hpp'
    edits[name] = once((base / name).read_text(),
        '// Original scalar F16 up projection',
        '''// Original Q2_K/Q8_1 scalar down, fixed2560/640/768 and ten slots.
int Q2DecodeDownRows4(const void* weights, const float* x, const int32_t* ids,
                      float* out, hipStream_t stream);
// Original scalar F16 up projection''')
    name = 'src/models/qwen38_flash_next/CMakeLists.txt'
    s = once((base / name).read_text(),
        '    ${QFN_ROCM_DIR}/hc_scalar_up_mix.hip\n',
        '    ${QFN_ROCM_DIR}/hc_scalar_up_mix.hip\n    ${QFN_ROCM_DIR}/q2_decode_down_rows.hip\n')
    edits[name] = once(s,
        '  set_source_files_properties(${QFN_ROCM_DIR}/w8a8_wave64.hip\n',
        '''  # Match the measured MMQ component flags only for this new file.
  set_source_files_properties(${QFN_ROCM_DIR}/q2_decode_down_rows.hip
    PROPERTIES LANGUAGE HIP COMPILE_OPTIONS "-std=gnu++17;-fPIC;-DGGML_HIP_NO_VMM;-Wno-unused-value")
  set_source_files_properties(${QFN_ROCM_DIR}/w8a8_wave64.hip
''')
    shutil.copytree(base, out)
    patches = []
    for name, content in sorted(edits.items()):
        old = (base / name).read_text() if (base / name).exists() else ''
        (out / name).write_text(content)
        patches.append(''.join(difflib.unified_diff(old.splitlines(True), content.splitlines(True),
            fromfile='a/' + name if old else '/dev/null', tofile='b/' + name)))
    patch.write_text(''.join(patches))
    files = {name: sha(out / name) for name in sorted(set(parent['files']) | set(edits))}
    report = {'schema': 'synapse-lie.q2-decode-down-rows-model-source.v1',
        'source': str(out.relative_to(ROOT)), 'files': files,
        'official_gufo_pin': parent['official_gufo_pin'],
        'parent_manifest': str(parent_path.relative_to(ROOT)),
        'parent_manifest_sha256': sha(parent_path), 'changed_files': sorted(edits),
        'component_result_sha256': sha(component),
        'candidate_include_sha256': sha(candidate),
        'dispatch': 'Non-prefill one-token vector Q2_K down:2560rows,640live/768stored,ten slots,512 experts.',
        'common_kernel_source_unchanged': files[REL+'kernels.hip.cpp'] == parent['files'][REL+'kernels.hip.cpp'],
        'mmq_sources_unchanged': all(files[n] == h for n, h in parent['files'].items() if '/mmq/' in n),
        'new_precision_boundary': False, 'new_persistent_buffers': 0,
        'input_pool_bytes': 11520, 'same_original_pool_reservation': True,
        'component_is_bit_exact': False, 'original_model_quality_qualified': False,
        'common_build_type': 'RelWithDebInfo', 'runtime_qualified': False,
        'generator_sha256': sha(Path(__file__)),
        'patch': str(patch.relative_to(ROOT)), 'patch_sha256': sha(patch)}
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'files': len(files), 'changes': sorted(edits)}))


if __name__ == '__main__':
    main()
