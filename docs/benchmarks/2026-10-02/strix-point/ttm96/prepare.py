#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# One-shot .161 maintenance, expressly authorized: "procedi con il tuning".
import datetime,fcntl,hashlib,json,os,shutil,stat,subprocess,sys,time
from pathlib import Path
ROOT=Path('/home/pop/workspace/synapse-lie/strix-point-ttm96-r1')
BASE=ROOT.parent
TARGET=Path('/etc/modprobe.d/90-synapse-lie-ttm.conf')
KERNEL='6.16.3-76061603-generic'
INITRD=Path('/boot/initrd.img-'+KERNEL)
CONFIG=b'# SPDX-License-Identifier: MIT\n# Synapse LIE .161: operator-authorized 96 GiB GPU shared-memory limit.\n# 25165824 pages * 4096 bytes; this maximum does not reserve RAM.\noptions ttm pages_limit=25165824\n'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
 with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def syncfile(p):
 with Path(p).open('rb') as f: os.fsync(f.fileno())
def record():
 tmp=ROOT/'prepare-result.tmp'
 tmp.write_text(json.dumps(r,indent=2)+'\n'); syncfile(tmp); tmp.replace(ROOT/'prepare-result.json')
def run(argv):
 p=subprocess.run(argv,text=True,capture_output=True)
 r['commands'].append({'argv':argv,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}); record()
 if p.returncode: raise RuntimeError('Command failed: '+repr(argv))
 return p.stdout
r={'state':'PREFLIGHT','started_at':now(),'authorization':{'quote':'procedi con il tuning','scope':'TTM pages_limit=25165824, current kernel initramfs, reboot, verify HIP, resume transfer'},'commands':[],'exit_code':1}
lock=None
try:
 assert os.geteuid()==0 and os.uname().release==KERNEL
 assert os.environ.get('SUDO_USER')=='pop'
 assert ROOT.resolve()==ROOT and ROOT.stat().st_uid==1000
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='6ca3cc6a-65f5-4c7d-aade-f69b2d99cfc9'
 assert os.sysconf('SC_PAGE_SIZE')==4096
 assert not os.path.lexists(TARGET)
 assert INITRD.is_file() and not INITRD.is_symlink()
 assert not (ROOT/'prepare-result.json').exists()
 lock=os.open(BASE/'campaign.lock',os.O_RDWR|os.O_NOFOLLOW)
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 st=os.fstat(lock); live=(BASE/'campaign.lock').stat()
 assert st.st_uid==1000 and (st.st_dev,st.st_ino)==(live.st_dev,live.st_ino)
 r['lease']={'device':st.st_dev,'inode':st.st_ino}
 r['before']={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'kernel':KERNEL,'cmdline':Path('/proc/cmdline').read_text().strip(),'pages_limit':int(Path('/sys/module/ttm/parameters/pages_limit').read_text()),'page_pool_size':int(Path('/sys/module/ttm/parameters/page_pool_size').read_text()),'gtt_total':int(Path('/sys/class/drm/card1/device/mem_info_gtt_total').read_text()),'config_absent':True,'initramfs_sha256':sha(INITRD),'initramfs_bytes':INITRD.stat().st_size}
 assert r['before']['pages_limit']==16179861
 assert shutil.disk_usage('/boot').free>2*INITRD.stat().st_size+1024**3
 record()
 backup=ROOT/'initramfs.before.img'
 with INITRD.open('rb') as src, backup.open('xb') as dst: shutil.copyfileobj(src,dst,1024*1024)
 shutil.copystat(INITRD,backup); syncfile(backup)
 assert sha(backup)==r['before']['initramfs_sha256']
 r['backup']=str(backup); r['state']='BACKED_UP'; record()
 fd=os.open(TARGET,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
 with os.fdopen(fd,'wb') as f: f.write(CONFIG); f.flush(); os.fsync(f.fileno())
 os.chmod(TARGET,0o644)
 r['config']={'path':str(TARGET),'sha256':sha(TARGET),'text':CONFIG.decode(),'uid':TARGET.stat().st_uid,'mode':oct(stat.S_IMODE(TARGET.stat().st_mode))}
 assert TARGET.read_bytes()==CONFIG
 r['state']='REBUILDING_INITRAMFS'; record()
 log=ROOT/'update-initramfs.log'
 with log.open('x') as output:
  p=subprocess.Popen(['update-initramfs','-u','-k',KERNEL],stdout=output,stderr=subprocess.STDOUT,env=dict(os.environ,LC_ALL='C'))
  r['initramfs_pid']=p.pid; record()
  while p.poll() is None:
   samples=[]
   for hw in sorted(Path('/sys/class/hwmon').glob('hwmon*')):
    if (hw/'name').read_text().strip() in ('k10temp','amdgpu','nvme'):
     for t in hw.glob('temp*_input'): samples.append({'sensor':str(t),'name':(hw/'name').read_text().strip(),'c':int(t.read_text())/1000})
   with (ROOT/'thermal.jsonl').open('a') as f: f.write(json.dumps({'at':now(),'samples':samples})+'\n')
   time.sleep(1)
 r['commands'].append({'argv':['update-initramfs','-u','-k',KERNEL],'exit_code':p.returncode,'log':str(log)}); record()
 if p.returncode: raise RuntimeError('Initramfs rebuild failed; retain backup, do not reboot')
 listing=run(['lsinitramfs',str(INITRD)])
 (ROOT/'initramfs-contents.txt').write_text(listing)
 assert 'etc/modprobe.d/90-synapse-lie-ttm.conf' in listing.splitlines()
 r['after_prepare']={'initramfs_sha256':sha(INITRD),'initramfs_bytes':INITRD.stat().st_size,'config_in_initramfs':True,'config_sha256':sha(TARGET)}
 assert r['after_prepare']['config_sha256']==r['config']['sha256']
 syncfile(INITRD); os.sync()
 r['state']='PREPARED'; r['exit_code']=0
except BaseException as e:
 r['error']=repr(e); r['state']='FAILED'
finally:
 if lock is not None: os.close(lock); r['lease_released_at']=now()
 r['finished_at']=now(); record()
print(json.dumps({k:v for k,v in r.items() if k!='commands'}))
sys.exit(r['exit_code'])
