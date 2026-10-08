# SPDX-License-Identifier: MIT
"""HOST bank-provenance/profile fixtures, not original training or GPU evidence."""
import copy
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value

profile = module('steering_response_profile', ROOT/'tools/strix-point-steering-quality-profile.py')
wire = module('steering_response_HOST_wire', ROOT/'tests/test_strix_point_steering_quality.py')
supervision = module('steering_response_HOST_children', ROOT/'tests/test_strix_point_steering_quality_run.py')
NATIVE = os.environ.get('LIE_STEERING_NATIVE_CLIENT')

def identity(payload):
    return {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


class Profile(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in profile.HELPERS:
            shutil.copyfile(ROOT/'tools'/name, root/name)
        bank = struct.pack('<4f', .6, .8, -.8, .6)
        (root/'direction.ffn.f32').write_bytes(bank)
        config = wire.config(); config['bank_sha256'] = identity(bank)['sha256']
        corpus = (json.dumps(wire.DATA)+'\n').encode()
        (root/'corpus.json').write_bytes(corpus)
        settings = (json.dumps(config)+'\n').encode()
        (root/'steering-quality-settings.json').write_bytes(settings)
        manifest = {'action':'bench', 'bench_profile':'modern-steering-quality', 'stack':'rocm10-fedora43',
            'transport':'distrobox', 'decode_mode':'ar', 'runtime_build_id':'HOST-mocked-original-shape',
            'runtime_source_pin':'a'*40, 'source_commit':'b'*40, 'bundle_manifest_sha256':'c'*64,
            'artifacts':{'runtime/bin/'+name:'d'*64 for name in
                         ('synapse-lie-server','synapse-lie-bench','lie-steering-build')},
            'model_plan':{'repository':'HOST-model-never-opened','revision':'e'*40,
                          'files':[{'name':'HOST-never-opened.gguf','bytes':1,'sha256':'f'*64}]},
            'bundle':'/HOST-bundle-not-opened', 'steering_quality':config,
            'steering_quality_settings_sha256':identity(settings)['sha256'],
            'steering_quality_corpus':identity(corpus), 'steering_quality_load_timeout_seconds':30,
            'steering_quality_helpers':{name:identity((root/name).read_bytes())['sha256'] for name in profile.HELPERS}}
        receipt = {'schema':'synapse-lie.original-steering-capture-qualification.v1',
            'state':profile.RECEIPT_STATE, 'runtime_source_commit':manifest['source_commit'],
            'runtime_build_id':manifest['runtime_build_id'], 'upstream_source_pin':manifest['runtime_source_pin'],
            'bundle_manifest_sha256':manifest['bundle_manifest_sha256'], 'native_builder_sha256':'d'*64,
            'source_model':copy.deepcopy(manifest['model_plan']), 'training_corpus':identity(corpus),
            'actual_exits':{name:0 for name in ('controller','supervisor','native_builder','collector','strong_closure','independent_review')},
            'capture':{'schema':'synapse-lie.point-steering-build.v1','state':'PASSED',
                'classification':'ORIGINAL_ACTIVATION_CAPTURE_LEARNED_QUALITY_UNQUALIFIED',
                'actual_native_exit_code':0, 'pairs':100, 'source_inputs':profile.prompts(wire.DATA),
                'model_generation_or_quality_tested':False, 'layers':2, 'width':2, 'ffn_branches':2,
                'captured_rows':400, 'raw':{'bytes':6400,'sha256':'0'*64},
                'settings':{'components':'ffn','rope':'native','prompt_format':'chat',
                            'context':config['context'],'prefill_chunk':config['chunk']},
                'native_identity':{'synthetic':False,'program':'lie-steering-build',
                    'build_id':manifest['runtime_build_id'],'source_pin':manifest['runtime_source_pin'],
                    'engine':config['fingerprint']}, 'banks':{'direction.ffn.f32':identity(bank)}},
            'closure':{'state':profile.CLOSURE_STATE, 'identities':[
                {'role':role,'pid':100+i,'start_ticks':200+i,'exact_identity_absent':True}
                for i,role in enumerate(('supervisor','Distrobox launcher','observed container init','observed native GPU owner'))],
                'model_stats_reverified_unchanged':True,'container_cgroup':{'empty':True},
                'whole_container_process_scans':[{'processes_checked':10,'owned_cgroup_matches':[],'unreadable':[]} for _ in range(2)],
                'original_lease':{'free_briefly':True,'released':True}},
            'ownership':{'all_four_specific_current_non_use':True,'all_four_verified_release_notifications':True,
                         'standing_reservation_or_future_grant':False}}
        self.receipt(root, manifest, receipt)
        campaign = types.SimpleNamespace(root=root,m=manifest,r={},record=Mock(),
            verified_model=Mock(return_value=(root/'HOST-model-not-opened',[{'HOST-stat-fixture':True}])),
            check_model_after=Mock(),run_container=Mock())
        return campaign, receipt

    def receipt(self, root, manifest, receipt):
        payload = (json.dumps(receipt)+'\n').encode(); (root/'steering-training-receipt.json').write_bytes(payload)
        manifest['steering_quality_training_receipt'] = identity(payload)

    def execute(self, campaign, *, wrong=False, mutate_wire=False, replace_input=False,
                missing_result=False, corrupt_partial=False, native=False):
        prepared = profile.preflight(campaign)
        runner, root = prepared['supervisor'], campaign.root
        rows,cases,snapshots = wire.fixture()
        if wrong:
            answer=json.loads(rows['bank'][1]['assistant']['content']); answer['answer']='wrong'
            wire.change_answer(rows['bank'][1],json.dumps(answer))
        children={}; server=None; thread=None; requests=[]; errors=[]
        real_popen=runner.subprocess.Popen; real_identity=runner.owned.process_identity
        if native:
            class Handler(http.server.BaseHTTPRequestHandler):
                def log_message(self,*_args):pass
                def do_POST(self):
                    try:
                        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(body)
                        sample,snapshot=wire.synthetic_reply(body,'chat-PROFILE-'+str(len(requests)))
                        snapshots[snapshot['id']]=snapshot
                        payload=(''.join('data: '+json.dumps(c)+'\n\n' for c in sample['response_chunks'])+'data: [DONE]\n\n').encode()
                        self.send_response(200);self.send_header('Content-Type','text/event-stream')
                        self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
                    except BaseException as error:errors.append(repr(error));self.close_connection=True
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def launched(argv,**kwargs):
            phase='bank' if '--dir-steering-file' in argv or '/bank/' in ' '.join(argv) else 'absent'
            role='server' if argv[0]=='HOST-server' else 'client'
            if phase=='bank' and role=='server':
                self.assertIsNotNone(children['absent.server'].poll());self.assertIsNotNone(children['absent.client'].poll())
            if native and role=='client':
                value=real_popen(argv,**kwargs)
            else:
                value=supervision.child(1000+len(children))
                if role=='client':
                    directory=root/'steering-quality'/phase
                    (directory/'measurements.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows[phase]))
                    (directory/'requests.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in cases[phase]))
            children[phase+'.'+role]=value;return value
        def get(_port,path):
            identifier=path.split('/')[-2]
            value=snapshots[identifier] if native else next(v for v in snapshots.values() if v['id']==identifier)
            return {'status':200,'body':json.dumps(value)}
        def container(command,bundle,timeout,model):
            self.assertEqual((bundle,timeout,model),(campaign.m['bundle'],prepared['deadline'],root/'HOST-model-not-opened'))
            self.assertIn('/work/strix-point-steering-quality-run.py',command)
            if missing_result:
                campaign.r['child_exit_code']=1
                if corrupt_partial:(root/'steering-quality-result.json').symlink_to(root/'corpus.json')
                raise RuntimeError('HOST owned container fails before response supervision')
            args=types.SimpleNamespace(directory=root,bank=root/'direction.ffn.f32',model='HOST-never-opened',
                                       server='HOST-server',client=NATIVE if native else 'HOST-client',load_timeout=30)
            with patch.object(runner.subprocess,'Popen',side_effect=launched), \
                 patch.object(runner.owned,'private_ports',return_value=(server.server_port if server else 41001,41002)), \
                 patch.object(runner.owned,'process_identity',side_effect=lambda c:real_identity(c) if native and c in (children.get('absent.client'),children.get('bank.client')) else {'pid':c.pid,'start_ticks':1,'cgroup':'HOST simulated lifetime'}), \
                 patch.object(runner,'ready'),patch.object(runner,'get',side_effect=get):
                code=runner.run(args,prepared['settings'],prepared['corpus'])
            campaign.r['child_exit_code']=code
            if mutate_wire:
                path=root/'steering-quality/bank/measurements.jsonl'
                altered=[json.loads(line) for line in path.read_text().splitlines()]
                altered[1]['response_chunks'][-1]['usage']['total_tokens']+=1
                path.write_text(''.join(json.dumps(row)+'\n' for row in altered))
            if replace_input:
                original=root/'corpus.json';replacement=root/'replacement.json'
                replacement.write_bytes(original.read_bytes());replacement.replace(original)
            if code:raise RuntimeError('HOST complete quality failure, actual container1')
        campaign.run_container.side_effect=container
        try:
            result=profile.run(campaign)
            self.assertFalse(errors,errors)
            if native:self.assertEqual(len(requests),70)
            return result
        finally:
            if server:
                server.shutdown();server.server_close();thread.join(timeout=5);self.assertFalse(thread.is_alive())

    def test_model_neutral_geometry_and_complete_predeclared_training_sources(self):
        campaign,_receipt=self.fixture();prepared=profile.preflight(campaign)
        self.assertEqual(prepared['bank_source']['training_pairs'],100)
        self.assertEqual((prepared['bank_source']['layers'],prepared['bank_source']['width']),(2,2))
        self.assertFalse(prepared['bank_source']['quality_already_qualified'])
        campaign.verified_model.assert_not_called();campaign.run_container.assert_not_called()

    def test_refuse_formal_eight_pair_or_synthetic_or_incomplete_training(self):
        changes=[('pairs',8),('pairs',True),('captured_rows',399),('model_generation_or_quality_tested',True)]
        for key,value in changes:
            with self.subTest(key=key,value=value):
                campaign,r=self.fixture();r['capture'][key]=value;self.receipt(campaign.root,campaign.m,r)
                with self.assertRaises(RuntimeError):profile.preflight(campaign)
                campaign.verified_model.assert_not_called()
        campaign,r=self.fixture();r['capture']['native_identity']['synthetic']=True;self.receipt(campaign.root,campaign.m,r)
        with self.assertRaises(RuntimeError):profile.preflight(campaign)

    def test_refuse_model_runtime_prompt_and_raw_geometry_drift(self):
        paths=[('source_model','revision'),('capture','source_inputs','target-prompts.txt','sha256'),
               ('capture','native_identity','engine'),('capture','raw','bytes')]
        for path in paths:
            with self.subTest(path=path):
                campaign,r=self.fixture();target=r
                for key in path[:-1]:target=target[key]
                target[path[-1]]=1 if path[-1]=='bytes' else 'different'
                self.receipt(campaign.root,campaign.m,r)
                with self.assertRaises((ValueError,RuntimeError)):profile.preflight(campaign)

    def test_require_all_actual_native_review_and_control_exits(self):
        for key in ('controller','supervisor','native_builder','collector','strong_closure','independent_review'):
            for value in (1,False,None):
                with self.subTest(key=key,value=value):
                    campaign,r=self.fixture();r['actual_exits'][key]=value;self.receipt(campaign.root,campaign.m,r)
                    with self.assertRaises(RuntimeError):profile.preflight(campaign)

    def test_require_whole_container_retirement_release_and_complete_scans(self):
        for fault in ('pid','members','unreadable','release','future','peers'):
            with self.subTest(fault=fault):
                campaign,r=self.fixture()
                if fault=='pid':r['closure']['identities'][3]['exact_identity_absent']=False
                if fault=='members':r['closure']['whole_container_process_scans'][1]['owned_cgroup_matches']=[1]
                if fault=='unreadable':r['closure']['whole_container_process_scans'][0]['unreadable']=[2]
                if fault=='release':r['closure']['original_lease']['released']=False
                if fault=='future':r['ownership']['standing_reservation_or_future_grant']=True
                if fault=='peers':r['ownership']['all_four_verified_release_notifications']=False
                self.receipt(campaign.root,campaign.m,r)
                with self.assertRaises(RuntimeError):profile.preflight(campaign)

    def test_refuse_nonfinite_or_nonunit_bank_even_with_updated_claimed_hashes(self):
        for values in ((float('nan'),.8,-.8,.6),(.1,.1,-.8,.6),(0,0,-.8,.6)):
            with self.subTest(values=values):
                campaign,r=self.fixture();payload=struct.pack('<4f',*values)
                (campaign.root/'direction.ffn.f32').write_bytes(payload)
                campaign.m['steering_quality']['bank_sha256']=identity(payload)['sha256']
                settings=json.dumps(campaign.m['steering_quality']).encode();(campaign.root/'steering-quality-settings.json').write_bytes(settings)
                campaign.m['steering_quality_settings_sha256']=identity(settings)['sha256']
                r['capture']['banks']['direction.ffn.f32']=identity(payload);self.receipt(campaign.root,campaign.m,r)
                with self.assertRaises(RuntimeError):profile.preflight(campaign)

    def test_bind_all_five_exact_helper_filenames_before_import(self):
        for name in profile.HELPERS:
            with self.subTest(name=name):
                campaign,_r=self.fixture();(campaign.root/name).write_text('raise Exception("HOST must not execute drifted helper")\n')
                with self.assertRaisesRegex(RuntimeError,'helper content drift'):profile.preflight(campaign)

    def test_bind_settings_corpus_and_receipt_bytes(self):
        for name in ('steering-quality-settings.json','corpus.json','steering-training-receipt.json'):
            with self.subTest(name=name):
                campaign,_r=self.fixture();p=campaign.root/name;p.write_bytes(p.read_bytes()+b' ')
                with self.assertRaises(RuntimeError):profile.preflight(campaign)

    def test_refuse_symlink_and_replay_before_model_or_container(self):
        campaign,_r=self.fixture();p=campaign.root/'direction.ffn.f32';copy=p.with_name('copy');p.rename(copy);p.symlink_to(copy)
        with self.assertRaises(RuntimeError):profile.preflight(campaign)
        campaign,_r=self.fixture();(campaign.root/'steering-quality').mkdir()
        with self.assertRaises(RuntimeError):profile.run(campaign)
        campaign.verified_model.assert_not_called();campaign.run_container.assert_not_called()

    def test_refuse_predictor_vision_mode_or_unbounded_deadline(self):
        for key,value in (('decode_mode','mtp'),('predictor_plan',{}),('projector_plan',{}),('steering_quality_load_timeout_seconds',True)):
            with self.subTest(key=key):
                campaign,_r=self.fixture();campaign.m[key]=value
                with self.assertRaises(ValueError):profile.preflight(campaign)

    def test_independent_full_wire_review_and_model_postflight(self):
        campaign,_r=self.fixture();proof=self.execute(campaign)
        self.assertEqual((proof['state'],proof['samples']),('PASSED',70))
        campaign.verified_model.assert_called_once();campaign.check_model_after.assert_called_once()
        self.assertEqual(campaign.r['child_exit_code'],0)
        self.assertEqual(len(campaign.r['steering_quality_partial_artifacts']),4)

    def test_quality_failure_preserves_full_scores_and_actual_native_success(self):
        campaign,_r=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'container failed'):self.execute(campaign,wrong=True)
        proof=campaign.r['steering_quality_result'];self.assertEqual((proof['state'],proof['samples']),('QUALITY_FAILED',70))
        self.assertEqual(proof['correct_answers'],69);self.assertEqual(campaign.r['child_exit_code'],1)
        result=json.loads((campaign.root/'steering-quality-result.json').read_text())
        self.assertEqual(result['native_exit_codes'],{'absent':0,'bank':0});campaign.check_model_after.assert_called_once()

    def test_helper_green_summary_cannot_override_changed_saved_wire(self):
        campaign,_r=self.fixture()
        with self.assertRaises(RuntimeError):self.execute(campaign,mutate_wire=True)
        self.assertNotIn('steering_quality_result',campaign.r)
        self.assertEqual(campaign.r['child_exit_code'],0);campaign.check_model_after.assert_called_once()

    def test_byte_identical_input_replacement_after_native_success_refuses(self):
        campaign,_r=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'input identity changed'):self.execute(campaign,replace_input=True)
        self.assertEqual(campaign.r['steering_quality_result']['state'],'PASSED')
        campaign.check_model_after.assert_called_once()

    def test_launch_failure_keeps_actual_exit_and_checks_model_without_retry(self):
        campaign,_r=self.fixture()
        with self.assertRaises(FileNotFoundError):self.execute(campaign,missing_result=True)
        self.assertEqual(campaign.r['child_exit_code'],1);self.assertEqual(campaign.r['steering_quality_partial_artifacts'],{})
        campaign.run_container.assert_called_once();campaign.check_model_after.assert_called_once()

    def test_partial_symlink_refusal_still_checks_model_and_records_failure(self):
        campaign,_r=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'Partial steering'):self.execute(campaign,missing_result=True,corrupt_partial=True)
        self.assertEqual(len(campaign.r['steering_quality_partial_read_errors']),1)
        campaign.check_model_after.assert_called_once();self.assertTrue(campaign.record.called)

    @unittest.skipUnless(NATIVE,'Optional real C clients with simulated model servers/training metadata')
    def test_native_client_cohort_through_complete_profile(self):
        campaign,_r=self.fixture();proof=self.execute(campaign,native=True)
        self.assertEqual((proof['state'],proof['samples']),('PASSED',70))
        result=json.loads((campaign.root/'steering-quality-result.json').read_text())
        for phase in ('absent','bank'):
            self.assertGreater(result['phases'][phase]['client_identity']['start_ticks'],0)
        campaign.check_model_after.assert_called_once()


if __name__=='__main__':unittest.main()
