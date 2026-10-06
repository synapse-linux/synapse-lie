#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare private HC normalization owners; do not change provider dispatch."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(text, signature):
    assert text.count(signature) == 1
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def main():
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*')
            if p.is_file()} == parent['files']
    files = {'ordinary': REL + 'kernels.hip.cpp',
             'moe': REL + 'q2_down_half_storage.inc'}
    names = {'ordinary': 'HcCombineF32HalfKernel',
             'moe': 'HcCombineMoeHalfDeferredNormKernel'}
    body = '''  float scale[kStreams];
#pragma unroll
  for (std::uint32_t k = 0; k < kStreams; ++k) {
    float total = 0.0F;
    for (std::uint32_t q = 0; q < kThreads / 32; ++q) {
      total += shared[k][q];
    }
    scale[k] = rsqrtf(total / static_cast<float>(hidden) + eps);
  }
'''
    replacement = '''  // The existing barrier publishes every wave partial. Four owners
  // finish the original ordered totals and floating division/rsqrt; keep
  // separate storage so writers cannot race with the original partials.
  __shared__ float published_scale[kStreams];
  if (threadIdx.x < kStreams) {
    const std::uint32_t k = threadIdx.x;
    float total = 0.0F;
    for (std::uint32_t q = 0; q < kThreads / 32; ++q) {
      total += shared[k][q];
    }
    published_scale[k] = rsqrtf(total / static_cast<float>(hidden) + eps);
  }
  __syncthreads();
  float scale[kStreams];
#pragma unroll
  for (std::uint32_t k = 0; k < kStreams; ++k) {
    scale[k] = published_scale[k];
  }
'''
    kernels = {}
    for kind in ('ordinary', 'moe'):
        original = function((base / files[kind]).read_text(),
                            '__global__ void ' + names[kind] + '(')
        assert original.count(body) == 1
        changed = original.replace(body, replacement)
        kernels[kind] = changed.replace(names[kind],
            'HcNormOwnerDraft' + ('Ordinary' if kind == 'ordinary' else 'Moe') + 'Kernel')
    include = ROOT / 'experiments/q2-hc-norm-owner-draft.inc'
    with include.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n'
            '// Private retained-Gufo-derived compiler probes; no selector or runtime result.\n' +
            '\n'.join(kernels.values()))
    prep = ROOT / 'evidence/q2-hc-norm-owner-draft-preparation'
    prep.mkdir()
    probe = prep / 'probe.hip'
    with probe.open('x') as stream:
        stream.write('#include "' + str(base / files['ordinary']) + '"\n'
            'namespace gufo::models::qwen38_flash_next::rocm {\n'
            '#include "' + str(include) + '"\n}\n')
    argv = json.loads((ROOT / 'evidence/q2-hc-inject-reuse-draft-preparation/assembly-v3-argv.json').read_text())
    argv[argv.index('-S') + 1] = str(probe)
    argv[-1] = str(prep / 'candidate.s')
    with (prep / 'assembly-argv.json').open('x') as stream:
        json.dump(argv, stream, indent=2)
        stream.write('\n')
    report = dict(schema='synapse-lie.q2-hc-norm-owner-draft.v1',
        official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'),
        parent_files_exact=len(parent['files']),
        original_files={name: sha(base / name) for name in files.values()},
        include=str(include.relative_to(ROOT)), include_sha256=sha(include),
        compiler_probe=str(probe.relative_to(ROOT)), compiler_probe_sha256=sha(probe),
        generator='tools/prepare-q2-hc-norm-owner-draft.py', generator_sha256=sha(Path(__file__)),
        new_mechanism='Four CTA threads own the four original sequential wave-partial totals and runtime floating divide/rsqrt. Publish in separate16-byte LDS storage after an additional barrier.',
        arithmetic='Original residual/SwiGLU/expert chains, sum-of-squares contraction, WaveSum, eight ordered partial additions, runtime hidden divisor, rsqrt and F32/F16 boundaries unchanged in source; compiler contraction and runtime equality remain unqualified.',
        extra_shared_source_bytes=16, extra_block_barriers=1,
        extra_device_or_persistent_allocations=0, extra_streams=0,
        producer_ownership_unchanged=True,
        risk='Additional barrier and LDS loads can outweigh reduced duplicate scale computation; compiler/source instruction counts are not latency or quality.',
        saved_controls_recompiled=False, parent_source_unchanged=True,
        GPU_run=False, production_provider=False, numerical_acceptance=False,
        performance_measured=False, goal_met=False)
    with (ROOT / 'config/q2-hc-norm-owner-draft.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(parent_files_exact=1027, extra_shared_source_bytes=16,
                         extra_block_barriers=1, GPU_run=False)))


if __name__ == '__main__':
    main()
