#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Instrument the measured HTTP providers without changing device arithmetic."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
NGRAM = 'src/models/qwen38_flash_next/ngram.cpp'
EXECUTOR = 'src/models/qwen38_flash_next/kernels/rocm/executor.cpp'


def inventory(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    base = json.loads((ROOT/'config/q2-curve-source.json').read_text())
    outputs = {k:ROOT/('.deps/gufo-q2-curve-ple-'+k) for k in ('q2','ud')}
    manifest = ROOT/'config/q2-curve-profile-source.json'
    if manifest.exists() or any(p.exists() for p in outputs.values()):
        raise ValueError('Refusing to overwrite a source composition')
    spec = importlib.util.spec_from_file_location('ple', ROOT/'tools/prepare-q2-ple.py')
    ple = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ple)
    variants = {}
    for key, out in outputs.items():
        parent = ROOT/base['variants'][key]['source']
        if inventory(parent) != base['variants'][key]['files']:
            raise ValueError('Measured provider changed: '+key)
        shutil.copytree(parent, out)
        (out/NGRAM).write_text(ple.instrument((parent/NGRAM).read_text()))
        text = (parent/EXECUTOR).read_text()
        start = text.index('bool Executor::Forward(Session& session,')
        end = text.index('\nbool Executor::ForwardBody(', start)
        body = text[start:end]
        body = ple.once(body, '  const bool speculative =',
                        '  q2curve::Span measured{mode == ForwardMode::kPrefill, session.position(), tokens.size()};\n  const bool speculative =')
        if not body.endswith('  return true;\n}\n'):
            raise ValueError('Unexpected forward completion')
        body = body[:-len('  return true;\n}\n')]+'  measured.completed = true;\n  return true;\n}\n'
        text = '#include "q2_curve_profile.hpp"\n'+text[:start]+body+text[end:]
        (out/EXECUTOR).write_text(text)
        shutil.copyfile(ROOT/'tests/q2_ple_diag.hpp', out/'q2_ple_diag.hpp')
        shutil.copyfile(ROOT/'experiments/q2_curve_profile.hpp', out/'q2_curve_profile.hpp')
        files = inventory(out)
        changed = [n for n in base['variants'][key]['files'] if files[n] != base['variants'][key]['files'][n]]
        if sorted(changed) != sorted([NGRAM, EXECUTOR]):
            raise ValueError('Unexpected source changes')
        patch = ''
        for name in changed+['q2_ple_diag.hpp','q2_curve_profile.hpp']:
            old = (parent/name).read_text().splitlines(True) if (parent/name).exists() else []
            patch += ''.join(difflib.unified_diff(old, (out/name).read_text().splitlines(True),
                                               fromfile='a/'+name if old else '/dev/null', tofile='b/'+name))
        patch_path = ROOT/('experiments/q2-curve-ple-'+key+'.patch')
        patch_path.write_text(patch)
        variants[key] = dict(source=str(out.relative_to(ROOT)), parent=str(parent.relative_to(ROOT)),
                             files=files, changed_files=changed, added_files=['q2_ple_diag.hpp','q2_curve_profile.hpp'],
                             unchanged_files=len(base['variants'][key]['files'])-len(changed),
                             patch_sha256=hashlib.sha256(patch_path.read_bytes()).hexdigest())
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-curve-profile-source.v1',
        parent_manifest_sha256=hashlib.sha256((ROOT/'config/q2-curve-source.json').read_bytes()).hexdigest(),
        variants=variants, scope='Same HTTP workload; PLE counters and completed Forward host spans; no device-kernel edits. Instrumented rates are not benchmark evidence.',
        gpu_runtime_qualified=False, promoted=False, goal_met=False),indent=2)+'\n')
    print(json.dumps({k:dict(files=len(v['files']),unchanged=v['unchanged_files']) for k,v in variants.items()}))


if __name__ == '__main__':
    main()
