#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind exact measured V packing to prefill and existing, ordered expert scratch."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Nonunique source anchor: ' + old)
    return source.replace(old, new, 1)


def main():
    parent_path = ROOT/'config/q2-decode-down-rows-model-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['source']
    for name, digest in parent['files'].items():
        if sha(base/name) != digest:
            raise ValueError('Changed parent: ' + name)
    result_path = ROOT/'config/q2-attention-v-blocks-results.json'
    result = json.loads(result_path.read_text())
    if (not result['all_pairs_exact'] or not result['all_oracles_pass'] or
            any(result['command_exits'].values()) or
            [c['improved_pairs'] for c in result['cases']] != [6, 5] or
            any(c['latency_change_percent'] >= 0 for c in result['cases'])):
        raise ValueError('Measured component gate differs')
    binding = json.loads((ROOT/'config/q2-attention-v-blocks-source.json').read_text())
    for name, digest in binding['files'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('Measured source changed: ' + name)
    out = ROOT/'.deps/gufo-q2-attention-v-blocks-run'
    manifest = ROOT/'config/q2-attention-v-blocks-model-source.json'
    patch = ROOT/'experiments/q2-attention-v-blocks-model.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Preserve existing provider')
    edits = {REL+dst: (ROOT/src).read_text() for src, dst in (
        ('experiments/q2-attention-v-control.inc', 'q2_attention_v_control.inc'),
        ('experiments/q2-attention-v-blocks.inc', 'q2_attention_v_blocks.inc'),
        ('experiments/q2-attention-v-blocks-model.hip', 'q2_attention_v_blocks.hip'),
        ('experiments/q2-attention-v-blocks-contract.h', 'q2_attention_v_blocks_contract.h'))}
    name = REL+'executor.cpp'
    s = once((base/name).read_text(), '#include "iq2_mixed_tiles.h"',
             '#include "iq2_mixed_tiles.h"\n#include "q2_attention_v_blocks_contract.h"')
    anchor = '  if (MatrixRows(n_tokens) &&\n      WmmaCausalAttention('
    route = '''  // The prior layer's Combine enqueues the last down_e read and clears
  // every deferred-MoE flag. Packing, attention and the next MoE writer all
  // use stream_; no host/device synchronization or new allocation is needed.
  // RowScratch may offset down_e, so only its original allocation is eligible.
  if (prefill_phase && n_tokens == 2048) {
    const bool base_allocation =
        std::find(allocations_.begin(), allocations_.end(),
                  static_cast<void*>(s_.down_e)) != allocations_.end();
    const lie_q2_attention_v_blocks_contract contract{
        1, static_cast<unsigned>(last_only),
        static_cast<unsigned>(moe_pending_ || moe_f32_pending_ ||
                              moe_q2_half_pending_),
        static_cast<unsigned>(base_allocation),
        static_cast<unsigned>(mask != nullptr), n_tokens, start_pos,
        options_.max_batch, c.hidden_size, c.num_experts_used, c.num_heads,
        c.num_kv_heads, c.head_dim, c.compress_ratio, mask_words_,
        std::size_t(2048) * 10 * 2560 * sizeof(float)};
    if (lie_q2_attention_v_blocks_bytes(&contract) != 0) {
      const auto status = static_cast<hipError_t>(AttentionVBlocksPrefill(
          s_.q, s_.attn_gate, s.k_cache, s.v_cache, mask, mask_words_, s_.ctx,
          reinterpret_cast<__half*>(s_.down_e), n_tokens, start_pos, stream_));
      if (!Check(status, "prefill value packing and attention", error_msg)) {
        return false;
      }
      return !project_output ||
             Dense(l.attn_out, s_.ctx, out, n_tokens, error_msg);
    }
  }
'''
    edits[name] = once(s, anchor, route+anchor)
    name = REL+'kernels.hpp'
    edits[name] = once((base/name).read_text(), 'bool WmmaCausalAttention(',
        '''// Caller must validate prefill, geometry, base scratch and same-stream
// last-reader ownership with q2_attention_v_blocks_contract.h first.
int AttentionVBlocksPrefill(const float* query, const float* gate,
                            const __half* keys, const __half* values,
                            const std::uint32_t* mask, std::uint32_t mask_words,
                            float* output, __half* temporary,
                            std::uint32_t rows, std::uint32_t start_pos,
                            hipStream_t stream);
bool WmmaCausalAttention(''')
    name = 'src/models/qwen38_flash_next/CMakeLists.txt'
    s = once((base/name).read_text(), '    ${QFN_ROCM_DIR}/q2_decode_down_rows.hip\n',
             '    ${QFN_ROCM_DIR}/q2_decode_down_rows.hip\n    ${QFN_ROCM_DIR}/q2_attention_v_blocks.hip\n')
    edits[name] = once(s,
        '  set_source_files_properties(${QFN_ROCM_DIR}/w8a8_wave64.hip\n',
        '''  set_source_files_properties(${QFN_ROCM_DIR}/q2_attention_v_blocks.hip
    PROPERTIES LANGUAGE HIP COMPILE_OPTIONS "-std=gnu++17;-fPIC;-DGGML_HIP_NO_VMM;-Wno-unused-value")
  set_source_files_properties(${QFN_ROCM_DIR}/w8a8_wave64.hip
''')
    shutil.copytree(base, out)
    patches = []
    for name, content in sorted(edits.items()):
        old = (base/name).read_text() if (base/name).exists() else ''
        (out/name).write_text(content)
        if Path(name).suffix in ('.cpp', '.hpp', '.h', '.hip'):
            subprocess.run(['clang-format', '-i', str(out/name)], check=True)
            content = (out/name).read_text()
        patches.append(''.join(difflib.unified_diff(
            old.splitlines(True), content.splitlines(True),
            fromfile='a/'+name if old else '/dev/null', tofile='b/'+name)))
    patch.write_text(''.join(patches))
    files = {name: sha(out/name) for name in sorted(set(parent['files']) | set(edits))}
    report = dict(schema='synapse-lie.q2-attention-v-blocks-model-source.v1',
        source=str(out.relative_to(ROOT)), files=files,
        official_gufo_pin=parent['official_gufo_pin'],
        parent_manifest=str(parent_path.relative_to(ROOT)),
        parent_manifest_sha256=sha(parent_path), changed_files=sorted(edits),
        component_result_sha256=sha(result_path),
        dispatch='Prefill2048, positions28672..129024, original24/2/256/4 attention, original200MiB base down_e, no pending expert consumer or last-only work.',
        common_kernel_source_unchanged=files[REL+'kernels.hip.cpp'] == parent['files'][REL+'kernels.hip.cpp'],
        mmq_sources_unchanged=all(files[n] == h for n,h in parent['files'].items() if '/mmq/' in n),
        new_precision_boundary=False, additional_allocated_bytes=0,
        scratch_available_bytes=2048*10*2560*4,
        maximum_scratch_reuse_bytes=131072*512*2,
        order='Prior Combine read -> V pack -> attention -> output projection -> subsequent MoE overwrite; one existing stream.',
        common_build_type='RelWithDebInfo',
        original_model_quality_qualified=False, runtime_qualified=False,
        generator_sha256=sha(Path(__file__)),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch))
    manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(files=len(files), changed=sorted(edits))))


if __name__ == '__main__':
    main()
