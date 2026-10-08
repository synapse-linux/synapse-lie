#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare paired capacity-safe sparse WMMA variants without a GPU run."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {p.relative_to(path).as_posix(): sha(p)
            for p in sorted(path.rglob('*')) if p.is_file()}


def once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def transform(source):
    marker = 'constexpr std::uint32_t kWmmaMaxMaskWords = 2048;'
    source = once(source, marker,
        '#include "lie_q2_attention_capacity.h"\n'
        'constexpr std::uint32_t kWmmaMaxMaskWords = LIE_Q2_ATTENTION_MASK_WORDS;')
    source = once(source,
        '// Union-mask capacity: one bit per 4-token block, 262,144 tokens of context.',
        '// Sparse mask extent covers the private context headroom; pitch is separate.')
    source = once(source, '__shared__ unsigned union_words[kListCapacity];',
        'constexpr unsigned kUnionCapacity =\n'
        '      kListCapacity > kWmmaMaxMaskWords ? kListCapacity : kWmmaMaxMaskWords;\n'
        '  __shared__ unsigned union_words[kUnionCapacity];')
    source = once(source, 'unsigned local_words[8];',
        'static_assert(kThreads == LIE_Q2_ATTENTION_SCAN_THREADS);\n'
        '    unsigned local_words[LIE_Q2_ATTENTION_WORDS_PER_THREAD];')
    begin = source.index('const unsigned words_per_thread = (word_count + 255) / 256;')
    end = source.index('// First visible block at or after', begin)
    scan = source[begin:end]
    assert scan.count('for (unsigned j = 0; j < 8; ++j)') == 2
    scan = scan.replace('for (unsigned j = 0; j < 8; ++j)',
                        'for (unsigned j = 0; j < LIE_Q2_ATTENTION_WORDS_PER_THREAD; ++j)')
    source = source[:begin] + scan + source[end:]
    return once(source,
        '(mask != nullptr && mask_words > kWmmaMaxMaskWords)',
        '(mask != nullptr &&\n'
        '       !lie_q2_attention_mask_supported(start_pos, n_tokens, mask_words))')


def main():
    manifest = ROOT/'config/q2-curve256-headroom-source.json'
    output = ROOT/'config/q2-attention-capacity-source.json'
    report = json.loads(manifest.read_text())
    header = ROOT/'experiments/q2_attention_capacity.h'
    targets = {key:ROOT/('.deps/gufo-q2-attention-capacity-'+key)
               for key in report['variants']}
    assert not output.exists() and all(not p.exists() for p in targets.values())
    variants = {}
    for key, entry in report['variants'].items():
        parent = ROOT/entry['source']
        assert inventory(parent) == entry['files']
        original = (parent/(REL+'kernels.hip.cpp')).read_text()
        candidate = transform(original)
        target = targets[key]
        shutil.copytree(parent, target)
        (target/(REL+'kernels.hip.cpp')).write_text(candidate)
        (target/(REL+'lie_q2_attention_capacity.h')).write_bytes(header.read_bytes())
        patch = ROOT/('experiments/q2-attention-capacity-'+key+'.patch')
        assert not patch.exists()
        patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),
            candidate.splitlines(True), fromfile='a/'+REL+'kernels.hip.cpp',
            tofile='b/'+REL+'kernels.hip.cpp')) + ''.join(difflib.unified_diff([], 
            header.read_text().splitlines(True), fromfile='/dev/null',
            tofile='b/'+REL+'lie_q2_attention_capacity.h')))
        files = inventory(target)
        changed = sorted(n for n in files if files[n] != entry['files'].get(n))
        assert changed == sorted([REL+'kernels.hip.cpp', REL+'lie_q2_attention_capacity.h'])
        variants[key] = dict(source=target.relative_to(ROOT).as_posix(),files=files,
            parent_source=entry['source'],changed_files=changed,
            patch=patch.relative_to(ROOT).as_posix(),patch_sha256=sha(patch))
    result = dict(schema='synapse-lie.q2-attention-capacity-source.v1',
        source_pin=report['source_pin'],parent_manifest=manifest.relative_to(ROOT).as_posix(),
        parent_manifest_sha256=sha(manifest),variants=variants,
        header=header.relative_to(ROOT).as_posix(),header_sha256=sha(header),
        generator=Path(__file__).relative_to(ROOT).as_posix(),generator_sha256=sha(Path(__file__)),
        maximum_visible_tokens=266240,maximum_visible_words=2080,
        scan_words_per_thread=9,compact_list_limit_unchanged=2052,
        guard_uses_visible_extent=True,mask_pitch_is_stride=True,
        fixed_reference_unchanged=True,arithmetic_sequence_source_unchanged=True,
        GPU_run=False,GPU_admission=False,independent_quality=False,performance_claim=False)
    output.write_text(json.dumps(result,indent=2)+'\n')
    prep = ROOT/'evidence/q2-attention-capacity-preparation'
    prep.mkdir(exist_ok=True)
    argv = json.loads((ROOT/'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv = [v.replace('.deps/gufo-q2-iq2-fixed-bounds-run',
                       targets['q2'].relative_to(ROOT).as_posix()).replace(
                       'evidence/q2-iq2-fixed-bounds-preparation/candidate.s',
                       'evidence/q2-attention-capacity-preparation/candidate.s') for v in argv]
    (prep/'assembly-argv.json').write_text(json.dumps(argv,indent=2)+'\n')
    print(json.dumps(dict(provider_files={k:len(v['files']) for k,v in variants.items()},
                          GPU_run=False,performance_claim=False)))


if __name__ == '__main__':
    main()
