#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate the exact scalar down/SiLU kernel in a private isolated provider."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Nonunique source anchor: ' + old)
    return s.replace(old, new, 1)

def main():
    parent_path = ROOT / 'config/q2-hc-scalar-isolated-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT / parent['source']
    for name, digest in parent['files'].items():
        if sha(base / name) != digest:
            raise ValueError('Changed parent: ' + name)
    result = json.loads((ROOT / 'config/q2-hc-down-silu-results.json').read_text())
    if not result['eligible_for_original_model_trial']:
        raise ValueError('Component not qualified')
    source = json.loads((ROOT / 'config/q2-hc-down-silu-source.json').read_text())
    candidate = ROOT / 'experiments/q2-hc-down-silu.hip'
    if sha(candidate) != source['files']['experiments/q2-hc-down-silu.hip']:
        raise ValueError('Qualified component source changed')
    out = ROOT / '.deps/gufo-q2-hc-down-silu-run'
    manifest = ROOT / 'config/q2-hc-down-silu-model-source.json'
    patch = ROOT / 'experiments/q2-hc-down-silu-model.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Preserve existing provider')
    edits = {REL + 'hc_down_silu.hip': candidate.read_text()}
    name = REL + 'executor.cpp'
    s = once((base / name).read_text(),
        '''    } else if (!Dense(m.down, s_.xn, s_.lo, n_tokens, error_msg)) {
      return false;
    }
    SiluScale(s_.lo, 1.0F / static_cast<float>(c.hc_count),
              static_cast<std::size_t>(n_tokens) * c.hc_low_rank, stream_);''',
        '''    } else if (fused_scalar_projection) {
      HcDownSilu(static_cast<const __half*>(m.down.data), s_.xn, s_.lo, stream_,
                 nullptr);
    } else if (!Dense(m.down, s_.xn, s_.lo, n_tokens, error_msg)) {
      return false;
    }
    if (!fused_scalar_projection) {
      SiluScale(s_.lo, 1.0F / static_cast<float>(c.hc_count),
                static_cast<std::size_t>(n_tokens) * c.hc_low_rank, stream_);
    }''')
    edits[name] = s
    name = REL + 'kernels.hpp'
    edits[name] = once((base / name).read_text(),
        '// Original scalar F16 up projection',
        '''// Exact scalar down and SiLU, original F16 weights/F32, fixed320/10240.
void HcDownSilu(const __half* w, const float* x, float* out, hipStream_t stream,
                float* raw);
// Original scalar F16 up projection''')
    name = 'src/models/qwen38_flash_next/CMakeLists.txt'
    s = once((base / name).read_text(),
        '    ${QFN_ROCM_DIR}/hc_scalar_up_mix.hip\n',
        '    ${QFN_ROCM_DIR}/hc_scalar_up_mix.hip\n    ${QFN_ROCM_DIR}/hc_down_silu.hip\n')
    edits[name] = once(s,
        '  set_source_files_properties(${QFN_ROCM_DIR}/hc_scalar_up_mix.hip\n',
        '  set_source_files_properties(${QFN_ROCM_DIR}/hc_scalar_up_mix.hip\n    ${QFN_ROCM_DIR}/hc_down_silu.hip\n')
    shutil.copytree(base, out)
    patches = []
    for name, content in sorted(edits.items()):
        old = (base / name).read_text() if (base / name).exists() else ''
        (out / name).write_text(content)
        patches.append(''.join(difflib.unified_diff(old.splitlines(True), content.splitlines(True),
            fromfile='a/' + name if old else '/dev/null', tofile='b/' + name)))
    patch.write_text(''.join(patches))
    files = {name: sha(out / name) for name in sorted(set(parent['files']) | set(edits))}
    report = {'schema': 'synapse-lie.q2-hc-down-silu-model-source.v1',
              'source': str(out.relative_to(ROOT)), 'files': files,
              'official_gufo_pin': parent['official_gufo_pin'],
              'parent_manifest': str(parent_path.relative_to(ROOT)),
              'parent_manifest_sha256': sha(parent_path), 'changed_files': sorted(edits),
              'common_kernel_source_unchanged': files[REL+'kernels.hip.cpp'] == parent['files'][REL+'kernels.hip.cpp'],
              'component_result_sha256': sha(ROOT/'config/q2-hc-down-silu-results.json'),
              'qualified_candidate_sha256': sha(candidate),
              'new_precision_boundary': False, 'new_runtime_allocations': 0,
              'dispatch': 'Same scalar HC eligibility: excludes prefill body, includes scalar logits head.',
              'common_build_type': 'RelWithDebInfo', 'scalar_file_option': '-g0',
              'runtime_qualified': False, 'generator_sha256': sha(Path(__file__)),
              'patch': str(patch.relative_to(ROOT)), 'patch_sha256': sha(patch)}
    manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'files':len(files), 'changes':sorted(edits)}))

if __name__ == '__main__':
    main()
