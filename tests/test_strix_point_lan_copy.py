#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tiny CPU fixtures for resumed LAN transfer integrity; no model or network."""
import hashlib,importlib.util,io,os,selectors,subprocess,sys,tempfile,time,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('lan',Path(__file__).resolve().parents[1]/'tools/strix-point-lan-copy.py')
lan=importlib.util.module_from_spec(spec); spec.loader.exec_module(lan)
class Tests(unittest.TestCase):
 def test_real_pipe_eof_precedes_ack(self):
  program='import importlib.util,sys; s=importlib.util.spec_from_file_location("lan",'+repr(str(Path(lan.__file__).resolve()))+'); m=importlib.util.module_from_spec(s);s.loader.exec_module(m);sys.stdout.buffer.write(b"payload");m.end_payload(sys.stdout.buffer);raise SystemExit(0 if sys.stdin.buffer.readline()==b"VERIFIED\\n" else 1)'
  child=subprocess.Popen([sys.executable,'-B','-c',program],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   data=b''; deadline=time.monotonic()+3
   with selectors.DefaultSelector() as poll:
    poll.register(child.stdout,selectors.EVENT_READ)
    while True:
     self.assertTrue(poll.select(max(0,deadline-time.monotonic())),'Sender withheld EOF while waiting for ACK')
     part=os.read(child.stdout.fileno(),1024)
     if not part:break
     data+=part
   self.assertEqual(data,b'payload');self.assertIsNone(child.poll())
   child.stdin.write(b'VERIFIED\n');child.stdin.flush()
   self.assertEqual(child.wait(timeout=3),0)
  finally:
   if child.poll() is None:child.terminate();child.wait(timeout=3)
   child.stdin.close();child.stdout.close();child.stderr.close()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.dest=Path(self.tmp.name)/'test.gguf'
  self.part=self.dest.with_suffix('.gguf.part'); self.data=b'original fixture payload'
  self.row={'bytes':len(self.data),'offset':7,'sha256':hashlib.sha256(self.data).hexdigest()}
  self.part.write_bytes(self.data[:7])
 def tearDown(self): self.tmp.cleanup()
 def receive(self,payload): return lan.receive(self.row,self.dest,io.BytesIO(payload),lambda _:None)
 def test_resume_hashes_prefix_and_publishes(self):
  r=self.receive(self.data[7:]); self.assertEqual(self.dest.read_bytes(),self.data)
  self.assertFalse(self.part.exists()); self.assertEqual(r['sha256'],self.row['sha256'])
 def test_corrupt_prefix_never_publishes(self):
  self.part.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'SHA-256'): self.receive(self.data[7:])
  self.assertFalse(self.dest.exists()); self.assertTrue(self.part.exists())
 def test_truncated_suffix_kept_partial(self):
  with self.assertRaisesRegex(ValueError,'Truncated'): self.receive(self.data[7:-1])
  self.assertFalse(self.dest.exists()); self.assertTrue(self.part.exists())
 def test_changed_offset_refused_before_append(self):
  self.row['offset']=8
  with self.assertRaisesRegex(ValueError,'prefix changed'): self.receive(self.data[8:])
  self.assertEqual(self.part.read_bytes(),self.data[:7])
 def test_existing_good_shard_is_reverified(self):
  self.part.unlink(); self.dest.write_bytes(self.data); self.row['offset']=len(self.data)
  self.assertTrue(self.receive(b'')['reverified_existing'])
 def test_existing_bad_shard_is_not_overwritten(self):
  self.part.unlink(); self.dest.write_bytes(b'x'*len(self.data)); self.row['offset']=len(self.data)
  with self.assertRaisesRegex(ValueError,'Published'): self.receive(b'')
  self.assertEqual(self.dest.read_bytes(),b'x'*len(self.data))
if __name__=='__main__': unittest.main()
