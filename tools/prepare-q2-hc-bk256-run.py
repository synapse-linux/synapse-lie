#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare immutable runtime sources from retained HC ports and a library control."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KERNELS = 'src/models/qwen38_flash_next/kernels/rocm/'
FORMAT = '/opt/rocm/llvm/bin/clang-format'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def fragment(text, begin, end):
    first = text.index(begin)
    last = text.index(end, first)+len(end)
    return text[first:last]


def format_text(text, filename):
    return subprocess.check_output([FORMAT, '--style=file', '--assume-filename='+str(filename)],
                                   input=text.encode()).decode()


def tokens(text):
    return re.sub(r'//[^\n]*|/\*.*?\*/|\s+', '', text, flags=re.S)


def main():
    manifest_path = ROOT/'config/q2-hc-bk256-run-source.json'
    if manifest_path.exists():
        raise ValueError('Refusing to overwrite runtime source receipt')
    variants = {}
    for key, parent_name in (('hc-bk256-initial', 'q2-hc-down-bk256-source.json'),
                             ('hc-bk256-bounded', 'q2-hc-down-bk256-bounded-source.json')):
        parent_path = ROOT/'config'/parent_name
        parent = json.loads(parent_path.read_text())
        base = ROOT/parent['candidate']
        if inventory(base) != parent['files']:
            raise ValueError('Retained draft port changed')
        candidate = ROOT/('.deps/gufo-q2-'+key+'-run')
        if candidate.exists():
            raise ValueError('Runtime source exists')
        shutil.copytree(base, candidate)
        hpp = candidate/(KERNELS+'kernels.hpp')
        text = hpp.read_text()
        before = fragment(text, 'bool HcDownBk256F16Gemm(', 'hipStream_t stream);')
        after = fragment(format_text(text, hpp), 'bool HcDownBk256F16Gemm(', 'hipStream_t stream);')
        hpp.write_text(text.replace(before, after, 1))
        blas = candidate/(KERNELS+'blaslt.cpp')
        text = blas.read_text()
        begin, end = '  // Isolated candidate replaces only', '  // Library edge tiles change the accumulation order'
        before = fragment(text, begin, end)
        after = fragment(format_text(text, blas), begin, end)
        blas.write_text(text.replace(before, after, 1))
        include = candidate/(KERNELS+'q2_hc_down_bk256.inc')
        text = include.read_text()
        prefix, body = text.split('namespace {', 1)
        include.write_text(prefix+format_text('namespace {'+body, candidate/(KERNELS+'kernels.hip.cpp')))
        files = inventory(candidate)
        changed = [name for name, digest in files.items() if parent['files'].get(name) != digest]
        for name in changed:
            if tokens((base/name).read_text()) != tokens((candidate/name).read_text()):
                raise ValueError('Formatting changed source tokens: '+name)
        patch_path = ROOT/'experiments'/('q2-'+key+'-run.patch')
        patch = '// SPDX-License-Identifier: MIT\n'
        for name in changed:
            patch += ''.join(difflib.unified_diff((base/name).read_text().splitlines(keepends=True),
                (candidate/name).read_text().splitlines(keepends=True), fromfile='a/'+name, tofile='b/'+name))
        with patch_path.open('x') as stream:
            stream.write(patch)
        variants[key] = dict(source=str(candidate.relative_to(ROOT)), files=files,
            parent_manifest='config/'+parent_name, parent_manifest_sha256=sha(parent_path),
            changed_files=changed, source_tokens_exact=True, patch=str(patch_path.relative_to(ROOT)),
            patch_sha256=sha(patch_path), unroll=16 if key.endswith('initial') else 2)
    fixed_manifest = ROOT/'config/q2-reaudit-composition-source.json'
    fixed = json.loads(fixed_manifest.read_text())['variants']['reaudit-q8-row']
    base = ROOT/fixed['source']
    if inventory(base) != fixed['files']:
        raise ValueError('Measured library control changed')
    license_text = (ROOT/'third_party/gufo/LICENSE').read_text()
    controls = {}
    for suffix in ('hpp', 'cpp'):
        original = base/(KERNELS+'blaslt.'+suffix)
        text = re.sub(r'\bBlasLt\b', 'HcBlasLtControl', original.read_text())
        if suffix == 'hpp':
            text = text.replace('GUFO_MODELS_QWEN38_FLASH_NEXT_KERNELS_ROCM_BLASLT_HPP_', 'LIE_Q2_HC_BLASLT_CONTROL_HPP_')
        else:
            text = text.replace(KERNELS+'blaslt.hpp', 'experiments/q2_hc_blaslt_control.hpp')
        path = ROOT/'experiments'/('q2_hc_blaslt_control.'+suffix)
        header = '// SPDX-License-Identifier: MIT\n/*\n'+license_text.rstrip()+'\n*/\n'
        header += '// Test-only original library control from this workstream\'s measured Gufo provider.\n'
        with path.open('x') as stream:
            stream.write(header+text)
        controls[str(path.relative_to(ROOT))] = dict(sha256=sha(path),
            origin=KERNELS+'blaslt.'+suffix, origin_sha256=sha(original),
            changes='Type/include guard renamed; original library dispatch, descriptors and7526 unchanged')
    report = dict(schema='synapse-lie.q2-hc-bk256-run-source.v1', variants=variants,
        control_parent=fixed['source'], control_parent_manifest='config/'+fixed_manifest.name,
        control_parent_manifest_sha256=sha(fixed_manifest), control_files=controls,
        arithmetic_source_changed=False, original_drafts_preserved=True, gpu_run=False,
        model_forward=False, performance_qualification=False, numerical_qualification=False)
    with manifest_path.open('x') as stream:
        stream.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(variants={k:len(v['files']) for k,v in variants.items()},
        formatted_tokens_exact=True, control_files=len(controls), gpu_run=False)))


if __name__ == '__main__':
    main()
