# SPDX-License-Identifier: MIT
# One declared campaign; per-arm supervisors own four leases and device children.
import datetime,fcntl,hashlib,json,os,pathlib,runpy,signal,subprocess,sys,tarfile,shutil
root=pathlib.Path(__file__).resolve().parent
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
ticks=lambda p:int(pathlib.Path(f'/proc/{p}/stat').read_text().rsplit(')',1)[1].split()[19])
m=json.loads((root/'suite-manifest.json').read_text())
state={'state':'CHECKING','started_at':now(),'pid':os.getpid(),'start_ticks':ticks(os.getpid()),'runs':[]}
child=None;stopped=False

def save():
 (root/'state.tmp').write_text(json.dumps(state,indent=2));(root/'state.tmp').replace(root/'state.json')
def stop(sig,frame):
 global stopped
 stopped=True
 if child is not None and child.poll() is None:child.terminate()
for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)

def pack():
 final={'at':now(),'owned_processes':[],'locks':[]}
 for item in state['runs']:
  path=root/item['arm']/'results/result.json'
  if not path.exists():continue
  r=json.loads(path.read_text())
  for key,identity in [('supervisor_pid','supervisor_start_ticks'),('child_pid','child_start_ticks'),('server_pid','server_start_ticks')]:
   if r.get(key):
    try:live=ticks(r[key])
    except FileNotFoundError:live=None
    final['owned_processes'].append({'pid':r[key],'expected_start_ticks':r.get(identity),'live_start_ticks':live,'owned_identity_absent':live!=r.get(identity)})
 for name in m['lock_order']:
  fd=os.open(name,os.O_RDONLY|os.O_CLOEXEC);s=os.fstat(fd);live=os.stat(name)
  row={'path':name,'device':s.st_dev,'inode':s.st_ino,'unchanged':(s.st_dev,s.st_ino)==(live.st_dev,live.st_ino)}
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);row['free']=True
  except BlockingIOError:row['free']=False
  finally:os.close(fd)
  final['locks'].append(row)
 final['kfd']=[p.name for p in pathlib.Path('/sys/class/kfd/kfd/proc').iterdir() if p.name.isdigit()]
 (root/'postflight.json').write_text(json.dumps(final,indent=2))
 files=[p for p in root.iterdir() if p.is_file() and p.suffix in ('.json','.py','.log')]
 for item in state['runs']:
  arm=root/item['arm'];files += [p for p in arm.iterdir() if p.is_file() and p.suffix in ('.json','.log')]
  if (arm/'results').exists():files += [p for p in (arm/'results').rglob('*') if p.is_file()]
 (root/'collection-sha256.json').write_text(json.dumps({str(p.relative_to(root)):sha(p) for p in files},indent=2))
 with tarfile.open(root.parent/(root.name+'-evidence.tar'),'w') as t:
  for p in files+[root/'collection-sha256.json']:t.add(p,arcname=str(p.relative_to(root)))

save()
try:
 cpu=root.parent/m['cpu_run']/'evidence/remote/result.json';commands=json.loads(cpu.read_text())
 assert len(commands)==9 and all(x['exit_code']==0 for x in commands)
 capsule=root.parent/(m['cpu_run']+'.tar');assert sha(capsule)==m['cpu_capsule_sha256']
 with tarfile.open(capsule) as t:
  for name,h in m['source_files'].items():assert hashlib.sha256(t.extractfile(name).read()).hexdigest()==h,name
 for name,h in m['files'].items():assert sha(root/name)==h,name
 report=runpy.run_path(str(root/'bench-report.py'))
 retained=set()
 for prior in m.get('retained_arms',[]):
  source=root.parent/prior['campaign'];arm=prior['arm'];assert source.parent==root.parent
  collection=json.loads((source/'collection-sha256.json').read_text())
  result=source/arm/'results/result.json';assert sha(result)==prior['result_sha256']
  old=json.loads(result.read_text());assert old['state']=='MODEL_HTTP_PERFORMANCE_PASS_NOT_INDEPENDENT_COMPARISON' and old['server_exit_code']==0
  for name,h in collection.items():
   if name.startswith(arm+'/'):assert sha(source/name)==h,name
  shutil.copytree(source/arm,root/arm)
  state['runs'].append({'arm':arm,'exit_code':0,'retained_from':prior['campaign'],'result_sha256':prior['result_sha256'],'started_at':old['started_at'],'finished_at':old['finished_at']})
  retained.add(arm);save()
 for arm in m['arms']:
  if arm['id'] in retained:continue
  if stopped:raise RuntimeError('operator interrupted')
  run=root/arm['id'];run.mkdir();http=arm['kind']=='http';core=arm.get('core',False)
  names=['smoke-model.py','serving_checks.py'] if http else ['run-bench.py','smoke-model.py','bench-report.py']
  for name in names:(run/name).write_bytes((root/name).read_bytes())
  binary_name='synapse-lie-server' if http else 'synapse-lie-bench'
  binary=run/binary_name;binary.write_bytes((root/(arm['variant']+'-'+binary_name)).read_bytes());binary.chmod(0o700);names.append(binary_name)
  if core:
   name=arm['input'];(run/name).write_bytes((root/name).read_bytes());names.append(name)
  probe_argv=[str(binary),*(['--suite','core'] if core else []),'--build-info']
  probe=subprocess.run(probe_argv,env=dict(os.environ,ROCR_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1'),capture_output=True,text=True,timeout=30)
  (run/'build-info-probe.json').write_text(json.dumps({'argv':probe_argv,'exit_code':probe.returncode,'stdout':probe.stdout,'stderr':probe.stderr},indent=2))
  if probe.returncode:raise RuntimeError('build-info probe failure')
  manifest={k:m[k] for k in ['authorization','models','lock_order']}
  manifest.update(source_commit=m['variants'][arm['variant']]['commit'],source_state=m['variants'][arm['variant']],source_files=m['source_files'],prepared_at=now(),build_info=json.loads(probe.stdout),cpu_receipt_sha256=sha(cpu),source_capsule_sha256=sha(capsule))
  if http:
   manifest.update(schema='synapse-lie.model-smoke.v1',suite=arm['suite'],binary_build=m['variants'][arm['variant']]['build_id'],binary_sha256=sha(binary),runner_sha256=sha(run/'smoke-model.py'),serving_checks_sha256=sha(run/'serving_checks.py'),cases=m['http_cases'],request_settings={'context':9216 if arm['suite']=='http-performance-v1' else 4096,'prefill_chunk':2048,'max_active':2,'temperature':0,'thinking':False,'mtp':False,'vision':False},openai_checks=True,reactive_checks=True,api_port=8000,management_port=19880)
   if arm['suite']=='http-performance-v1':manifest['performance_profile']=m['performance_profile']
   runner='smoke-model.py'
  else:
   manifest.update(schema='synapse-lie.simplified-bench-run.v1',benchmark_args=arm['args'],files={n:sha(run/n) for n in names},protocol='docs/CORE-GPU-PROTOCOL.md',timeout_seconds=3600)
   if core:manifest['benchmark_input']={'path':arm['input'],'bytes':(run/arm['input']).stat().st_size,'sha256':sha(run/arm['input'])}
   runner='run-bench.py'
  (run/'manifest.json').write_text(json.dumps(manifest,indent=2))
  state.update(state='RUNNING',current_arm=arm['id']);save()
  log=(run/'supervisor.log').open('xb')
  child=subprocess.Popen([sys.executable,'-B',str(run/runner),str(run)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  item={'arm':arm['id'],'pid':child.pid,'start_ticks':ticks(child.pid),'started_at':now()};state['runs'].append(item);save()
  try:child.wait(timeout=3800)
  except subprocess.TimeoutExpired:
   child.terminate()
   try:child.wait(timeout=180)
   except subprocess.TimeoutExpired:state['cleanup_unresolved']=True;raise RuntimeError('cleanup unresolved; no next arm')
   raise RuntimeError('helper deadline')
  item.update(exit_code=child.returncode,finished_at=now());log.close();save()
  if child.returncode:raise RuntimeError('arm failed: '+arm['id'])
  if core:
   data=report['read_result'](run/'results/measurements.jsonl')
   source=report['read_result'](root/arm['reference_arm']/'results/measurements.jsonl')
   point=next(p for p in source['configurations'] if p['prompt_tokens']==arm['prompt_tokens'] and p['users']==arm['users'])
   actual=data['configurations'][0]
   item['tokens_match_executor']=actual['physical_ids_sha256']==point['physical_ids_sha256'] and actual['output_ids']==point['output_ids']
   if not item['tokens_match_executor']:raise RuntimeError('core/executor token mismatch')
  elif not http and arm.get('compare'):
   item['comparison']=report['compare'](report['read_result'](run/'results/measurements.jsonl'),report['read_result'](root/arm['compare']/'results/measurements.jsonl'))
   if any(not x['tokens_equal'] or not x['pp_frontier_equal'] or not x['tg_frontier_equal'] for x in item['comparison']):raise RuntimeError('matched executor numerical mismatch')
  save()
 state.update(state='COMPLETED_PENDING_OFFLINE_REGRESSION_ANALYSIS',finished_at=now());save()
except BaseException as ex:
 state.update(state='FAILED',error=repr(ex),finished_at=now());save();print(json.dumps(state,indent=2),flush=True)
finally:
 if not state.get('cleanup_unresolved'):pack()
print(json.dumps(state,indent=2),flush=True)
if state['state']=='FAILED':raise SystemExit(1)
