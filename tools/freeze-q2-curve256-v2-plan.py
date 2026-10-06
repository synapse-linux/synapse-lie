#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the requested parallel 256K curve after the actual C17 host gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('curve',ROOT/'tools/analyze-q2-curve.py')
curve=importlib.util.module_from_spec(spec);spec.loader.exec_module(curve)
sha,read,require=curve.sha,curve.read,curve.require


def main():
    output=ROOT/'config/q2-curve256-v2-plan.json'
    require(not output.exists(),'Preserve existing plan')
    prior=read(ROOT/'config/q2-curve256-plan.json')
    names=set(prior['fixtures']) | {'tools/prepare-q2-curve256.py','tools/q2_curve256.py',
        'tools/q2-curve256-session.py','tools/q2-curve256-v2-window.py','tools/q2-curve256-v2-phase.py',
        'tools/freeze-q2-curve256-v2-plan.py','tools/q2_native_curve.py','tools/q2-curve-session.py',
        'cmake/curve/CMakeLists.txt','tests/q2_remote_test.py'}
    fixtures={name:sha(ROOT/name) for name in sorted(names)}
    label='q2-curve256-host-r3';path=ROOT/'evidence'/label
    host,transport=curve.artifact_integrity(path)
    require(host['mode']==transport['mode']=='curve256-cpu' and host.get('finished_at') and
        host['state']=='CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
        len(host['commands'])==6 and all(c['exit_code']==0 for c in host['commands']) and
        transport['exit_code']==0,'Actual .157 C17 host gate incomplete')
    counts=[]
    for name in ('03.log','06.log'):
        text=(path/'results'/name).read_text()
        m=re.search(r'100% tests passed[^\n]*?out of ([0-9]+)',text)
        require(m and 'q2-curve256-launch-contract' in text,'Host launch/parser gate missing')
        counts.append(int(m[1]))
    require(counts[0]==counts[1] and counts[0]>0,'Host gate differs')
    manifests={name:sha(ROOT/name) for name in ('config/q2-curve256-source.json',
        'config/q2-curve256-binaries.json','config/q2-native-bench-source.json',
        'config/q2-iq2-fixed-bounds-source.json','config/q2-iq2-fixed-bounds-model-results.json',
        'config/q2-curve-source.json','config/q2-fixed-prefill-reference.json')}
    source=read(ROOT/'config/q2-curve256-source.json')
    with tarfile.open(path/'source.tar.gz') as archive:
        for name,digest in {**fixtures,**manifests}.items():
            require(hashlib.sha256(archive.extractfile(name).read()).hexdigest()==digest,'Host capsule differs: '+name)
        for name,digest in source['core_files'].items():
            require(hashlib.sha256(archive.extractfile('curve-core/'+name).read()).hexdigest()==digest,'Host core differs: '+name)
    previous='config/q2-curve256-window-release.json'
    require(sha(ROOT/previous)=='30872b71a8ef89cad6e7f531522af0faf52f677af2a7afbbdf76c8eb0a5fe5ef','Latest release differs')
    plan=dict(schema='synapse-lie.q2-curve256-plan.v1',fixtures=fixtures,manifests=manifests,
        components=[],arms=[dict(label='q2-curve256-retained-r2',mode='q2-curve256',variant='curve256-q2'),
                             dict(label='q2-curve256-ud-r2',mode='ud-curve256',variant='curve256-ud')],
        host=label,host_result_sha256=sha(path/'results/result.json'),host_test_counts=dict(debug=counts[0],asan_ubsan=counts[1]),
        previous_release=previous,previous_release_sha256=sha(ROOT/previous),
        window_helper='tools/q2-curve256-v2-window.py',window_helper_sha256=sha(ROOT/'tools/q2-curve256-v2-window.py'),
        admission_path='config/q2-curve256-v2-window-admission.json',release_path='config/q2-curve256-v2-window-release.json',
        **{k:prior[k] for k in ('core_closure_sha256','core_cpu_lease','core_identities','core_groups','supplemental_cpu')},
        retired_cpu_cohorts=[dict(label='q2-curve256-host-r1', result_sha256=sha(ROOT/'evidence/q2-curve256-host-r1/results/result.json'))],core_files=source['core_files'],provider_file_counts={k:len(v['files']) for k,v in source['variants'].items()},
        depths=[0,4096,8192,12288,16384,32768,65536,131072,196608,262144],context_capacity=266240,
        prompt_tokens=2048,output_tokens=128,prefill_chunk=2048,cache_ram_mib=16384,warmups=1,repetitions=1,
        workload='Frozen native C synapse-lie-bench http-curve, Gufo prose seed1, AR/C1, MTP/vision/SSD off; original completed executor-call timing and 0.005 depth tolerance.',
        benchmark_comparison='Compare new Q2 and UD under the same capacity and protocol; preserve saved older Q2 curves for historical change assessment with their capacity difference explicit.',
        fixed_point_priority_retained=True,owner_requested_parallel_curve=True,run_controls=True,
        saved_counting_reference_rerun=False,native_client_rebuilt=False,MMQ_rebuilt=False,
        scope='Two new complete native curves through prefix262144 with pp2048/tg128 and capacity266240. '
              'Retained Q2 and pristine UD numerical sources unchanged; native client and matched MMQ archives reused. '
              'C17 private core extends only the capacity ceiling/help. '
              'No fixed counting rerun, Q4 experiment, model conversion, tuning or remote cleanup. '
              'Collect all artifacts, retire and release before numerical/performance analysis.',
        phase_helper='tools/q2-curve256-v2-phase.py',model_inference=False,GPU_admission=False)
    output.write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps(dict(fixtures=len(fixtures),host_test_counts=counts,plan_sha256=sha(output),GPU_admission=False)))


if __name__=='__main__':main()
