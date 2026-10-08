#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare wider-token HC tiles with the measured original-F16 arithmetic."""
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
    return {str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def main():
    parent_path=ROOT/'config/q2-hc-bk256-run-source.json'
    parent=json.loads(parent_path.read_text())
    base=parent['variants']['hc-bk256-bounded']
    source=ROOT/base['source']
    if inventory(source)!=base['files']:
        raise ValueError('Measured bounded parent changed')
    output=ROOT/'config/q2-hc-bn64-source.json'
    if output.exists():
        raise ValueError('Refusing to overwrite source receipt')
    text=(source/NAME).read_text()
    old='HcDownBk256Kernel<64, 32, 16, 16, 256, 1>'
    grid='dim3(5, (batch + 31) / 32)'
    if text.count(old)!=1 or text.count(grid)!=1:
        raise ValueError('Expected one launch and grid anchor')
    variants={}
    for key,wtm,wtn in [('token',16,32),('output',32,16)]:
        variant='hc-bn64-'+key
        candidate=ROOT/('.deps/gufo-q2-'+variant+'-run')
        patch_path=ROOT/('experiments/q2-'+variant+'.patch')
        if candidate.exists() or patch_path.exists():
            raise ValueError('Refusing to overwrite candidate: '+variant)
        shutil.copytree(source,candidate)
        value=text.replace(old,f'HcDownBk256Kernel<64, 64, {wtm}, {wtn}, 128, 1>')
        value=value.replace(grid,'dim3(5, (batch + 63) / 64)')
        (candidate/NAME).write_text(value)
        files=inventory(candidate)
        changed=[n for n,v in files.items() if base['files'].get(n)!=v]
        if changed!=[NAME] or len(files)!=1023:
            raise ValueError('Unexpected source delta')
        patch='// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
            text.splitlines(keepends=True),value.splitlines(keepends=True),
            fromfile='a/'+NAME,tofile='b/'+NAME))
        with patch_path.open('x') as stream:stream.write(patch)
        variants[variant]=dict(source=str(candidate.relative_to(ROOT)),
            parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
            parent_variant='hc-bk256-bounded',files=files,changed_files=changed,
            patch=str(patch_path.relative_to(ROOT)),patch_sha256=sha(patch_path),
            geometry=dict(bm=64,bn=64,wtm=wtm,wtn=wtn,bk=128,buffers=1,lds_bytes=34816,
                          threads=256,diagnostic_grid_blocks=160),k16_unroll=2,
            original_f16_weights=True,original_f16_activations=True,two_fp32_k16_chains=True,
            additional_device_allocations=0,arithmetic_order_changed=False,
            hypothesis='Twice the token tile; four independent FP32 partials per wave, better weight reuse',
            gpu_run=False,model_forward=False,numerical_qualification=False,performance_qualification=False)
    report=dict(schema='synapse-lie.q2-hc-bn64-source.v1',variants=variants,
        control_files=parent['control_files'],control_parent=parent['control_parent'],
        control_parent_manifest=parent['control_parent_manifest'],
        control_parent_manifest_sha256=parent['control_parent_manifest_sha256'],
        measured_parent_report='config/q2-hc-bk256-fixed-model-results.json',
        measured_parent_report_sha256=sha(ROOT/'config/q2-hc-bk256-fixed-model-results.json'),
        fixed_reference_sha256=sha(ROOT/'config/q2-fixed-prefill-reference.json'),
        public_derivation='Same attributed GSQHalo include; two launch parameters and matching grid only',
        gpu_run=False,model_forward=False,goal_met=False)
    with output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:dict(files=len(v['files']),geometry=v['geometry']) for k,v in variants.items()}))


if __name__=='__main__':
    main()
