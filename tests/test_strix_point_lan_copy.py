#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tiny CPU fixtures for resumed LAN transfer integrity; no model or network."""
import hashlib,importlib.util,io,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('lan',Path(__file__).resolve().parents[1]/'tools/strix-point-lan-copy.py')
lan=importlib.util.module_from_spec(spec); spec.loader.exec_module(lan)
class Tests(unittest.TestCase):
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
