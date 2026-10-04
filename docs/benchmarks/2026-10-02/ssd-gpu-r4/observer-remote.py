
from pathlib import Path
import datetime,json,os,time
root=Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')/'ssd-gpu-r4'
def read(p,limit=8192):
 try:
  with p.open() as f:return f.read(limit).strip()
 except OSError:return None
boot=read(Path('/proc/sys/kernel/random/boot_id'));start=time.monotonic();terminal_at=None
seen={};offsets={}
while time.monotonic()-start<7200:
 row={'event':'sample','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'remote_monotonic_s':time.monotonic(),'boot_id':boot,'observer_pid':os.getpid(),
      'temperatures':[],'gpu':[],'cpu_mhz':[],'campaign':None,'benchmark_events':[]}
 for d in sorted(Path('/sys/class/hwmon').glob('hwmon*')):
  name=read(d/'name')
  if name not in ('amdgpu','k10temp','coretemp','nvme'):continue
  for p in sorted(d.glob('temp*_input')):
   raw=read(p)
   row['temperatures'].append({'name':name,'path':str(p),'raw_millic':raw,
      'label':read(p.with_name(p.name[:-6]+'_label'))})
  row.setdefault('fans',[]).extend({'name':name,'path':str(p),'rpm':read(p)} for p in d.glob('fan*_input'))
 for d in sorted(Path('/sys/class/drm').glob('card[0-9]*/device')):
  if not (d/'gpu_busy_percent').exists():continue
  row['gpu'].append({'path':str(d),**{n:read(d/n) for n in ('gpu_busy_percent','pp_dpm_sclk','pp_dpm_mclk','mem_info_gtt_used','mem_info_vram_used')}})
 cpu=read(Path('/proc/cpuinfo'),131072) or ''
 row['cpu_mhz']=[float(s.split(':',1)[1]) for s in cpu.splitlines() if s.startswith('cpu MHz')]
 text=read(root/'state.json',131072)
 if text:
  try:
   state=json.loads(text);row['campaign']={k:state.get(k) for k in ('state','current_arm','error')}
   arm=state.get('current_arm')
   if arm:
    p=root/arm/'results/measurements.jsonl'
    if p.exists():
     with p.open() as f:
      f.seek(offsets.get(arm,0))
      while True:
       pos=f.tell();line=f.readline(4*1024*1024)
       if not line or not line.endswith('\n'):f.seek(pos);break
       try:
        event=json.loads(line)
        keep=('event','rep','warmup','pair','generation','decode_calls','exact_logits_and_tokens','prefill_tokens','cached_tokens','ssd_cached_tokens','output_tokens','prefill_ns','decode_ns','first_token_ns','total_ns','error','exit_code')
        row['benchmark_events'].append({k:event[k] for k in keep if k in event})
       except ValueError:pass
      offsets[arm]=f.tell()
   if state['state'] in ('FAILED','COMPLETED_PENDING_OFFLINE_REGRESSION_ANALYSIS'):
    if terminal_at is None:terminal_at=time.monotonic()
  except (ValueError,OSError) as e:row['campaign_read_error']=str(e)
 print(json.dumps(row,separators=(',',':')),flush=True)
 if terminal_at is not None and time.monotonic()-terminal_at>=15:break
 if text is None and time.monotonic()-start>180:break
 time.sleep(1)
