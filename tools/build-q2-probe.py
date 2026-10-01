#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build only the test driver against an immutable, hash-checked private MMQ archive."""
import datetime,hashlib,json,os,pathlib,re,resource,subprocess,sys
import q2_test_grid
import q2_hip_port as hip
ROOT=pathlib.Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    if len(sys.argv)!=3 or os.environ.get('SSH_CONNECTION') or any(not re.fullmatch('[a-z0-9-]{1,64}',x) for x in sys.argv[1:]):
        raise SystemExit('Usage: build-q2-probe.py NEW-LABEL SEALED-HIP-BUILD-LABEL (editing host only)')
    label,base_label=sys.argv[1:];base=ROOT/'build'/base_label
    for p in (base,ROOT/'build'/label,ROOT/'evidence'/label):
        if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('symlink build path')
    out=ROOT/'evidence'/label;out.mkdir();build=ROOT/'build'/label;build.mkdir()
    inputs=['tools/build-q2-probe.py','tools/q2_test_grid.py','tools/q2_hip_port.py','tools/q2_port.py','tests/q2_operator_probe.cpp','third_party/gufo-source.json']
    r={'state':'RUNNING','started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base_build':base_label,
       'gpu_execution':False,'model_access':False,'runtime_link_allowed':False,'commands':[],
       'inputs_before':{n:sha(ROOT/n) for n in inputs}}
    def save():(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    env={k:v for k,v in os.environ.items() if not k.startswith(('HIP_','HSA_','ROCR_','CUDA_','GUFO_','DS4_')) and k not in ('LD_PRELOAD','LD_LIBRARY_PATH')}
    env.update(HIP_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='-1',CUDA_VISIBLE_DEVICES='-1',LC_ALL='C');resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    def run(argv):
        n=len(r['commands']);row={'argv':list(map(str,argv)),'log':f'{n:02}.log'};r['commands'].append(row);save()
        with (out/row['log']).open('xb') as log:p=subprocess.run(row['argv'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        row['exit_code']=p.returncode;save()
        if p.returncode:raise RuntimeError('test driver build/check failed')
    try:
        old=json.loads((ROOT/'evidence'/base_label/'result.json').read_text())
        if old['state']!='Q2_HIP_BUILD_HOST_REFUSALS_PASS_NOT_GPU_OR_MODEL_QUALIFICATION' or old['runtime_link_allowed'] is not False:
            raise ValueError('private base build identity/refusal mismatch')
        source=base/'source';metadata=source/'LIE-Q2-HIP-SOURCE.json'
        meta=json.loads(hip.read_regular(source,'LIE-Q2-HIP-SOURCE.json'))
        if (meta['runtime_link_allowed'] is not False or meta['upstream_pin']!=hip.q2_port.PIN or
            meta['schema']!='synapse-lie.q2-hip-source.v1' or
            meta['hip_recipe_sha256']!=old['inputs_before']['adapters/gufo-q2/hip-edits.json']):
            raise ValueError('private source receipt mismatch')
        def source_ok():
            return all(hip.q2_port.sha(hip.read_regular(source,n))==v for n,v in meta['files'].items())
        if not source_ok():raise ValueError('private base source drift')
        archive='hip/provider/src/models/qwen38_flash_next/libgufo_qwen38_flash_next_mmq.a'
        if hip.q2_port.sha(hip.read_regular(base,archive))!=old['artifacts'][archive]:
            raise ValueError('private base archive drift')
        r['archive_sha256']=sha(base/archive);r['source_receipt_sha256']=sha(metadata)
        r['grid_source_sha256']=q2_test_grid.generate(source,build/'q2_iq2_grid.inc')
        run(['g++','--version'])
        run(['g++','-std=c++20','-O2','-g','-UNDEBUG','-Wall','-Wextra','-Werror',
             '-D__HIP_PLATFORM_AMD__','-I/opt/rocm/include','-I'+str(source),
             '-I'+str(source/'src/models/qwen38_flash_next/kernels/rocm/mmq'),'-I'+str(build),
             ROOT/'tests/q2_operator_probe.cpp',base/archive,'-L/opt/rocm/lib','-Wl,-rpath,/opt/rocm/lib',
             '-lamdhip64','-ldl','-pthread','-o',build/'q2-operator-probe'])
        run([build/'q2-operator-probe','--cpu-oracle']);run([build/'q2-operator-probe','--list-extended'])
        if r['inputs_before']!={n:sha(ROOT/n) for n in inputs}:
            raise ValueError('test driver input drift')
        if r['archive_sha256']!=sha(base/archive) or not source_ok():
            raise ValueError('base changed during test driver build')
        r['binary_sha256']=sha(build/'q2-operator-probe');r['grid_header_sha256']=sha(build/'q2_iq2_grid.inc')
        r['state']='Q2_TEST_DRIVER_LINK_CPU_ORACLE_PASS_NOT_GPU_QUALIFICATION'
    except BaseException as ex:r['state']='FAILED';r['error']=repr(ex);raise
    finally:r['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
