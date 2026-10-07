#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage unchanged FP32 selector queries in per-block LDS, no device execution."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def once(s,a,b):
    if s.count(a)!=1:
        raise ValueError('Nonunique source anchor: '+a)
    return s.replace(a,b,1)


def main():
    manifest=ROOT/'config/q2-decode-down-rows-model-source.json'
    parent=json.loads(manifest.read_text())
    name='src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
    source=ROOT/parent['source']/name
    if sha(source)!=parent['files'][name]:
        raise ValueError('Retained numerical source changed')
    text=source.read_text();start=text.index('__global__ void SelectScoreKernel(')
    end=text.index('\n/// Locate a descending histogram rank',start)
    s=text[start:end].replace('SelectScoreKernel','SelectScoreQueryLdsKernel',1)
    s=once(s,'''  if (t0 >= n_tokens || complete <= budget || b >= complete)
    return;
  float key[kSelectDim];''', '''  // These exits are uniform across the workgroup, before its barrier.
  if (t0 >= n_tokens || complete <= budget || blockIdx.y * blockDim.x >= complete)
    return;
  __shared__ float query_cache[kSelectHeads * kSelectDim];
  for (unsigned i = threadIdx.x; i < kSelectHeads * kSelectDim; i += blockDim.x)
    query_cache[i] = q[std::size_t{t0} * kSelectHeads * kSelectDim + i];
  __syncthreads();
  if (b >= complete)
    return;
  float key[kSelectDim];''')
    s=once(s,'const auto* query = q + (std::size_t{t0} * kSelectHeads + h) * kSelectDim;',
           'const auto* query = query_cache + h * kSelectDim;')
    out=ROOT/'experiments/q2-select-query-lds.inc'
    if out.exists():
        raise ValueError('Preserve existing candidate')
    out.write_text('// SPDX-License-Identifier: MIT\n// Derived from pinned Gufo selector; only FP32 query storage changes.\n'+s)
    report=dict(schema='synapse-lie.q2-select-query-lds-source.v1',
        parent_manifest=str(manifest.relative_to(ROOT)),parent_manifest_sha256=sha(manifest),
        official_gufo_pin=parent['official_gufo_pin'],source=str(source.relative_to(ROOT)),source_sha256=sha(source),
        candidate=str(out.relative_to(ROOT)),candidate_sha256=sha(out),generator_sha256=sha(Path(__file__)),
        arithmetic_order_unchanged=True,query_type='FP32',key_type='F16',
        extra_lds_bytes=2048,extra_workgroup_barriers=1,new_persistent_buffers=0,
        model_dispatch_changed=False,benchmark_input_changed=False,gpu_run=False)
    (ROOT/'config/q2-select-query-lds-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
