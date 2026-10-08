#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare two new HC staging candidates from the measured bounded provider."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
NAME = 'src/models/qwen38_flash_next/kernels/rocm/q2_hc_down_bk256.inc'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def main():
    parent_path = ROOT/'config/q2-hc-bk256-run-source.json'
    parent = json.loads(parent_path.read_text())
    base = parent['variants']['hc-bk256-bounded']
    source = ROOT/base['source']
    if inventory(source) != base['files']:
        raise ValueError('Measured bounded provider changed')
    output = ROOT/'config/q2-hc-bk128-source.json'
    if output.exists():
        raise ValueError('Refusing to overwrite a retained source receipt')
    text = (source/NAME).read_text()
    old = 'HcDownBk256Kernel<64, 32, 16, 16, 256, 1>'
    if text.count(old) != 1:
        raise ValueError('Expected one unchanged launch anchor')
    variants = {}
    for key, buffers in [('single',1),('double',2)]:
        variant = 'hc-bk128-'+key
        candidate = ROOT/('.deps/gufo-q2-'+variant+'-run')
        patch_path = ROOT/('experiments/q2-'+variant+'.patch')
        if candidate.exists() or patch_path.exists():
            raise ValueError('Refusing to overwrite candidate: '+variant)
        shutil.copytree(source,candidate)
        (candidate/NAME).write_text(text.replace(old,
            f'HcDownBk256Kernel<64, 32, 16, 16, 128, {buffers}>'))
        files = inventory(candidate)
        changed = [name for name,value in files.items() if base['files'].get(name)!=value]
        if changed != [NAME] or len(files)!=1023:
            raise ValueError('Unexpected source delta')
        patch = '// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
            text.splitlines(keepends=True),(candidate/NAME).read_text().splitlines(keepends=True),
            fromfile='a/'+NAME,tofile='b/'+NAME))
        with patch_path.open('x') as stream:stream.write(patch)
        variants[variant] = dict(source=str(candidate.relative_to(ROOT)),
            parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
            parent_variant='hc-bk256-bounded',files=files,changed_files=changed,
            patch=str(patch_path.relative_to(ROOT)),patch_sha256=sha(patch_path),
            geometry=dict(bm=64,bn=32,wtm=16,wtn=16,bk=128,buffers=buffers,
                          lds_bytes=96*136*2*buffers,threads=256),
            k16_unroll=2,two_fp32_k16_chains=True,
            original_f16_weights=True,original_f16_activations=True,
            additional_device_allocations=0,arithmetic_source_changed=False,
            hypothesis=('Smaller LDS and per-thread staged loads, more K barriers' if buffers==1 else
                        'Same barrier count as BK256 single; overlap LDS stores and halve per-thread staged loads'),
            gpu_run=False,model_forward=False,numerical_qualification=False,performance_qualification=False)
    report=dict(schema='synapse-lie.q2-hc-bk128-source.v1',variants=variants,
        control_files=parent['control_files'],control_parent=parent['control_parent'],
        control_parent_manifest=parent['control_parent_manifest'],
        control_parent_manifest_sha256=parent['control_parent_manifest_sha256'],
        measured_parent_report='config/q2-hc-bk256-fixed-model-results.json',
        measured_parent_report_sha256=sha(ROOT/'config/q2-hc-bk256-fixed-model-results.json'),
        fixed_reference_sha256=sha(ROOT/'config/q2-fixed-prefill-reference.json'),
        arithmetic_order='Ascending K16, even and odd partial chains unchanged; BK128 divisible by32',
        public_derivation='Same attributed GSQHalo numerical include; no additional upstream import',
        gpu_run=False,model_forward=False,goal_met=False)
    with output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:dict(files=len(v['files']),geometry=v['geometry']) for key,v in variants.items()}))


if __name__=='__main__':
    main()
