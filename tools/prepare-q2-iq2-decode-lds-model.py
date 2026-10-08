#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose the exact IQ2 LDS component with the retained scalar-down provider."""
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
    parent_path = ROOT / 'config/q2-decode-down-rows-model-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT / parent['source']
    for name, digest in parent['files'].items():
        if sha(base / name) != digest:
            raise ValueError('Changed parent: ' + name)
    component = ROOT / 'config/q2-iq2-decode-lds-results.json'
    result = json.loads(component.read_text())
    if (result['exit_code'] != 0 or result['exact_replays'] != 906 or
            result['independent_checks'] != 1359 or result['independent_failures'] or
            result['lds_faster_pairs'] != 4):
        raise ValueError('Measured component gate differs')
    binding = json.loads((ROOT / 'config/q2-iq2-decode-lds-source.json').read_text())
    candidate = ROOT / 'experiments/q2-iq2-decode-lds.inc'
    if sha(candidate) != binding['candidate_sha256']:
        raise ValueError('Measured component source changed')
    out = ROOT / '.deps/gufo-q2-iq2-decode-lds-run'
    manifest = ROOT / 'config/q2-iq2-decode-lds-model-source.json'
    patch = ROOT / 'experiments/q2-iq2-decode-lds-model.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Preserve existing provider')
    edits = {
        REL + 'q2_iq2_decode_lds.inc': candidate.read_text(),
        REL + 'q2_iq2_decode_lds.hip':
            (ROOT / 'experiments/q2-iq2-decode-lds-model.hip').read_text()}
    name = REL + 'executor.cpp'
    anchor = '  if (!MatrixRows(n_tokens) && n_used <= 32 && same_shape &&\n'
    edits[name] = once((base / name).read_text(), anchor,
        '''  if (!prefill_phase && n_tokens == 1 && n_used == 10 && same_shape &&
      a.type == GgmlType::kIQ2_XXS && a.rows == 640 && a.cols == 2560 &&
      a.experts == 512) {
    if (IQ2DecodeLds(a.data, b.data, x, ids, out, stream_) != 0) {
      AssignError(error_msg, "IQ2 scalar LDS gate/up failed");
      return false;
    }
    return true;
  }
''' + anchor)
    name = REL + 'kernels.hpp'
    edits[name] = once((base / name).read_text(),
        '// Original scalar F16 up projection',
        '''// Original IQ2_XXS/Q8_1 scalar gate/up, fixed640/2560 and ten slots.
int IQ2DecodeLds(const void* gate, const void* up, const float* x,
                 const int32_t* ids, float* out, hipStream_t stream);
// Original scalar F16 up projection''')
    name = 'src/models/qwen38_flash_next/CMakeLists.txt'
    s = once((base / name).read_text(),
        '    ${QFN_ROCM_DIR}/q2_decode_down_rows.hip\n',
        '    ${QFN_ROCM_DIR}/q2_decode_down_rows.hip\n    ${QFN_ROCM_DIR}/q2_iq2_decode_lds.hip\n')
    edits[name] = once(s,
        '  set_source_files_properties(${QFN_ROCM_DIR}/w8a8_wave64.hip\n',
        '''  set_source_files_properties(${QFN_ROCM_DIR}/q2_iq2_decode_lds.hip
    PROPERTIES LANGUAGE HIP COMPILE_OPTIONS "-std=gnu++17;-fPIC;-DGGML_HIP_NO_VMM;-Wno-unused-value")
  set_source_files_properties(${QFN_ROCM_DIR}/w8a8_wave64.hip
''')
    shutil.copytree(base, out)
    patches = []
    for name, content in sorted(edits.items()):
        old = (base / name).read_text() if (base / name).exists() else ''
        (out / name).write_text(content)
        patches.append(''.join(difflib.unified_diff(
            old.splitlines(True), content.splitlines(True),
            fromfile='a/' + name if old else '/dev/null', tofile='b/' + name)))
    patch.write_text(''.join(patches))
    files = {name: sha(out / name) for name in sorted(set(parent['files']) | set(edits))}
    report = dict(schema='synapse-lie.q2-iq2-decode-lds-model-source.v1',
        source=str(out.relative_to(ROOT)), files=files,
        official_gufo_pin=parent['official_gufo_pin'],
        parent_manifest=str(parent_path.relative_to(ROOT)),
        parent_manifest_sha256=sha(parent_path), changed_files=sorted(edits),
        component_result_sha256=sha(component), candidate_include_sha256=sha(candidate),
        dispatch='Non-prefill one-token IQ2_XXS gate/up:640rows,2560columns,ten slots,512experts.',
        common_kernel_source_unchanged=files[REL+'kernels.hip.cpp'] == parent['files'][REL+'kernels.hip.cpp'],
        mmq_sources_unchanged=all(files[n] == h for n,h in parent['files'].items() if '/mmq/' in n),
        new_precision_boundary=False, new_persistent_buffers=0, input_pool_bytes=2880,
        same_original_pool_reservation=True, component_is_bit_exact=True,
        original_model_quality_qualified=False, runtime_qualified=False,
        common_build_type='RelWithDebInfo', generator_sha256=sha(Path(__file__)),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch))
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(files=len(files), changes=sorted(edits))))


if __name__ == '__main__':
    main()
