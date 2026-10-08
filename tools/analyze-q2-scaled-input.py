#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit scaled-input numerical rejection and complete component/model timings."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import numpy as np


def module(filename):
    spec = importlib.util.spec_from_file_location(filename, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


shared = module('analyze-q2-shared-overlap.py')
common = module('analyze-q2-hc-input.py')
require = common.require


def component(path):
    root, result, events = common.read(path)
    transport = json.loads((path/'transport.json').read_text())
    require(result['mode'] == 'scaled-input-check' and not result['model_access']
            and transport['source_variant'] == 'scaled-input', 'Wrong component contract')
    require([c['exit_code'] for c in result['commands']] == [0,0,1]
            and result['state'] == 'FAILED' and transport['exit_code'] == 1,
            'Numerical rejection not preserved')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4
            and not result['preflight_kfd'] and not result['postflight_kfd'], 'Unresolved GPU admission')
    text = (root/'03.log').read_text()
    cases = [e for e in events if e['event'] == 'scaled_replay']
    errors = {m[1]:dict(relative_rms=float(m[2]),error_over_peak=float(m[3]))
              for m in re.finditer(r'^scaled (\S+) rrms=(\S+) scaled_max=(\S+)$',text,re.M)}
    expected = {f'n65-m129-tile{t}-shift{s}-{p}' for t in (16,48,64)
                for s in (-12,0,12) for p in ('normal','tiny')}
    require(len(cases) == 18 and {c['label'] for c in cases} == expected == set(errors), 'Missing case')
    for c in cases:
        n = c['label']; match = re.fullmatch(r'n65-m129-tile(\d+)-shift(-?\d+)-(normal|tiny)',n)
        tile, shift, kind = int(match[1]),int(match[2]),match[3]
        ref = root/(f'operator-Q2 routed F16 tokens=65 rows=129 tile={tile} '+
                    ('ordinary' if kind=='normal' else 'tiny')+
                    (f' shift={shift}' if shift else '')+'.f32')
        raw_a,raw_b=ref.read_bytes(),(root/('scaled-'+n+'.f32')).read_bytes()
        a,b=(np.frombuffer(v,dtype='<f4').astype(np.float64) for v in (raw_a,raw_b))
        require(a.size == b.size == c['values'] == 16770 and np.isfinite(a).all()
                and np.isfinite(b).all() and c['packed_values_checked'] == 83200, 'Invalid complete buffer')
        changed=int(np.count_nonzero(np.frombuffer(raw_a,dtype='<u4')!=np.frombuffer(raw_b,dtype='<u4')))
        require(changed==c['changed'], 'Full-output mismatch count changed')
        c.update(errors[n],reference_sha256=hashlib.sha256(raw_a).hexdigest(),
                 candidate_sha256=hashlib.sha256(raw_b).hexdigest(),
                 max_abs_vs_compensated=float(np.abs(b-a).max()),
                 relative_l2_vs_compensated=float(np.linalg.norm(b-a)/max(np.linalg.norm(a),1e-60)))
    failures=sum(c['relative_rms']>0.002 or c['error_over_peak']>0.002 for c in cases)
    require(failures==18 and text.count('NUMERICAL_FAILURE: independent operator tolerance exceeded')==18,
            'Unexpected failed-case inventory')
    timing={}
    replays=[e for e in events if e['event']=='tile_replay']
    require({e['active_experts'] for e in replays}=={512,128,64} and len(replays)==3,'Missing shaped replay')
    old=Path('evidence/q2-down-tiles-micro-r1/results/03.log')
    old_events=[json.loads(l) for l in old.read_text().splitlines() if l.startswith('{"event":')]
    old_hashes={e['active_experts']:e['reference_sha256'] for e in old_events if e['event']=='tile_replay'}
    for active in (512,128,64):
        rows=[e for e in events if e['event']=='tile_microbench' and e['active_experts']==active]
        require(len(rows)==10 and all(e['tile']==48 and e['launches']==8 for e in rows), 'Changed timing scope')
        arms={}
        for candidate,name in ((False,'reference'),(True,'candidate')):
            selected=[e for e in rows if bool(e['position']^(e['rep']&1))==candidate]
            require([e['rep'] for e in selected]==list(range(5)), 'Missing timing repetition')
            arms[name]=common.stats([e['us_per_launch'] for e in selected])
        timing[str(active)]=dict(**arms,time_change_percent=100*(arms['candidate']['median']/arms['reference']['median']-1))
        replay=next(e for e in replays if e['active_experts']==active)
        require(replay['values']==52428800 and not replay['exact']
                and replay['reference_sha256']==old_hashes[active], 'Original shaped control changed')
        samples=[json.loads(l) for l in (root/f'packed-tiles-48-samples-{active}.jsonl').read_text().splitlines()]
        require(len(samples)==1024 and all(math.isfinite(s[k]) for s in samples for k in ('value','reference')), 'Invalid oracle samples')
        err=sum((s['value']-s['reference'])**2 for s in samples)
        norm=sum(s['reference']**2 for s in samples)
        rms=math.sqrt(err/max(norm,1e-30))
        peak=max(abs(s['reference']) for s in samples)
        relative_peak=max(abs(s['value']-s['reference']) for s in samples)/max(peak,1e-20)
        require(math.isclose(rms,replay['relative_rms'],rel_tol=1e-9)
                and math.isclose(relative_peak,replay['error_over_peak'],rel_tol=1e-9), 'Oracle summary differs')
        require(rms<=0.002 and relative_peak<=0.002,'Shaped numerical failure was not counted')
    require([e for e in events if e['event']=='scaled_summary']==[dict(event='scaled_summary',operator_cases=18,
            failures=18,representation_changed=True,packing_timed=True)],'Changed final verdict')
    return dict(path=str(path),binary_sha256=result['binary_sha256'],cases=cases,timing=timing,
                replays=replays,operator_failures=failures,numerical_pass=False,
                original_control_hashes_match=True,command_exits=[0,0,1])


def model(paths):
    roots=[];report={}
    for name,variant,path in zip(('reference','candidate','ud'),('hc-up-chains','scaled-input','qualified'),paths):
        root,row=shared.arm(path,variant);roots.append(root);report[name]=row
    report['replay']=shared.compare(*roots[:2])
    historical=Path('evidence/q2-explore-reference-r1')
    qualified,_,meta=shared.hc.read(historical,'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    report['qualified_reference']=dict(meta=meta,frontiers=shared.hc.frontiers(qualified,roots[1],logits=True,subset=True),
        retained_frontiers=shared.hc.frontiers(qualified,roots[0],logits=True,subset=True),
        changed_token_files=[p.name for p in roots[1].iterdir() if p.suffix in ('.i32','.u32')
                             and p.read_bytes()!=(qualified/p.name).read_bytes()])
    for rows,reference,target in ((report['replay']['frontiers'],roots[0],roots[1]),
                                  (report['qualified_reference']['frontiers'],qualified,roots[1]),
                                  (report['qualified_reference']['retained_frontiers'],qualified,roots[0])):
        for row in rows:
            match=re.fullmatch(r'(.+)-(\d+)-(prefill|last)\.f32',row['name'])
            require(match is not None,'Unexpected frontier history label')
            input_name=match[1]+'-input.i32'
            output_name=match[1]+'-'+match[2]+'-output.u32'
            same_input=(reference/input_name).read_bytes()==(target/input_name).read_bytes()
            same_output=(reference/output_name).read_bytes()==(target/output_name).read_bytes()
            row['matched_history']=same_input and (match[3]=='prefill' or same_output)
    report['limit']='Saved-frontier diagnostic with unchanged limits; qualify KL only on matched histories. Original Q2 reference is historical, not an independent teacher or task-quality suite.'
    report['relative_medians']={key:{metric:report['candidate']['measurements'][metric]['median']/
        report[key]['measurements'][metric]['median'] for metric in ('prefill_tok_s','decode_steps_s')}
        for key in ('reference','ud') if key in report}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component',type=Path)
    parser.add_argument('--models',type=Path,nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.models and len(args.models) not in (2,3):parser.error('Models require reference/candidate and optional UD')
    report=dict(scope='Exploratory activation representation with original weights; numerical rejection retained',
                goal_met=False,promoted=False,component=component(args.component))
    if args.models:report['model']=model(args.models)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(numerical_pass=False,timing=report['component']['timing'],
                         model_relative_medians=report.get('model',{}).get('relative_medians'))))


if __name__=='__main__':main()
