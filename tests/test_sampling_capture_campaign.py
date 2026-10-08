#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only capture transport/receipt fixtures; never load weights or use a GPU."""
import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
point = module('capture_point', 'strix-point-campaign.py')
collect = module('capture_collect', 'strix-point-bench-collect.py')

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base_patch = patch.object(point, 'BASE', self.root); self.base_patch.start()
    def tearDown(self):
        self.base_patch.stop(); self.temp.cleanup()
    def fixture(self, name='data', tools=False):
        root = self.root/name; directory = root/'capture'; directory.mkdir(parents=True)
        (root/'manifest.json').write_text('{}')
        rows = [dict(event='identity', schema='synapse-lie.sampling-capture.v'+('2' if tools else '1'),
                     program='lie-sampling-capture', build_id='fixture-runtime', synthetic=False,
                     classification='ORIGINAL-WEIGHT-ROW-CAPTURE', engine='gufo-embedded-f783fedb',
                     source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', dense_sampling='lie-c17-dense',
                     row_encoding='IEEE754-F32-little-endian', decode_mode='ar', context=8192,
                     prefill_chunk=2048, profiles=6, tokens_per_profile=8,
                     eos_policy='stop; un-emitted EOS is captured without position advance' if tools else
                                'ignore; EOS remains an ordinary sampled token')]
        if tools:
            data = b'LIEVOC01'+struct.pack('<I',6)+b''.join(
                struct.pack('<II',1,int(i==5))+bytes([65+i]) for i in range(6))
            (directory/'vocabulary.bin').write_bytes(data)
            rows.append(dict(event='vocabulary',file='vocabulary.bin',tokens=6,
                             bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        # Independent frozen seven-control contract, not an inference fixture.
        controls = ((0,1,0,0,0,0),(1,1,0,.05,0,0),(1,1,32,0,0,0),
                    (.7,.9,0,.05,0,0),(1,1,32,.05,.4,.2),(2,1,0,.2,-.3,-.1))
        for profile, (t,p,k,m,f,a) in enumerate(controls):
            begin = dict(event='profile_begin',profile=profile,vocab=6,prompt_ids=[1,2],
                         generation=dict(temperature=t,top_p=p,top_k=k,min_p=m,
                                         frequency_penalty=f,presence_penalty=a,seed=123))
            if tools:
                begin['constraint'] = dict(format='json_object',required=True,parallel=False,
                                          name='describe_stack',parameters_json='{}',definition_json='{}')
            rows.append(begin); output=[]
            for step in range(3 if tools else 8):
                data=struct.pack('<6f',-1,0,1,2,3,4)
                file=f'profile-{profile}-row-{step}.f32le'; (directory/file).write_bytes(data)
                stop=tools and step==2
                if not stop: output.append(1+step%2)
                row=dict(event='row',profile=profile,step=step,file=file,
                         bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                         token=None if stop else output[-1],position=2+len(output))
                if tools: row.update(emitted=int(not stop),stop=stop)
                rows.append(row)
            complete=dict(event='profile_complete',profile=profile,rows=3 if tools else 8,output_ids=output)
            if tools: complete['tool_call']=dict(name='describe_stack',arguments={'order':'LIFO','size':3})
            rows.append(complete)
        rows.append(dict(event='complete',exit_code=0,profiles=6,rows=18 if tools else 48))
        self.write(root,rows); return root,rows
    def write(self, root, rows):
        (root/'capture/capture.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows))
    def validate(self, root, tools=False):
        return point.validate_sampling_capture(root,'tools' if tools else 'text',8,'fixture-runtime')
    def mtp_fixture(self, name='mtp', tools=False):
        root,old=self.fixture(name,tools); directory=root/'capture'
        for p in directory.glob('*.f32le'): p.unlink()
        identity=copy.deepcopy(old[0]); identity.update(schema='synapse-lie.sampling-capture.v3',decode_mode='mtp',
            mtp_model='/mtp/predictor.gguf',mtp_draft_tokens_requested=7,observer_abi=1,greedy_reservation=1,tools=tools)
        rows=[identity]
        if tools: rows.append(copy.deepcopy(old[1]))
        total=0
        for begin in (r for r in old if r['event']=='profile_begin'):
            rows.append(copy.deepcopy(begin)); profile=begin['profile']; n=cycles=0; output=[]; pending=False
            while len(output)<8:
                limit=1 if not profile else min(8,8-len(output))
                rows.append(dict(event='cycle_begin',profile=profile,cycle=cycles,position=2+len(output),reservation=limit))
                stop=tools and len(output)==5; anchor=0 if stop else 3 if pending else 1
                def trace(kind,token,accepted=0,deferred=0,proposal=None):
                    nonlocal n
                    data=struct.pack('<6f',-1,0,1,2,3,4); file=f'profile-{profile}-trace-{n}.f32le'
                    (directory/file).write_bytes(data)
                    mask=None
                    if tools and kind!='proposal':
                        payload=bytes([0,1,0,0,0,0]); mf=f'profile-{profile}-trace-{n}.u8'; (directory/mf).write_bytes(payload)
                        mask=dict(file=mf,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
                    rows.append(dict(event='sampling_trace',profile=profile,cycle=cycles,index=n,kind=kind,token=token,
                        accepted=accepted,deferred=deferred,rng_before='000000000000007b',rng_after='000000000000007b',
                        logit_count=6,raw=dict(file=file,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),
                        logit_ids=list(range(6)) if kind=='proposal' else [],history_ids=[1,2],penalties=[],allowed=mask,proposal=proposal))
                    n+=1
                trace('target-draw',anchor,deferred=int(pending)); pending=False; emitted=[] if stop else [anchor]
                drafted=accepted=0
                if not stop and profile and limit>1:
                    proposal=dict(ids=[2],probabilities=[1.0],token=2,probability=1.0)
                    trace('proposal',2,proposal=proposal); drafted=1
                    pending=cycles==0; accepted=int(not pending)
                    trace('verification',3 if pending else 2,accepted,proposal=proposal)
                    if accepted: emitted.append(2)
                output.extend(emitted)
                rows.append(dict(event='cycle_complete',profile=profile,cycle=cycles,position=2+len(output),
                                 drafted=drafted,accepted=accepted,stop=stop,output_ids=emitted)); cycles+=1
                if stop: break
            done=dict(event='profile_complete',profile=profile,rows=n,cycles=cycles,output_ids=output)
            if tools: done['tool_call']=dict(name='describe_stack',arguments={'order':'LIFO','size':3})
            rows.append(done); total+=n
        rows.append(dict(event='complete',exit_code=0,profiles=6,rows=total)); self.write(root,rows); return root,rows
    def validate_mtp(self, root, tools=False):
        return point.validate_sampling_capture(root,'tools' if tools else 'text',8,'fixture-runtime','mtp','/mtp/predictor.gguf',7)
    def test_mtp_typed_cycles_and_partial_collection_are_not_probability_acceptance(self):
        for tools in (False,True):
            with self.subTest(tools=tools):
                root,_=self.mtp_fixture('mtp-'+str(tools),tools); result=self.validate_mtp(root,tools)
                self.assertEqual(result['decode_mode'],'mtp'); self.assertEqual(result['profiles'],6)
                self.assertGreater(result['proposals'],0); self.assertGreater(result['accepted_verifications'],0)
                self.assertEqual(result['rejected_verifications'],5); self.assertEqual(result['deferred_draws'],5)
                self.assertFalse(result['probability_mask_MTP_quality_performance_acceptance'])
                inventory=collect.sampling_capture_inventory(root)
                self.assertEqual(inventory,result['artifacts'])
                (root/'capture/profile-5-trace-1151.f32le').write_bytes(b'partial')
                (root/'capture/profile-5-trace-1151.u8').touch()
                self.assertIn('capture/profile-5-trace-1151.u8',collect.sampling_capture_inventory(root))
    def test_mtp_capture_refuses_unbound_identity_and_invalid_controller_states(self):
        root,rows=self.mtp_fixture()
        mutations=[(0,'mtp_model','wrong'),(0,'observer_abi',True),(0,'mtp_draft_tokens_requested',7.),(0,'tools',0)]
        for event,changes in (('cycle_begin',{'reservation':0,'position':99}),
                              ('sampling_trace',{'rng_before':'7b','history_ids':[99],'penalties':[{'token':1,'generated_count':True,'repeated':0}],
                                                 'index':True,'accepted':True}),
                              ('cycle_complete',{'accepted':7,'position':99,'output_ids':[99]}),
                              ('profile_complete',{'cycles':0,'rows':0,'output_ids':[True]*8})):
            i=next(i for i,r in enumerate(rows) if r['event']==event)
            mutations.extend((i,k,v) for k,v in changes.items())
        proposal=next(i for i,r in enumerate(rows) if r.get('kind')=='proposal')
        mutations.append((proposal,'proposal',dict(ids=[2],probabilities=[.5],token=2,probability=.5)))
        for i,key,value in mutations:
            with self.subTest(index=i,key=key):
                changed=copy.deepcopy(rows); changed[i][key]=value; self.write(root,changed)
                with self.assertRaises(RuntimeError): self.validate_mtp(root)
        self.write(root,rows[:-1])
        with self.assertRaisesRegex(RuntimeError,'unordered'): self.validate_mtp(root)
        self.write(root,rows)
        path=root/'capture/profile-0-trace-0.f32le'; path.write_bytes(b'corrupt')
        with self.assertRaisesRegex(RuntimeError,'hash or length'): self.validate_mtp(root)
    def test_mtp_capture_binds_predictor_and_checks_both_weights_after_child_failure(self):
        root,_=self.mtp_fixture(tools=True)
        manifest=dict(authorization='CPU fixture only',action='bench',stack='rocm10-fedora43',transport='distrobox',
            bench_profile='modern-sampling-capture',decode_mode='mtp',capture_mode='tools',capture_row_budget=8,
            bundle=str(self.root),artifacts={'runtime/bin/lie-sampling-capture':'0'*64},runtime_build_id='fixture-runtime',
            model_plan={'files':[{'name':'first-shard.gguf'}]},predictor_plan={'destination':str(self.root)})
        c=point.Campaign(root,manifest); predictor=self.root/'predictor.gguf'; witness={'path':str(predictor)}
        with patch.object(c,'verified_model',return_value=(self.root,[])), \
             patch.object(c,'verified_predictor',return_value=(predictor,witness)), \
             patch.object(c,'run_container') as run,patch.object(c,'check_model_after') as after:
            c.bench(); after.assert_called_once_with([witness]); command=run.call_args.args[0]
            self.assertEqual(command[command.index('--mtp-model')+1],'/mtp/predictor.gguf')
            self.assertEqual(command[command.index('--draft-tokens')+1],'7')
        (root/'capture-artifacts.json').unlink()
        with patch.object(c,'verified_model',return_value=(self.root,[])), \
             patch.object(c,'verified_predictor',return_value=(predictor,witness)), \
             patch.object(c,'run_container',side_effect=RuntimeError('owned MTP child failure')), \
             patch.object(c,'check_model_after') as after,self.assertRaisesRegex(RuntimeError,'owned MTP child failure'):
            c.bench()
        after.assert_called_once_with([witness])
    def test_text_complete_structure_is_not_probability_acceptance(self):
        root,_=self.fixture(); result=self.validate(root)
        self.assertEqual(result['rows_per_profile'],[8]*6)
        self.assertEqual(len(result['artifacts']),49)
        self.assertFalse(result['probability_mask_MTP_quality_performance_acceptance'])
    def test_tool_eos_and_semantic_misses_are_separate_from_structure(self):
        root,rows=self.fixture(tools=True)
        rows[-2]['tool_call']['arguments']={'order':'FIFO','size':0}; self.write(root,rows)
        result=self.validate(root,True)
        self.assertEqual(result['rows'],18); self.assertEqual(result['semantic_matches'],5)
        self.assertEqual(len(result['artifacts']),20)
        self.assertFalse(result['probability_mask_MTP_quality_performance_acceptance'])
    def test_refuses_synthetic_stale_runtime_wrong_mode_and_typed_identity(self):
        root,rows=self.fixture()
        for key,value in (('synthetic',True),('synthetic',0),('build_id','old'),('dense_sampling','gufo'),
                          ('decode_mode','mtp'),('classification','NOT-INFERENCE'),('context',8192.),
                          ('source_pin','wrong'),('eos_policy','stop')):
            with self.subTest(key=key,value=value):
                changed=copy.deepcopy(rows); changed[0][key]=value; self.write(root,changed)
                with self.assertRaisesRegex(RuntimeError,'capture identity'): self.validate(root)
    def test_refuses_missing_duplicate_out_of_order_or_extra_completion(self):
        root,rows=self.fixture()
        for changed in (rows[:-1],rows+[rows[-1]],rows[:2]+rows[3:],rows[:-1]+[dict(rows[-1],rows=47)],
                        rows[:2]+[rows[3],rows[2]]+rows[4:]):
            self.write(root,changed)
            with self.assertRaises(RuntimeError): self.validate(root)
    def test_refuses_row_hash_length_frontier_token_and_path_drift(self):
        root,rows=self.fixture()
        for key,value in (('sha256','0'*64),('bytes',4),('bytes',24.),('position',4),('token',True),
                          ('file','../foreign'),('step',True),('profile',True)):
            with self.subTest(key=key):
                changed=copy.deepcopy(rows); changed[2][key]=value; self.write(root,changed)
                with self.assertRaises(RuntimeError): self.validate(root)
    def test_refuses_changed_filters_prompt_vocabulary_and_tool_constraints(self):
        root,rows=self.fixture(tools=True)
        changes=[(2,'generation',dict(rows[2]['generation'],min_p=.1)),
                 (2,'prompt_ids',[True,2]),(2,'vocab',5),
                 (2,'constraint',dict(rows[2]['constraint'],required=False))]
        for index,key,value in changes:
            changed=copy.deepcopy(rows); changed[index][key]=value; self.write(root,changed)
            with self.assertRaises((RuntimeError,ValueError)): self.validate(root,True)
        changed=copy.deepcopy(rows); changed[1]['sha256']='0'*64; self.write(root,changed)
        with self.assertRaisesRegex(RuntimeError,'vocabulary hash'): self.validate(root,True)
    def test_refuses_incomplete_eos_provisional_call_and_claimed_stop_token(self):
        root,rows=self.fixture(tools=True)
        for changed in (rows[:5]+rows[6:], rows[:6]+[dict(rows[6],event='provisional_call')]+rows[7:]):
            self.write(root,changed)
            with self.assertRaises(RuntimeError): self.validate(root,True)
        for key,value in (('token',5),('position',5),('emitted',False),('stop',1)):
            changed=copy.deepcopy(rows); changed[5][key]=value; self.write(root,changed)
            with self.assertRaises(RuntimeError): self.validate(root,True)
        for args in ({'order':'LIFO','size':True},{'order':'LIFO','size':10},
                     {'order':'LIFO','size':3,'extra':0}):
            changed=copy.deepcopy(rows); changed[6]['tool_call']['arguments']=args; self.write(root,changed)
            with self.assertRaises(RuntimeError): self.validate(root,True)
    def test_refuses_duplicate_keys_nonfinite_json_and_boolean_output_ids(self):
        root,rows=self.fixture(); path=root/'capture/capture.jsonl'; original=path.read_text()
        for data in (original.replace('"profiles":6','"profiles":6,"profiles":6',1),
                     original.replace('"top_p":1','"top_p":NaN',1)):
            path.write_text(data)
            with self.assertRaises(RuntimeError): self.validate(root)
        changed=copy.deepcopy(rows); changed[10]['output_ids'][0]=True; self.write(root,changed)
        with self.assertRaises(RuntimeError): self.validate(root)
    def test_row_symlink_fifo_and_oversize_refuse_without_reading(self):
        root,_=self.fixture(); path=root/'capture/profile-0-row-0.f32le'; path.unlink()
        outside=self.root/'other'; outside.write_bytes(b'foreign')
        path.symlink_to(outside)
        with self.assertRaises((ValueError,OSError)): self.validate(root)
        path.unlink(); os.mkfifo(path)
        with self.assertRaisesRegex(RuntimeError,'bounded regular'): self.validate(root)
        path.unlink()
        with path.open('wb') as f:f.truncate(4*1048576+1)
        with self.assertRaisesRegex(RuntimeError,'bounded regular'): self.validate(root)
    def test_collection_preserves_failed_uncommitted_and_empty_partial_artifacts(self):
        root,rows=self.fixture(); self.write(root,rows[:-1])
        (root/'capture/profile-0-row-127.f32le').write_bytes(b'uncommitted')
        (root/'capture/vocabulary.bin').touch()
        inventory=collect.sampling_capture_inventory(root)
        self.assertIn('capture/profile-0-row-127.f32le',inventory)
        self.assertEqual(inventory['capture/vocabulary.bin']['bytes'],0)
        self.assertEqual(len(inventory),51)
    def test_collection_refuses_unknown_paths_symlinks_fifos_and_oversize(self):
        root,_=self.fixture(); bad=root/'capture/profile-6-row-0.f32le'; bad.touch()
        with self.assertRaisesRegex(RuntimeError,'artifact path'): collect.sampling_capture_inventory(root)
        bad.unlink(); path=root/'capture/profile-0-row-0.f32le'; path.unlink()
        path.symlink_to(root/'manifest.json')
        with self.assertRaises(OSError): collect.sampling_capture_inventory(root)
        path.unlink(); os.mkfifo(path)
        with self.assertRaisesRegex(RuntimeError,'bounded native'): collect.sampling_capture_inventory(root)
        path.unlink()
        with path.open('wb') as f:f.truncate(4*1048576+1)
        with self.assertRaisesRegex(RuntimeError,'bounded native'): collect.sampling_capture_inventory(root)
    def test_campaign_routes_native_tools_and_checks_model_on_child_failure(self):
        root,_=self.fixture(tools=True)
        manifest=dict(authorization='CPU fixture only',action='bench',stack='rocm10-fedora43',
                      transport='distrobox',bench_profile='modern-sampling-capture',decode_mode='ar',
                      capture_mode='tools',capture_row_budget=8,bundle=str(self.root),
                      artifacts={'runtime/bin/lie-sampling-capture':'0'*64},runtime_build_id='fixture-runtime',
                      model_plan={'files':[{'name':'first-shard.gguf'}]})
        c=point.Campaign(root,manifest)
        with patch.object(c,'verified_model',return_value=(self.root,[])), \
             patch.object(c,'run_container') as run, patch.object(c,'check_model_after') as after:
            c.bench(); after.assert_called_once_with([])
            command=run.call_args.args[0]
            self.assertEqual(command[0],'/bundle/runtime/bin/lie-sampling-capture')
            self.assertIn('--tools',command); self.assertNotIn('--suite',command)
            self.assertEqual(command[command.index('--output-dir')+1],'/work/capture')
        (root/'capture-artifacts.json').unlink()
        with patch.object(c,'verified_model',return_value=(self.root,[])), \
             patch.object(c,'run_container',side_effect=RuntimeError('owned child failure')), \
             patch.object(c,'check_model_after') as after, self.assertRaisesRegex(RuntimeError,'owned child failure'):
            c.bench()
        after.assert_called_once_with([])
    def test_collector_stages_nested_rows_and_refuses_existing_hash_drift(self):
        root,_=self.fixture(); label='capture-unit-only'
        local=self.root/'evidence'/label; local.mkdir(parents=True)
        (local/'plan.json').write_text('{}')
        files={str(p.relative_to(root)):p.read_bytes() for p in (root/'capture').iterdir()}
        files.update({name:b'CPU transport fixture; no model or GPU' for name in collect.FILES['sampling-capture']})
        inventory={'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
                            for name,data in files.items()},'result_state':'PASSED','child_exit_code':0,
                   'supervisor_absent':True,'gpu_child_absent':True,'owned_child_absent':True,'lease_free':True}
        def run(argv, **kwargs):
            if argv[0]=='ssh':
                compile(kwargs['input'],'mocked-remote-collector','exec')
                self.assertIn('def sampling_capture_inventory',kwargs['input'])
                return subprocess.CompletedProcess(argv,0,stdout=json.dumps(inventory),stderr='')
            self.assertEqual(argv[0],'scp')
            prefix='pop@192.168.5.161:'+collect.BASE+'/'+label+'/'
            self.assertTrue(argv[-2].startswith(prefix))
            Path(argv[-1]).write_bytes(files[argv[-2][len(prefix):]])
            return subprocess.CompletedProcess(argv,0,stdout='',stderr='')
        with patch.object(collect,'ROOT',self.root), \
             patch.object(sys,'argv',['collector',label,'--kind','sampling-capture']), \
             patch.object(collect.subprocess,'run',side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collect.main(),0)
            saved=json.loads((local/'collection.json').read_text())
            self.assertEqual(len(saved['inventory']['files']),55)
            self.assertEqual((local/'capture/profile-5-row-7.f32le').read_bytes(),files['capture/profile-5-row-7.f32le'])
            (local/'capture/profile-0-row-0.f32le').write_bytes(b'drift')
            self.assertEqual(collect.main(),1)
        self.assertIn('Staged source drift',json.loads((local/'collection.json').read_text())['error'])
    def test_invalid_capture_settings_refuse_before_model_verification(self):
        root,_=self.fixture(); c=point.Campaign(root,dict(authorization='fixture',bench_profile='modern-sampling-capture'))
        with patch.object(c,'verified_model') as verify, self.assertRaises(ValueError):c.bench()
        verify.assert_not_called()
    def test_distrobox_capture_file_records_possible_model_attempt(self):
        root,_=self.fixture()
        c=point.Campaign(root,dict(authorization='fixture',action='bench',stack='rocm10-fedora43',
                                  transport='distrobox',bench_profile='modern-sampling-capture',
                                  decode_mode='ar',distrobox_name='lie-capture-fixture'))
        image='sha256:'+'1'*64; container='c'*64
        child=Mock(pid=12345,returncode=0); child.poll.return_value=0
        inspection={'Image':image,'Id':container,'Config':{'Labels':{'synapse-lie.run':str(root)}}}
        with patch.object(c,'sample'),patch.object(c,'wait_owned_gpu_retirement'), \
             patch.object(c,'command',return_value=subprocess.CompletedProcess([],0,stdout=json.dumps(inspection),stderr='')), \
             patch.object(point,'kfd_group',return_value=123),patch.object(point,'ticks',return_value=42), \
             patch.object(point.subprocess,'run',return_value=subprocess.CompletedProcess([],0)), \
             patch.object(point.subprocess,'Popen',return_value=child):
            c.execute_distrobox(['/bundle/runtime/bin/lie-sampling-capture'],self.root,self.root,image,30)
        self.assertTrue(c.r['model_attempted'])

if __name__=='__main__': unittest.main()
