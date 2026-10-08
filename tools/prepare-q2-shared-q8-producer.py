#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reuse the existing raw-HC Q8 epilogue for the immediately following FFN."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected source boundary: ' + before[:100])
    return text.replace(before, after)


def main():
    parent_path = ROOT/'config/q2-iq2-mixed-model-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    files = {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()}
    if files != parent['files']:
        raise ValueError('Fixed-reference mixed provider changed')
    out = ROOT/'.deps/gufo-q2-shared-q8-producer'
    manifest = ROOT/'config/q2-shared-q8-producer-source.json'
    patch = ROOT/'experiments/q2-shared-q8-producer.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite retained experiment')
    names = [PREFIX+n for n in ('kernels.hip.cpp', 'kernels.hpp', 'executor.cpp', 'executor.hpp')]
    original = {n: (base/n).read_text() for n in names}
    changed = dict(original)
    kernel = original[names[0]]
    start = kernel.index('bool HcMixRawF16Gemm(')
    end = kernel.index('\n}\n', start)+3
    entry = kernel[start:end]
    entry = once(entry, 'bool HcMixRawF16Gemm(', 'bool HcMixRawQ8F16Gemm(')
    entry = once(entry, 'float* mixed, __half* mixed_half,',
                       'float* mixed, __half* mixed_half, void* mixed_q8,')
    entry = once(entry, 'xn == nullptr || mixed == nullptr ||',
                       'xn == nullptr || mixed == nullptr || mixed_q8 == nullptr ||')
    entry = once(entry, '4 * hidden, rank, xn, mixed_half, nullptr);',
                       '4 * hidden, rank, xn, mixed_half, mixed_q8);\n'
                       '  if (hipGetLastError() != hipSuccess) return false;')
    entry = once(entry, '  return true;', '  return hipGetLastError() == hipSuccess;')
    changed[names[0]] = kernel[:end]+'\n'+entry+kernel[end:]
    header = original[names[1]]
    decl = header[header.index('bool HcMixRawF16Gemm('):]
    decl = decl[:decl.index(';')+1]
    new_decl = once(decl, 'bool HcMixRawF16Gemm(', 'bool HcMixRawQ8F16Gemm(')
    new_decl = once(new_decl, 'float* mixed, __half* mixed_half,',
                             'float* mixed, __half* mixed_half, void* mixed_q8,')
    changed[names[1]] = once(header, decl, decl+'\n\n'
        '/// Same raw-HC arithmetic; additionally emits the existing tiled Q8\n'
        '/// format from rounded F32 mixed values. Q8 output is required and\n'
        '/// must not overlap other inputs/outputs; launch errors return false.\n'+new_decl)
    ex = original[names[2]]
    ex = once(ex, 'float* mixed, float* inject, std::uint32_t n_tokens,\n'
                  '                     std::string* error_msg) const {',
                  'float* mixed, float* inject, std::uint32_t n_tokens,\n'
                  '                     std::string* error_msg, bool produce_q8) const {')
    anchor = '  } else if (fused_raw_projection) {\n'
    extra = '''  } else if (fused_raw_projection && produce_q8) {
    // The FFN shared gate/up reads these exact mixed rows next. Reuse the
    // existing Q8 epilogue; publish its identity only after both launches pass.
    if (!HcMixRawQ8F16Gemm(m.up.data, reinterpret_cast<const __half*>(s_.hc_gate),
                           xn, fused_inject ? m.inject.f32() : nullptr, mixed,
                           static_cast<__half*>(s_.x_half), s_.x_q8t, inject,
                           n_tokens, c.hidden_size, c.hc_low_rank, stream_)) {
      AssignError(error_msg, "fused raw HC Q8 producer failed");
      return false;
    }
    half_src_ = mixed;
    half_rows_ = n_tokens;
    half_cols_ = c.hidden_size;
    half_bf16_ = false;
    q8t_src_ = mixed;
    q8t_rows_ = n_tokens;
    q8t_cols_ = c.hidden_size;
'''
    ex = once(ex, anchor, extra+anchor)
    ex = once(ex, 'HcMix(l.hc_ffn, s_.res, true, s_.mixed, s_.inject, n, error_msg)',
                  'HcMix(l.hc_ffn, s_.res, true, s_.mixed, s_.inject, n, error_msg, true)')
    changed[names[2]] = ex
    changed[names[3]] = once(original[names[3]],
        'float* inject, std::uint32_t n_tokens,\n             std::string* error_msg) const;',
        'float* inject, std::uint32_t n_tokens,\n'
        '             std::string* error_msg, bool produce_q8 = false) const;')
    shutil.copytree(base, out)
    diffs = []
    for name in names:
        (out/name).write_text(changed[name])
        diffs.append(''.join(difflib.unified_diff(original[name].splitlines(True),
            changed[name].splitlines(True), fromfile='a/'+name, tofile='b/'+name)))
    actual = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    differences = sorted(n for n in files if actual[n] != files[n])
    if actual.keys() != files.keys() or differences != sorted(names):
        raise ValueError('Unexpected source delta')
    patch.write_text(''.join(diffs))
    report = dict(schema='synapse-lie.q2-shared-q8-producer-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=actual,
        parent_manifest_sha256=sha(parent_path), patch_sha256=sha(patch),
        changed_files=differences, unchanged_files=len(files)-len(names),
        mechanism='Enable the existing tiled Q8 epilogue in raw F16 HC, only for the FFN mixer; publish the existing Q8 cache for shared gate/up.',
        arithmetic='No device kernel body change. Same WMMA/F32 HC mix, F16 output, absmax/127 scale, reciprocal and roundf codes as existing Q8 epilogue.',
        lifetime='Same stream and allocated bounded buffers; caches invalidated before rewrite and published after successful launches. Attention, narrow/decode and MTP callers retain the existing default.',
        fixed_reference='config/q2-fixed-prefill-reference.json',
        retained_norm_candidate_composed=False,
        next_gate='Exact complete mixed/F16/tiled-Q8 outputs and shared gate/up/SwiGLU/down cycle at2048, plus zero/ragged/disabled/error boundaries, before the fixed model point.',
        runtime_validated=False, promoted=False, goal_met=False)
    with manifest.open('x') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('candidate','changed_files','unchanged_files')}))


if __name__ == '__main__':
    main()
