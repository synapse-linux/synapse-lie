#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot, operator-authorized original-model smoke. Not numerical qualification.
Uses an existing verified binary; no builds, installs, model hashes or fallback.
The manifest is a run record, not reusable authorization for a future run.
"""
import datetime
import fcntl
import hashlib
import http.client as http_client
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import threading
import time


def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid): return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19])
def kfd(): return set(int(p.name) for p in Path('/sys/class/kfd/kfd/proc').iterdir() if p.name.isdecimal())
def dri_clients():
    clients=set(); denied=0
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal(): continue
        try:
            for f in (p/'fd').iterdir():
                try: target=os.readlink(f)
                except OSError: continue
                if target.startswith('/dev/dri/'):
                    clients.add(int(p.name)); break
        except PermissionError: denied+=1
        except FileNotFoundError: pass
    return clients,denied

def memory():
    return {a:int(b.split()[0])*1024 for a,b in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines()) if a in ('MemTotal','MemAvailable','SwapTotal','SwapFree')}
def gpu():
    result={}
    for name in ('gpu_busy_percent','mem_info_gtt_used','mem_info_vram_used'):
        p=Path('/sys/class/drm/card1/device')/name
        result[name]=p.read_text().strip()
    return result

def model_stat(record):
    s=Path(record['path']).stat()
    actual={'bytes':s.st_size,'device':s.st_dev,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}
    if actual!={k:record[k] for k in actual}: raise RuntimeError('model stat drift: '+record['path'])
    return {'path':record['path'],**actual,'historical_sha256':record['historical_sha256'],'full_hash_recomputed':False}

def http(port,path,body=None,timeout=120):
    c=http_client.HTTPConnection('127.0.0.1',port,timeout=timeout)
    try:
        c.request('GET' if body is None else 'POST',path,body,{} if body is None else {'Content-Type':'application/json'})
        r=c.getresponse(); payload=r.read(1024*1024+1)
        if len(payload)>1024*1024: raise RuntimeError('response bound')
        return {'status':r.status,'headers':dict(r.getheaders()),'body':payload.decode('utf-8','strict')}
    finally: c.close()

def sse(text):
    frames=text.split('\n\n')
    if frames[-2:]!=['data: [DONE]',''] or text.count('data: [DONE]')!=1: raise RuntimeError('invalid SSE terminal')
    data=[]
    for frame in frames[:-2]:
        if not frame.startswith('data: '): raise RuntimeError('invalid SSE frame')
        item=json.loads(frame[6:])
        if 'error' in item: raise RuntimeError('SSE backend error: '+str(item['error']))
        data.append(item)
    if not data or len({x['id'] for x in data})!=1: raise RuntimeError('SSE identity')
    if data[0]['choices'][0]['delta'].get('role')!='assistant': raise RuntimeError('SSE role')
    if any(x.get('system_fingerprint')!='gufo-embedded-f783fedb' for x in data): raise RuntimeError('SSE provider identity')
    finish=[x['choices'][0]['finish_reason'] for x in data if x.get('choices') and x['choices'][0]['finish_reason'] is not None]
    if len(finish)!=1 or data[-1].get('choices')!=[]: raise RuntimeError('SSE finish/usage')
    return {'content':''.join(x['choices'][0]['delta'].get('content','') for x in data if x.get('choices')),
            'finish':finish[0],'usage':data[-1]['usage']}

def main():
    if len(sys.argv)!=2: raise SystemExit('Usage: smoke-model.py PRIVATE-RUN-DIRECTORY')
    run=Path(sys.argv[1]).resolve(); manifest=json.loads((run/'manifest.json').read_text())
    if manifest['authorization']['kind']!='operator-one-shot-window' or not manifest['authorization']['gpu_test_authorized']:
        raise SystemExit('Explicit current operator authorization required')
    out=run/'results'; out.mkdir()  # Refuse replays/overwrites, including previous failures.
    result={'state':'PREFLIGHT','started_at':now(),'manifest_sha256':sha(run/'manifest.json'),
            'runner_sha256':sha(Path(__file__)),'supervisor_pid':os.getpid(),'supervisor_start_ticks':ticks(os.getpid()),
            'authorization':manifest['authorization'],'ds4_ack_claimed':False,'model_attempted':False,
            'model_inference_observed':False,'numerical_qualification':False,'performance_qualification':False,
            'commands':[],'tests':[],'locks':[]}
    locks=[]; proc=None; stop_watch=threading.Event(); watch=None; abort=threading.Event(); registered=False
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    def save():
        tmp=out/'result.tmp'; tmp.write_text(json.dumps(result,indent=2)+'\n'); tmp.replace(out/'result.json')
    def stage(value):
        result['state']=value; save(); print(now(),value,flush=True)
    def signal_stop(signum,frame):
        abort.set(); result['received_signal']=signum
        if proc is not None and proc.poll() is None: proc.terminate()
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,signal_stop)
    def check():
        if abort.is_set(): raise RuntimeError('run interrupted or foreign GPU activity detected')
        if proc is not None and proc.poll() is not None: raise RuntimeError('server exited: '+str(proc.returncode))
    def register(event):
        row={'owner':'synapse-lie','event':event,'at':now(),'run':str(run),'pid':os.getpid(),
             'start_ticks':result['supervisor_start_ticks'],'authorization_kind':'operator-one-shot-window',
             'source_commit':manifest['source_commit'],'model':manifest['models'][0]['path'],
             'command':result.get('server_argv'),'server_exit_code':result.get('server_exit_code'),'state':result['state']}
        fd=os.open('/tmp/synapse-lie-ds4-coordination/runs.jsonl',os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX); os.write(fd,(json.dumps(row)+'\n').encode()); os.fsync(fd)
        finally: os.close(fd)
    def command(argv,env):
        p=subprocess.run(argv,capture_output=True,text=True,env=env,timeout=20)
        row={'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}; result['commands'].append(row); save()
        if p.returncode: raise RuntimeError('command failed: '+str(argv))
        return p.stdout
    try:
        # Existing files only; no rewriting, deleting, or forging another owner's lock.
        # Nonblocking acquisition never waits in a conflicting lock order.
        for name in manifest['lock_order']:
            p=Path(name); fd=os.open(p,os.O_RDONLY|os.O_CLOEXEC)
            try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException: os.close(fd); raise
            locks.append(fd); s=os.fstat(fd); live=p.stat()
            if (s.st_dev,s.st_ino)!=(live.st_dev,live.st_ino): raise RuntimeError('lock identity race')
            result['locks'].append({'path':name,'device':s.st_dev,'inode':s.st_ino})
        baseline_dri,denied=dri_clients()
        result['preflight_dri']={'pids':sorted(baseline_dri),'permission_denied':denied}
        result['preflight_kfd']=sorted(kfd()); result['preflight_memory']=memory(); result['preflight_gpu']=gpu()
        if result['preflight_kfd']: raise RuntimeError('foreign KFD client before launch')
        result['models_before']=[model_stat(m) for m in manifest['models']]
        trunk=sum(m['bytes'] for m in manifest['models'] if '/mtp-' not in m['path'])
        if result['preflight_memory']['MemAvailable']<=trunk: raise RuntimeError('available RAM below trunk-file-size estimate; not an OOM/fit claim')
        binary=run/'synapse-lie-server'
        if sha(binary)!=manifest['binary_sha256']: raise RuntimeError('binary identity mismatch')
        result['binary_sha256']=sha(binary)
        env={k:v for k,v in os.environ.items() if not k.startswith(('GUFO_','DS4_','HIP_','ROCR_','HSA_','CUDA_')) and k not in ('LD_PRELOAD','LD_LIBRARY_PATH')}
        for key,name in [('HOME','home'),('XDG_CACHE_HOME','cache'),('TMPDIR','tmp')]:
            p=run/name; p.mkdir(); env[key]=str(p)
        env.update(LC_ALL='C',LD_BIND_NOW='1',ROCR_VISIBLE_DEVICES='0',HIP_VISIBLE_DEVICES='0')
        no_gpu=dict(env,ROCR_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1')
        info=json.loads(command([str(binary),'--build-info'],no_gpu))
        if info!=manifest['build_info']: raise RuntimeError('compiled provider identity mismatch')
        result['build_info']=info
        command(['uname','-srmo'],no_gpu)
        command(['readelf','-d',str(binary)],no_gpu)
        linked=command(['ldd',str(binary)],no_gpu)
        if 'not found' in linked: raise RuntimeError('missing runtime DSO')
        dsos={}
        for line in linked.splitlines():
            for word in line.split():
                if word.startswith('/') and Path(word).is_file():
                    p=Path(word).resolve()
                    if not str(p).startswith(('/usr/','/opt/rocm/')): raise RuntimeError('unapproved DSO location: '+str(p))
                    dsos[str(p)]=sha(p)
        result['dsos']=dsos
        result['power_settings']={}
        for p in Path('/sys/devices/system/cpu/cpufreq').glob('policy*/*'):
            if p.name in ('scaling_governor','energy_performance_preference'):
                try: result['power_settings'][str(p)]=p.read_text().strip()
                except OSError: pass
        for name in ('power_dpm_force_performance_level','pp_power_profile_mode'):
            p=Path('/sys/class/drm/card1/device')/name
            try: result['power_settings'][str(p)]=p.read_text().strip()
            except OSError: pass
        for port in (19879,19880):
            with socket.socket() as sock: sock.bind(('127.0.0.1',port))
        if kfd(): raise RuntimeError('foreign KFD client appeared during preflight')
        check()
        result['server_argv']=[str(binary),'--model',manifest['models'][0]['path'],'--context','4096','--prefill-chunk','2048','--max-active','1','--request-timeout-ms','120000','--port','19879','--management-port','19880']
        register('start'); registered=True
        result['model_attempted']=True; stage('MODEL_LOADING')
        with (out/'server.log').open('xb') as log:
            proc=subprocess.Popen(result['server_argv'],env=env,cwd=run,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        result['server_pid']=proc.pid; result['server_start_ticks']=ticks(proc.pid); save()
        def observer():
            with (out/'telemetry.jsonl').open('x') as log:
                while not stop_watch.is_set():
                    try:
                        clients=kfd(); drm,denied=dri_clients()
                        foreign=(clients-{proc.pid}) | (drm-baseline_dri-{proc.pid})
                        row={'at':now(),'memory':memory(),'gpu':gpu(),'kfd':sorted(clients),'dri':sorted(drm),'dri_permission_denied':denied}
                        log.write(json.dumps(row)+'\n'); log.flush()
                        if foreign:
                            result['foreign_gpu_clients']=sorted(foreign); abort.set()
                            if proc.poll() is None: proc.terminate()
                            return
                    except Exception as ex:
                        result['observer_error']=repr(ex); abort.set()
                        if proc.poll() is None: proc.terminate()
                        return
                    stop_watch.wait(1)
        watch=threading.Thread(target=observer); watch.start()
        deadline=time.monotonic()+900; announced=0
        while True:
            check()
            try:
                state=http(19880,'/actuator/llm',timeout=3)
                if state['status']==200:
                    obj=json.loads(state['body']); result['last_loading_state']=obj
                    if obj['backend']['state']=='FAILED': raise RuntimeError('model load failed: '+str(obj['backend']['error']))
                    if obj['ready']: break
            except (OSError,http_client.HTTPException): pass
            if time.monotonic()>deadline: raise RuntimeError('model loading deadline')
            if time.monotonic()-announced>10:
                save(); print(now(),'waiting for model readiness',flush=True); announced=time.monotonic()
            time.sleep(.25)
        result['ready_at']=now(); result['ready_info']=json.loads(http(19880,'/actuator/info')['body'])
        if result['ready_info']['backend']['synthetic'] or result['ready_info']['backend']['ownership']!='delegated': raise RuntimeError('unexpected provider')
        stage('MODEL_READY_SMOKE_RUNNING')
        for case in manifest['cases']:
            pair=[]
            for streaming in (False,True):
                check()
                request={'model':'qwen3.8-flash-next','messages':[{'role':'user','content':case['prompt']}],
                         'temperature':0,'max_tokens':case['max_tokens'],'stream':streaming,'chat_template_kwargs':{'enable_thinking':False}}
                if streaming: request['stream_options']={'include_usage':True}
                start=time.monotonic(); response=http(19879,'/v1/chat/completions',json.dumps(request,ensure_ascii=False).encode())
                row={'case':case['name'],'stream':streaming,'request':request,'response':response,'elapsed_wall_seconds':time.monotonic()-start}
                result['tests'].append(row); save()
                if response['status']!=200: raise RuntimeError('chat HTTP failure: '+response['body'])
                if streaming:
                    if 'text/event-stream' not in response['headers'].get('Content-Type',''): raise RuntimeError('SSE content type')
                    parsed=sse(response['body'])
                else:
                    obj=json.loads(response['body'])
                    if obj.get('system_fingerprint')!='gufo-embedded-f783fedb': raise RuntimeError('completion provider')
                    parsed={'content':obj['choices'][0]['message']['content'],'finish':obj['choices'][0]['finish_reason'],'usage':obj['usage']}
                row['parsed']=parsed; pair.append(parsed)
                if parsed['usage']['completion_tokens']<=0 or parsed['finish'] not in ('stop','length'): raise RuntimeError('no valid generated completion')
                result['model_inference_observed']=True; save()
                if parsed['content'].strip()!=case['expected']: raise RuntimeError('predeclared smoke text mismatch: '+repr(parsed['content']))
            if pair[0]!=pair[1]: raise RuntimeError('nonstream/SSE mismatch')
            print(now(),'PASS',case['name'],repr(pair[0]['content']),flush=True)
        check()
        deadline=time.monotonic()+20
        while True:
            check(); result['final_llm']=json.loads(http(19880,'/actuator/llm')['body'])
            scheduler=result['final_llm']['scheduler']
            if scheduler['active']==0 and scheduler['queued']==0: break
            if time.monotonic()>deadline: raise RuntimeError('session retirement deadline')
            time.sleep(.05)
        expected=sum(row['parsed']['usage']['completion_tokens'] for row in result['tests'])
        if scheduler['completed']!=len(manifest['cases'])*2 or scheduler['failed'] or scheduler['cancelled'] or scheduler['generated_tokens']!=expected:
            raise RuntimeError('unexpected worker accounting / foreign request')
        stage('SMOKE_PASSED_AWAITING_SHUTDOWN')
    except BaseException as ex:
        result['error']=repr(ex); stage('FAILED')
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    result['forced_owned_child_kill']=True; proc.kill(); proc.wait()
            result['server_exit_code']=proc.returncode
            if proc.returncode!=0 or result.get('forced_owned_child_kill'):
                result['state']='FAILED'; result.setdefault('error','unclean server exit')
        stop_watch.set()
        if watch is not None: watch.join()
        try:
            result['models_after']=[model_stat(m) for m in manifest['models']]
            result['binary_unchanged']=sha(run/'synapse-lie-server')==manifest['binary_sha256']
            result['postflight_kfd']=sorted(kfd()); result['postflight_gpu']=gpu(); result['postflight_memory']=memory()
            if not result['binary_unchanged'] or (proc is not None and proc.pid in result['postflight_kfd']): raise RuntimeError('retirement/identity failure')
            if result['state']=='SMOKE_PASSED_AWAITING_SHUTDOWN': result['state']='MODEL_HTTP_SSE_SMOKE_PASS_NOT_NUMERICAL_QUALIFICATION'
        except Exception as ex:
            result['state']='FAILED'; result['closure_error']=repr(ex)
        result['finished_at']=now(); save()
        if registered: register('end')
        for fd in reversed(locks): os.close(fd)
    print(json.dumps({k:result[k] for k in ('state','model_attempted','model_inference_observed','finished_at')},indent=2),flush=True)
    return 0 if result['state']=='MODEL_HTTP_SSE_SMOKE_PASS_NOT_NUMERICAL_QUALIFICATION' else 1

if __name__=='__main__': raise SystemExit(main())
