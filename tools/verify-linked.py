#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local compile/link + no-model smoke only. Never launches GPU/model work."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def main():
    if len(sys.argv)!=3 or not re.fullmatch(r'[a-z0-9-]{1,48}',sys.argv[1]):
        raise SystemExit('Usage: tools/verify-linked.py EXCLUSIVE-LABEL PRIVATE-GUFO-BUILD')
    if os.environ.get('SSH_CONNECTION'): raise SystemExit('Remote builds require the coordinated protocol')
    label=sys.argv[1]; gufo=Path(sys.argv[2]).resolve(); out=ROOT/'evidence'/label; out.mkdir()
    build=ROOT/'build'/label; build.mkdir()
    spec=importlib.util.spec_from_file_location('lie_verify',ROOT/'tools/verify.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    before=module.inputs(); (out/'inputs-before.json').write_text(json.dumps(before,indent=2)+'\n')
    result={'state':'RUNNING','started_at':now(),'commands':[],'hardware_inference':False,
            'model_access':False,'gpu_execution':False,'build':str(build),'gufo_build':str(gufo)}
    def save(): (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    env=dict(os.environ,ROCR_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1',LD_BIND_NOW='1')
    for key,directory in [('HOME','home'),('XDG_CACHE_HOME','cache'),('TMPDIR','tmp')]:
        path=out/directory; path.mkdir(); env[key]=str(path)
    def run(argv):
        i=len(result['commands']); entry={'argv':list(map(str,argv)),'started_at':now()}
        with (out/f'{i:02}.log').open('xb') as log:
            p=subprocess.Popen(entry['argv'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            entry['pid']=p.pid; result['commands'].append(entry); save()
            try: code=p.wait(timeout=180)
            except subprocess.TimeoutExpired:
                entry['timeout']=True
                try: os.killpg(p.pid,signal.SIGTERM)
                except ProcessLookupError: pass
                try: code=p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try: os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    code=p.wait()
        entry['exit_code']=code; entry['finished_at']=now(); save()
        if code or entry.get('timeout'): raise RuntimeError(f'command {i} failed')
    save()
    try:
        run(['cmake','-S',ROOT,'-B',build,'-G','Ninja','-DCMAKE_BUILD_TYPE=Debug',
             '-DLIE_GUFO_RUNTIME=ON','-DGUFO_BUILD='+str(gufo),'-DLIE_BUILD_ID='+label])
        run(['cmake','--build',build,'--parallel','1'])
        binary=build/'synapse-lie-server'
        run(['readelf','-d',binary]); run(['ldd',binary]); run([binary,'--help']); run([binary,'--build-info'])
        run(['ctest','--test-dir',build,'--output-on-failure','-V'])
        result['binary_sha256']=sha(binary)
        result['gufo_receipt_sha256']=sha(gufo/'BUILD-RECEIPT.json')
        result['inputs_unchanged']=before==module.inputs()
        if not result['inputs_unchanged']: raise RuntimeError('inputs changed')
        result['state']='HIP_ADAPTER_LINKED_CPU_AND_SYNTHETIC_TESTS_PASS_NO_MODEL_EXECUTION'
    except Exception as ex:
        result['state']='FAILED'; result['error']=repr(ex); raise
    finally:
        result['finished_at']=now(); save()
    print(json.dumps({k:v for k,v in result.items() if k!='commands'},indent=2))
if __name__=='__main__': main()
