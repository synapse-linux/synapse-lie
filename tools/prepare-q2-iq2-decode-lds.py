#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract the retained scalar IQ2 body and change only codebook placement."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/mmq/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Nonunique source anchor: ' + old)
    return text.replace(old, new, 1)


def main():
    manifest = ROOT / 'config/q2-hc-scalar-isolated-source.json'
    parent = json.loads(manifest.read_text())
    base = ROOT / parent['source']
    inputs = {REL + name: base / (REL + name)
              for name in ('mmvq.hip.cpp', 'vecdotq.hpp')}
    for name, path in inputs.items():
        if sha(path) != parent['files'][name]:
            raise ValueError('Retained source differs: ' + name)
    vec = inputs[REL + 'vecdotq.hpp'].read_text()
    start = vec.index('static __device__ __forceinline__ float vec_dot_iq2_xxs_q8_1(')
    end = vec.index('\n#define VDR_IQ2_XS_Q8_1_MMVQ', start)
    dot = vec[start:end]
    dot = once(dot, 'vec_dot_iq2_xxs_q8_1(', 'Iq2DecodeDotLds(')
    dot = once(dot, 'const int & iqs) {',
               'const int & iqs, const uint2* __restrict__ grid) {')
    dot = once(dot, '((const uint2*)iq2xxs_grid)[aux8[k0/2]]', 'grid[aux8[k0/2]]')
    mmvq = inputs[REL + 'mmvq.hip.cpp'].read_text()
    start = mmvq.index('typedef float (*vec_dot_q_hip_t)')
    end = mmvq.index('// Keep one anchor per expert', start)
    body = mmvq[start:end]
    body = once(body, 'bool gated = false>', 'bool gated = false, bool kGridLds = false>')
    body = once(body, 'void mul_mat_vec_q_moe(', 'void Iq2DecodeGridKernel(')
    body = once(body, '  constexpr int qk =',
                '  static_assert(type == GGML_TYPE_IQ2_XXS && gated && c_rows_per_block == 2);\n'
                '  constexpr int qk =')
    body = once(body, '  const bool is_up =', '''  // All threads stage before any return. Preserve separate gate/up waves.
  __shared__ uint2 grid[kGridLds ? 256 : 1];
  if constexpr (kGridLds) {
    const unsigned tid = threadIdx.y * blockDim.x + threadIdx.x;
    for (unsigned i = tid; i < 256; i += blockDim.x * blockDim.y)
      grid[i] = reinterpret_cast<const uint2*>(iq2xxs_grid)[i];
    __syncthreads();
  }

  const bool is_up =''')
    body = once(body,
                '            tmp[i] += vec_dot_q_hip(vx, &y[kby], row_offsets[i] + kbx, kqs);',
                '''            if constexpr (kGridLds)
                tmp[i] += Iq2DecodeDotLds(vx, &y[kby], row_offsets[i] + kbx, kqs, grid);
            else
                tmp[i] += vec_dot_q_hip(vx, &y[kby], row_offsets[i] + kbx, kqs);''')
    out = ROOT / 'experiments/q2-iq2-decode-lds.inc'
    with out.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n'
                     '// Derived from independently pinned Gufo MMVQ; vendor notices apply.\n'
                     '// Change only IQ2 codebook placement, retaining Q8_1 and arithmetic.\n'
                     + dot + '\n' + body.rstrip() + '\n')
    report = {'schema': 'synapse-lie.q2-iq2-decode-lds-source.v1',
              'official_gufo_pin': parent['official_gufo_pin'],
              'parent_manifest': str(manifest.relative_to(ROOT)),
              'parent_manifest_sha256': sha(manifest),
              'inputs': {str(p.relative_to(ROOT)): sha(p) for p in inputs.values()},
              'candidate': str(out.relative_to(ROOT)), 'candidate_sha256': sha(out),
              'generator_sha256': sha(Path(__file__)),
              'mechanism': 'Stage the existing 256-entry IQ2 codebook once per 64-thread workgroup.',
              'extra_lds_bytes': 2048, 'extra_workgroup_barriers': 1,
              'rows_per_projection': 2, 'gate_up_separate_waves': True,
              'quantization_changed': False, 'prefill_changed': False,
              'model_dispatch_changed': False, 'gpu_run': False}
    with (ROOT / 'config/q2-iq2-decode-lds-source.json').open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
