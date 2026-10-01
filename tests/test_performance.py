#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Performance accounting and real loopback client fixture; never model evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from test_tools_http import exchange,port
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('checks',root/'tools/serving_checks.py')
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)

def main():
    a,m=port(),port()
    while a==m: m=port()
    with tempfile.TemporaryDirectory(prefix='lie-performance-fixture-') as d:
        with Path(d,'log').open('wb') as log:
            p=subprocess.Popen([sys.argv[1],'--model',':fixture:','--port',str(a),'--management-port',str(m)],stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+5
                while True:
                    assert p.poll() is None
                    try:
                        if exchange(m,'/actuator/health/readiness')[0]==200: break
                    except OSError: pass
                    assert time.monotonic()<deadline
                    time.sleep(.01)
                records=[]
                result=checks.run_performance(a,m,'cpu-test-fixture','cpu-test-fixture-NOT-INFERENCE',records.append,lambda:None,
                    {'repetitions':2,'output_tokens':16,'prompts':[{'label':'fixture','padding_lines':0,'prompt_tokens':4}],'measure_tools':False})
                assert result['state']=='PASS' and result['measured_requests']==16 and result['warmup_requests']==8,result
                for row in result['configurations']:
                    assert row['end_to_end_ms']['n']==2*row['concurrency']
                    assert row['aggregate_output_tps']['n']==2
                    assert row['prompt_tokens']==[4]
                    assert row['first_text_ms'] is not None if row['stream'] else row['first_text_ms'] is None
                samples=[r for r in records if r['event']=='performance_sample']
                groups=[r for r in records if r['event']=='performance_group']
                samples[-1]['status']=500
                try: checks.performance_summary(samples,groups)
                except ValueError: pass
                else: raise AssertionError('failed request averaged as success')
                assert result['final_scheduler']['active']==0
            finally:
                p.terminate();p.wait(timeout=5)
            assert p.returncode==0,Path(d,'log').read_text()
if __name__=='__main__':main()
