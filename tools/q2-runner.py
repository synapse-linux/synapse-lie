#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fixed isolated checks. GPU work requires all four existing nonblocking leases."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from q2_process import supervise

ROOT = Path(__file__).resolve().parents[1]
LOCKS = [
    '/home/paperboy/workspace/projects/cachyos/ai/ds4-gufo/qualification/.pipeline.lock',
    '/home/paperboy/.local/state/ds4-kernel-work/20260927T161150Z-qwen-hip-prefill/download-gufo-native/download.lock',
    '/home/paperboy/.local/state/ds4-kernel-work/20260927T161150Z-qwen-hip-prefill/.qualification.lock',
    '/tmp/synapse-lie-ds4-gpu.lock',
]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    mode = sys.argv[1]
    model_mode = mode in ('q2-smoke','q2-bench','q2-profile','ud-base','ud-patched')
    if mode not in ('cpu', 'hip-build', 'operators') and not model_mode:
        raise SystemExit('Unsupported mode')
    result = {'state': 'RUNNING', 'mode': mode, 'started_at': now(),
              'pid': os.getpid(), 'commands': [], 'locks': [], 'model_access': False}
    results = ROOT/'results'; results.mkdir()
    held = []
    model_paths = []
    registered = False
    def clients():
        return sorted(int(p.name) for p in Path('/sys/class/kfd/kfd/proc').glob('*') if p.name.isdecimal())
    def observation(pid=None):
        row={'at':now(),'kfd':clients()}
        for name in ['meminfo']:
            row[name]=Path('/proc',name).read_text()
        row['sensors']={}
        for pattern in ['card*/device/gpu_busy_percent','card*/device/pp_dpm_sclk',
                        'card*/device/hwmon/hwmon*/temp*_input','card*/device/hwmon/hwmon*/power*_average']:
            for path in Path('/sys/class/drm').glob(pattern):
                try: row['sensors'][str(path)]=path.read_text().strip()
                except OSError as ex: row['sensors'][str(path)]=str(ex)
        if pid:
            for name in ['status','io','stat']:
                try: row[name]=Path('/proc',str(pid),name).read_text()
                except OSError as ex: row[name]=str(ex)
        with (results/'telemetry.jsonl').open('a') as stream: stream.write(json.dumps(row)+'\n')
    def device_observers():
        observers=[];denied=0
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                found=[]
                for fd in (proc/'fd').iterdir():
                    try: target=os.readlink(fd)
                    except FileNotFoundError: continue
                    if target=='/dev/kfd' or target.startswith('/dev/dri/') or target.endswith('.gguf'): found.append(target)
                if found: observers.append({'pid':int(proc.name),'comm':(proc/'comm').read_text().strip(),'handles':sorted(set(found))})
            except (PermissionError,FileNotFoundError): denied+=1
        return {'observers':observers,'unreadable_or_retired_processes':denied}
    def register(event):
        row = {'event': event, 'owner': 'synapse-lie-q2', 'label': ROOT.name,
               'pid': os.getpid(), 'start_ticks': Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
               'at': now(), 'mode': mode, 'source_pin': 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
               'model_access': result['model_access'], 'state': result['state']}
        fd = os.open('/tmp/synapse-lie-ds4-coordination/runs.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX);os.write(fd,(json.dumps(row)+'\n').encode());os.fsync(fd)
        finally: os.close(fd)
    def save():
        (results/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    def stat_model(path):
        st=Path(path).stat()
        return {'path':path,'bytes':st.st_size,'device':st.st_dev,'inode':st.st_ino,
                'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns}
    def run(argv, env, limit=1800):
        row = {'argv': argv, 'started_at': now()}; result['commands'].append(row); save()
        logfile = results/f'{len(result["commands"]):02}.log'
        with logfile.open('wb') as log:
            try:
                supervise(argv,cwd=ROOT,env=env,log=log,row=row,timeout=limit,save=save,
                          clients=clients if mode!='cpu' else lambda: (),
                          observe=observation if mode!='cpu' else lambda pid: None)
            finally:
                row['finished_at']=now();save()
        row['finished_at'] = now(); save()
        print(json.dumps(row),flush=True)
        print(logfile.read_text(),flush=True)
        if row['exit_code'] or row.get('timeout'):
            raise RuntimeError('Qualification command failed')
    save()
    try:
        if mode != 'cpu':
            for name in LOCKS:
                before=os.stat(name,follow_symlinks=False)
                fd=os.open(name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
                try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BaseException: os.close(fd);raise
                held.append(fd);after=os.fstat(fd);live=os.stat(name,follow_symlinks=False)
                if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino) or (after.st_dev,after.st_ino)!=(live.st_dev,live.st_ino):
                    raise RuntimeError('Lease identity changed')
                expected=[(52,3232146),(52,3206482),(52,3228451),(55,45067)][len(held)-1]
                if (after.st_dev,after.st_ino)!=expected: raise RuntimeError('Unexpected lease identity')
                result['locks'].append({'path':name,'device':after.st_dev,'inode':after.st_ino})
            result['preflight_kfd']=clients()
            result['meminfo']=Path('/proc/meminfo').read_text()
            result['power']={str(p):p.read_text() for pattern in ['card*/device/gpu_busy_percent','card*/device/power_dpm_force_performance_level','card*/device/pp_dpm_sclk'] for p in Path('/sys/class/drm').glob(pattern)}
            result['visibility_limit']='KFD and readable proc/sysfs only; desktop and denied FD coverage not exclusivity proof'
            result['preflight_observers']=device_observers()
            if result['preflight_kfd']: raise RuntimeError('Foreign KFD client before build/launch')
            if any(handle.endswith('.gguf') for proc in result['preflight_observers']['observers'] for handle in proc['handles']):
                raise RuntimeError('Foreign model handle before build/launch')
            register('start');registered=True
        if model_mode:
            if mode=='q2-profile':
                profiler=shutil.which('rocprofv3')
                if profiler is None and Path('/opt/rocm/bin/rocprofv3').is_file(): profiler='/opt/rocm/bin/rocprofv3'
                if profiler is None: raise RuntimeError('Installed rocprofv3 unavailable; no dependency installation attempted')
                result['profiler']=profiler
            inventory=json.loads((ROOT/'config/models-157.inventory.json').read_text())['files']
            if mode.startswith('q2-'):
                selected=[f for f in inventory if f['path'].endswith('/Qwen3.8-Flash-Next-Q2.gguf')]
            else:
                selected=[f for f in inventory if '/Qwen3.8-Flash-Next-UD-Q4_K_XL-' in f['path']]
            if len(selected)!=(1 if mode.startswith('q2-') else 4): raise RuntimeError('Incomplete model inventory')
            model_paths=[f['path'] for f in selected]
            result['models_before']=[stat_model(p) for p in model_paths]
            for actual,expected in zip(result['models_before'],selected):
                if any(actual[k]!=expected[k] for k in actual): raise RuntimeError('Model identity differs from inventory')
            result['model_hash_scope']='Stat inventory; no full payload rehash'
            result['resource_scope']='Quantized AR weights only; PLE read through upstream bounded row cache; MTP disabled; context 9216/chunk 2048'
            save()
        env = {k:v for k,v in os.environ.items() if not k.startswith(('GUFO_','DS4_','HIP_','ROCR_','HSA_','CUDA_')) and k not in ('LD_PRELOAD','LD_LIBRARY_PATH')}
        env.update(LC_ALL='C',HIP_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='-1',
                   ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        profiles=[('debug',False),('sanitize',True)] if mode=='cpu' else [('hip',False)]
        for name,sanitize in profiles:
            build = ROOT/'build'/name
            run(['cmake','-S',str(ROOT),'-B',str(build),'-G','Ninja',
                 '-DCMAKE_BUILD_TYPE='+('Debug' if mode=='cpu' else 'RelWithDebInfo'),
                 '-DQ2_SANITIZERS='+('ON' if sanitize else 'OFF'),
                 '-DQ2_HIP='+('OFF' if mode=='cpu' else 'ON'),
                 '-DCMAKE_HIP_ARCHITECTURES=gfx1151'],env)
            build_args=['cmake','--build',str(build),'--parallel','2']
            if mode!='cpu':build_args+=['--target','q2_model' if model_mode else 'q2_operators']
            run(build_args,env)
            if mode=='cpu':run(['ctest','--test-dir',str(build),'--output-on-failure'],env)
            elif mode=='operators':
                gpu_env=dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0')
                run([str(build/'cmake/hip/q2_operators')],gpu_env,120)
            elif model_mode:
                binary=build/'cmake/hip/q2_model'
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                run(['ldd',str(binary)],env,30)
                result['model_access']=True
                save()
                if mode=='q2-profile':
                    run([profiler,'--kernel-trace','-d',str(results/'profile'),'-o','q2','--',
                         str(binary),model_paths[0],'profile'],dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                    run(['python3',str(ROOT/'source/tools/prof/prof.py'),'show',str(results/'profile/q2_results.db'),'--json'],env,120)
                    run(['python3',str(ROOT/'tools/analyze-q2-profile.py'),str(results/'profile/q2_results.db'),
                         str(results/'profile-phases.json')],env,120)
                else:
                    run([str(binary),model_paths[0],'smoke' if mode=='q2-smoke' else 'bench'],
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
        result['state'] = 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' if mode=='cpu' else 'HIP_BUILD_PASS_NOT_MODEL_QUALIFIED' if mode=='hip-build' else 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED'
        if model_mode: result['state']='MODEL_SMOKE_PASS' if mode=='q2-smoke' else 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT'
        if mode=='q2-profile': result['state']='DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK'
    except Exception as ex:
        result['state'] = 'FAILED'; result['error'] = repr(ex)
    finally:
        try:
            if model_paths:
                result['models_after']=[stat_model(p) for p in model_paths]
                if result['models_after']!=result['models_before']: raise RuntimeError('Model identity changed')
            if mode!='cpu':
                result['postflight_kfd']=clients()
                result['postflight_observers']=device_observers()
                result['postflight_locks']=[{'path':name,'device':os.stat(name).st_dev,'inode':os.stat(name).st_ino} for name in LOCKS[:len(held)]]
                if result['postflight_locks']!=result['locks']: raise RuntimeError('Lease identity changed after run')
            result['artifacts']={str(p.relative_to(results)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in results.rglob('*') if p.is_file() and p.name!='result.json'}
        except Exception as ex:
            result['state']='FAILED';result['postflight_error']=repr(ex)
        finally:
            try:
                if registered:register('end')
            finally:
                for fd in reversed(held): os.close(fd)
        result['finished_at'] = now(); save()
        print(json.dumps(result),flush=True)
    raise SystemExit(1 if result['state']=='FAILED' else 0)


if __name__ == '__main__':
    main()
