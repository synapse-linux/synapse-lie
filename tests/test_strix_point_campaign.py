#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only ownership/restore fixtures. Commands and observations are mocked."""
import importlib.util
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('point', Path(__file__).resolve().parents[1]/'tools/strix-point-campaign.py')
point = importlib.util.module_from_spec(spec)
spec.loader.exec_module(point)

def observation(*_args):
    return {'at': 'fixture', 'kfd': [], 'dri': [], 'kernel_kfd': [], 'denied_fd': 0,
            'memory': {}, 'temperatures': [{'name': 'k10temp', 'value_c': 35, 'limit_c': 85}]}

class Fixture(point.Campaign):
    active = True
    fail_stop = False
    def command(self, argv, check=True, timeout=30):
        del check, timeout
        self.r['commands'].append(argv)
        assert argv[:2] == ['systemctl', '--user'], argv
        if argv[2] == 'stop':
            self.active = False
            if self.fail_stop: raise RuntimeError('fixture stop interrupted after service exit')
        if argv[2] == 'start': self.active = True
        output = 'ActiveState='+('active' if self.active else 'inactive')+'\nSubState=fixture\nMainPID=999999999\n'
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr='')

class Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.patches = [patch.object(point, 'BASE', self.base), patch.object(point, 'observe', observation)]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.directory.cleanup()
    def campaign(self, name='run'):
        root = self.base/name; root.mkdir()
        (root/'manifest.json').write_text('{}')
        return Fixture(root, {'authorization': 'CPU fixture; not an actual grant'})
    def prefill_receipt(self, probe, mode='ar', mocked_original=True):
        path = Path(__file__).parent/'fixtures/prefill-probe-receipts.json'
        data = json.loads(path.read_text())
        self.assertEqual(data['classification'], 'SYNTHETIC_NATIVE_C17_HOST_FIXTURE_NOT_INFERENCE')
        rows = copy.deepcopy(data['cases'][probe+'-'+mode]['rows'])
        identity = rows[0]
        # Only exercise receipt validation here. These transformed records are
        # mocked original-shaped data, never original-weight/GPU evidence.
        if mocked_original:
            for row in rows:
                if 'synthetic' in row:
                    row['synthetic'] = False
            identity.update(context_capacity=4096, build_id='mocked-prefill-runtime')
        settings = {'context':identity['context_capacity'], 'chunk':identity['prefill_chunk'],
                    'users':identity['users'], 'tg':identity['output_limit'],
                    'warmups':identity['warmups'], 'repetitions':identity['repetitions']}
        prompt = next(row['physical_ids'] for row in rows if row['event']=='input')
        return rows, settings, identity['prefill_capacity'], prompt
    def validate_prefill_receipt(self, rows, probe, settings, capacity, prompt):
        return point.validate_prefill_probe(rows, probe, settings, capacity, prompt)
    def test_prefill_receipts_accept_complete_mocked_ar_and_mtp_witnesses(self):
        for probe in ('live','ram','ssd'):
            for mode in ('ar','mtp'):
                with self.subTest(probe=probe,mode=mode):
                    rows, settings, capacity, prompt = self.prefill_receipt(probe,mode)
                    proof = self.validate_prefill_receipt(rows,probe,settings,capacity,prompt)
                    self.assertEqual(proof['confirmed_output_ids'], list(range(32)))
                    self.assertEqual(proof['jobs'], 2 if probe=='live' else 5)
                    self.assertEqual(proof['cache_namespace_steps_verified'], 0 if probe=='live' else 5)
                    self.assertEqual(proof['native_inflight_and_credit_cancel_verified'],probe=='live')
    def test_prefill_receipts_refuse_actual_synthetic_identity(self):
        for probe in ('live','ram','ssd'):
            for mode in ('ar','mtp'):
                with self.subTest(probe=probe,mode=mode):
                    args = self.prefill_receipt(probe,mode,mocked_original=False)
                    with self.assertRaisesRegex(RuntimeError,'original native identity'):
                        self.validate_prefill_receipt(args[0],probe,*args[1:])
    def test_prefill_receipts_bind_all_physical_input_and_confirmed_output_ids(self):
        for probe in ('live','ram','ssd'):
            rows, settings, capacity, prompt = self.prefill_receipt(probe)
            targets = [('input','physical_ids'),('job','output_ids'),
                       ('prefill_probe_complete','baseline_output_ids')]
            if probe=='live': targets.append(('prefill_live_result','peer_output_ids'))
            for event, key in targets:
                for value in (True,1.0,12345):
                    with self.subTest(probe=probe,event=event,value=value):
                        bad = copy.deepcopy(rows)
                        next(r for r in bad if r['event']==event)[key][1] = value
                        with self.assertRaises(RuntimeError):
                            self.validate_prefill_receipt(bad,probe,settings,capacity,prompt)
            for index, row in enumerate(rows):
                if row['event'] != 'job': continue
                bad = copy.deepcopy(rows); bad[index]['output_ids'][-1] = 12345
                with self.subTest(probe=probe,job=index),self.assertRaises(RuntimeError):
                    self.validate_prefill_receipt(bad,probe,settings,capacity,prompt)
            bad = copy.deepcopy(rows)
            next(r for r in bad if r['event']=='input')['physical_ids_sha256'] = '0'*64
            with self.assertRaisesRegex(RuntimeError,'physical input hash'):
                self.validate_prefill_receipt(bad,probe,settings,capacity,prompt)
    def test_prefill_live_receipt_requires_same_call_immutable_queue_and_real_cancellation(self):
        rows, settings, capacity, prompt = self.prefill_receipt('live')
        mutations = [('prefill_transition','same_owner_call_observed',False),
                     ('prefill_transition','immutable_admissions',False),
                     ('prefill_transition','queued_after_changes',0),
                     ('prefill_transition','prefill_started_before',8),
                     ('prefill_transition','prefill_started_after',10),
                     ('prefill_transition','prefill_returned_after',9),
                     ('prefill_live_result','peer_prefill_calls',8),
                     ('prefill_live_result','complete_peer_output_equal',False),
                     ('reactive','synthetic',True),('reactive','held_output_blocked',True),
                     ('reactive','held_borrowed_tokens',0),('reactive','held_output_tokens',32),
                     ('reactive','completed_delta',0),('reactive','cancelled_delta',0),
                     ('reactive','decode_batches_delta',0),('reactive','mtp_accepted_delta',1),
                     ('prefill_cancel','same_owner_call_observed',False),
                     ('prefill_cancel','cancel_during_prefill_delta',0),
                     ('prefill_cancel','cancelled_delta',True),('prefill_cancel','failed_delta',1),
                     ('prefill_cancel','output_tokens',1),('prefill_cancel','retired',1)]
        for event,key,value in mutations:
            bad = copy.deepcopy(rows); next(r for r in bad if r['event']==event)[key]=value
            with self.subTest(event=event,key=key),self.assertRaises(RuntimeError):
                self.validate_prefill_receipt(bad,'live',settings,capacity,prompt)
        for event,keys in [('prefill_transition',('initial_core','current_core','active_job','queued_job')),
                           ('prefill_live_result',('active_job','peer_job'))]:
            for key in keys:
                for field in ('chunk_tokens','capacity_tokens','revision'):
                    bad = copy.deepcopy(rows); next(r for r in bad if r['event']==event)[key][field]=True
                    with self.subTest(event=event,key=key,field=field),self.assertRaises(RuntimeError):
                        self.validate_prefill_receipt(bad,'live',settings,capacity,prompt)
        rows, settings, capacity, prompt = self.prefill_receipt('live','mtp')
        next(r for r in rows if r['event']=='reactive')['mtp_accepted_delta']=0
        with self.assertRaisesRegex(RuntimeError,'MTP mode'):
            self.validate_prefill_receipt(rows,'live',settings,capacity,prompt)
    def test_prefill_cache_receipts_require_full_hot_prefix_and_separate_chunk_namespaces(self):
        for probe in ('ram','ssd'):
            rows, settings, capacity, prompt = self.prefill_receipt(probe)
            for event in ('job','prefill_cache_step'):
                indices=[i for i,r in enumerate(rows) if r['event']==event]
                for step,index in enumerate(indices):
                    for key,value in [('cached_tokens',0 if step in (1,3,4) else 64),
                                      ('prefill_calls',1),('ssd_cached_tokens',1)]:
                        bad=copy.deepcopy(rows); bad[index][key]=value
                        with self.subTest(probe=probe,event=event,step=step,key=key),self.assertRaises(RuntimeError):
                            self.validate_prefill_receipt(bad,probe,settings,capacity,prompt)
                    key='prefill_revision' if event=='job' else 'selection'
                    bad=copy.deepcopy(rows)
                    if event=='job': bad[index][key]=99
                    else: bad[index][key]['revision']=99
                    with self.subTest(probe=probe,event=event,step=step,key=key),self.assertRaises(RuntimeError):
                        self.validate_prefill_receipt(bad,probe,settings,capacity,prompt)
            for field,value in [('verified',1),('ssd_pending',1),('ssd_errors',1)]:
                bad=copy.deepcopy(rows); next(r for r in bad if r['event']=='prefill_cache_step')[field]=value
                with self.subTest(probe=probe,field=field),self.assertRaises(RuntimeError):
                    self.validate_prefill_receipt(bad,probe,settings,capacity,prompt)
        rows,settings,capacity,prompt=self.prefill_receipt('ssd')
        for event,key,value in [('prefill_cache_step','ssd_writes',0),
                                ('ssd_drained','writes',1),('ssd_drained','pending',1),
                                ('ssd_drained','errors',1)]:
            bad=copy.deepcopy(rows); next(r for r in bad if r['event']==event)[key]=value
            with self.subTest(event=event,key=key),self.assertRaises(RuntimeError):
                self.validate_prefill_receipt(bad,'ssd',settings,capacity,prompt)
    def test_prefill_receipts_reject_missing_duplicate_and_invalid_typed_events(self):
        for probe in ('live','ram','ssd'):
            rows,settings,capacity,prompt=self.prefill_receipt(probe)
            for index,row in enumerate(rows):
                if row['event']=='core_ready': continue
                with self.subTest(probe=probe,missing=row['event']),self.assertRaises(RuntimeError):
                    self.validate_prefill_receipt(rows[:index]+rows[index+1:],probe,settings,capacity,prompt)
                with self.subTest(probe=probe,duplicate=row['event']),self.assertRaises(RuntimeError):
                    self.validate_prefill_receipt(rows[:index]+[row]+rows[index:],probe,settings,capacity,prompt)
            for bad in (rows+[None],rows[:-1]+[{'event':'complete','exit_code':False}]):
                with self.assertRaises(RuntimeError):
                    self.validate_prefill_receipt(bad,probe,settings,capacity,prompt)
    def prefill_campaign(self,name,probe,mode='ar'):
        c=self.campaign(name)
        rows,settings,capacity,prompt=self.prefill_receipt(probe,mode)
        tokens=c.root/'tokens.json'; tokens.write_text(json.dumps(prompt))
        c.m.update(action='bench',stack='rocm10-fedora43',transport='distrobox',
                   bench_profile='modern-core-prefill-probe',prefill_probe=probe,decode_mode=mode,
                   bundle=str(self.base),tokens_sha256=point.sha(tokens),prompt_tokens_expected=len(prompt),
                   runtime_build_id='mocked-prefill-runtime',settings=settings,prefill_capacity=capacity,
                   eos_policy='ignore',generation=rows[0]['generation'],
                   model_plan={'files':[{'name':'target.gguf'}]})
        if mode=='mtp': c.m['predictor_plan']={'files':[{'name':'mtp.gguf'}]}
        return c,rows
    def test_prefill_campaign_routes_all_three_native_modes_and_binds_complete_receipts(self):
        for probe in ('live','ram','ssd'):
            for mode in ('ar','mtp'):
                with self.subTest(probe=probe,mode=mode):
                    c,rows=self.prefill_campaign('prefill-route-'+probe+'-'+mode,probe,mode)
                    def run(command,_bundle,_timeout,_model):
                        self.assertEqual(command[command.index('--prefill-probe')+1],probe)
                        self.assertEqual(command[command.index('--prefill-capacity')+1],'32')
                        self.assertEqual(command[command.index('--kv-cache-ram-mb')+1],
                                         '4096' if probe=='ram' else '0')
                        self.assertEqual('--kv-disk-dir' in command,probe=='ssd')
                        self.assertEqual('--model-mtp' in command,mode=='mtp')
                        self.assertIn('--ignore-eos',command)
                        self.assertNotIn('--reactive-probe',command)
                        (c.root/'measurements.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                    with patch.object(c,'verified_model',return_value=(self.base/'model',[])), \
                         patch.object(c,'verified_predictor',return_value=(self.base/'mtp.gguf',{})), \
                         patch.object(c,'check_model_after'),patch.object(c,'run_container',side_effect=run):
                        c.bench()
                    self.assertFalse(c.r['bench_result']['performance_comparison'])
                    self.assertEqual(c.r['bench_result']['prefill_probe']['confirmed_output_ids'],list(range(32)))
                    self.assertEqual(c.r['bench_result']['measurements_sha256'],point.sha(c.root/'measurements.jsonl'))
    def test_prefill_campaign_refuses_invalid_manifest_before_model_or_container(self):
        mutations=[('prefill_probe','other'),('prefill_capacity',8),('prefill_capacity',True),
                   ('settings.users',1),('settings.warmups',1),('settings.repetitions',2),
                   ('generation.temperature',1),('generation.frequency_penalty',1),
                   ('generation.presence_penalty',1),('eos_policy','stop'),
                   ('progress_interval_ms',1000),('bench_profile','modern-core')]
        for index,(key,value) in enumerate(mutations):
            c,_=self.prefill_campaign('prefill-invalid-'+str(index),'live')
            if '.' in key:
                parent,child=key.split('.'); c.m[parent][child]=value
            else: c.m[key]=value
            with self.subTest(key=key),patch.object(c,'verified_model') as model, \
                 patch.object(c,'run_container') as run,self.assertRaises(ValueError):
                c.bench()
            model.assert_not_called(); run.assert_not_called()
        c,_=self.prefill_campaign('prefill-short','live')
        c.m['settings']['chunk']=64;c.m['prefill_capacity']=128
        with patch.object(c,'verified_model') as model,patch.object(c,'run_container') as run, \
             self.assertRaisesRegex(ValueError,'exceed'):
            c.bench()
        model.assert_not_called();run.assert_not_called()
    def progress_fixture(self):
        settings = {'context':4096, 'chunk':2048, 'users':2, 'tg':32,
                    'warmups':1, 'repetitions':1}
        jobs = []; observations = []
        for rep in range(2):
            final_states = []
            for user in range(2):
                job = {'rep':rep, 'user':user, 'warmup':int(rep == 0),
                       'prompt_tokens':3, 'cached_tokens':0, 'prefill_tokens':3,
                       'prefill_calls':1, 'output_tokens':32, 'decode_calls':32,
                       'prefill_ns':10, 'decode_ns':20}
                jobs.append(job)
                state = {k:v for k,v in job.items() if k not in ('rep', 'warmup')}
                state.update(prepared=True, retired=True, terminal_observed=True, consumer_tokens=32)
                final_states.append(state)
            live_states = copy.deepcopy(final_states)
            for state in live_states:
                state.update(retired=False, terminal_observed=False, prefill_tokens=1,
                             output_tokens=0, consumer_tokens=0, decode_calls=0,
                             prefill_ns=1, decode_ns=0)
            base = {'event':'core_progress', 'schema':'synapse-lie.core-progress.v1',
                    'synthetic':False, 'rep':rep, 'warmup':int(rep == 0), 'queued':0,
                    'active':2, 'output_blocked':0, 'prefill_started':2, 'prefill_returned':1}
            observations.append(dict(base, snapshot_monotonic_ns=100 + rep*100,
                                     elapsed_ns=0, final_snapshot=False, executor_phase='prefill',
                                     jobs=live_states))
            observations.append(dict(base, snapshot_monotonic_ns=150 + rep*100,
                                     elapsed_ns=50, final_snapshot=True, executor_phase='idle',
                                     jobs=final_states))
        return settings, jobs, observations
    def write_progress(self, observations):
        path = self.base/'progress.log'
        path.write_text('Provider diagnostic\n' + ''.join(json.dumps(r)+'\n' for r in observations))
        return path
    def test_progress_warmup_two_users_matches_completed_jobs(self):
        settings, jobs, observations = self.progress_fixture()
        path = self.write_progress(observations)
        result = point.validate_core_progress(path, jobs, settings)
        self.assertEqual(result['observations'], 4)
        self.assertEqual(result['live_samples'], 2)
        self.assertEqual(result['final_samples'], 2)
        self.assertEqual(result['partial_prefill_job_observations'], 4)
        self.assertEqual(result['inflight_prefill_observations'], 2)
        self.assertEqual(result['stderr_sha256'], point.sha(path))
    def test_final_progress_flag_cannot_replace_retirement_or_job_evidence(self):
        settings, jobs, observations = self.progress_fixture()
        for key, value in [('retired',False), ('terminal_observed',False), ('prepared',False),
                           ('output_tokens',31), ('consumer_tokens',31), ('prefill_tokens',2),
                           ('prefill_calls',2), ('prefill_ns',11), ('error','fixture failure')]:
            with self.subTest(key=key):
                bad = copy.deepcopy(observations); bad[1]['jobs'][0][key] = value
                with self.assertRaises(RuntimeError):
                    point.validate_core_progress(self.write_progress(bad), jobs, settings)
        with self.assertRaisesRegex(RuntimeError, 'job identities'):
            point.validate_core_progress(self.write_progress(observations), jobs[:-1], settings)
    def test_progress_rejects_synthetic_invalid_typed_or_missing_observations(self):
        settings, jobs, observations = self.progress_fixture()
        for key, value in [('synthetic',True), ('rep',True), ('warmup',0),
                           ('prefill_started',-1), ('final_snapshot',1),
                           ('schema','other'), ('executor_phase','unknown')]:
            with self.subTest(key=key):
                bad = copy.deepcopy(observations); bad[0][key] = value
                with self.assertRaises(RuntimeError):
                    point.validate_core_progress(self.write_progress(bad), jobs, settings)
        for omitted in (0,1,2,3):
            with self.subTest(omitted=omitted), self.assertRaises(RuntimeError):
                point.validate_core_progress(self.write_progress(observations[:omitted]+observations[omitted+1:]), jobs, settings)
        bad = copy.deepcopy(observations); bad[0]['jobs'][1]['user'] = 0
        with self.assertRaisesRegex(RuntimeError, 'progress jobs'):
            point.validate_core_progress(self.write_progress(bad), jobs, settings)
    def test_progress_refuses_clock_counter_regression_and_unbounded_input(self):
        settings, jobs, observations = self.progress_fixture()
        bad = copy.deepcopy(observations); bad[1]['elapsed_ns'] = 49
        with self.assertRaisesRegex(RuntimeError, 'clock origin'):
            point.validate_core_progress(self.write_progress(bad), jobs, settings)
        bad = copy.deepcopy(observations); bad[1]['snapshot_monotonic_ns'] = 100
        with self.assertRaisesRegex(RuntimeError, 'ordering'):
            point.validate_core_progress(self.write_progress(bad), jobs, settings)
        bad = copy.deepcopy(observations); bad[0]['jobs'][0]['prefill_ns'] = 11
        with self.assertRaisesRegex(RuntimeError, 'counter regression'):
            point.validate_core_progress(self.write_progress(bad), jobs, settings)
        with self.assertRaisesRegex(RuntimeError, 'ordering'):
            point.validate_core_progress(self.write_progress(observations[:2]+[observations[1]]+observations[2:]), jobs, settings)
        path = self.write_progress(observations); path.write_text('x'*65537)
        with self.assertRaisesRegex(RuntimeError, 'Oversized'):
            point.validate_core_progress(path, jobs, settings)
        path.write_text('{"event":"core_progress"\n')
        with self.assertRaisesRegex(RuntimeError, 'Malformed'):
            point.validate_core_progress(path, jobs, settings)
    def test_modern_core_progress_is_explicit_and_checked_against_results(self):
        c = self.campaign('progress-command')
        settings, jobs, observations = self.progress_fixture()
        settings.update(users=2, warmups=0, repetitions=1)
        jobs = jobs[2:]; observations = observations[2:]
        for row in jobs + observations:
            row.update(rep=0, warmup=0)
        tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-core', decode_mode='ar', bundle=str(self.base),
                   model_plan={'files':[{'name':'target.gguf'}]}, tokens_sha256=point.sha(tokens),
                   prompt_tokens_expected=3, runtime_build_id='fixture-runtime', settings=settings,
                   progress_interval_ms=1000)
        reported_interval = [1000]
        emit_progress = [True]
        def run(command, _bundle, _timeout, _model):
            self.assertEqual(command[command.index('--progress-ms')+1], '1000')
            rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1', 'synthetic':False,
                     'mode':'ar','build_id':'fixture-runtime','cache_policy':'off',
                     'progress_interval_ms':reported_interval[0]}]
            rows += [dict(job,event='job') for job in jobs]
            rows += [{'event':'sample'}, {'event':'complete','exit_code':0}]
            (c.root/'measurements.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (c.root/'distrobox.stderr.log').write_text(''.join(json.dumps(r)+'\n' for r in observations) if emit_progress[0] else '')
        with patch.object(c,'verified_model',return_value=(self.base,[])), \
             patch.object(c,'run_container',side_effect=run), patch.object(c,'check_model_after'):
            c.bench()
        self.assertEqual(c.r['bench_result']['progress']['final_samples'],1)
        for interval in (False,0,2000):
            reported_interval[0] = interval
            with self.subTest(reported_interval=interval), \
                 patch.object(c,'verified_model',return_value=(self.base,[])), \
                 patch.object(c,'run_container',side_effect=run), patch.object(c,'check_model_after'), \
                 self.assertRaisesRegex(RuntimeError,'benchmark identity'):
                c.bench()
        reported_interval[0] = 1000; emit_progress[0] = False
        with patch.object(c,'verified_model',return_value=(self.base,[])), \
             patch.object(c,'run_container',side_effect=run), patch.object(c,'check_model_after'), \
             self.assertRaisesRegex(RuntimeError,'Missing live or final'):
            c.bench()
        for interval in (True,-1,1,99,60001):
            c.m['progress_interval_ms'] = interval
            with self.subTest(interval=interval), self.assertRaisesRegex(ValueError,'progress interval'):
                c.bench()
        c.m.update(progress_interval_ms=1000,bench_profile='modern-core-reactive-probe')
        with self.assertRaisesRegex(ValueError,'progress interval'):
            c.bench()
    def test_restore_and_release(self):
        c = self.campaign(); c.enter()
        self.assertFalse(c.active)
        c.finish()
        self.assertTrue(c.active)
        self.assertFalse(c.r['cleanup_failures'])
        self.assertIn('lease_released_at', c.r)
    def test_ssd_text_restart_mounts_predictor_read_only_only_for_mtp(self):
        self.assert_restart_mounts('modern-core-ssd-text-restart', 'ssd-text')
    def test_steering_restart_mounts_predictor_read_only_only_for_mtp(self):
        self.assert_restart_mounts('modern-core-steering-restart', 'steering')
    def test_steering_admission_mounts_predictor_read_only_only_for_mtp(self):
        self.assert_restart_mounts('modern-core-steering-admission', 'steering-admission')
    def assert_restart_mounts(self, profile, label):
        predictor = self.base/'predictor'; predictor.mkdir()
        model = self.base/'target'; model.mkdir()
        for mode in ('ar', 'mtp'):
            c = self.campaign(label+'-volume-'+mode)
            c.m.update(action='bench', stack='rocm10-fedora43',
                       bench_profile=profile, decode_mode=mode,
                       distrobox_name='lie-host-ssd-text-'+mode,
                       predictor_plan={'destination':str(predictor)})
            # Stop at the actual argv boundary before any container or GPU work.
            with patch.object(c, 'sample'), patch.object(point, 'kfd_group', return_value=123), \
                 patch.object(point.subprocess, 'run', side_effect=RuntimeError('host-only argv witness')) as run, \
                 self.assertRaisesRegex(RuntimeError, 'host-only argv witness'):
                c.execute_distrobox(['/fixture/bench'], self.base, model, 'sha256:fixture', 30)
            argv = run.call_args.args[0]
            volumes = [argv[i+1] for i,item in enumerate(argv) if item == '--volume']
            self.assertIn(str(model)+':/model:ro', volumes)
            self.assertEqual(volumes.count(str(predictor)+':/mtp:ro'), 1 if mode == 'mtp' else 0)
    def memory_campaign(self, name='memory-run'):
        root = self.base/name; root.mkdir()
        (root/'manifest.json').write_text('{}')
        return Fixture(root, {'authorization':'CPU fixture; not an actual grant',
            'memory_admission':{'expected_peak_gtt_bytes':109*2**30,
                                'min_available_ram_bytes':2**30}})
    def test_unfit_gtt_refuses_before_router_stop_and_releases_lease(self):
        c = self.memory_campaign()
        row = observation()
        row['memory'] = {'MemAvailable':112*2**30}
        row['gpu'] = {'mem_info_gtt_total':96*2**30,'mem_info_gtt_used':0}
        with patch.object(point, 'observe', return_value=row):
            with self.assertRaisesRegex(RuntimeError, 'GTT peak'): c.enter()
        c.finish()
        self.assertTrue(c.active)
        self.assertFalse(any('stop' in cmd for cmd in c.r['commands']))
        self.assertIn('lease_released_at', c.r)
    def test_running_memory_pressure_restores_router_and_releases_lease(self):
        c = self.memory_campaign()
        row = observation()
        row['memory'] = {'MemAvailable':112*2**30}
        row['gpu'] = {'mem_info_gtt_total':112*2**30,'mem_info_gtt_used':0}
        with patch.object(point, 'observe', return_value=row): c.enter()
        self.assertFalse(c.active)
        row['gpu']['mem_info_gtt_used'] = 108*2**30
        row['memory']['MemAvailable'] = 2**30+1
        with patch.object(point, 'observe', return_value=row):
            with self.assertRaisesRegex(RuntimeError, 'Projected available RAM'): c.sample()
        row['memory']['MemAvailable'] = 2**30-1
        with patch.object(point, 'observe', return_value=row):
            with self.assertRaisesRegex(RuntimeError, 'RAM floor'): c.sample()
        c.finish()
        self.assertTrue(c.active)
        self.assertFalse(c.r['cleanup_failures'])
        self.assertIn('lease_released_at', c.r)
    def test_memory_guard_requires_telemetry_and_typed_positive_budgets(self):
        c = self.memory_campaign()
        with self.assertRaisesRegex(RuntimeError, 'telemetry'): c.sample()
        for value in (True, 0, -1, 2**63):
            with self.assertRaisesRegex(ValueError, 'positive byte budgets'):
                Fixture(c.root, {'authorization':'fixture', 'memory_admission':
                    {'expected_peak_gtt_bytes':value,'min_available_ram_bytes':2**30}})
    def test_interrupted_stop_restores(self):
        c = self.campaign(); c.fail_stop = True
        with self.assertRaises(RuntimeError): c.enter()
        c.finish()
        self.assertTrue(c.active)
    def test_inactive_service_stays_inactive(self):
        c = self.campaign(); c.active = False
        c.enter(); c.finish()
        self.assertFalse(c.active)
        self.assertFalse(any('start' in cmd for cmd in c.r['commands']))
    def test_contended_lease_never_stops_service(self):
        first = self.campaign(); second = self.campaign('second')
        try:
            first.enter()
            with self.assertRaises(BlockingIOError): second.enter()
            second.finish()
            self.assertFalse(any('stop' in cmd for cmd in second.r['commands']))
            self.assertNotIn('lease_released_at', second.r)
        finally: first.finish()
    def test_foreign_kfd_refused_and_service_restored(self):
        c = self.campaign()
        bad = observation(); bad['kernel_kfd'] = [123]
        with patch.object(point, 'observe', return_value=bad):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.enter()
        c.finish(); self.assertTrue(c.active)
    def test_owned_kfd_retirement_does_not_mask_a_foreign_client(self):
        c = self.campaign()
        c.cid = 'a'*64
        owner = {'pid': 999999998, 'start_ticks': 12,
                 'cgroup': '/docker/'+c.cid, 'devices': ['/dev/kfd']}
        active = observation()
        active['kfd'] = [owner]
        active['dri'] = [owner]
        active['kernel_kfd'] = [owner['pid']]
        with patch.object(point, 'observe', return_value=active): c.sample()
        retired = observation()
        retired['kernel_kfd'] = [owner['pid']]
        with patch.object(point, 'observe', return_value=retired): c.sample()
        # A live PID, including a reused one, must not inherit the exception.
        with patch.object(point, 'observe', return_value=retired), \
             patch.object(point, 'ticks', return_value=13), \
             patch.object(point.Path, 'read_text', return_value='foreign-container'):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.sample()
        retired['kernel_kfd'].append(999999997)
        with patch.object(point, 'observe', return_value=retired):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.sample()
    def test_owned_kfd_fd_retirement_preserves_pid_start_and_cgroup(self):
        c = self.campaign('owned-fd-gap')
        c.cid = 'a'*64
        c.owned_kfd[999999998] = 12
        gap = observation(); gap['kernel_kfd'] = [999999998]
        with patch.object(point, 'observe', return_value=gap), \
             patch.object(point, 'ticks', return_value=12), \
             patch.object(point.Path, 'read_text', return_value='docker-'+c.cid):
            c.sample()
        with patch.object(point, 'observe', return_value=gap), \
             patch.object(point, 'ticks', return_value=13), \
             patch.object(point.Path, 'read_text', return_value='docker-'+c.cid):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.sample()
        with patch.object(point, 'observe', return_value=gap), \
             patch.object(point, 'ticks', return_value=12), \
             patch.object(point.Path, 'read_text', return_value='foreign-container'):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.sample()
    def test_owned_gpu_retirement_wait_is_bounded(self):
        c = self.campaign()
        waiting = observation(); waiting['kernel_kfd'] = [999999998]
        with patch.object(c, 'sample', side_effect=[waiting, observation()]) as sample, \
             patch.object(point.time, 'sleep'):
            c.wait_owned_gpu_retirement()
            self.assertEqual(sample.call_count, 2)
        with patch.object(c, 'sample', return_value=waiting), \
             patch.object(point.time, 'monotonic', side_effect=[0, 5.1]):
            with self.assertRaisesRegex(RuntimeError, 'retirement deadline'):
                c.wait_owned_gpu_retirement()
    def test_thermal_and_interruption_stop_admission(self):
        c = self.campaign()
        bad = observation(); bad['temperatures'][0]['value_c'] = 85
        with patch.object(point, 'observe', return_value=bad):
            with self.assertRaisesRegex(RuntimeError, 'Thermal'): c.sample()
        c.interrupted = 15
        with self.assertRaisesRegex(RuntimeError, 'Interrupted'): c.sample()
    def test_100c_ceiling_requires_exact_operator_override(self):
        root = self.base/'thermal'; root.mkdir()
        (root/'manifest.json').write_text('{}')
        manifest = {'authorization': 'fixture', 'thermal_ceiling_c': 100}
        with self.assertRaisesRegex(ValueError, 'operator 100 C'):
            Fixture(root, manifest)
        manifest['thermal_override_quote'] = point.THERMAL_OVERRIDE_QUOTE
        c = Fixture(root, manifest)
        self.assertEqual(c.thermal_ceiling_c, 100)
        with patch.object(point, 'observe', return_value=observation()) as read:
            c.sample()
            read.assert_called_once_with(100.0)
        manifest['thermal_ceiling_c'] = 101
        with self.assertRaisesRegex(ValueError, 'Unsupported thermal ceiling'):
            Fixture(root, manifest)
    def test_cpu_guard_records_gpu_without_stopping_and_guards_nvme(self):
        root = self.base/'cpu-guard'; root.mkdir()
        (root/'manifest.json').write_text('{}')
        manifest = {'authorization': 'fixture', 'thermal_policy': point.CPU_GUARD_POLICY,
                    'thermal_ceiling_c': 98}
        with self.assertRaisesRegex(ValueError, 'CPU guard'):
            Fixture(root, manifest)
        manifest['thermal_policy_quote'] = point.CPU_GUARD_QUOTE
        c = Fixture(root, manifest)
        hot = observation()
        hot['temperatures'] = [
            {'name': 'k10temp', 'value_c': 97, 'limit_c': 98, 'guarded': True},
            {'name': 'amdgpu', 'value_c': 103, 'limit_c': 98, 'guarded': False},
            {'name': 'nvme', 'value_c': 84, 'limit_c': 85, 'guarded': True},
        ]
        with patch.object(point, 'observe', return_value=hot) as read:
            c.sample()
            read.assert_called_once_with(98.0, gpu_observation_only=True)
            hot['temperatures'][0]['value_c'] = 98
            with self.assertRaisesRegex(RuntimeError, 'Thermal'): c.sample()
            hot['temperatures'][0]['value_c'] = 97
            hot['temperatures'][2]['value_c'] = 85
            with self.assertRaisesRegex(RuntimeError, 'Thermal'): c.sample()
    def test_kernel_retirement_waits_before_admission(self):
        c = self.campaign()
        before = observation()
        before['kfd'] = [{'pid': 999999999, 'start_ticks': 12}]
        pending = observation(); pending['kernel_kfd'] = [999999999]
        with patch.object(point, 'observe', side_effect=[before, pending, observation()]), patch.object(point.time, 'sleep') as sleep:
            c.enter()
            sleep.assert_called_once_with(0.1)
            self.assertEqual(c.r['admission']['kernel_kfd'], [])
        c.finish()
    def test_owned_container_threads_are_written_to_telemetry(self):
        c = self.campaign(); c.cid = 'test-owned-container'
        row = observation()
        row['dri'] = [{'pid': point.os.getpid(), 'start_ticks': point.ticks(point.os.getpid()),
                       'cgroup': c.cid, 'devices': ['/dev/kfd']}]
        row['kfd'] = row['dri']; row['kernel_kfd'] = [point.os.getpid()]
        with patch.object(point, 'observe', return_value=row): c.sample()
        saved = json.loads((c.root/'telemetry.jsonl').read_text())
        self.assertIn('Threads', saved['dri'][0]['status'])
    def test_container_exit_race_waits_for_final_docker_state(self):
        for pid in (0, 12345):
            with self.subTest(pid=pid):
                c = self.campaign(f'exit-{pid}')
                states = iter(({'Running': True, 'Pid': pid},
                               {'Running': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}))
                def command(argv, check=True, timeout=30):
                    del check, timeout
                    if argv[1] == 'create': output = 'a'*64
                    elif argv[1] == 'inspect': output = json.dumps(next(states))
                    else: output = ''
                    return subprocess.CompletedProcess(argv, 0, stdout=output, stderr='')
                with patch.object(c, 'command', side_effect=command), \
                     patch.object(point, 'ticks', side_effect=FileNotFoundError), \
                     patch.object(point.time, 'sleep'):
                    c.execute_container(['docker', 'create'], 2)
                self.assertEqual(c.r['child_exit_code'], 0)
                self.assertNotIn('container_start_ticks', c.r)
    def test_failed_core_keeps_model_identity_and_error_evidence(self):
        c = self.campaign(); model = self.base/'model'; model.mkdir()
        path = model/'fixture.gguf'; path.write_bytes(b'tiny fixture')
        st = path.stat()
        row = {'path': str(path), 'bytes': st.st_size, 'device': st.st_dev, 'inode': st.st_ino,
               'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns, 'sha256': point.sha(path)}
        plan = {'destination': str(model), 'files': [{'name': path.name, 'sha256': row['sha256']}]}
        (model/'SOURCE.json').write_text(json.dumps({'result': {'state': 'VERIFIED', 'files': [row]}, 'plan': plan}))
        c.m.update(model_plan=plan, bundle=str(self.base), settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':1,'repetitions':3})
        def failure(*args):
            (c.root/'measurements.jsonl').write_text('{"event":"failed","error":"synthetic load failure"}\n')
            raise RuntimeError('fixture GPU child failure')
        with patch.object(c, 'run_container', failure):
            with self.assertRaises(RuntimeError): c.core()
        self.assertTrue(c.r['model_stat_unchanged'])
        self.assertIn('synthetic load failure', c.r['measurements_raw'])
    def rebind_fixture(self):
        root = self.base/'rebind-run'; root.mkdir()
        (root/'manifest.json').write_text('{}')
        model = self.base/'rebind-model'; model.mkdir()
        path = model/'fixture.gguf'; path.write_bytes(b'unchanged fixture bytes')
        st = path.stat()
        row = {'path':str(path),'bytes':st.st_size,'device':st.st_dev+1,
               'inode':st.st_ino,'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns,
               'sha256':point.sha(path)}
        plan = {'destination':str(model),'files':[{'name':path.name,'sha256':row['sha256']}]}
        source = model/'SOURCE.json'
        source.write_text(json.dumps({'result':{'state':'VERIFIED','files':[row]},'plan':plan}))
        binding = {'boot_id':'c82c90ed-7f94-4212-bc52-681c63eac395',
                   'filesystem_uuid':'720d3f3a-db4b-4287-bf9c-77cc76bcb7cb',
                   'previous_device':row['device'],'current_device':st.st_dev}
        c = Fixture(root, {'authorization':'fixture','model_plan':plan,
                           'staging_filesystem_rebind':binding})
        return c, path, source, row, binding
    def test_boot_rebind_keeps_pinned_source_and_exact_postflight(self):
        c, path, source, row, binding = self.rebind_fixture()
        original = source.read_bytes()
        read_text = point.Path.read_text
        def read(p, *args, **kwargs):
            if str(p) == '/proc/sys/kernel/random/boot_id': return binding['boot_id']
            return read_text(p, *args, **kwargs)
        mount = subprocess.CompletedProcess([],0,stdout=json.dumps(
            {'filesystems':[{'uuid':binding['filesystem_uuid']}]}),stderr='')
        with patch.object(point.Path,'read_text',read), patch.object(c,'command',return_value=mount):
            model, before = c.verified_model()
        self.assertEqual(model,path.parent)
        self.assertEqual(source.read_bytes(),original)
        self.assertEqual(c.r['staging_filesystem_rebind'],binding)
        c.check_model_after(before)
        self.assertTrue(c.r['model_stat_unchanged'])
        path.write_bytes(b'changed after launch')
        with self.assertRaisesRegex(RuntimeError,'during run'): c.check_model_after(before)
    def test_rebind_refuses_unapproved_device_and_any_other_stat_drift(self):
        c, path, source, row, binding = self.rebind_fixture()
        c.staging_rebind = None
        with self.assertRaisesRegex(RuntimeError,'identity drift'): c.verified_model()
        c.staging_rebind = binding
        original = json.loads(source.read_text())
        for field in ('bytes','inode','mtime_ns','ctime_ns','device'):
            changed = json.loads(json.dumps(original))
            changed['result']['files'][0][field] += 1
            source.write_text(json.dumps(changed))
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError,'identity drift'):
                c.verified_model()
        source.write_text(json.dumps(original))
        with patch.object(point.Path,'read_text',autospec=True,side_effect=lambda p,*a,**k:
                'different-boot' if str(p)=='/proc/sys/kernel/random/boot_id' else json.dumps(original)):
            with self.assertRaisesRegex(RuntimeError,'boot mismatch'): c.verified_model()
        read_text = point.Path.read_text
        def read(p,*args,**kwargs):
            return binding['boot_id'] if str(p)=='/proc/sys/kernel/random/boot_id' else read_text(p,*args,**kwargs)
        wrong = subprocess.CompletedProcess([],0,stdout='{"filesystems":[{"uuid":"foreign"}]}',stderr='')
        with patch.object(point.Path,'read_text',read), patch.object(c,'command',return_value=wrong):
            with self.assertRaisesRegex(RuntimeError,'UUID mismatch'): c.verified_model()
    def test_rebind_manifest_requires_complete_typed_identities(self):
        c, path, source, row, binding = self.rebind_fixture()
        for key,value in [('boot_id','unbound'),('filesystem_uuid',None),
                          ('previous_device',True),('current_device',0),
                          ('current_device',binding['previous_device'])]:
            invalid = dict(binding); invalid[key] = value
            with self.subTest(key=key,value=value), self.assertRaisesRegex(ValueError,'explicit boot'):
                Fixture(c.root, {'authorization':'fixture','staging_filesystem_rebind':invalid})
    def test_direct_bench_keeps_partial_failure_and_model_identity(self):
        c = self.campaign(); model = self.base/'model'; model.mkdir()
        shard = model/'fixture.gguf'; shard.write_bytes(b'fixture model identity')
        st = shard.stat()
        row = {'path': str(shard), 'bytes': st.st_size, 'device': st.st_dev, 'inode': st.st_ino,
               'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns,
               'sha256': point.sha(shard)}
        plan = {'destination': str(model), 'files': [{'name': shard.name, 'sha256': row['sha256']}]}
        (model/'SOURCE.json').write_text(json.dumps({'result': {'state': 'VERIFIED', 'files': [row]}, 'plan': plan}))
        c.m.update(model_plan=plan, bundle=str(self.base), bench_profile='single')
        def failure(argv, bundle, timeout, model_path):
            self.assertEqual(argv[argv.index('--suite')+1], 'single')
            self.assertEqual(argv[argv.index('--depths')+1], '0,4096,8192,12288,16384,32768,65536,131072')
            self.assertEqual(argv[argv.index('--tg')+1], '128')
            self.assertEqual(timeout, 3600)
            self.assertEqual(model_path, model)
            (c.root/'measurements.jsonl').write_text('{"event":"failed","error":"synthetic thermal stop"}\n')
            raise RuntimeError('fixture child failed')
        with patch.object(c, 'run_container', failure):
            with self.assertRaisesRegex(RuntimeError, 'fixture child failed'): c.bench()
        self.assertTrue(c.r['model_stat_unchanged'])
        self.assertEqual(c.r['bench_partial']['measurements_sha256'], point.sha(c.root/'measurements.jsonl'))
        self.assertNotIn('bench_result', c.r)
        c.m['bench_profile'] = 'arbitrary'
        with self.assertRaisesRegex(ValueError, 'fixed benchmark'): c.bench()
        c.m['bench_profile'] = 'single'
        c.m['bench_impl'] = 'gufo'
        def reference_failure(argv, bundle, timeout, model_path):
            self.assertEqual(argv[0], '/bundle/runtime/bin/synapse-lie-bench-gufo-reference')
            self.assertNotIn('--execution', argv)
            raise RuntimeError('reference fixture failure')
        with patch.object(c, 'run_container', reference_failure):
            with self.assertRaisesRegex(RuntimeError, 'reference fixture failure'): c.bench()
        c.m['bench_impl'] = 'unexpected'
        with self.assertRaisesRegex(ValueError, 'implementation'): c.bench()
    def test_core_sampling_identity_types_profiles_and_historical_defaults(self):
        baseline = point.core_generation(None, historical=True)
        self.assertEqual(baseline, {'temperature':0,'top_p':1,'frequency_penalty':0,
                                   'presence_penalty':0,'seed':-1,'top_k':0,'min_p':0})
        old = {k:v for k,v in baseline.items() if k not in ('top_k','min_p')}
        self.assertEqual(point.core_generation(old, historical=True), baseline)
        ds4 = dict(baseline, temperature=1, min_p=.05, seed=123)
        self.assertEqual(point.core_generation(ds4), ds4)
        self.assertEqual(point.core_generation(dict(ds4, top_k=2147483647, seed=9223372036854775807))['top_k'], 2147483647)
        invalid = [None, [], old, dict(ds4, unknown=1),
                   dict(ds4, top_k=-1), dict(ds4, top_k=2147483648),
                   dict(ds4, seed=9223372036854775808), dict(ds4, seed=-1),
                   dict(ds4, top_p=0), dict(ds4, min_p=-.01), dict(ds4, min_p=1.01)]
        for key in ds4:
            invalid += [dict(ds4, **{key:bad}) for bad in (True,None,'1',float('nan'),float('inf'))]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                point.core_generation(value)
        for value in (dict(old, unknown=1), {}, {'min_p':0}):
            with self.subTest(historical=value), self.assertRaises(ValueError):
                point.core_generation(value, historical=True)
    def test_modern_core_sampling_is_forwarded_and_witnessed_in_ar_and_mtp(self):
        profile = {'temperature':1,'top_p':1,'frequency_penalty':0,
                   'presence_penalty':0,'seed':123,'top_k':0,'min_p':.05}
        for mode in ('ar','mtp'):
            c = self.campaign('sampled-'+mode)
            tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
            c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                       bench_profile='modern-core', decode_mode=mode, bundle=str(self.base),
                       model_plan={'files':[{'name':'target.gguf'}]}, tokens_sha256=point.sha(tokens),
                       prompt_tokens_expected=3, runtime_build_id='fixture-runtime', generation=profile,
                       settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':0,'repetitions':1})
            reported = [dict(profile)]
            def run(command, *_args):
                for key,value in profile.items():
                    self.assertEqual(command[command.index('--'+key.replace('_','-'))+1], str(value))
                self.assertEqual('--model-mtp' in command, mode=='mtp')
                rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1','mode':mode,
                         'synthetic':False,'cache_policy':'off','build_id':'fixture-runtime',
                         'generation':reported[0]},
                        {'event':'job','prompt_tokens':3,'output_tokens':32,
                         'mtp_drafted_tokens':4 if mode=='mtp' else 0,
                         'mtp_accepted_tokens':3 if mode=='mtp' else 0},
                        {'event':'sample'},{'event':'complete','exit_code':0}]
                (c.root/'measurements.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with patch.object(c,'verified_model',return_value=(self.base,[])), \
                 patch.object(c,'verified_predictor',return_value=(self.base/'mtp.gguf',{})), \
                 patch.object(c,'run_container',side_effect=run), patch.object(c,'check_model_after'):
                c.bench()
                self.assertEqual(c.r['bench_result']['generation'],profile)
                for changed in (dict(profile,top_k=5),dict(profile,min_p=0),dict(profile,seed=124),
                                dict(profile,min_p=True),None):
                    reported[0] = changed
                    with self.subTest(mode=mode,changed=changed), self.assertRaisesRegex(RuntimeError,'sampling identity'):
                        c.bench()
    def test_modern_core_prefill_reservation_and_admitted_witnesses(self):
        for chunk in (1, 2048, 4096, 8192, 16384, 32768):
            c = self.campaign('prefill-' + str(chunk))
            tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
            c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                       bench_profile='modern-core', decode_mode='ar', bundle=str(self.base),
                       model_plan={'files':[{'name':'target.gguf'}]}, tokens_sha256=point.sha(tokens),
                       prompt_tokens_expected=3, runtime_build_id='fixture-runtime',
                       prefill_capacity=32768,
                       settings={'context':65536,'chunk':chunk,'users':1,'tg':32,'warmups':0,'repetitions':1})
            identity = {'prefill_chunk':chunk,'prefill_capacity':32768}
            admitted = dict(identity, prefill_revision=1)
            def run(command, *_args):
                self.assertEqual(command[command.index('--chunk')+1], str(chunk))
                self.assertEqual(command[command.index('--prefill-capacity')+1], '32768')
                rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1','mode':'ar',
                         'synthetic':False,'cache_policy':'off','build_id':'fixture-runtime',**identity},
                        {'event':'job','prompt_tokens':3,'output_tokens':32,
                         'mtp_drafted_tokens':0,'mtp_accepted_tokens':0,**admitted},
                        {'event':'sample'},{'event':'complete','exit_code':0}]
                (c.root/'measurements.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with patch.object(c,'verified_model',return_value=(self.base,[])), \
                 patch.object(c,'run_container',side_effect=run), patch.object(c,'check_model_after'):
                c.bench()
                self.assertEqual(c.r['bench_result']['prefill'],
                                 {'chunk_tokens':chunk,'capacity_tokens':32768,
                                  'revision':1,'admitted_jobs_verified':1})
                for target in (identity, admitted):
                    for key in tuple(target):
                        good = target[key]
                        for bad in (None, True, str(good), good+1):
                            target[key] = bad
                            with self.subTest(chunk=chunk,key=key,bad=bad), \
                                 self.assertRaisesRegex(RuntimeError,'prefill identity'):
                                c.bench()
                        target[key] = good

    def test_modern_core_prefill_refuses_invalid_admission_before_model(self):
        c = self.campaign('prefill-admission')
        c.m.update(action='bench',stack='rocm10-fedora43',transport='distrobox',
                   bench_profile='modern-core',decode_mode='ar',
                   settings={'context':65536,'chunk':4096,'users':1,'tg':32,'warmups':0,'repetitions':1})
        with patch.object(c,'verified_model') as model, patch.object(c,'run_container') as container:
            for bad in (None,True,'8192',0,2048,32769):
                c.m['prefill_capacity'] = bad
                with self.subTest(capacity=bad),self.assertRaisesRegex(ValueError,'prefill capacity'):
                    c.bench()
            c.m['prefill_capacity'] = 32768
            for bad in (True,0,32769):
                c.m['settings']['chunk'] = bad
                with self.subTest(chunk=bad),self.assertRaisesRegex(ValueError,'core settings'):
                    c.bench()
            model.assert_not_called(); container.assert_not_called()

    def test_modern_core_eos_policy_is_forwarded_and_bound_without_shortening_oracle(self):
        for mode in ('ar','mtp'):
            c=self.campaign('eos-policy-'+mode)
            tokens=c.root/'tokens.json';tokens.write_text('[1,2,3]')
            c.m.update(action='bench',stack='rocm10-fedora43',transport='distrobox',
                       bench_profile='modern-core',decode_mode=mode,bundle=str(self.base),
                       model_plan={'files':[{'name':'target.gguf'}]},tokens_sha256=point.sha(tokens),
                       prompt_tokens_expected=3,runtime_build_id='fixture-runtime',
                       settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':0,'repetitions':1})
            returned=['stop'];count=[32];finish=['length']
            def run(command,*_args):
                self.assertEqual('--ignore-eos' in command,c.m.get('eos_policy','stop')=='ignore')
                identity={'event':'identity','schema':'synapse-lie.core-bench.v1','mode':mode,
                          'synthetic':False,'cache_policy':'off','build_id':'fixture-runtime'}
                if returned[0]!='absent':identity['eos_policy']=returned[0]
                rows=[identity,{'event':'job','prompt_tokens':3,'output_tokens':count[0],'finish':finish[0],
                                'mtp_drafted_tokens':4 if mode=='mtp' else 0,
                                'mtp_accepted_tokens':3 if mode=='mtp' else 0},
                      {'event':'sample'},{'event':'complete','exit_code':0}]
                (c.root/'measurements.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with patch.object(c,'verified_model',return_value=(self.base,[])), \
                 patch.object(c,'verified_predictor',return_value=(self.base/'mtp.gguf',{})), \
                 patch.object(c,'run_container',side_effect=run),patch.object(c,'check_model_after'):
                c.bench();self.assertEqual(c.r['bench_result']['eos_policy'],'stop')
                returned[0]='absent';c.bench() # Historical results mean stop.
                count[0]=7
                with self.assertRaisesRegex(RuntimeError,'Incomplete modern core output'):c.bench()
                c.m['eos_policy']='ignore';returned[0]='ignore';count[0]=32
                c.bench();self.assertEqual(c.r['bench_result']['eos_policy'],'ignore')
                count[0]=7
                with self.assertRaisesRegex(RuntimeError,'Incomplete modern core output'):c.bench()
                count[0]=32;finish[0]='stop'
                with self.assertRaisesRegex(RuntimeError,'Incomplete modern core output'):c.bench()
                finish[0]='length'
                for value in ('stop','absent',None,True,1,'unknown'):
                    returned[0]=value
                    with self.subTest(mode=mode,value=value),self.assertRaisesRegex(RuntimeError,'benchmark identity'):c.bench()
    def test_modern_core_refuses_bad_eos_policy_before_model_or_container(self):
        c=self.campaign('eos-policy-preflight')
        c.m.update(action='bench',stack='rocm10-fedora43',transport='distrobox',
                   bench_profile='modern-core',decode_mode='ar',
                   settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':0,'repetitions':1})
        with patch.object(c,'verified_model') as model,patch.object(c,'run_container') as container:
            for value in (None,True,1,{},[], 'unknown'):
                c.m['eos_policy']=value
                with self.subTest(value=value),self.assertRaisesRegex(ValueError,'EOS policy'):c.bench()
            model.assert_not_called();container.assert_not_called()
    def test_modern_core_sampling_refuses_bad_profiles_before_model_or_container(self):
        c = self.campaign('sampling-preflight')
        profile = {'temperature':1,'top_p':1,'frequency_penalty':0,
                   'presence_penalty':0,'seed':123,'top_k':0,'min_p':.05}
        c.m.update(action='bench',stack='rocm10-fedora43',transport='distrobox',
                   bench_profile='modern-core',decode_mode='ar',
                   settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':0,'repetitions':1})
        with patch.object(c,'verified_model') as model, patch.object(c,'run_container') as container:
            for value in (None,dict(profile,seed=-1),dict(profile,min_p=True),dict(profile,top_k=2147483648)):
                c.m['generation'] = value
                with self.subTest(value=value), self.assertRaises(ValueError):
                    c.bench()
            model.assert_not_called(); container.assert_not_called()
    def test_modern_core_ar_and_mtp_require_real_output_and_predictor_identity(self):
        def plan(directory, name):
            directory.mkdir()
            path = directory/name; path.write_bytes(b'fixture '+name.encode())
            st = path.stat()
            row = {'path': str(path), 'bytes': st.st_size, 'device': st.st_dev,
                   'inode': st.st_ino, 'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns,
                   'sha256': point.sha(path)}
            result = {'destination': str(directory), 'files': [{'name': name, 'sha256': row['sha256']}]}
            (directory/'SOURCE.json').write_text(json.dumps({'result': {'state': 'VERIFIED', 'files': [row]},
                                                               'plan': result}))
            return result
        model = plan(self.base/'model', 'target.gguf')
        predictor = plan(self.base/'predictor', 'mtp.gguf')
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-'+mode)
                tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
                c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                           bench_profile='modern-core', decode_mode=mode, bundle=str(self.base),
                           model_plan=model, tokens_sha256=point.sha(tokens), prompt_tokens_expected=3,
                           runtime_build_id='rocm10-point-modern-r1-runtime',
                           settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':0,'repetitions':1})
                if mode == 'mtp': c.m['predictor_plan'] = predictor
                def run(command, _bundle, _timeout, _model):
                    self.assertEqual('--model-mtp' in command, mode == 'mtp')
                    rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                             'mode':mode,'synthetic':False,'cache_policy':'off',
                             'build_id':'rocm10-point-modern-r1-runtime'},
                            {'event':'job','prompt_tokens':3,'output_tokens':32,
                             'mtp_drafted_tokens':4 if mode=='mtp' else 0,
                             'mtp_accepted_tokens':3 if mode=='mtp' else 0},
                            {'event':'sample'}, {'event':'complete','exit_code':0}]
                    (c.root/'measurements.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                with patch.object(c, 'run_container', side_effect=run): c.bench()
                self.assertTrue(c.r['model_stat_unchanged'])
                self.assertEqual(c.r['bench_result']['accepted'], 3 if mode=='mtp' else 0)
        c.m['mtp_draft_tokens'] = 8
        with self.assertRaisesRegex(ValueError, 'draft bound'): c.bench()
    def test_modern_mtp_ram_gate_requires_a_measured_prefix_restore(self):
        c = self.campaign('modern-ram')
        tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-core-ram', decode_mode='mtp',
                   bundle=str(self.base), tokens_sha256=point.sha(tokens),
                   prompt_tokens_expected=3,
                   runtime_build_id='rocm10-point-modern-r3-runtime',
                   settings={'context':4096,'chunk':2048,'users':1,'tg':32,
                             'warmups':1,'repetitions':1},
                   model_plan={'files':[{'name':'target.gguf'}]})
        rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                 'mode':'mtp','synthetic':False,'cache_policy':'ram',
                 'build_id':'rocm10-point-modern-r3-runtime'},
                {'event':'job','warmup':1,'prompt_tokens':3,'output_tokens':32,
                 'cached_tokens':0,'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                {'event':'sample','warmup':1,'cache_hits':0},
                {'event':'job','warmup':0,'prompt_tokens':3,'output_tokens':32,
                 'cached_tokens':3,'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                {'event':'sample','warmup':0,'cache_hits':1},
                {'event':'complete','exit_code':0}]
        def run(command, _bundle, _timeout, _model):
            self.assertEqual(command[command.index('--kv-cache-ram-mb')+1], '4096')
            self.assertEqual(command[command.index('--kv-cache-policy')+1], 'ds4')
            self.assertIn('--model-mtp', command)
            (c.root/'measurements.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in rows))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            c.bench()
            self.assertEqual(c.r['bench_result']['measured_cached_tokens'], 3)
            self.assertEqual(c.r['bench_result']['measured_cache_hits'], 1)
            rows[3]['cached_tokens'] = 0
            with self.assertRaisesRegex(RuntimeError, 'did not restore'):
                c.bench()
    def test_modern_direct_reactive_probe_requires_peer_progress_and_cancel(self):
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-reactive-'+mode)
                tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
                c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                           bench_profile='modern-core-reactive-probe', decode_mode=mode,
                           bundle=str(self.base), tokens_sha256=point.sha(tokens),
                           prompt_tokens_expected=3,
                           runtime_build_id='rocm10-point-modern-r4-runtime',
                           settings={'context':4096,'chunk':2048,'users':2,'tg':32,
                                     'warmups':0,'repetitions':1},
                           model_plan={'files':[{'name':'target.gguf'}]})
                if mode == 'mtp': c.m['predictor_plan'] = {'files':[{'name':'mtp.gguf'}]}
                reactive = {'event':'reactive','scope':'direct-c-core-held-loan-peer-cancel',
                            'synthetic':False,'peer_output_tokens':32,'held_output_tokens':8,
                            'held_borrowed_tokens':1,'held_output_blocked':1,
                            'completed_delta':1,'cancelled_delta':1,'decode_batches_delta':4,
                            'mtp_drafted_delta':6 if mode=='mtp' else 0,
                            'mtp_accepted_delta':2 if mode=='mtp' else 0}
                def run(command, _bundle, _timeout, _model):
                    self.assertIn('--reactive-probe', command)
                    self.assertEqual(command[command.index('--users')+1], '2')
                    self.assertEqual('--model-mtp' in command, mode == 'mtp')
                    rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                             'mode':mode,'synthetic':False,'cache_policy':'off',
                             'reactive_probe':True,'build_id':'rocm10-point-modern-r4-runtime'},
                            {'event':'core_ready'},reactive,{'event':'complete','exit_code':0}]
                    (c.root/'measurements.jsonl').write_text(
                        ''.join(json.dumps(row)+'\n' for row in rows))
                with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
                     patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
                     patch.object(c, 'check_model_after'), \
                     patch.object(c, 'run_container', side_effect=run):
                    c.bench()
                    self.assertEqual(c.r['bench_result']['reactive'], reactive)
                    reactive['held_output_blocked'] = 0
                    with self.assertRaisesRegex(RuntimeError, 'reactive GPU probe'):
                        c.bench()
                    reactive['held_output_blocked'] = 1
                    c.m['settings']['users'] = 1
                    with self.assertRaisesRegex(ValueError, 'C2'):
                        c.bench()
    def test_modern_vision_gate_uses_pinned_image_and_real_output(self):
        fixture = point.vision_fixture_png()
        self.assertEqual(fixture[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(hashlib.sha256(fixture).hexdigest(),
                         '93fb5acb49b2a7f77581f957663f3e4572ccb1dbd8f496dcc163f6eca5c8b76e')
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-vision-'+mode)
                c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                           bench_profile='modern-core-vision', decode_mode=mode,
                           bundle=str(self.base), runtime_build_id='rocm10-point-modern-r4-runtime',
                           model_plan={'files':[{'name':'target.gguf'}]},
                           projector_plan={'files':[{'name':'projector.gguf'}]},
                           vision_fixture_sha256=hashlib.sha256(fixture).hexdigest(),
                           vision_prompt_sha256=hashlib.sha256(point.VISION_PROMPT.encode()).hexdigest(),
                           settings={'context':8192,'chunk':2048,'users':1,'tg':32,
                                     'warmups':0,'repetitions':1})
                if mode == 'mtp': c.m['predictor_plan'] = {'files':[{'name':'mtp.gguf'}]}
                def run(command, _bundle, _timeout, _model):
                    self.assertEqual(command[command.index('--model-vision')+1], '/vision/projector.gguf')
                    self.assertEqual('--model-mtp' in command, mode == 'mtp')
                    self.assertEqual((c.root/'image.png').read_bytes(), fixture)
                    self.assertEqual((c.root/'prompt.txt').read_text(), point.VISION_PROMPT)
                    rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                             'mode':'mtp+vision' if mode=='mtp' else 'vision',
                             'synthetic':False,'input_kind':'messages-with-image',
                             'image_sha256':c.m['vision_fixture_sha256'],
                             'vision_model':'/vision/projector.gguf','cache_policy':'off',
                             'build_id':'rocm10-point-modern-r4-runtime'},
                            {'event':'input','prompt_tokens':150,'physical_ids_sha256':'a'*64},
                            {'event':'job','output_tokens':2,'prefill_tokens':150,
                             'output_ids':[4,5],'mtp_accepted_tokens':1 if mode=='mtp' else 0,
                             'mtp_drafted_tokens':2 if mode=='mtp' else 0},
                            {'event':'sample'}, {'event':'complete','exit_code':0}]
                    (c.root/'measurements.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
                     patch.object(c, 'verified_projector', return_value=(self.base/'projector.gguf', {})), \
                     patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
                     patch.object(c, 'check_model_after'), \
                     patch.object(c, 'run_container', side_effect=run):
                    c.bench()
                    self.assertEqual(c.r['bench_result']['output_ids'], [4,5])
    def test_projector_receipt_requires_unchanged_file_identity(self):
        c = self.campaign('projector-identity')
        directory = self.base/'projector'; directory.mkdir()
        path = directory/'projector.gguf'; path.write_bytes(b'pinned fixture projector')
        st = path.stat()
        row = {'path':str(path),'bytes':st.st_size,'device':st.st_dev,
               'inode':st.st_ino,'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns,
               'sha256':point.sha(path)}
        plan = {'destination':str(directory),
                'files':[{'name':path.name,'sha256':row['sha256']}]}
        (directory/'SOURCE.json').write_text(json.dumps({
            'plan':plan,'result':{'state':'VERIFIED','files':[row]}}))
        c.m['projector_plan'] = plan
        self.assertEqual(c.verified_projector()[0], path)
        path.write_bytes(b'changed fixture')
        with self.assertRaisesRegex(RuntimeError, 'Projector identity drift'):
            c.verified_projector()
    def test_modern_mtp_ssd_gate_is_explicit_and_requires_disk_hit(self):
        c = self.campaign('modern-ssd')
        tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-core-ssd', decode_mode='mtp',
                   bundle=str(self.base), tokens_sha256=point.sha(tokens),
                   prompt_tokens_expected=3,
                   runtime_build_id='rocm10-point-modern-r3-runtime',
                   settings={'context':4096,'chunk':2048,'users':1,'tg':32,
                             'warmups':1,'repetitions':1},
                   model_plan={'files':[{'name':'target.gguf'}]})
        def run(command, _bundle, _timeout, _model):
            self.assertEqual(command[command.index('--kv-cache-ram-mb')+1], '0')
            self.assertEqual(command[command.index('--kv-disk-dir')+1], '/work/kv')
            self.assertEqual(command[command.index('--kv-disk-space-mb')+1], '4096')
            self.assertTrue((c.root/'kv').is_dir())
            rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                     'mode':'mtp','synthetic':False,'cache_policy':'ssd',
                     'build_id':'rocm10-point-modern-r3-runtime'},
                    {'event':'job','warmup':1,'prompt_tokens':3,'output_tokens':32,
                     'cached_tokens':0,'ssd_cached_tokens':0,
                     'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                    {'event':'sample','warmup':1,'ssd_hits':0,'ssd_errors':0},
                    {'event':'job','warmup':0,'prompt_tokens':3,'output_tokens':32,
                     'cached_tokens':3,'ssd_cached_tokens':3,
                     'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                    {'event':'sample','warmup':0,'ssd_hits':1,'ssd_errors':0},
                    {'event':'complete','exit_code':0}]
            (c.root/'measurements.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in rows))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            c.bench()
        self.assertEqual(c.r['bench_result']['measured_ssd_cached_tokens'], 3)
        self.assertEqual(c.r['bench_result']['measured_ssd_hits'], 1)
    def test_modern_http_gate_checks_original_wire_result_and_helper_identity(self):
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-http-'+mode)
                helper = c.root/'http-gate.py'
                helper.write_bytes(b'fixture HTTP helper')
                c.m.update(action='bench', stack='rocm10-fedora43',
                           transport='distrobox', bench_profile='modern-http',
                           decode_mode=mode, bundle=str(self.base),
                           model_plan={'files':[{'name':'target.gguf'}]},
                           http_gate_sha256=point.sha(helper))
                if mode == 'mtp': c.m['predictor_plan'] = {'files':[{'name':'mtp.gguf'}]}
                write = {'enabled': True}
                def run(command, _bundle, _timeout, _model):
                    self.assertEqual(command[:3], ['/usr/bin/python3','-B','/work/http-gate.py'])
                    self.assertEqual('/mtp/mtp.gguf' in command, mode == 'mtp')
                    self.assertEqual(_timeout, 1200)
                    if write['enabled']:
                        (c.root/'http-result.json').write_text(json.dumps({
                            'schema':'synapse-lie.point-http-original.v1',
                            'state':'PASSED','mode':mode,'server_exit_code':0,
                            'passed':['models','chat_json','chat_sse',
                                      'responses_json','responses_sse']}))
                with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
                     patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
                     patch.object(c, 'check_model_after'), \
                     patch.object(c, 'run_container', side_effect=run):
                    c.bench()
                    self.assertEqual(c.r['http_result']['mode'], mode)
                    helper.write_bytes(b'changed')
                    with self.assertRaisesRegex(ValueError, 'helper drift'): c.bench()
                    helper.write_bytes(b'fixture HTTP helper')
                    run_result = json.loads((c.root/'http-result.json').read_text())
                    run_result['passed'].remove('responses_sse')
                    (c.root/'http-result.json').write_text(json.dumps(run_result))
                    write['enabled'] = False
                    with self.assertRaisesRegex(RuntimeError, 'Incomplete original-weight HTTP'):
                        c.bench()
    def test_modern_http_tools_require_function_receipts_not_text_only(self):
        c = self.campaign('modern-http-tools')
        helper = c.root/'http-gate.py'; helper.write_bytes(b'fixture tool helper')
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-http', decode_mode='ar', bundle=str(self.base),
                   model_plan={'files':[{'name':'target.gguf'}]}, http_tool_gate=True,
                   http_gate_sha256=point.sha(helper))
        result = {'schema':'synapse-lie.point-http-original.v1', 'state':'PASSED',
                  'mode':'ar', 'server_exit_code':0,
                  'passed':['models','chat_json','chat_sse','responses_json','responses_sse']}
        def run(command, *_):
            self.assertEqual(command[-1], '--tools')
            (c.root/'http-result.json').write_text(json.dumps(result))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'Incomplete original-weight HTTP'):
                c.bench()
            result['passed'] += ['chat_function_json','chat_function_sse','chat_tool_result',
                                 'responses_function_json','responses_function_sse',
                                 'responses_tool_replay','responses_tool_result','allowed_tools']
            c.bench()
            self.assertEqual(len(c.r['http_result']['passed']), 13)
    def test_modern_http_controls_bind_complete_sidecar_and_refuse_partial_receipts(self):
        c = self.campaign('modern-http-controls')
        helper = c.root/'http-gate.py'; helper.write_bytes(b'fixture HTTP helper')
        controls = c.root/'http-controls.py'; controls.write_bytes(b'fixture controls helper')
        c.m.update(action='bench',stack='rocm10-fedora43',transport='distrobox',
                   bench_profile='modern-http',decode_mode='ar',bundle=str(self.base),
                   model_plan={'files':[{'name':'target.gguf'}]},http_control_gate=True,
                   http_gate_sha256=point.sha(helper),http_controls_sha256=point.sha(controls))
        selected = sorted(point.HTTP_CONTROL_CHECKS)
        result = {'schema':'synapse-lie.point-http-original.v1','state':'PASSED','mode':'ar',
                  'server_exit_code':0,'passed':['models','chat_json','chat_sse','responses_json','responses_sse']+selected}
        sidecar = {'schema':'synapse-lie.point-openai-controls.v1','state':'PASSED','passed':selected}
        def run(command,*_):
            self.assertEqual(command[-1],'--controls')
            (c.root/'http-result.json').write_text(json.dumps(result))
            (c.root/'http-controls-result.json').write_text(json.dumps(sidecar))
        with patch.object(c,'verified_model',return_value=(self.base/'model',[])), \
             patch.object(c,'check_model_after'), patch.object(c,'run_container',side_effect=run) as child:
            c.bench()
            self.assertEqual(c.r['http_controls_sha256'],point.sha(c.root/'http-controls-result.json'))
            sidecar['passed']=selected[:-1]
            with self.assertRaisesRegex(RuntimeError,'Incomplete original-weight OpenAI'): c.bench()
            sidecar['passed']=selected+[selected[0]]
            with self.assertRaisesRegex(RuntimeError,'Incomplete original-weight OpenAI'): c.bench()
            controls.write_bytes(b'changed')
            count=child.call_count
            with self.assertRaisesRegex(ValueError,'controls helper drift'): c.bench()
            self.assertEqual(child.call_count,count)
    def test_modern_http_controls_refuse_nonboolean_selection(self):
        c=self.campaign('modern-http-control-type')
        helper=c.root/'http-gate.py'; helper.write_bytes(b'fixture helper')
        c.m.update(stack='rocm10-fedora43',transport='distrobox',bench_profile='modern-http',
                   decode_mode='ar',model_plan={'files':[{'name':'target.gguf'}]},
                   http_gate_sha256=point.sha(helper),http_control_gate=1)
        with patch.object(c,'verified_model',return_value=(self.base/'model',[])), \
             patch.object(c,'run_container') as child:
            with self.assertRaisesRegex(ValueError,'boolean selection'): c.bench()
            child.assert_not_called()
    def test_modern_http_output_budgets_bind_helper_and_exact_receipt(self):
        c=self.campaign('modern-http-output-budget')
        helper=c.root/'http-gate.py';helper.write_bytes(b'fixture HTTP helper')
        budget=c.root/'http-output-budget.py';budget.write_bytes(b'fixture budget helper')
        c.m.update(action='bench',stack='rocm10-fedora43',transport='distrobox',
                   bench_profile='modern-http',decode_mode='ar',bundle=str(self.base),
                   model_plan={'files':[{'name':'target.gguf'}]},http_output_budget_gate=True,
                   http_gate_sha256=point.sha(helper),http_output_budget_sha256=point.sha(budget))
        selected=sorted(point.HTTP_OUTPUT_BUDGET_CHECKS)
        sidecar={'schema':'synapse-lie.point-output-budget.v1','state':'PASSED','passed':selected}
        result={'schema':'synapse-lie.point-http-original.v1','state':'PASSED','mode':'ar',
                'server_exit_code':0,'passed':['models','chat_json','chat_sse','responses_json','responses_sse']+selected}
        def run(command,*_):
            self.assertEqual(command[-1],'--output-budget')
            (c.root/'http-result.json').write_text(json.dumps(result))
            (c.root/'http-output-budget-result.json').write_text(json.dumps(sidecar))
        with patch.object(c,'verified_model',return_value=(self.base/'model',[])), \
             patch.object(c,'check_model_after'),patch.object(c,'run_container',side_effect=run) as child:
            c.bench()
            self.assertEqual(c.r['http_output_budget_sha256'],point.sha(c.root/'http-output-budget-result.json'))
            for invalid in (selected[:-1],selected+[selected[0]]):
                sidecar['passed']=invalid
                with self.assertRaisesRegex(RuntimeError,'Incomplete original-weight automatic'):c.bench()
            budget.write_bytes(b'changed')
            count=child.call_count
            with self.assertRaisesRegex(ValueError,'output-budget helper drift'):c.bench()
            self.assertEqual(child.call_count,count)
    def test_modern_http_output_budgets_refuse_nonboolean_before_model_access(self):
        c=self.campaign('modern-http-output-type')
        helper=c.root/'http-gate.py';helper.write_bytes(b'fixture helper')
        c.m.update(stack='rocm10-fedora43',transport='distrobox',bench_profile='modern-http',
                   decode_mode='ar',http_gate_sha256=point.sha(helper),http_output_budget_gate=1)
        with patch.object(c,'verified_model') as model,patch.object(c,'run_container') as child:
            with self.assertRaisesRegex(ValueError,'boolean selection'):c.bench()
            model.assert_not_called();child.assert_not_called()
    def test_modern_http_integer_gate_binds_separate_complete_sidecar(self):
        c=self.campaign('modern-http-integer')
        helper=c.root/'http-gate.py';helper.write_bytes(b'fixture helper')
        integer=c.root/'http-schema-integer.py';integer.write_bytes(b'integer oracle fixture')
        c.m.update(stack='rocm10-fedora43',transport='distrobox',bench_profile='modern-http',
                   decode_mode='ar',bundle=str(self.base),model_plan={'files':[{'name':'target.gguf'}]},
                   http_schema_integer_gate=True,http_gate_sha256=point.sha(helper),
                   http_schema_integer_sha256=point.sha(integer))
        selected=sorted(point.HTTP_SCHEMA_INTEGER_CHECKS)
        sidecar={'schema':'synapse-lie.point-schema-integer.v1','state':'PASSED',
                 'passed':selected,'witnesses':{k:{} for k in selected}}
        result={'schema':'synapse-lie.point-http-original.v1','state':'PASSED','mode':'ar',
                'server_exit_code':0,'schema_integer_checks':66,
                'passed':['models','chat_json','chat_sse','responses_json','responses_sse']}
        def run(command,*_):
            self.assertEqual(command[-1],'--schema-integer')
            (c.root/'http-result.json').write_text(json.dumps(result))
            (c.root/'http-schema-integer-result.json').write_text(json.dumps(sidecar))
        with patch.object(c,'verified_model',return_value=(self.base/'model',[])), \
             patch.object(c,'check_model_after'),patch.object(c,'run_container',side_effect=run) as child:
            c.bench()
            self.assertEqual(c.r['http_schema_integer_sha256'],point.sha(c.root/'http-schema-integer-result.json'))
            for invalid in (selected[:-1],selected+[selected[0]]):
                sidecar['passed']=invalid
                with self.assertRaisesRegex(RuntimeError,'Incomplete original-weight bounded'):c.bench()
            sidecar['passed']=selected;sidecar['witnesses'].pop(selected[0])
            with self.assertRaisesRegex(RuntimeError,'Incomplete original-weight bounded'):c.bench()
            integer.write_bytes(b'changed');count=child.call_count
            with self.assertRaisesRegex(ValueError,'integer-schema helper drift'):c.bench()
            self.assertEqual(child.call_count,count)

    def test_modern_http_integer_gate_refuses_nonboolean_before_model_access(self):
        c=self.campaign('modern-http-integer-type')
        helper=c.root/'http-gate.py';helper.write_bytes(b'fixture helper')
        c.m.update(stack='rocm10-fedora43',transport='distrobox',bench_profile='modern-http',
                   decode_mode='ar',http_gate_sha256=point.sha(helper),http_schema_integer_gate=1)
        with patch.object(c,'verified_model') as model,patch.object(c,'run_container') as child:
            with self.assertRaisesRegex(ValueError,'boolean selection'):c.bench()
            model.assert_not_called();child.assert_not_called()

    def test_modern_http_multi_pins_corpus_mode_and_complete_native_result(self):
        c = self.campaign('modern-http-multi')
        helper = c.root/'http-multi-gate.py'; helper.write_bytes(b'fixture multi helper')
        corpus = c.root/'corpus.jsonl'; corpus.write_bytes(b'{"id":"prose"}\n')
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-http-multi', decode_mode='ar', http_impl='lie',
                   http_users='1', http_case='prose', http_warmups=1,
                   http_repetitions=3, bundle=str(self.base),
                   model_plan={'files':[{'name':'target.gguf'}]},
                   artifacts={'runtime/bin/synapse-lie-bench':'fixture'},
                   http_multi_gate_sha256=point.sha(helper),
                   corpus_sha256=point.sha(corpus))
        def run(command, _bundle, _timeout, _model):
            self.assertIn('/bundle/runtime/bin/synapse-lie-server', command)
            self.assertEqual(_timeout, 6500)
            self.assertEqual(command[command.index('--server-sessions') + 1],
                             str(c.m.get('http_server_sessions', 8)))
            rows = [{'event':'identity', 'schema':'synapse-lie.http-multi-bench.v1',
                     'model':'qwen3.8-flash-next'}, {'event':'complete','exit_code':0}]
            data = ''.join(json.dumps(row)+'\n' for row in rows)
            (c.root/'measurements.jsonl').write_text(data)
            (c.root/'http-multi-result.json').write_text(json.dumps({
                'schema':'synapse-lie.point-http-multi-original.v1',
                'state':'PASSED','client_exit_code':0,'server_exit_code':0,
                'implementation':'lie','mode':'ar','users':c.m['http_users'],
                'capacity_policy':c.m.get('http_capacity_policy', 'fixed-8'),
                'server_sessions':c.m.get('http_server_sessions', 8), 'cohorts':4,
                'corpus_sha256':point.sha(corpus),
                'measurements_sha256':point.sha(c.root/'measurements.jsonl')}))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            c.bench()
            self.assertEqual(c.r['bench_result']['cohorts'], 4)
            c.m['http_case'] = 'repetition'
            c.bench()
            c.m.update(http_users='2', http_capacity_policy='fresh-per-level',
                       http_server_sessions=1)
            with self.assertRaisesRegex(ValueError, 'fixed prepared HTTP'): c.bench()
            c.m['http_server_sessions'] = 2
            c.bench()
            self.assertEqual(c.r['bench_result']['capacity_policy'], 'fresh-per-level')
            c.m['http_case'] = 'prose'
            corpus.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'corpus drift'): c.bench()
            corpus.write_bytes(b'{"id":"prose"}\n')
            c.m['http_impl'] = 'gufo'
            bundle_receipt = self.base/'BUNDLE.json'; bundle_receipt.write_text('{}')
            c.m['artifacts'].update({'runtime/bin/gufo':'fixture',
                                     'BUNDLE.json':point.sha(bundle_receipt)})
            with self.assertRaisesRegex(ValueError, 'Gufo control provenance'):
                c.bench()
    def test_http_multi_helper_sets_fresh_server_capacity(self):
        module_path = Path(__file__).resolve().parents[1]/'tools/strix-point-http-multi-gate.py'
        helper_spec = importlib.util.spec_from_file_location('point_http_multi', module_path)
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        args = SimpleNamespace(impl='gufo', mode='ar', server='/bundle/gufo',
                               model='/model/target.gguf', predictor=None,
                               server_sessions=2)
        gufo = helper.server_command(args, 9000)
        self.assertEqual(gufo[gufo.index('--sessions') + 1], '2')
        args.impl = 'lie'
        lie = helper.server_command(args, 9000)
        self.assertEqual(lie[lie.index('--max-active') + 1], '2')
    def test_modern_ssd_restart_requires_a_cross_process_disk_hit(self):
        c = self.campaign('modern-ssd-restart')
        helper = c.root/'ssd-restart-gate.py'; helper.write_bytes(b'fixture restart helper')
        tokens = c.root/'tokens.json'; tokens.write_text(json.dumps([1]*8192))
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-core-ssd-restart', decode_mode='mtp',
                   bundle=str(self.base), model_plan={'files':[{'name':'target.gguf'}]},
                   predictor_plan={'files':[{'name':'mtp.gguf'}]},
                   ssd_restart_gate_sha256=point.sha(helper), tokens_sha256=point.sha(tokens))
        write = {'enabled': True}
        def run(command, _bundle, timeout, _model):
            self.assertEqual(command[:3], ['/usr/bin/python3','-B','/work/ssd-restart-gate.py'])
            self.assertIn('/mtp/mtp.gguf', command)
            self.assertEqual(timeout, 1500)
            if write['enabled']:
                (c.root/'ssd-restart-result.json').write_text(json.dumps({
                    'schema':'synapse-lie.point-ssd-restart.v1','state':'PASSED',
                    'mode':'mtp','cold_exit_code':0,'hot_exit_code':0,
                    'hot_cached_tokens':8192,'hot_prefill_tokens':0,
                    'hot_ssd_cached_tokens':8192,'hot_ssd_hits':1,
                    'ssd_errors':0,'output_ids_equal':True}))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            c.bench()
            self.assertEqual(c.r['ssd_restart_result']['hot_cached_tokens'], 8192)
            self.assertTrue((c.root/'kv').is_dir())
            helper.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'helper or tokens drift'): c.bench()
            helper.write_bytes(b'fixture restart helper')
            value = json.loads((c.root/'ssd-restart-result.json').read_text())
            value['hot_ssd_hits'] = 0
            (c.root/'ssd-restart-result.json').write_text(json.dumps(value))
            write['enabled'] = False
            with self.assertRaisesRegex(RuntimeError, 'Incomplete original-weight SSD restart'):
                c.bench()
    def test_rocm_stack_identity_is_explicit(self):
        c = self.campaign()
        self.assertEqual(c.image_and_rocm(), (point.IMAGE, point.ROCM))
        c.m['stack'] = 'rocm10-fedora43'
        c.m['image'] = 'unversioned-image'
        with self.assertRaisesRegex(ValueError, 'pinned'): c.image_and_rocm()
        image = 'sha256:'+'a'*64
        c.m['image'] = image
        with patch.object(c, 'command', return_value=subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({'Id': image, 'Architecture': 'amd64'}))):
            self.assertEqual(c.image_and_rocm(), (image, None))
            c.m['stack'] = 'rocm10-fedora44-rpm'
            self.assertEqual(c.image_and_rocm(), (image, None))
            c.m['stack'] = 'rocm10-almalinux10-rpm'
            self.assertEqual(c.image_and_rocm(), (image, None))
        with patch.object(c, 'command', return_value=subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({'Id': 'sha256:'+'b'*64, 'Architecture': 'amd64'}))):
            with self.assertRaisesRegex(ValueError, 'identity'): c.image_and_rocm()
    def test_distrobox_benchmark_transport_is_explicit(self):
        c = self.campaign(); bundle = self.base/'bundle'; bundle.mkdir()
        (bundle/'probe').write_bytes(b'fixture')
        model = self.base/'model'; model.mkdir()
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   distrobox_name='lie-test', artifacts={'probe': point.sha(bundle/'probe')})
        image = 'sha256:'+'a'*64
        with patch.object(c, 'image_and_rocm', return_value=(image, None)), \
             patch.object(c, 'execute_distrobox') as execute:
            c.run_container(['/bench'], bundle, 10, model)
            execute.assert_called_once_with(['/bench'], bundle, model, image, 10)
        c.m['transport'] = 'unknown'
        with patch.object(c, 'image_and_rocm', return_value=(image, None)):
            with self.assertRaisesRegex(ValueError, 'transport'):
                c.run_container(['/bench'], bundle, 10, model)
        c.m['transport'] = 'distrobox'; c.m['distrobox_name'] = 'foreign-name'
        with self.assertRaisesRegex(ValueError, 'explicit ROCm 10 name'):
            c.execute_distrobox(['/bench'], bundle, model, image, 10)
    def test_rocm10_build_has_no_gpu_devices_or_network(self):
        c = self.campaign()
        source = self.base/'rocm10-fedora-161'/'source'
        (source/'tools').mkdir(parents=True)
        (source.parent/'source.tar.gz').write_bytes(b'fixture source archive')
        helper = source/'tools/strix-point-rocm10-compile.py'
        helper.write_bytes(b'fixture compile helper')
        c.m.update(stack='rocm10-fedora43',
                   source_archive_sha256=point.sha(source.parent/'source.tar.gz'),
                   compile_helper_sha256=point.sha(helper))
        image = 'sha256:'+'c'*64
        def run(argv, timeout, model_attempted=False):
            self.assertEqual(timeout, 7200)
            self.assertFalse(model_attempted)
            self.assertNotIn('--device', argv)
            self.assertEqual(argv[argv.index('--network')+1], 'none')
            self.assertEqual(argv[argv.index('--entrypoint')+1], '/usr/bin/python3')
            receipt = source/'evidence/rocm10-point-compile-r1/result.json'
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"state":"BUILT_NOT_GPU_TESTED","exit_code":0}')
        with patch.object(point, 'ROCM10_SOURCE', source), \
             patch.object(c, 'image_and_rocm', return_value=(image, None)), \
             patch.object(c, 'execute_container', side_effect=run):
            c.build()
        self.assertEqual(c.r['build_result']['exit_code'], 0)
    def test_point_gufo_server_port_build_is_sealed_and_device_free(self):
        c = self.campaign('gufo-port-build')
        source = self.base/'rocm10-fedora-161/source-modern-r6'
        source.mkdir(parents=True)
        (source/'SOURCE-COMMIT.txt').write_text('128f490\n')
        inventory = source/'SOURCE-FILES.sha256'; inventory.write_bytes(b'fixture inventory')
        wmma = self.base/'rocm10-fedora-161/rocwmma-point-2.2.0'
        wmma.mkdir(parents=True)
        (wmma/'FILES.sha256').write_bytes(b'fixture headers')
        helper = c.root/'gufo-build.py'; helper.write_bytes(b'fixture Gufo builder')
        c.m.update(stack='rocm10-fedora43', build_flavor='gufo-point-server',
                   source_commit='128f490', source_files_sha256=point.sha(inventory),
                   rocwmma_files_sha256=point.sha(wmma/'FILES.sha256'),
                   gufo_build_helper_sha256=point.sha(helper))
        def run(argv, timeout, model_attempted=False):
            self.assertEqual(timeout, 7500)
            self.assertFalse(model_attempted)
            self.assertNotIn('--device', argv)
            self.assertEqual(argv[argv.index('--network')+1], 'none')
            self.assertIn('ROCR_VISIBLE_DEVICES=-1', argv)
            binary = c.root/'gufo-build/gufo'; binary.parent.mkdir(); binary.write_bytes(b'fixture')
            (c.root/'gufo-build-result.json').write_text(json.dumps({
                'schema':'synapse-lie.point-gufo-port-build.v1',
                'state':'BUILT_NOT_GPU_TESTED','exit_code':0,
                'upstream_pin':'f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                'target':'gfx1150','gpu_device_available':False,
                'installation':False,'binary_sha256':point.sha(binary)}))
        with patch.object(c, 'image_and_rocm', return_value=('sha256:'+'d'*64,None)), \
             patch.object(c, 'execute_container', side_effect=run):
            c.build()
        self.assertEqual(c.r['build_result']['state'], 'BUILT_NOT_GPU_TESTED')
    def modern_rocm10_build_fixture(self, omit_capture=False, corrupt_capture=False,
                                   omit_attention=False, corrupt_attention=False,
                                   long_selection=True, long_receipt='match'):
        c = self.campaign()
        label = 'rocm10-point-modern-r1'
        commit = 'abcdef0123456789'
        source = self.base/'rocm10-fedora-161'/'source-modern-r1'
        helper = source/'cmake/point/Build.cmake'
        helper.parent.mkdir(parents=True)
        helper.write_bytes(b'fixture CMake helper')
        (source/'SOURCE-COMMIT.txt').write_text(commit+'\n')
        inventory = source/'SOURCE-FILES.sha256'
        inventory.write_text(''.join(f'{point.sha(source/name)}  ./{name}\n'
                                     for name in ('SOURCE-COMMIT.txt','cmake/point/Build.cmake')))
        archive = source.with_suffix('.tar.gz')
        archive.write_bytes(b'sealed source fixture')
        c.m.update(stack='rocm10-fedora43', build_flavor='modern-cmake',
                   build_label=label, source_commit=commit,
                   source_archive_sha256=point.sha(archive),
                   source_files_sha256=point.sha(inventory),
                   compile_helper_sha256=point.sha(helper))
        c.m['long_context_wmma'] = long_selection
        image = 'sha256:'+'d'*64
        def run(argv, timeout, model_attempted=False):
            self.assertEqual(timeout, 7200)
            self.assertFalse(model_attempted)
            self.assertNotIn('--device', argv)
            self.assertEqual(argv[argv.index('--network')+1], 'none')
            self.assertEqual(argv[argv.index('--entrypoint')+1], '/usr/bin/cmake')
            self.assertIn('-DLABEL='+label, argv)
            self.assertIn('-DLIE_LONG_CONTEXT_WMMA='+('ON' if long_selection else 'OFF'), argv)
            binary_dir = source/'build'/f'{label}-runtime'
            binary_dir.mkdir()
            names = ('synapse-lie-server','synapse-lie-bench',
                     'synapse-lie-bench-gufo-reference','lie-hip-probe','lie-sampling-capture','lie-attention-qualify')
            binaries = {}
            for name in names:
                if name == 'lie-sampling-capture' and omit_capture:
                    continue
                if name == 'lie-attention-qualify' and omit_attention:
                    continue
                file = binary_dir/name
                file.write_bytes(name.encode())
                binaries[name] = '0'*64 if name == 'lie-sampling-capture' and corrupt_capture else point.sha(file)
                if name == 'lie-attention-qualify' and corrupt_attention:
                    binaries[name] = '0'*64
            receipt = source/'evidence'/f'{label}-compile'/'result.json'
            receipt.parent.mkdir()
            data = {'state':'BUILT_NOT_GPU_TESTED',
                                           'exit_code':0,'source_commit':commit,
                                           'label':label,'hip_architecture':'gfx1150',
                                           'checkpoint_compression':True,
                                           'binaries':binaries}
            if long_receipt != 'missing':
                data['long_context_wmma'] = long_selection if long_receipt == 'match' else long_receipt
            receipt.write_text(json.dumps(data))
        with patch.object(c, 'image_and_rocm', return_value=(image, None)), \
             patch.object(c, 'execute_container', side_effect=run):
            c.build()
        return c
    def test_modern_rocm10_build_is_sealed_and_device_free(self):
        c = self.modern_rocm10_build_fixture()
        self.assertEqual(c.r['build_result']['source_commit'], 'abcdef0123456789')
        self.assertIn('lie-sampling-capture', c.r['build_result']['binaries'])
    def test_modern_build_refuses_missing_capture_artifact(self):
        with self.assertRaisesRegex(RuntimeError, 'Modern binary inventory mismatch'):
            self.modern_rocm10_build_fixture(omit_capture=True)
    def test_modern_build_refuses_changed_capture_artifact(self):
        with self.assertRaisesRegex(RuntimeError, 'Modern binary drift: lie-sampling-capture'):
            self.modern_rocm10_build_fixture(corrupt_capture=True)
    def test_modern_build_refuses_missing_attention_artifact(self):
        with self.assertRaisesRegex(RuntimeError, 'Modern binary inventory mismatch'):
            self.modern_rocm10_build_fixture(omit_attention=True)
    def test_modern_build_refuses_changed_attention_artifact(self):
        with self.assertRaisesRegex(RuntimeError, 'Modern binary drift: lie-attention-qualify'):
            self.modern_rocm10_build_fixture(corrupt_attention=True)
    def test_modern_build_long_workspace_off_is_explicit(self):
        c = self.modern_rocm10_build_fixture(long_selection=False)
        self.assertIs(c.r['build_result']['long_context_wmma'], False)
    def test_modern_build_refuses_nonboolean_long_workspace(self):
        with self.assertRaisesRegex(ValueError, 'selection must be boolean'):
            self.modern_rocm10_build_fixture(long_selection='true')
    def test_modern_build_refuses_missing_long_workspace_receipt(self):
        with self.assertRaisesRegex(RuntimeError, 'Incomplete modern ROCm 10 build receipt'):
            self.modern_rocm10_build_fixture(long_receipt='missing')
    def test_modern_build_refuses_wrong_long_workspace_receipt(self):
        with self.assertRaisesRegex(RuntimeError, 'Incomplete modern ROCm 10 build receipt'):
            self.modern_rocm10_build_fixture(long_receipt=False)
    def test_modern_build_refuses_nonboolean_long_workspace_receipt(self):
        with self.assertRaisesRegex(RuntimeError, 'Incomplete modern ROCm 10 build receipt'):
            self.modern_rocm10_build_fixture(long_receipt=1)
    def test_seccomp_override_requires_explicit_rocm10_manifest(self):
        c = self.campaign()
        bundle = self.base/'bundle'; bundle.mkdir()
        (bundle/'probe').write_bytes(b'fixture')
        c.m.update(artifacts={'probe': point.sha(bundle/'probe')},
                   rocm10_seccomp_unconfined=True)
        with patch.object(point, 'kfd_group', return_value=1000), \
             patch.object(c, 'image_and_rocm', return_value=(point.IMAGE, point.ROCM)):
            with self.assertRaisesRegex(ValueError, 'ROCm 10 only'):
                c.run_container(['/probe'], bundle, 1)
        c = self.campaign('rocm10')
        c.m.update(artifacts={'probe': point.sha(bundle/'probe')},
                   rocm10_seccomp_unconfined=True, stack='rocm10-fedora43')
        with patch.object(point, 'kfd_group', return_value=1000), \
             patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)), \
             patch.object(c, 'execute_container') as execute:
            c.run_container(['/probe'], bundle, 1)
        argv = execute.call_args.args[0]
        self.assertIn('seccomp=unconfined', argv)
        self.assertNotIn('dst=/opt/rocm,readonly', argv)
    def test_diagnostic_retains_hip_failure(self):
        c = self.campaign()
        c.m.update(bundle=str(self.base))
        def run(*_args):
            (c.root/'stdout.log').write_text(json.dumps({
                'scope': 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL',
                'steps': [{'step': 'copy_pageable_h2d_32', 'code': 1,
                           'name': 'hipErrorInvalidValue'}]}))
        with patch.object(c, 'run_container', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'HIP errors'): c.diagnostic()
        self.assertEqual(c.r['diagnostic']['steps'][0]['name'], 'hipErrorInvalidValue')
    def test_almalinux_native_diagnostic_uses_compiled_binary(self):
        c = self.campaign()
        c.m.update(stack='rocm10-almalinux10-rpm', diagnostic_impl='native', bundle=str(self.base))
        def run(command, *_args):
            self.assertEqual(command, ['/opt/lie/hip-smoke'])
            (c.root/'stdout.log').write_text(json.dumps({
                'scope': 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL', 'device_count': 1,
                'steps': [{'step': 'copy_pageable_h2d_32', 'code': 0}],
                'output': [1, 3, 2, 4, 5, 7, 6, 8]}))
        with patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)), \
             patch.object(c, 'run_container', side_effect=run):
            c.diagnostic()
        self.assertEqual(c.r['diagnostic_impl'], 'native')
        c.m['stack'] = 'rocm10-fedora44-rpm'
        with patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)):
            with self.assertRaisesRegex(ValueError, 'implementation'): c.diagnostic()
    def test_diagnostic_requires_exact_round_trip(self):
        c = self.campaign()
        c.m.update(bundle=str(self.base))
        def run(*_args):
            (c.root/'stdout.log').write_text(json.dumps({
                'scope': 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL', 'device_count': 1,
                'steps': [{'step': 'copy_d2h_32', 'code': 0}], 'output': [0]*8}))
        with patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)), \
             patch.object(c, 'run_container', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'HIP errors'): c.diagnostic()
    def test_almalinux_image_build_checks_native_source_hash(self):
        c = self.campaign()
        context = self.base/'alma'; context.mkdir()
        (context/'Dockerfile').write_text('FROM scratch\n')
        (context/'hip-smoke.cpp').write_text('// fixture\n')
        c.m.update(stack='rocm10-almalinux10-rpm',
                   dockerfile_sha256=point.sha(context/'Dockerfile'),
                   hip_smoke_sha256='0'*64)
        with patch.object(point, 'ROCM10_ALMA_CONTEXT', context):
            with self.assertRaisesRegex(ValueError, 'smoke source drift'): c.image_build()
            c.m['hip_smoke_sha256'] = point.sha(context/'hip-smoke.cpp')
            (context/'unexpected').write_text('fixture')
            with self.assertRaisesRegex(ValueError, 'context contents'): c.image_build()
    def test_full_rocm10_profile_is_diagnostic_only_and_explicit(self):
        c = self.campaign()
        bundle = self.base/'bundle'; bundle.mkdir()
        (bundle/'probe').write_bytes(b'fixture')
        c.m.update(action='diagnostic', stack='rocm10-fedora44-rpm',
                   artifacts={'probe': point.sha(bundle/'probe')},
                   rocm10_diagnostic_full_profile=True)
        with patch.object(point, 'kfd_group', return_value=1000), \
             patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)):
            with self.assertRaisesRegex(ValueError, 'requires explicit'):
                c.run_container(['/probe'], bundle, 1)
            c.m.update(rocm10_seccomp_unconfined=True,
                       rocm10_published_container_profile=True)
            with patch.object(c, 'execute_container') as execute:
                c.run_container(['/probe'], bundle, 1)
            argv = execute.call_args.args[0]
            self.assertNotIn('--read-only', argv)
            self.assertNotIn('--cap-drop', argv)
            self.assertNotIn('no-new-privileges', argv)
            self.assertEqual(argv[argv.index('--ipc')+1], 'host')
            self.assertIn('SYS_PTRACE', argv)
            self.assertIn('LD_LIBRARY_PATH=/bundle/runtime/lib:/opt/rocm/core/lib/rocm_sysdeps/lib:/opt/rocm/lib', argv)
            c.m['action'] = 'bench'
            with self.assertRaisesRegex(ValueError, 'requires explicit'):
                c.run_container(['/probe'], bundle, 1)

if __name__ == '__main__': unittest.main()
