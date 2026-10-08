#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect retained consumer output differences without new GPU execution."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def main():
    path = ROOT/'config/q2-half-fixed-width-component-results.json'
    component = json.loads(path.read_text())
    base = ROOT/'evidence/q2-half-fixed-width-component-r1/results'
    receipt = json.loads((base/'result.json').read_text())
    exact = [sum(e['output_sha256'][k]['parent'] == e['output_sha256'][k]['candidate']
                 for e in component['replay']) for k in range(3)]
    rows = []
    for e in component['replay']:
        for k, role in enumerate(('residual','scales','normalized_half')):
            identities = e['output_sha256'][k]
            if identities['parent'] == identities['candidate']:
                continue
            stem = e['case']+'-r'+str(e['rotation'])+'-o'+str(k)
            names = [stem+'-'+arm+'.bin' for arm in ('parent','candidate')]
            for arm, name in zip(('parent','candidate'), names):
                assert receipt['artifacts'][name]['sha256'] == identities[arm]
                assert (base/name).stat().st_size == receipt['artifacts'][name]['bytes']
            width = 2 if k == 2 else 4
            dtype = np.dtype('<u2' if width == 2 else '<u4')
            floating = np.dtype('<f2' if width == 2 else '<f4')
            count = ((base/names[0]).stat().st_size - 128)//width
            a,b = [np.memmap(base/name,dtype=dtype,mode='r',offset=64,shape=(count,)) for name in names]
            changed = max_ulp = 0
            max_abs = max_relative = 0.0
            for start in range(0,count,262144):
                x,y = a[start:start+262144],b[start:start+262144]
                mask = x != y
                changed += int(np.count_nonzero(mask))
                if not np.any(mask):continue
                u,v = x[mask],y[mask]
                sign = 1 << (8*width-1)
                ordered = lambda z: np.where((z & sign) != 0,
                    sign-(z.astype(np.int64)&(sign-1)), sign+z.astype(np.int64))
                max_ulp = max(max_ulp,int(np.max(np.abs(ordered(u)-ordered(v)))))
                uf,vf = u.view(floating).astype(np.float64),v.view(floating).astype(np.float64)
                assert np.all(np.isfinite(uf)) and np.all(np.isfinite(vf))
                delta = np.abs(uf-vf)
                max_abs = max(max_abs,float(np.max(delta)))
                max_relative = max(max_relative,float(np.max(delta/np.maximum(np.abs(uf),1e-300))))
            rows.append(dict(case=e['case'],rotation=e['rotation'],output=role,
                elements=count,changed=changed,max_ulp=max_ulp,max_abs=max_abs,
                max_relative=max_relative,source_files=names,
                artifact_sha256={name:receipt['artifacts'][name]['sha256'] for name in names}))
    report = dict(schema='synapse-lie.q2-half-fixed-width-differences.v1',
        component_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        exact_pairs=dict(zip(('residual','scales','normalized_half'),exact)),total_pairs=105,
        changed_outputs=rows, summary={role:dict(
            pairs=sum(x['output']==role for x in rows),
            changed_values=sum(x['changed'] for x in rows if x['output']==role),
            max_ulp=max((x['max_ulp'] for x in rows if x['output']==role),default=0),
            max_abs=max((x['max_abs'] for x in rows if x['output']==role),default=0))
            for role in ('residual','scales','normalized_half')},
        limits='Saved-array differences are real. Identical residual narrows the first observed change to normalization; no causal compiler-stage isolation or independent task-quality acceptance is established.',
        gpu_rerun=False,model_inference=False,numerical_acceptance=False,goal_met=False)
    out = ROOT/'config/q2-half-fixed-width-differences.json'
    with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(exact_pairs=report['exact_pairs'],summary=report['summary'],gpu_rerun=False)))

if __name__ == '__main__':
    main()
