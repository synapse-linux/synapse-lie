#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a local-only SSM K-stage probe; never launch GPU work."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def once(s,a,b):
    if s.count(a)!=1:
        raise ValueError('Nonunique anchor: '+a)
    return s.replace(a,b,1)

def main():
    inc=ROOT/'experiments/q2-ssm-bk4.inc'
    fixture=ROOT/'tests/q2_ssm_bk4.hip'
    out=ROOT/'evidence/q2-ssm-bk4-preparation'
    manifest=ROOT/'config/q2-ssm-bk4-source.json'
    if any(p.exists() for p in (inc,fixture,out,manifest)):
        raise ValueError('Preserve existing probe')
    parent_path=ROOT/'config/q2-hc-scalar-isolated-source.json'
    parent=json.loads(parent_path.read_text());base=ROOT/parent['source']
    for n,h in parent['files'].items():
        if sha(base/n)!=h:
            raise ValueError('Changed retained provider: '+n)
    donor=ROOT/'experiments/q2-ssm-wave-balance.inc'
    source=donor.read_text().replace('DenseSsmWaveBalance','DenseSsmBk4')
    source=once(source,'static_assert(BM == 256 && BN == 128 && BK == 2 && WM == 4 &&',
                       'static_assert(BM == 128 && BN == 128 && BK == 4 && WM == 4 &&')
    source=once(source,'DenseSsmBk4Kernel<256, 128, 2, 4, 2, 1, false, true>',
                       'DenseSsmBk4Kernel<128, 128, 4, 4, 2, 1, false, true>')
    source=once(source,'dim3((n_tokens + 127) / 128, m / 256)',
                       'dim3((n_tokens + 127) / 128, m / 128)')
    source=source.replace('// Same tile, K16 accumulation order, Q8/F16 rounding and convolution.',
        '// BM128/BN128/BK4: preserve K16 order, Q8/F16 rounding and convolution.\n'
        '// K2560 has20 stages instead of40; this doubles row blocks and uses64KiB LDS.')
    test=(ROOT/'tests/q2_ssm_wave_balance.hip').read_text()
    test=test.replace('wave-balance assignment','wider K-stage experiment').replace('q2-ssm-wave-balance.inc','q2-ssm-bk4.inc').replace('DenseSsmWaveBalance','DenseSsmBk4').replace('ssm_wave_balance','ssm_bk4').replace('ssm-wave-balance-','ssm-bk4-')
    test=once(test,'DenseSsmBk4Kernel<256, 128, 2, 4, 2, 1, false,',
                    'DenseSsmBk4Kernel<128, 128, 4, 4, 2, 1, false,')
    for path,value in ((inc,source),(fixture,test)):
        p=subprocess.run(['clang-format','--style=file:'+str(base/'.clang-format')],input=value,text=True,capture_output=True,check=True)
        path.write_text(p.stdout)
    out.mkdir()
    reference=json.loads((ROOT/'evidence/q2-hc-scalar-isolated-preparation/fixture-object-command.json').read_text())['argv']
    args=reference[:reference.index('-c')]
    cmds=[('object',args+['-c',str(fixture),'-o',str(out/'fixture.o')]),
          ('assembly',args+['--offload-device-only','-S',str(fixture),'-o',str(out/'candidate.s')]),
          ('link',['/opt/rocm/llvm/bin/clang++','--hip-link','--offload-arch=gfx1151',str(out/'fixture.o'),'evidence/q2-ssm-wave-balance-preparation/w8a8.o','evidence/q2-ssm-wave-balance-preparation/sha256.o','-o',str(out/'q2_ssm_bk4_check'),'-lcrypto','-Wl,-rpath,/opt/rocm/lib'])]
    rows=[]
    for label,argv in cmds:
        row={'label':label,'argv':argv,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        with (out/(label+'.stdout')).open('x') as o,(out/(label+'.stderr')).open('x') as e:
            p=subprocess.run(argv,cwd=ROOT,stdout=o,stderr=e)
        row.update(exit_code=p.returncode,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat());rows.append(row)
        (out/'commands.json').write_text(json.dumps(rows,indent=2)+'\n');print(label,p.returncode,flush=True)
        if p.returncode:
            raise SystemExit(p.returncode)
    report={'schema':'synapse-lie.q2-ssm-bk4-source.v1',
        'official_gufo_pin':parent['official_gufo_pin'],
        'parent_manifest':str(parent_path.relative_to(ROOT)),'parent_manifest_sha256':sha(parent_path),
        'donor':str(donor.relative_to(ROOT)),'donor_sha256':sha(donor),
        'files':{str(p.relative_to(ROOT)):sha(p) for p in (inc,fixture,Path(__file__),ROOT/'experiments/q2-ssm-resident-oracle.inc')},
        'parent_geometry':[256,128,2,8,1], 'candidate_geometry':[128,128,4,4,2],
        'k32_blocks':80,'parent_stages':40,'candidate_stages':20,
        'parent_row_blocks':64,'candidate_row_blocks':128,
        'candidate_lds_bytes':65536,'same_k16_order':True,
        'new_precision_boundary':False,'prompt_chunk_tokens':2048,
        'risks':['Twice as many output-row blocks and duplicated activation reads.',
                 '64KiB LDS and register occupancy must be checked; fewer stages do not imply a win.'],
        'binary':str((out/'q2_ssm_bk4_check').relative_to(ROOT)),
        'binary_sha256':sha(out/'q2_ssm_bk4_check'),
        'gpu_run':False,'remote_staged':False,'runtime_qualified':False,'model_run':False}
    manifest.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    main()
