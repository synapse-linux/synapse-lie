# SPDX-License-Identifier: MIT
"""Interrupt a fake compiler group through the actual build helper. No HIP or GPU."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

def running(identity):
    pid,start=identity
    try:
        fields=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
        return fields[0] != 'Z' and fields[19] == start
    except FileNotFoundError:
        return False

class Interruption(unittest.TestCase):
    def test_owned_nested_compiler_retired_and_exit_recorded(self):
        with tempfile.TemporaryDirectory(prefix='lie-build-interruption-') as tmp:
            root=Path(tmp)
            for name in ('build','evidence','cmake/gufo-runtime','.deps/gufo-f783fedb','third_party','bin'):
                (root/name).mkdir(parents=True)
            (root/'cmake/gufo-runtime/CMakeLists.txt').write_text('# fixture\n')
            (root/'cmake/hip-target.cmake').write_text('# fixture\n')
            data=b'fixture only\n'
            (root/'.deps/gufo-f783fedb/fixture').write_bytes(data)
            (root/'third_party/gufo-source.json').write_text(json.dumps({'files':{'fixture':hashlib.sha256(data).hexdigest()}}))
            fake=root/'bin/cmake'
            fake.write_text('#!'+sys.executable+'\nimport json,os,pathlib,subprocess,sys,time\n'
                            'assert sys.argv[1:]==["--version"]\n'
                            'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])\n'
                            'identities=[[p,pathlib.Path("/proc",str(p),"stat").read_text().rsplit(")",1)[1].split()[19]] for p in (os.getpid(),child.pid)]\n'
                            'pathlib.Path("pids.json").write_text(json.dumps(identities))\n'
                            'time.sleep(60)\n')
            fake.chmod(0o700)
            program='import importlib.util,pathlib,sys; s=importlib.util.spec_from_file_location("build",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.ROOT=pathlib.Path(sys.argv[2]); sys.argv=["build-gufo.py","fixture","--qwen-only"]; m.main()'
            env=dict(os.environ,PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
            env.pop('SSH_CONNECTION',None)
            with (root/'outer.log').open('w') as log:
                child=subprocess.Popen([sys.executable,'-B','-c',program,str(ROOT/'tools/build-gufo.py'),str(root)],env=env,stdout=log,stderr=log,start_new_session=True)
                pids=[]
                try:
                    deadline=time.monotonic()+5
                    while not (root/'pids.json').exists() and child.poll() is None and time.monotonic()<deadline:
                        time.sleep(0.02)
                    self.assertTrue((root/'pids.json').exists())
                    pids=json.loads((root/'pids.json').read_text())
                    child.send_signal(signal.SIGTERM)
                    self.assertNotEqual(child.wait(timeout=5),0)
                    deadline=time.monotonic()+2
                    while any(running(pid) for pid in pids) and time.monotonic()<deadline:
                        time.sleep(0.02)
                    self.assertFalse(any(running(pid) for pid in pids))
                    receipt=json.loads((root/'evidence/fixture/result.json').read_text())
                    self.assertEqual(receipt['state'],'FAILED')
                    self.assertEqual(receipt['commands'][0]['exit_code'],-signal.SIGTERM)
                    self.assertTrue(receipt['commands'][0]['interrupted'])
                finally:
                    if child.poll() is None:
                        child.kill();child.wait()
                    # Only identities created by this fixture, if its assertion failed.
                    for identity in pids:
                        if running(identity):
                            try: os.kill(identity[0],signal.SIGKILL)
                            except ProcessLookupError: pass

if __name__=='__main__':
    unittest.main()
