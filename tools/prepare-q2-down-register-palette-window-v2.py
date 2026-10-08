#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind a fresh r2 host result before freezing or transferring its window helper."""
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    spec=importlib.util.spec_from_file_location('hc',ROOT/'tools/analyze-q2-hc-bk256.py')
    hc=importlib.util.module_from_spec(spec);spec.loader.exec_module(hc)
    path=ROOT/'evidence/q2-down-register-palette-host-r2'
    result,transport=hc.curve.artifact_integrity(path)
    assert result['state']=='CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not result['model_access']
    assert len(result['commands'])==6 and all(c['exit_code']==0 for c in result['commands']) and transport['exit_code']==0
    for name in ('03.log','06.log'):assert '100% tests passed out of 34' in (path/'results'/name).read_text()
    template=ROOT/'tools/q2-down-register-palette-window.py'
    s=template.read_text().replace('-r1','-r2')
    old=hashlib.sha256((ROOT/'evidence/q2-down-register-palette-host-r1/results/result.json').read_bytes()).hexdigest()
    digest=hashlib.sha256((path/'results/result.json').read_bytes()).hexdigest()
    assert s.count(old)==1;s=s.replace(old,digest)
    s=s.replace('Coordinate one new Q2 IQ2 tail16 candidate on .157; no cleanup.',
                'Coordinate a fresh Q2 down register-palette candidate on .157; no cleanup.')
    # The last GPU release preceded the completed r1 CPU cohort. Preserve
    # that cohort's process retirement checks without rerunning its tests or
    # including it among the newly admitted v2 cohorts.
    anchor='        cohorts = []\n'
    assert s.count(anchor)==1
    history='''        historical_path = ROOT/'q2-down-register-palette-host-r1/results/result.json'
        if hashlib.sha256(historical_path.read_bytes()).hexdigest() != HISTORICAL_SHA:
            raise RuntimeError('Historical host receipt changed')
        historical = read(historical_path)
        if (historical['state'] != 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' or
                not historical.get('finished_at') or len(historical['commands']) != 6 or
                any(c['exit_code'] for c in historical['commands'])):
            raise RuntimeError('Historical host closure incomplete')
        identities[historical['pid']] = dict(pid=historical['pid'], start_ticks=None)
        for command in historical['commands']:
            identities[command['pid']] = dict(pid=command['pid'],start_ticks=int(command['start_ticks']))
            groups.add(command['pid'])
'''.replace('HISTORICAL_SHA',repr(old))
    s=s.replace(anchor,history+anchor)
    for name in ('admission','release'):
        s=s.replace('q2-down-register-palette-window-'+name+'.json','q2-down-register-palette-v2-window-'+name+'.json')
    s=s.replace('Fresh host33+33','Fresh host34+34')
    out=ROOT/'tools/q2-down-register-palette-window-v2.py'
    with out.open('x') as f:f.write(s)
    print(json.dumps(dict(host_result_sha256=digest,helper_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),GPU_run=False)))
if __name__=='__main__':main()
