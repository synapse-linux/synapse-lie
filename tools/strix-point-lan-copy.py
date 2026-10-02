#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One admitted read-only .157 -> .161 UD transfer over two controller SSH pipes."""
import datetime,fcntl,hashlib,importlib.util,json,os,signal,stat,sys,threading,time
from pathlib import Path

campaign_path=Path(__file__).with_name('campaign.py')
if not campaign_path.exists(): campaign_path=Path(__file__).with_name('strix-point-campaign.py')
spec=importlib.util.spec_from_file_location('point',campaign_path)
point=importlib.util.module_from_spec(spec); spec.loader.exec_module(point)
CHUNK=8*1024*1024

def identity(path):
 s=path.stat()
 return dict(path=str(path),bytes=s.st_size,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)

def receive(row, destination, stream, progress):
 """Hash the saved prefix and exact streamed suffix before exclusive publication."""
 partial=destination.with_suffix(destination.suffix+'.part')
 existing=destination if destination.exists() else partial
 digest=hashlib.sha256(); size=0
 if existing.exists():
  with os.fdopen(os.open(existing,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
   st=os.fstat(f.fileno())
   if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid(): raise ValueError('Unsafe saved shard')
   while block:=f.read(CHUNK): digest.update(block); size+=len(block)
 if size!=row['offset']: raise ValueError('Saved prefix changed since planning')
 if existing==destination:
  if size!=row['bytes'] or digest.hexdigest()!=row['sha256']: raise ValueError('Published shard mismatch')
  return dict(sha256=digest.hexdigest(),reverified_existing=True,**identity(destination))
 with os.fdopen(os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600),'ab') as f:
  if os.fstat(f.fileno()).st_size!=size: raise ValueError('Partial changed before append')
  while size<row['bytes']:
   block=stream.read(min(CHUNK,row['bytes']-size))
   if not block: raise ValueError('Truncated LAN payload')
   f.write(block); digest.update(block); size+=len(block); progress(size)
  f.flush(); os.fsync(f.fileno())
 if digest.hexdigest()!=row['sha256']: raise ValueError('LAN payload SHA-256 mismatch')
 os.link(partial,destination); partial.unlink()
 return dict(sha256=digest.hexdigest(),**identity(destination))

def main():
 role,root=sys.argv[1],Path(sys.argv[2])
 assert role in ('send','receive') and root.resolve()==root and root.stat().st_uid==os.getuid()
 expected_host='192.168.5.157' if role=='send' else '192.168.5.161'
 assert os.environ['SSH_CONNECTION'].split()[2]==expected_host
 m=json.loads((root/'manifest.json').read_text()); r={'state':'PREFLIGHT','started_at':point.now(),'pid':os.getpid(),'start_ticks':point.ticks(os.getpid()),'role':role,'exit_code':1,'files':[]}
 locks=[]; campaign=None; registered=False; stop=threading.Event(); watcher=None; watch_error=[]
 def record(): point.save(root/'copy-result.json',r)
 def signal_stop(signum,frame): raise InterruptedError('Transfer interrupted: '+str(signum))
 for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,signal_stop)
 def register(event):
  item=dict(owner='synapse-lie-point-copy',event=event,at=point.now(),run=str(root),pid=r['pid'],start_ticks=r['start_ticks'],state=r['state'],command=['python3','lan-copy.py',role,str(root)],model=m['sources'][0]['path'],exit_code=r['exit_code'])
  fd=os.open('/tmp/synapse-lie-ds4-coordination/runs.jsonl',os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
  try:
   fcntl.flock(fd,fcntl.LOCK_EX); data=(json.dumps(item)+'\n').encode(); assert os.write(fd,data)==len(data); os.fsync(fd)
  finally: os.close(fd)
 def checked_source(row):
  p=Path(row['path']); actual=identity(p)
  if any(actual[k]!=row[k] for k in actual): raise ValueError('Source identity changed')
  return actual
 try:
  record()
  if role=='send':
   for path in m['lock_order']:
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW); locks.append(fd); fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    s=os.fstat(fd); live=Path(path).stat()
    assert [s.st_dev,s.st_ino]==m['lock_identities'][path]==[live.st_dev,live.st_ino]
   r['locks']=m['lock_identities']; r['models_before']=[checked_source(x) for x in m['sources']]
   before=point.observe(); r['before']=before; baseline={(p['pid'],p['start_ticks']) for p in before['dri']}
   def sample():
    obs=point.observe()
    with (root/'telemetry.jsonl').open('a') as f: f.write(json.dumps(obs)+'\n')
    if obs['kernel_kfd'] or obs['kfd']: raise RuntimeError('Foreign GPU client')
    if {(p['pid'],p['start_ticks']) for p in obs['dri']}-baseline: raise RuntimeError('New foreign DRI client')
    if any(x['value_c']>=x['limit_c'] for x in obs['temperatures']): raise RuntimeError('Thermal limit')
   sample(); register('start'); registered=True
  else:
   assert root.parent==point.BASE
   campaign=point.Campaign(root,m); campaign.enter(); sample=campaign.sample
  deadline=time.monotonic()+1800
  def watch():
   try:
    while not stop.wait(1):
     sample()
     if time.monotonic()>deadline: raise TimeoutError('LAN transfer deadline')
   except BaseException as ex: watch_error.append(repr(ex)); os.kill(os.getpid(),signal.SIGTERM)
  watcher=threading.Thread(target=watch,daemon=True); watcher.start()
  r['state']='TRANSFERRING'; record(); completed=0; last=0
  for row,source in zip(m['transfer_files'],m['sources'],strict=True):
   def progress(size):
    nonlocal last
    if time.monotonic()-last>=2:
     point.save(root/'copy-progress.json',dict(at=point.now(),file=row['name'],file_bytes=size,completed_bytes=completed+size,total_bytes=m['model_plan']['total_bytes']))
     last=time.monotonic()
   if role=='send':
    checked_source(source)
    fd=os.open(source['path'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME)
    with os.fdopen(fd,'rb') as f:
     assert identity(Path(source['path']))==r['models_before'][len(r['files'])]
     f.seek(row['offset']); sent=row['offset']
     while sent<row['bytes']:
      block=f.read(min(CHUNK,row['bytes']-sent))
      if not block: raise ValueError('Truncated source')
      sys.stdout.buffer.write(block); sent+=len(block); progress(sent)
    checked_source(source); r['files'].append(dict(name=row['name'],streamed_bytes=row['bytes']-row['offset']))
   else:
    dest=Path(m['model_plan']['destination'])/row['name']
    if dest.parent.resolve()!=dest.parent or not dest.parent.is_relative_to(point.BASE/'models'): raise ValueError('Unsafe destination')
    r['files'].append(receive(row,dest,sys.stdin.buffer,progress))
   completed+=row['bytes']; record()
  if role=='send':
   sys.stdout.buffer.close()
   if sys.stdin.buffer.readline()!=b'VERIFIED\n': raise ValueError('Receiver did not acknowledge verification')
   r['models_after']=[checked_source(x) for x in m['sources']]
  else:
   if sys.stdin.buffer.read(1): raise ValueError('Unexpected trailing LAN payload')
   r['state']='VERIFIED'; r['exit_code']=0
   destination=Path(m['model_plan']['destination'])
   with (destination/'SOURCE.json').open('x') as f:
    json.dump({'plan':m['model_plan'],'result':r,'transport':'admitted read-only .157 LAN suffix copy'},f,indent=2); f.flush(); os.fsync(f.fileno())
  r['state']='VERIFIED'; r['exit_code']=0
 except BaseException as ex: r['state']='FAILED'; r['error']=repr(ex)
 finally:
  stop.set()
  if watcher: watcher.join(timeout=5)
  if watch_error: r['watch_error']=watch_error; r['exit_code']=1; r['state']='FAILED'
  if campaign:
   campaign.finish(); r['campaign']=campaign.r
   if campaign.r.get('cleanup_failures'): r['exit_code']=1; r['state']='FAILED'
  if registered:
   try: register('end')
   except Exception as ex: r['registry_error']=repr(ex); r['exit_code']=1
  for fd in reversed(locks): os.close(fd)
  r['finished_at']=point.now(); r['leases_released']=True; record()
 if role=='receive': print(json.dumps(r),flush=True)
 return r['exit_code']
if __name__=='__main__': raise SystemExit(main())
