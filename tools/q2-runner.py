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
from q2_thermal import sample as thermal_sample, enforce as thermal_enforce
from q2_reuse import verify_sources

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
    cpu_mode = mode in ('cpu', 'ple-cpu', 'ple-io-cpu', 'ple-cache-cpu', 'ple-lookahead-cpu')
    io_mode = mode in ('q2-ple-io', 'ud-ple-io')
    ple_mode = mode in ('q2-ple', 'ud-ple', 'q2-ple-cache64k', 'q2-ple-lookahead', 'q2-ple-first-access')
    ple_target = 'q2_ple_lookahead' if mode in ('q2-ple-lookahead', 'q2-ple-first-access') else 'q2_ple'
    model_mode = io_mode or ple_mode or mode in ('q2-smoke','q2-bench','q2-bench2k','ud-bench2k','q2-profile','ud-profile','ud-base','ud-patched')
    profile_mode = mode in ('q2-profile','ud-profile')
    hc_mode = mode in ('hc-operators', 'hc-bench', 'hc-pp-operators', 'hc-pp-bench', 'hc-library-bench', 'hc-input-bench', 'hc-up-operators', 'hc-up-bench', 'hc-moe-operators', 'hc-moe-bench', 'hc-norm-operators', 'hc-norm-bench', 'routed-operators', 'iq2-pair-operators', 'packed-operators', 'packed-bench')
    hc_target = 'q2_hc_input' if mode == 'hc-input-bench' else 'q2_hc_norm_half' if mode.startswith('hc-norm-') else 'q2_hc_moe_fused' if mode.startswith('hc-moe-') else 'q2_hc_up_fused' if mode == 'hc-up-operators' else 'q2_packed_bench' if mode == 'packed-bench' else 'q2_packed' if mode == 'packed-operators' else 'q2_iq2_pair' if mode == 'iq2-pair-operators' else 'q2_routed' if mode == 'routed-operators' else 'q2_hc_pp' if mode.startswith('hc-pp-') or mode == 'hc-library-bench' else 'q2_hc'
    if not cpu_mode and mode not in ('hip-build', 'operators', 'operators-reference') and not model_mode and not hc_mode:
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
        row={'at':now(),'kfd':clients(),'thermal':thermal_sample()}
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
        if any(sensor['over_limit'] for sensor in row['thermal']):
            result['thermal_stop'] = row['thermal']
            save()
        thermal_enforce(row['thermal'])
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
        observation()
        row = {'argv': argv, 'started_at': now()}; result['commands'].append(row); save()
        logfile = results/f'{len(result["commands"]):02}.log'
        with logfile.open('wb') as log:
            try:
                supervise(argv,cwd=ROOT,env=env,log=log,row=row,timeout=limit,save=save,
                          clients=clients if not cpu_mode else lambda: (),
                          observe=observation)
            finally:
                row['finished_at']=now();save()
        row['finished_at'] = now(); save()
        print(json.dumps(row),flush=True)
        print(logfile.read_text(),flush=True)
        if row['exit_code'] or row.get('timeout'):
            raise RuntimeError('Qualification command failed')
    save()
    try:
        if not cpu_mode:
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
            if profile_mode:
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
            if mode in ('q2-ple-lookahead', 'q2-ple-first-access'):
                result['resource_scope']='Original Q2 AR weights; native/prepared-serial/C17-lookahead; unchanged kernels/cache; context 8224/chunk 2048; two bounded pinned PLE buffers; no page eviction'
            if mode == 'q2-ple-first-access':
                result['resource_scope']='Original Q2 AR weights; eight new input sets with native/C17-lookahead first order ABBAABBA; warmup on padding; page residency observed; context 8224/chunk 2048; two bounded pinned PLE buffers; no page eviction'
            if io_mode:
                result['resource_scope']='Original PLE rows only; no model upload or forward; descriptor-local advice and bounded BF16 cache capacity; no cache eviction or file mutation'
            save()
        env = {k:v for k,v in os.environ.items() if not k.startswith(('GUFO_','DS4_','HIP_','ROCR_','HSA_','CUDA_')) and k not in ('LD_PRELOAD','LD_LIBRARY_PATH')}
        env.update(LC_ALL='C',HIP_VISIBLE_DEVICES='-1',ROCR_VISIBLE_DEVICES='-1',
                   ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        reuse_args=[]
        if mode.endswith('bench2k') and '--rebuild-mmq' not in sys.argv[2:]:
            observation()
            previous=ROOT.parent/('q2-explore-reference-r1' if mode.startswith('q2-') else 'q2-explore-ud-r1')
            receipt=json.loads((previous/'results/result.json').read_text())
            if receipt['state']!='MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT' or any(c['exit_code'] for c in receipt['commands']):
                raise RuntimeError('MMQ reuse reference was not qualified')
            identity=verify_sources(previous/'source', ROOT/'source')
            prior_binary=previous/'build/hip/cmake/hip/q2_model'
            if hashlib.sha256(prior_binary.read_bytes()).hexdigest()!=receipt['binary_sha256_after']:
                raise RuntimeError('MMQ reuse reference binary changed')
            archive=previous/'build/hip/cmake/hip/qwen/libgufo_qwen38_flash_next_mmq.a'
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            reuse=ROOT/'reuse';reuse.mkdir()
            copied=reuse/'libgufo_qwen38_flash_next_mmq.a'
            shutil.copyfile(archive,copied)
            if hashlib.sha256(copied.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('MMQ archive copy differs')
            result['mmq_reuse']=dict(identity,reference=str(previous),archive=str(archive),sha256=digest,
                                     reference_binary_sha256=receipt['binary_sha256_after'])
            reuse_args=['-DQ2_MMQ_ARCHIVE='+str(copied)]
            save()
        profiles=[('debug',False),('sanitize',True)] if cpu_mode else [('io' if io_mode else 'hip',False)]
        for name,sanitize in profiles:
            build = ROOT/'build'/name
            run(['cmake','-S',str(ROOT),'-B',str(build),'-G','Ninja',
                 '-DCMAKE_BUILD_TYPE='+('Debug' if cpu_mode else 'RelWithDebInfo'),
                 '-DQ2_SANITIZERS='+('ON' if sanitize else 'OFF'),
                 '-DQ2_HIP='+('OFF' if cpu_mode or io_mode else 'ON'),
                 '-DCMAKE_HIP_ARCHITECTURES=gfx1151']+reuse_args,env)
            # Bound CPU build pressure after the recorded two-job thermal
            # stop. This changes build concurrency, not runtime device policy.
            build_args=['cmake','--build',str(build),'--parallel','1' if model_mode else '2']
            if not cpu_mode:build_args+=['--target','q2_ple_io' if io_mode else ple_target if ple_mode else 'q2_model' if model_mode else hc_target if hc_mode else 'q2_operators']
            run(build_args,env)
            if cpu_mode:run(['ctest','--test-dir',str(build),'--output-on-failure'],env)
            elif io_mode:
                binary=build/'q2_ple_io'
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                result['model_access']=True
                save()
                try:
                    run([str(binary),model_paths[0]],env,600)
                finally:
                    result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                    if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
            elif mode in ('operators','operators-reference'):
                gpu_env=dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0')
                run([str(build/'cmake/hip/q2_operators')],gpu_env,120)
            elif hc_mode:
                binary=build/'cmake/hip'/hc_target
                if mode == 'hc-library-bench': run(['ldd',str(binary)],env,30)
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                try:
                    run([str(binary)] + ([] if mode in ('hc-input-bench', 'hc-up-operators', 'routed-operators', 'iq2-pair-operators', 'packed-operators', 'packed-bench') else ['library' if mode == 'hc-library-bench' else 'bench-up' if mode == 'hc-up-bench' else 'bench' if mode.endswith('-bench') else 'operators']),
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),
                        300 if mode == 'hc-library-bench' else 120)
                finally:
                    result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                    if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
            elif model_mode:
                binary=build/'cmake/hip'/(ple_target if ple_mode else 'q2_model')
                result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
                run(['ldd',str(binary)],env,30)
                result['model_access']=True
                save()
                if ple_mode:
                    run([str(binary),model_paths[0]] + (['--first-access'] if mode == 'q2-ple-first-access' else []),dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                elif profile_mode:
                    run([profiler,'--kernel-trace','-d',str(results/'profile'),'-o','q2','--',
                         str(binary),model_paths[0],'profile'],dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                    run(['python3',str(ROOT/'source/tools/prof/prof.py'),'show',str(results/'profile/q2_results.db'),'--json'],env,120)
                    run(['python3',str(ROOT/'tools/analyze-q2-profile.py'),str(results/'profile/q2_results.db'),
                         str(results/'profile-phases.json')],env,120)
                    run(['python3',str(ROOT/'tools/q2-resource-report.py'),str(results/'profile/q2_results.db'),
                         str(results/'profile-resources.json')],env,120)
                else:
                    run([str(binary),model_paths[0],'smoke' if mode=='q2-smoke' else 'bench2k' if mode.endswith('bench2k') else 'bench'],
                        dict(env,HIP_VISIBLE_DEVICES='0',ROCR_VISIBLE_DEVICES='0'),1800)
                result['binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
                if result['binary_sha256_after']!=result['binary_sha256']: raise RuntimeError('Binary changed')
        result['state'] = 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' if cpu_mode else 'HIP_BUILD_PASS_NOT_MODEL_QUALIFIED' if mode=='hip-build' else 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED'
        if model_mode: result['state']='MODEL_SMOKE_PASS' if mode=='q2-smoke' else 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT'
        if profile_mode: result['state']='DIAGNOSTIC_PROFILE_COMPLETE_NOT_WALL_BENCHMARK'
        if ple_mode: result['state']='PLE_DIAGNOSTIC_COMPLETE_NOT_PERFORMANCE_VERDICT'
        if io_mode: result['state']='PLE_ROW_IO_COMPLETE_NO_MODEL_FORWARD'
        if mode == 'packed-bench': result['state']='SYNTHETIC_Q2_PACKED_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
        if mode in ('hc-bench','hc-pp-bench','hc-library-bench','hc-input-bench','hc-up-bench','hc-moe-bench','hc-norm-bench'): result['state']='SYNTHETIC_HC_MICROBENCH_COMPLETE_NOT_MODEL_THROUGHPUT'
    except Exception as ex:
        result['state'] = 'FAILED'; result['error'] = repr(ex)
    finally:
        try:
            if 'mmq_reuse' in result:
                for archive_path in (Path(result['mmq_reuse']['archive']), ROOT/'reuse/libgufo_qwen38_flash_next_mmq.a'):
                    if hashlib.sha256(archive_path.read_bytes()).hexdigest()!=result['mmq_reuse']['sha256']:
                        raise RuntimeError('MMQ archive changed during run')
                result['mmq_reuse']['unchanged_after']=True
            if model_paths:
                result['models_after']=[stat_model(p) for p in model_paths]
                if result['models_after']!=result['models_before']: raise RuntimeError('Model identity changed')
            if not cpu_mode:
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
