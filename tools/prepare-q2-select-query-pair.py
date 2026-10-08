#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Probe two exact selector query rows sharing each loaded key, without model changes."""
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prior',ROOT/'tools/prepare-q2-ssm-row-group.py')
prior=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha,once=prior.sha,prior.once


def main():
    assert sys.argv[1:] in ([], ['--packed'], ['--packed-loop'], ['--bitpack'], ['--interleave'], ['--interleave8'])
    interleave = sys.argv[1:] in (['--interleave'], ['--interleave8'])
    group8 = sys.argv[1:] == ['--interleave8']
    bitpack = sys.argv[1:] == ['--bitpack']
    packed = bool(sys.argv[1:]) and not bitpack and not interleave
    rolled = sys.argv[1:] == ['--packed-loop']
    manifest=ROOT/'config/q2-iq2-fixed-bounds-source.json'
    parent=json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    base=ROOT/parent['source']
    assert prior.inventory(base)==parent['files']
    text=(base/prior.REL).read_text()
    a=text.index('__global__ void SelectScoreKernel(')
    b=text.index('/// Locate a descending histogram rank',a)
    body=text[a:b]
    body=once(body,'SelectScoreKernel','SelectScoreQueryPairKernel')
    body=once(body,'  const auto t0 = blockIdx.x;\n  const auto complete = (*start_pos + first_token + t0 + 1) / ratio;',
        '  const auto first = 2 * blockIdx.x;\n'
        '  if (first >= n_tokens) return;\n'
        '  const auto last = min(first + 1, n_tokens - 1);\n'
        '  const auto last_complete = (*start_pos + first_token + last + 1) / ratio;')
    body=once(body,'  if (t0 >= n_tokens || complete <= budget || b >= complete)',
              '  if (last_complete <= budget || b >= last_complete)')
    body=once(body,'  float total = 0.0F;',
        '  // Reuse the same original F16 key for two complete query reductions.\n'
        '  // Query arithmetic, head order and the exact32-lane sum tree remain.\n'
        '#pragma unroll\n  for (unsigned row = 0; row < 2; ++row) {\n'
        '    const auto t0 = first + row;\n'
        '    const auto complete = (*start_pos + first_token + t0 + 1) / ratio;\n'
        '    if (t0 >= n_tokens || complete <= budget || b >= complete) continue;\n'
        '  float total = 0.0F;')
    body=once(body,'  scores[std::size_t{t0} * max_blocks + b] = total;\n}',
              '  scores[std::size_t{t0} * max_blocks + b] = total;\n  }\n}')
    body+='''
void SelectBlocksQueryPair(const float* q, const __half* blocks, std::uint32_t* mask,
                          float* scores, std::uint32_t n_tokens,
                          const std::uint32_t* start_pos, std::uint32_t first_token,
                          std::uint32_t ratio, std::uint32_t budget,
                          std::uint32_t mask_words, std::uint32_t max_blocks,
                          hipStream_t stream) {
  const dim3 grid((n_tokens + 1) / 2, (max_blocks + kThreads - 1) / kThreads);
  hipLaunchKernelGGL(SelectScoreQueryPairKernel, grid, dim3(kThreads), 0, stream,
                    q, blocks, scores, n_tokens, start_pos, first_token,
                    ratio, budget, max_blocks);
  hipLaunchKernelGGL(SelectMarkKernel, dim3(n_tokens), dim3(kThreads), 0, stream,
                    mask, scores, start_pos, first_token, ratio, budget,
                    mask_words, max_blocks);
}
'''
    if packed:
        body=once(body,'  float key[kSelectDim];','  __half key[kSelectDim];')
        body=once(body,'key[i] = __half2float(blocks[std::size_t{b} * kSelectDim + i]);',
                  'key[i] = blocks[std::size_t{b} * kSelectDim + i];')
        body=once(body,'key[lane + i * 32], dot);','__half2float(key[lane + i * 32]), dot);')
        body=body.replace('SelectScoreQueryPairKernel','SelectScoreQueryPairPackedKernel').replace('SelectBlocksQueryPair','SelectBlocksQueryPairPacked')
    if rolled:
        body=once(body,'#pragma unroll\n  for (unsigned row = 0; row < 2; ++row)', '#pragma unroll 1\n  for (unsigned row = 0; row < 2; ++row)')
        body=body.replace('SelectScoreQueryPairPackedKernel','SelectScoreQueryPairPackedLoopKernel').replace('SelectBlocksQueryPairPacked','SelectBlocksQueryPairPackedLoop')
    if bitpack:
        body=once(body,'  float key[kSelectDim];','  std::uint32_t key[kSelectDim / 2];')
        body=once(body,'for (unsigned i = 0; i < kSelectDim; ++i)\n    key[i] = __half2float(blocks[std::size_t{b} * kSelectDim + i]);',
                  'for (unsigned i = 0; i < kSelectDim / 2; ++i)\n    key[i] = reinterpret_cast<const std::uint32_t*>(blocks)[std::size_t{b} * (kSelectDim / 2) + i];')
        body=once(body,'key[lane + i * 32], dot);',
                  'SelectPairKey(key[(lane + i * 32) / 2], 16 * (lane % 2)), dot);')
        body=once(body,'    const auto t0 = first + row;', '    const auto t0 = min(first + row, n_tokens - 1);')
        body=once(body,'    if (t0 >= n_tokens || complete <= budget || b >= complete) continue;\n','')
        body=once(body,'  scores[std::size_t{t0} * max_blocks + b] = total;',
                  '  if (first + row < n_tokens && complete > budget && b < complete)\n    scores[std::size_t{t0} * max_blocks + b] = total;')
        body=body.replace('SelectScoreQueryPairKernel','SelectScoreQueryPairBitpackKernel').replace('SelectBlocksQueryPair','SelectBlocksQueryPairBitpack')
        body='''// Keep encoded half pairs live; prevent CSE from retaining128 widened keys.
__device__ __forceinline__ float SelectPairKey(std::uint32_t bits, unsigned shift) {
  asm volatile("" : "+v"(bits));
  return __half2float(__ushort_as_half(static_cast<unsigned short>(bits >> shift)));
}
'''+body
    if interleave:
        start=body.index('  // Reuse the same original F16 key')
        stop=body.index('    const auto* query =',start)
        body=body[:start]+'''  float total[2] = {};
#pragma unroll
  for (unsigned h = 0; h < kSelectHeads; ++h) {
#pragma unroll
    for (unsigned row = 0; row < 2; ++row) {
      const auto t0 = min(first + row, n_tokens - 1);
'''+body[stop:]
        body=once(body,'    total += fmaxf(partial[0], 0.0F);',
                  '    total[row] += fmaxf(partial[0], 0.0F);\n    __builtin_amdgcn_sched_barrier(0);')
        body=once(body,'  scores[std::size_t{t0} * max_blocks + b] = total;\n  }\n}',
                  '''  }
#pragma unroll
  for (unsigned row = 0; row < 2; ++row) {
    const auto t0 = first + row;
    const auto complete = (*start_pos + first_token + t0 + 1) / ratio;
    if (t0 < n_tokens && complete > budget && b < complete)
      scores[std::size_t{t0} * max_blocks + b] = total[row];
  }
}''')
        body=body.replace('SelectScoreQueryPairKernel','SelectScoreQueryPairInterleaveKernel').replace('SelectBlocksQueryPair','SelectBlocksQueryPairInterleave')
    if group8:
        body=once(body,'if ((lane + 1) % 16 == 0)','if ((lane + 1) % 8 == 0)')
        body=body.replace('SelectScoreQueryPairInterleaveKernel','SelectScoreQueryPairInterleave8Kernel').replace('SelectBlocksQueryPairInterleave','SelectBlocksQueryPairInterleave8')
    body='// SPDX-License-Identifier: MIT\n// Derived from pinned Gufo exact FP32 selector; private component only.\n'+body
    name='q2-select-query-pair'+('-interleave8' if group8 else '-interleave' if interleave else '-bitpack' if bitpack else '-packed-loop' if rolled else '-packed' if packed else '')
    out=ROOT/('evidence/'+name+'-preparation')
    inc=ROOT/('experiments/'+name+'.inc')
    assert not out.exists() and not inc.exists()
    formatted=subprocess.run(['clang-format','--style=file:'+str(base/'.clang-format')],input=body,text=True,capture_output=True)
    assert formatted.returncode==0,formatted.stderr
    out.mkdir();inc.write_text(formatted.stdout)
    (out/'draft.inc').write_bytes(inc.read_bytes())
    probe=out/'probe.hip.cpp'
    probe.write_text('// SPDX-License-Identifier: MIT\n#include "../../'+parent['source']+'/'+prior.REL+'"\n'
        'namespace gufo::models::qwen38_flash_next::rocm {\n#include "draft.inc"\n}\n')
    argv=json.loads((ROOT/'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S')+1]=str(probe.relative_to(ROOT))
    assembly=out/'candidate.s';argv[argv.index('-o')+1]=str(assembly.relative_to(ROOT))
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out/'assembly.stdout').open('x') as stdout,(out/'assembly.stderr').open('x') as stderr:
        result=subprocess.run(argv,cwd=ROOT,stdout=stdout,stderr=stderr)
    report=dict(argv=argv,started_at=started,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exit_code=result.returncode,draft=str(inc.relative_to(ROOT)),draft_sha256=sha(inc),
        parent_manifest_sha256=sha(manifest),assembly_sha256=sha(assembly) if assembly.exists() else None,
        original_query_FP32=True,original_key_F16=True,original_per_query_arithmetic=True,
        query_rows_per_thread=2,logical_key_load_factor=0.5,packed_F16_register_keys=packed,rolled_query_loop=rolled,bitpacked_keys=bitpack,interleaved_queries=interleave,query_load_group=8 if group8 else 16,topk_changed=False,
        paired_lane_experiment=False,production_selector=False,GPU_run=False,model_speedup=False)
    (out/'assembly-command.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(exit_code=result.returncode,draft=str(inc.relative_to(ROOT)),GPU_run=False)))
    return result.returncode


if __name__=='__main__':
    raise SystemExit(main())
