#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run one exclusive host-only argmax diagnostic on .157; no GPU/model forward."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'experiments/q2-argmax-cost.cpp'
out = ROOT / 'evidence/q2-argmax-cost-r1'
out.mkdir()
remote = r'''
import datetime,hashlib,json,os,pathlib,subprocess,sys
root=pathlib.Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/q2-argmax-cost-r1')
root.mkdir()
source=root/'probe.cpp';source.write_bytes(sys.stdin.buffer.read())
logits=pathlib.Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/q2-library-norm-model-reference-r1/results/pp2048-1-last.f32')
env=dict(os.environ,LC_ALL='C',HIP_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='-1')
r=dict(scope='Host-only saved-logit diagnostic; no model forward/GPU',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),logits_sha256=hashlib.sha256(logits.read_bytes()).hexdigest(),commands=[])
commands=[['/usr/bin/c++','--version']]
for name,extra in [('timing',[]),('allocations',['-DQ2_TRACK_NEW=1'])]:
 commands += [['/usr/bin/c++','-std=c++20','-O2','-g','-DNDEBUG',*extra,str(source),'-o',str(root/name)],[str(root/name),str(logits)]]
for i,cmd in enumerate(commands):
 p=subprocess.run(cmd,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
 r['commands'].append(dict(argv=cmd,exit_code=p.returncode,output=p.stdout))
 (root/'result.json').write_text(json.dumps(r,indent=2)+'\n')
 if p.returncode:break
r['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(root/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
sys.exit(r['commands'][-1]['exit_code'])
'''
with (out / 'result.json').open('x') as stdout, (out / 'stderr.log').open('x') as stderr:
    p = subprocess.run(['ssh','-F','/dev/null','-o','BatchMode=yes','paperboy@192.168.5.157',
                        'python3 -c ' + shlex.quote(remote)],input=source.read_bytes(),stdout=stdout,stderr=stderr)
(out / 'transport.json').write_text(json.dumps(dict(exit_code=p.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),indent=2)+'\n')
raise SystemExit(p.returncode)
