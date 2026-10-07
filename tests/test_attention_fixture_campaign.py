#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional HOST-only controller checks; all GPU/container commands are mocked."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
point = module('attention_point', 'strix-point-campaign.py')
collect = module('attention_collect', 'strix-point-bench-collect.py')

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.base = patch.object(point, 'BASE', self.root); self.base.start()
    def tearDown(self):
        self.base.stop(); self.temp.cleanup()
    def fixture(self, name='on', enabled=True):
        root = self.root/name; directory = root/'attention'; directory.mkdir(parents=True)
        (root/'manifest.json').write_text('{}')
        records = [dict(event='identity', schema='synapse-lie.attention-fixture.v1',
            program='lie-attention-qualify', build_id='host-mocked-receipt',
            source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
            synthetic=True, component_only=True, model_inference=False, host_fixture=False,
            long_context_wmma=enabled, classification='GENERATED-COMPONENT-NOT-MODEL-INFERENCE',
            encoding='IEEE754-F32/U32-little-endian', cases=13, width=6144,
            uniform_max_abs_error_limit=1e-6)]
        # Frozen independent public test geometry. These records simulate the
        # transport contract; zeros are not claimed as any GPU/model output.
        specs = ((16384,4,512,False,False),(262144,4,512,False,False),
            (262145,1,17,False,False),(262147,3,512,False,False),
            (524288,4,512,False,False),(524289,1,17,False,False),
            (1048576,1,32,False,False),(1048576,7,512,False,False),
            (1048576,7,1536,False,False),(1048576,1,2051,False,False),
            (1048576,1,2052,False,False),(1048576,3,0,True,False),
            (1048576,7,512,False,True))
        for index,(end,rows,selected,zero_mask,zero_query) in enumerate(specs):
            start=end-rows; pool=start//4; prefix=rows*selected
            base=16384 if start>=65536 else 0; short_start=(base+prefix)*4+start%4
            short_end=short_start+rows; tails=(end+3)//4-pool
            deep_pitch=((end+3)//4+31)//32; short_pitch=((short_end+3)//4+31)//32
            deep_capacity=(end+3)//4*4; short_capacity=(short_end+3)//4*4
            refusal=not enabled and deep_pitch>2048
            j=dict(event='case',index=index,end=end,rows=rows,selections=selected,
                deep_start=start,short_start=short_start,deep_capacity=deep_capacity,
                short_capacity=short_capacity,deep_pitch=deep_pitch,short_pitch=short_pitch,
                short_base=base,prefix_blocks=prefix,block_count=prefix+tails,values=rows*6144,
                zero_mask=zero_mask,zero_query=zero_query,gpu_execution=True,short_accepted=True,
                accepted=not refusal,expected_refusal=refusal,output_unchanged=refusal,
                exact=not refusal,numerical=True,passed=True,artifacts_complete=True,
                primary_error=0,cleanup_error=0,adapter_exit_code=0,refusal=2 if refusal else 0,
                device_arch='gfx1150',uniform_oracle_applicable=zero_query,uniform_max_abs_error=0,
                requested_device_bytes=2*(deep_capacity+short_capacity)*512*2+
                rows*(deep_pitch+short_pitch)*4+rows*6144*16+(prefix+tails)*4)
            block_ids=[i*pool//prefix for i in range(prefix)]+list(range(pool,pool+tails))
            deep_mask=[0]*(rows*deep_pitch); short_mask=[0]*(rows*short_pitch)
            for i,block in enumerate(block_ids[:prefix]):
                row=i//selected; deep_mask[row*deep_pitch+block//32] |= 1<<(block%32)
                short_block=base+i; short_mask[row*short_pitch+short_block//32] |= 1<<(short_block%32)
            if not zero_mask:
                for row in range(rows):
                    deep_mask[row*deep_pitch+pool//32] |= 1<<(pool%32)
                    block=base+prefix; short_mask[row*short_pitch+block//32] |= 1<<(block%32)
            values = dict(deep_output=(b'\xff' if refusal else b'\0')*(rows*6144*4),
                short_output=b'\0'*(rows*6144*4),blocks=struct.pack('<'+'I'*len(block_ids),*block_ids),
                deep_mask=struct.pack('<'+'I'*len(deep_mask),*deep_mask),
                short_mask=struct.pack('<'+'I'*len(short_mask),*short_mask))
            suffixes=dict(deep_output='deep.f32',short_output='short.f32',blocks='blocks.u32',
                          deep_mask='deep-mask.u32',short_mask='short-mask.u32')
            for key,data in values.items():
                file=f'case-{index:02d}.{suffixes[key]}'; (directory/file).write_bytes(data)
                j[key]=dict(file=file,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
            records.append(j)
        records.append(dict(event='complete',exit_code=0,completed_cases=13))
        self.write(root,records); return root,records
    def write(self, root, records):
        (root/'attention/attention.jsonl').write_text(''.join(json.dumps(j,separators=(',',':'))+'\n' for j in records))
    def validate(self, root, enabled=True):
        return point.validate_attention_fixture(root,'host-mocked-receipt',enabled)
    def test_complete_on_and_off_receipts_preserve_all_outputs(self):
        root,_=self.fixture(); result=self.validate(root)
        self.assertFalse(result['model_inference']); self.assertEqual(result['cases'],13)
        self.assertEqual(len(result['artifacts']),66); self.assertEqual(result['expected_refusals'],0)
        root,_=self.fixture('off',False); result=self.validate(root,False)
        self.assertEqual(result['expected_refusals'],11)
        self.assertEqual(len(collect.attention_fixture_inventory(root)),66)
    def test_refuses_wrong_identity_typed_geometry_and_fault_flags(self):
        root,records=self.fixture()
        changes=[(0,'host_fixture',True),(0,'build_id','old'),(0,'model_inference',True),
                 (0,'source_pin','old'),(0,'long_context_wmma',1),(0,'cases',13.),
                 (1,'end',True),(1,'gpu_execution',False),(1,'requested_device_bytes',0),
                 (1,'primary_error',1),(1,'cleanup_error',1),(1,'refusal',2),
                 (1,'device_arch','gfx1151'),(1,'passed',False),
                 (0,'uniform_max_abs_error_limit',1e-3),(13,'uniform_max_abs_error',1e-3)]
        for index,key,value in changes:
            with self.subTest(key=key):
                changed=copy.deepcopy(records); changed[index][key]=value; self.write(root,changed)
                with self.assertRaises(RuntimeError): self.validate(root)
    def test_refuses_raw_hash_mismatch_and_rehashed_output_or_mask_corruption(self):
        root,records=self.fixture()
        for key in ('deep_output','deep_mask','blocks'):
            with self.subTest(key=key):
                changed=copy.deepcopy(records); item=changed[1][key]
                path=root/'attention'/item['file']; original=path.read_bytes()
                data=bytes([original[0]^1])+original[1:]; path.write_bytes(data)
                self.write(root,changed)
                with self.assertRaisesRegex(RuntimeError,'hash/length'): self.validate(root)
                item['sha256']=hashlib.sha256(data).hexdigest(); self.write(root,changed)
                with self.assertRaises(RuntimeError): self.validate(root)
                path.write_bytes(original)
        changed=copy.deepcopy(records)
        for key in ('deep_output','short_output'):
            item=changed[1][key]; path=root/'attention'/item['file']; data=struct.pack('<I',0x7fc00000)+path.read_bytes()[4:]
            path.write_bytes(data); item['sha256']=hashlib.sha256(data).hexdigest()
        self.write(root,changed)
        with self.assertRaisesRegex(RuntimeError,'Nonfinite'): self.validate(root)
    def test_refuses_missing_duplicate_or_extra_terminal_and_duplicate_keys(self):
        root,records=self.fixture()
        for changed in (records[:-1],records+[records[-1]],records[:2]+records[3:],
                        records[:-1]+[dict(records[-1],completed_cases=12)]):
            self.write(root,changed)
            with self.assertRaises(RuntimeError): self.validate(root)
        self.write(root,records); path=root/'attention/attention.jsonl'
        path.write_text(path.read_text().replace('"cases":13','"cases":13,"cases":13',1))
        with self.assertRaisesRegex(RuntimeError,'Duplicate'): self.validate(root)
    def test_collection_preserves_empty_partial_and_refuses_unsafe_paths(self):
        root=self.root/'partial'; directory=root/'attention'; directory.mkdir(parents=True)
        (directory/'attention.jsonl').write_text('{"event":"failed"}\n')
        path=directory/'case-12.deep.f32'; path.touch()
        self.assertEqual(collect.attention_fixture_inventory(root)['attention/'+path.name]['bytes'],0)
        path.unlink(); path.symlink_to(directory/'attention.jsonl')
        with self.assertRaises(OSError): collect.attention_fixture_inventory(root)
        path.unlink(); os.mkfifo(path)
        with self.assertRaisesRegex(RuntimeError,'bounded attention'): collect.attention_fixture_inventory(root)
        path.unlink(); path.write_bytes(b'')
        with path.open('wb') as f:f.truncate(2**20+1)
        with self.assertRaisesRegex(RuntimeError,'bounded attention'): collect.attention_fixture_inventory(root)
        path.unlink(); (directory/'case-13.deep.f32').touch()
        with self.assertRaisesRegex(RuntimeError,'artifact path'): collect.attention_fixture_inventory(root)
    def test_campaign_is_model_free_and_preserves_child_failure(self):
        root,_=self.fixture(); manifest=dict(authorization='HOST mock only',action='bench',
            bench_profile='modern-attention-fixture',stack='rocm10-fedora43',transport='docker',
            long_context_wmma=True,runtime_build_id='host-mocked-receipt',bundle=str(self.root),
            artifacts={'runtime/bin/lie-attention-qualify':'0'*64})
        c=point.Campaign(root,manifest)
        with patch.object(c,'run_container') as run, patch.object(c,'verified_model',side_effect=AssertionError('no model')):
            c.bench()
        run.assert_called_once_with(['/bundle/runtime/bin/lie-attention-qualify','--run','--output-dir','/work/attention'],
                                    str(self.root),300)
        self.assertFalse(c.r['model_attempted'])
        c=point.Campaign(root,manifest)
        with patch.object(c,'run_container',side_effect=RuntimeError('owned child failure')):
            with self.assertRaisesRegex(RuntimeError,'owned child failure'): c.bench()
        self.assertEqual(len(collect.attention_fixture_inventory(root)),66)
        for key,value in (('long_context_wmma',1),('model_plan',{}),('predictor_plan',{}),('transport','distrobox')):
            bad=dict(manifest); bad[key]=value; c=point.Campaign(root,bad)
            with patch.object(c,'run_container') as run:
                with self.assertRaises(ValueError): c.bench()
                run.assert_not_called()

if __name__ == '__main__': unittest.main()
