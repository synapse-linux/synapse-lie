#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Copy admitted UD suffixes directly from .157 to .161, with a scoped SSH agent.
The local host stages controls and receives receipts; model bytes stay remote.
No SSH account configuration or source model file is modified.
"""
import argparse,base64,hashlib,json,os,re,signal,subprocess,sys,time
from pathlib import Path
SSH=['ssh','-F','/dev/null','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3']

def save(path,value):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def retire(child):
 if child is not None and child.poll() is None:
  child.terminate()
  try: child.wait(timeout=15)
  except subprocess.TimeoutExpired: child.kill();child.wait()

def remote(root,dest):
 assert root.resolve()==root and root.stat().st_uid==os.getuid()
 assert os.environ['SSH_CONNECTION'].split()[2]=='192.168.5.157'
 assert dest.parent==Path('/home/pop/workspace/synapse-lie')
 assert os.environ.get('SSH_AUTH_SOCK')
 record={'pid':os.getpid(),'role':'direct-source-controller','source_root':str(root),'destination_root':str(dest),'model_bytes_via_local_host':False}
 sender=receiver=None
 def interrupted(sig,frame): raise InterruptedError('Direct copy interrupted: '+str(sig))
 for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,interrupted)
 try:
  with (root/'sender-stderr.log').open('xb') as se,(root/'receiver-stderr.log').open('xb') as re,(root/'receiver-stdout.log').open('xb') as ro:
   sender=subprocess.Popen([sys.executable,'-B',str(root/'lan-copy.py'),'send',str(root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=se)
   argv=SSH+['-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(root/'known_hosts'),'pop@192.168.5.161','python3 -B '+str(dest/'lan-copy.py')+' receive '+str(dest)]
   record['receiver_argv']=argv;record['sender_pid']=sender.pid
   receiver=subprocess.Popen(argv,stdin=sender.stdout,stdout=ro,stderr=re);sender.stdout.close()
   record['receiver_ssh_pid']=receiver.pid;save(root/'direct-controller-result.json',record)
   code=receiver.wait(timeout=14500);record['receiver_exit_code']=code
   if code==0: sender.stdin.write(b'VERIFIED\n');sender.stdin.flush()
   sender.stdin.close();record['sender_exit_code']=sender.wait(timeout=30)
 except BaseException as ex: record['error']=repr(ex)
 finally:
  # Receiver EOF/cleanup and sender finally retire their own service/leases.
  retire(receiver);retire(sender)
  for name,p in (('receiver',receiver),('sender',sender)):
   if p: record.setdefault(name+'_exit_code',p.returncode)
  record['exit_code']=0 if record.get('sender_exit_code')==record.get('receiver_exit_code')==0 else 1
  save(root/'direct-controller-result.json',record);print(json.dumps(record),flush=True)
 return record['exit_code']

def local(label,manifest):
 assert re.fullmatch('[a-z0-9-]{1,48}',label)
 repo=Path(__file__).resolve().parents[1];out=repo/'evidence'/label;out.mkdir()
 m=json.loads(manifest.read_text())
 files={'manifest.json':(json.dumps(m,indent=2)+'\n').encode(),'campaign.py':(repo/'tools/strix-point-campaign.py').read_bytes(),'lan-copy.py':(repo/'tools/strix-point-lan-copy.py').read_bytes(),'direct-controller.py':Path(__file__).read_bytes()}
 hosts={'send':('paperboy@192.168.5.157','/home/paperboy/synapse-lie-strix-point/'+label),'receive':('pop@192.168.5.161','/home/pop/workspace/synapse-lie/'+label)}
 r={'hosts':hosts,'model_bytes_via_local_host':False,'source_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()},'staging':{}}
 keys=subprocess.run(['ssh-keygen','-F','192.168.5.161'],capture_output=True,text=True,check=True).stdout
 known='\n'.join(x for x in keys.splitlines() if x and not x.startswith('#'))+'\n'
 assert known.strip()
 files['known_hosts']=known.encode()
 for name,data in files.items(): (out/name).write_bytes(data)
 agent=connection=None
 def interrupted(sig,frame): raise InterruptedError('Copy controller interrupted: '+str(sig))
 for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,interrupted)
 sock=repo/'evidence'/('copy-'+str(os.getpid())+'.sock')
 try:
  for role,(host,path) in hosts.items():
   program='import pathlib,base64,os\np=pathlib.Path('+repr(path)+')\nassert p.parent.resolve()==p.parent and p.parent.stat().st_uid==os.getuid()\np.mkdir()\nfiles='+repr({k:base64.b64encode(v).decode() for k,v in files.items()})+'\nfor name,data in files.items():\n with (p/name).open("xb") as f: f.write(base64.b64decode(data))\n'
   p=subprocess.run(SSH+[host,'python3 -'],input=program,text=True,capture_output=True,timeout=30)
   r['staging'][role]={'exit_code':p.returncode,'stderr':p.stderr};save(out/'controller-result.json',r);p.check_returncode()
  with (out/'agent.log').open('x') as log:
   agent=subprocess.Popen(['ssh-agent','-D','-a',str(sock)],stdin=subprocess.DEVNULL,stdout=log,stderr=log)
   r['owned_agent_pid']=agent.pid
   for _ in range(50):
    if sock.exists(): break
    time.sleep(.05)
   if not sock.exists(): raise RuntimeError('Owned agent did not start')
   env=dict(os.environ,SSH_AUTH_SOCK=str(sock),SSH_ASKPASS_REQUIRE='never')
   argv=['ssh-add','-q','-t','18000','-H',str(Path.home()/'.ssh/known_hosts'),'-h','paperboy@192.168.5.157','-h','192.168.5.157>pop@192.168.5.161',str(Path.home()/'.ssh/id_ed25519')]
   p=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
   r['agent_load']={'exit_code':p.returncode,'stderr':p.stderr,'constraints':['paperboy@192.168.5.157','192.168.5.157>pop@192.168.5.161'],'lifetime_seconds':18000};save(out/'controller-result.json',r);p.check_returncode()
   host,source=hosts['send'];dest=hosts['receive'][1]
   argv=SSH+['-A',host,'python3 -B '+source+'/direct-controller.py remote '+source+' '+dest]
   r['argv']=argv
   with (out/'controller-stdout.log').open('x') as stdout,(out/'controller-stderr.log').open('x') as stderr:
    connection=subprocess.Popen(argv,env=env,stdout=stdout,stderr=stderr)
    r['connection_pid']=connection.pid;save(out/'controller-result.json',r)
    r['exit_code']=connection.wait(timeout=14600)
 except BaseException as ex: r['error']=repr(ex);r['exit_code']=1
 finally:
  retire(connection);retire(agent)
  if agent:r['owned_agent_exit_code']=agent.returncode
  save(out/'controller-result.json',r);print(json.dumps(r),flush=True)
 return r.get('exit_code',1)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['local','remote']);parser.add_argument('first');parser.add_argument('second',type=Path)
 args=parser.parse_args()
 raise SystemExit(remote(Path(args.first),args.second) if args.mode=='remote' else local(args.first,args.second))
