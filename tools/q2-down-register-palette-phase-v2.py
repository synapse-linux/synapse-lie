#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reject dependent GPU work without a verified, still-active admission."""
import argparse,hashlib,json,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SSH=['ssh','-F','/dev/null','-o','BatchMode=yes','-o','ConnectTimeout=10','paperboy@192.168.5.157']
def identity(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def validate(plan_path,admission_path):
    plan=json.loads(plan_path.read_text())
    receipt=json.loads(admission_path.read_text())
    if receipt['state']!='Q2_DOWN_REGISTER_PALETTE_WINDOW_ADMITTED' or not receipt['gpu_reserved'] or receipt['owner']!='synapse-lie-q2':
        raise ValueError('Expected active Q2 down admission')
    if receipt['previous_release_sha256']!=plan['previous_release_sha256']:
        raise ValueError('Previous release differs')
    if set(receipt['planned_labels'])!={a['label'] for a in plan['arms']+plan['components']}:
        raise ValueError('Admission cohort scope differs')
    if identity(ROOT/plan['window_helper'])!=plan['window_helper_sha256']:
        raise ValueError('Frozen window helper differs')
    for name,digest in {**plan['fixtures'],**plan['manifests']}.items():
        if identity(ROOT/name)!=digest:raise ValueError('Frozen identity differs: '+name)
    return plan,receipt,identity(admission_path)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=('check','component','model'))
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--admission',type=Path,required=True)
    args=p.parse_args()
    correction=json.loads((ROOT/'config/q2-down-register-palette-analysis-correction.json').read_text())
    if identity(args.plan)!=correction['plan_sha256'] or identity(args.admission)!=correction['admission_sha256']:
        raise ValueError('Analysis correction scope differs')
    for name,digest in correction['added_files'].items():
        if identity(ROOT/name)!=digest:raise ValueError('Analysis correction identity differs: '+name)
    plan,receipt,digest=validate(args.plan,args.admission)
    arm=plan['components' if args.phase=='component' else 'arms'][0]
    target=ROOT/'evidence'/arm['label']
    # Any existing transport, including failed connection evidence, remains
    # immutable. A reconnect uses a newly frozen cohort and plan.
    if args.phase!='check' and target.exists():raise ValueError('Cohort exists; preserve it and freeze a fresh cohort')
    if args.phase=='model':
        import importlib.util
        spec=importlib.util.spec_from_file_location('component',ROOT/'tools/analyze-q2-down-register-palette-component-v2.py')
        analyzer=importlib.util.module_from_spec(spec);spec.loader.exec_module(analyzer)
        component=analyzer.analyze(args.plan)
        if not component['device_work_safe']:
            raise ValueError('Component device safety gate incomplete')
    remote='/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'+args.admission.name
    code='''import hashlib,json,pathlib
path=pathlib.Path(REMOTE)
assert hashlib.sha256(path.read_bytes()).hexdigest()==DIGEST
r=json.loads(path.read_text())
assert r['state']=='Q2_DOWN_REGISTER_PALETTE_WINDOW_ADMITTED' and r['gpu_reserved']
last=json.loads(pathlib.Path('/tmp/synapse-lie-ds4-coordination/runs.jsonl').read_text().splitlines()[-1])
assert last['owner']=='synapse-lie-q2' and last['receipt_sha256']==DIGEST
assert last['event']=='window_admit'
assert not list(pathlib.Path('/sys/class/kfd/kfd/proc').glob('*'))
print(json.dumps(dict(admission_active=True,receipt_sha256=DIGEST)))
'''.replace('REMOTE',repr(remote)).replace('DIGEST',repr(digest))
    checked=subprocess.run(SSH+['python3 -c '+shlex.quote(code)],check=False)
    if checked.returncode:return checked.returncode
    if args.phase=='check':return 0
    argv=[sys.executable,str(ROOT/'tools/q2-remote.py'),arm['mode'],arm['label'],
        '--source-variant',arm['variant']]
    if args.phase=='model':argv+=['--rebuild-mmq']
    return subprocess.run(argv,check=False).returncode
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as error:
        print('Refusing GPU phase: '+str(error),file=sys.stderr);sys.exit(2)
