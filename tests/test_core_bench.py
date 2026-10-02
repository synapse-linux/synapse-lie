#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Shared-core consumer/accounting fixtures; never model inference."""
import copy
import importlib.util
import hashlib
import os
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import tempfile
import unittest

BINARY=str(Path(sys.argv.pop(1)).resolve())
REPORT=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/bench-report.py'))
RUNNER=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/run-bench.py'))


class CoreBench(unittest.TestCase):
    def test_state_ssd_cross_process_exact_pairs_and_corruption(self):
        with tempfile.TemporaryDirectory(prefix='lie-state-ssd-') as tmp:
            root=Path(tmp);source=root/'tokens.json';source.write_text(json.dumps(list(range(12))))
            store=root/'store'
            def run(name,mode,checkpoint=8):
                output=root/(name+'.jsonl')
                p=subprocess.run([BINARY,'--suite','state','--model',':fixture:','--output',str(output),
                                  '--tokens-file',str(source),'--pp',str(checkpoint),'--chunk','4','--context','128',
                                  '--state-ssd-mode',mode,'--prefix-ssd-dir',str(store),
                                  '--prefix-ssd-quota-mib','1','--prefix-ssd-staging-mib','1'],capture_output=True,text=True,timeout=15)
                return p,output
            p,path=run('write','write');self.assertEqual(p.returncode,0,p.stderr)
            written=REPORT['read_result'](path);self.assertEqual(written['pairs'],[])
            self.assertEqual(written['ssd_transfer']['writes'],1)
            p,path=run('read','read');self.assertEqual(p.returncode,0,p.stderr)
            restored=REPORT['read_result'](path)
            self.assertEqual(restored['ssd']['stable_identity_sha256'],written['ssd']['stable_identity_sha256'])
            self.assertEqual(len(restored['pairs']),3)
            self.assertEqual(restored['pairs'][0]['new_tokens'],4)
            self.assertEqual(restored['pairs'][0]['output_ids'],list(range(16)))
            # A shorter available prefix is not sufficient for this exact gate.
            p,path=run('wrong-frontier','read',12);self.assertEqual(p.returncode,1)
            with self.assertRaises(ValueError):REPORT['read_result'](path)
            p,path=run('nonempty-write','write');self.assertEqual(p.returncode,1)
            checkpoint=next(store.glob('*.lie'))
            with checkpoint.open('r+b') as f:
                f.seek(-1,2);byte=f.read(1);f.seek(-1,2);f.write(bytes([byte[0]^1]))
            p,path=run('corrupt','read');self.assertEqual(p.returncode,1)
            with self.assertRaises(ValueError):REPORT['read_result'](path)

    def test_ssd_restart_accounting(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-ssd-') as tmp:
            root=Path(tmp);store=root/'store';results=[]
            args=['--prefix-ssd-dir',str(store),'--prefix-ssd-quota-mib','1','--prefix-ssd-staging-mib','1']
            for index in range(2):
                case=root/str(index);case.mkdir()
                p,path=self.run_case(case,*args)
                self.assertEqual(p.returncode,0,p.stderr)
                result=REPORT['read_result'](path);results.append(result)
                self.assertEqual(result['identity']['cache_policy'],'ssd')
                self.assertEqual(result['jobs'][0]['ssd_cached_tokens'],0 if index==0 else 4)
                if index==1:self.assertEqual(result['jobs'][0]['prefill_ns'],0)
                rows=[json.loads(line) for line in path.read_text().splitlines()]
                drained=next(row for row in rows if row['event']=='ssd_drained')
                self.assertEqual(drained['pending'],0)
                self.assertEqual(drained['errors'],0)
            self.assertEqual(results[0]['configurations'][0]['output_ids'],results[1]['configurations'][0]['output_ids'])
            REPORT['export'](results[1],root/'graphs','SSD fixture')
            self.assertIn('ssd_read_median_ms',(root/'graphs/summary.csv').read_text())
            bad=copy.deepcopy(results[1]);bad['configurations'][0]['ssd_staging_bytes']*=2
            with self.assertRaises(ValueError):REPORT['compare'](results[1],bad)

    def test_typed_state_clone_and_suffix(self):
        with tempfile.TemporaryDirectory(prefix='lie-state-bench-') as tmp:
            root=Path(tmp);source=root/'input.json';source.write_text(json.dumps(list(range(12))))
            for checkpoint in (8,12):
                output=root/f'state-{checkpoint}.jsonl'
                p=subprocess.run([BINARY,'--suite','state','--model',':fixture:','--output',str(output),'--tokens-file',str(source),'--pp',str(checkpoint),'--chunk','4','--context','128'],capture_output=True,text=True,timeout=15)
                self.assertEqual(p.returncode,0,p.stderr)
                data=REPORT['read_result'](output)
                self.assertEqual(len(data['pairs']),3)
                self.assertEqual(data['pairs'][0]['reused_tokens'],checkpoint)
                self.assertEqual(data['pairs'][0]['new_tokens'],12-checkpoint)
                self.assertEqual(data['pairs'][0]['output_ids'],list(range(16)))

    def run_case(self,root,*args,model=':fixture:',tokens=None,text=None,cache='0'):
        root=Path(root);source=root/'input';output=root/'result.jsonl'
        source.write_text(text if text is not None else json.dumps(tokens or [0,1,2,3]))
        kind='--prompt-file' if text is not None else '--tokens-file'
        p=subprocess.run([BINARY,'--suite','core','--model',model,'--output',str(output),kind,str(source),
                          '--tg','16','--repetitions','2',*(['--prefix-cache-mib',cache] if cache is not None else []),*args],capture_output=True,text=True,timeout=15)
        return p,output

    def test_real_core_lifecycle_counts_and_replay(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-bench-') as tmp:
            p,path=self.run_case(tmp,'--users','4','--warmups','1')
            self.assertEqual(p.returncode,0,p.stderr)
            r=REPORT['read_result'](path)
            self.assertTrue(r['identity']['synthetic'])
            self.assertEqual(r['identity']['execution'],'shared-reactive-core')
            self.assertEqual(len(r['jobs']),12)
            self.assertEqual(len(r['samples']),3)
            for row in r['jobs']:
                self.assertEqual(row['prefill_tokens'],4)
                self.assertEqual(row['output_tokens'],16)
                self.assertEqual(row['output_ids'],list(range(16)))
            for row in r['samples']:
                self.assertEqual(row['output_tokens'],64)
                self.assertAlmostEqual(row['output_per_total_wall_tps'],64e9/row['wall_ns'])
            self.assertTrue(REPORT['compare'](r,r)[0]['eligible'])

    def test_ram_default_and_accounted_full_hit(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-cache-') as tmp:
            p,path=self.run_case(tmp,'--warmups','1',cache=None)
            self.assertEqual(p.returncode,0,p.stderr)
            result=REPORT['read_result'](path)
            self.assertEqual(result['identity']['cache_policy'],'ram')
            self.assertEqual(result['identity']['prefix_cache_bytes'],4*1024**3)
            self.assertEqual(result['jobs'][0]['cached_tokens'],0)
            for job in result['jobs'][1:]:
                self.assertEqual(job['cached_tokens'],4)
                self.assertEqual(job['prefill_tokens'],0)
                self.assertEqual(job['prefill_ns'],0)
                self.assertEqual(job['output_ids'],list(range(16)))
            self.assertIsNone(result['configurations'][0]['job_prefill_tps'])
            REPORT['export'](result,Path(tmp)/'graphs','RAM fixture')
            self.assertTrue((Path(tmp)/'graphs/benchmark.png').exists())
            rows=[json.loads(x) for x in path.read_text().splitlines()]
            next(r for r in rows if r['event']=='job' and not r['warmup'])['cached_tokens']=5
            bad=Path(tmp)/'bad.jsonl';bad.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
            with self.assertRaises(ValueError):REPORT['read_result'](bad)

    def test_raw_text_and_early_eos(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-raw-') as tmp:
            p,path=self.run_case(tmp,model=':eos:',text='abc def ghi jkl')
            self.assertEqual(p.returncode,0,p.stderr)
            r=REPORT['read_result'](path)
            self.assertEqual(r['identity']['input_kind'],'raw-text')
            self.assertEqual(r['configurations'][0]['prompt_tokens'],4)
            self.assertFalse(r['configurations'][0]['full_output_budget'])
            self.assertEqual(r['jobs'][0]['output_tokens'],7)
            self.assertEqual(r['jobs'][0]['finish'],'stop')

    def test_failure_preserved_and_no_average(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-failure-') as tmp:
            p,path=self.run_case(tmp,model=':failure:')
            self.assertEqual(p.returncode,1,p.stderr)
            rows=[json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(rows[-1]['event'],'failed')
            with self.assertRaises(ValueError):REPORT['read_result'](path)

    def test_invalid_input_and_exclusive_output(self):
        for tokens in [[-1],[2147483648],[True],[256]]:
            with tempfile.TemporaryDirectory(prefix='lie-core-invalid-') as tmp:
                p,path=self.run_case(tmp,tokens=tokens)
                self.assertNotEqual(p.returncode,0)
                if path.exists():self.assertEqual(json.loads(path.read_text().splitlines()[-1])['event'],'failed')
        with tempfile.TemporaryDirectory(prefix='lie-core-exclusive-') as tmp:
            path=Path(tmp)/'result.jsonl';path.write_text('preserve\n')
            p,_=self.run_case(tmp)
            self.assertEqual(p.returncode,1);self.assertEqual(path.read_text(),'preserve\n')

    def test_report_rejects_corruption_and_scope_mismatch(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-report-') as tmp:
            p,path=self.run_case(tmp);self.assertEqual(p.returncode,0,p.stderr)
            original=[json.loads(x) for x in path.read_text().splitlines()]
            for mode in ['count','hash','ids','time','missing']:
                rows=copy.deepcopy(original)
                if mode=='missing':rows.pop()
                elif mode=='hash':next(r for r in rows if r['event']=='input')['physical_ids_sha256']='bad'
                elif mode=='ids':next(r for r in rows if r['event']=='job')['output_ids'][0]=5
                elif mode=='count':next(r for r in rows if r['event']=='sample')['output_tokens']=0
                else:next(r for r in rows if r['event']=='job')['first_token_ns']=-1
                bad=Path(tmp)/'bad.jsonl';bad.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
                with self.assertRaises(ValueError):REPORT['read_result'](bad)
            result=REPORT['read_result'](path);other=copy.deepcopy(result)
            other['configurations'][0]['prefill_chunk']=1
            with self.assertRaises(ValueError):REPORT['compare'](result,other)

    def test_supervisor_binds_core_input_and_ports(self):
        bind=RUNNER['bind_args']
        with tempfile.TemporaryDirectory(prefix='lie-core-binding-') as tmp:
            root=Path(tmp);p=root/'tokens.json';p.write_text('[1,2,3]')
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            manifest={'files':{'tokens.json':digest},'benchmark_input':{'path':'tokens.json','bytes':p.stat().st_size,'sha256':digest}}
            args=['--suite','core','--tokens-file','tokens.json','--users','2']
            self.assertEqual(bind(args,root,manifest)[3],str(p))
            for invalid in [args+['--tokens-file','tokens.json'],args+['--prompt-file','tokens.json'],
                            ['--suite','core'],['--suite','core','--tokens-file','../tokens.json'],
                            args+['--execution','serial'],args+['--output','escape']]:
                with self.assertRaises(ValueError):bind(invalid,root,manifest)
            for key,value in [('bytes',0),('bytes',True),('bytes',100),('sha256','wrong'),('path','elsewhere')]:
                bad=copy.deepcopy(manifest);bad['benchmark_input'][key]=value
                with self.assertRaises(ValueError):bind(args,root,bad)
            p.write_text('[4,5,6]')
            with self.assertRaises(ValueError):bind(args,root,manifest)
            p.unlink();p.symlink_to(root/'missing')
            with self.assertRaises(OSError):bind(args,root,manifest)
        ports=RUNNER['H']['serving_ports']
        self.assertEqual(ports({}),(19879,19880))
        self.assertEqual(ports({'api_port':8000}),(8000,19880))
        for cfg in [{'api_port':True},{'api_port':19880},{'management_port':65536}]:
            with self.assertRaises(ValueError):ports(cfg)
        self.assertGreaterEqual(int(RUNNER['H']['process_status'](os.getpid())['Threads']),1)

    def test_ssd_supervisor_admission_and_sealed_restart(self):
        with tempfile.TemporaryDirectory(prefix='lie-ssd-admission-') as tmp:
            root=Path(tmp);producer=root/'writer';producer.mkdir();consumer=root/'reader';consumer.mkdir()
            args=['--suite','core','--prefix-cache-mib','0','--prefix-ssd-dir','prefix-store',
                  '--prefix-ssd-quota-mib','1','--prefix-ssd-staging-mib','1']
            cfg={'ssd_store':{'mode':'create','quota_bytes':1024**2,'staging_bytes':1024**2,
                              'full_model_hash_authorized':True,'checkpoint_hash_authorized':True}}
            bound,record=RUNNER['bind_ssd'](args,producer,cfg)
            self.assertEqual(bound[5],str(producer/'prefix-store'))
            self.assertFalse((producer/'prefix-store').exists())
            for change in ({'full_model_hash_authorized':False},{'staging_bytes':True},{'mode':'unknown'}):
                bad=copy.deepcopy(cfg);bad['ssd_store'].update(change)
                with self.assertRaises(ValueError):RUNNER['bind_ssd'](args,producer,bad)
            with self.assertRaises(ValueError):RUNNER['bind_ssd'](args[:6],producer,cfg)
            with self.assertRaises(ValueError):RUNNER['bind_ssd'](args[:2]+args[4:],producer,cfg) # Undeclared default RAM.
            store=producer/'prefix-store';store.mkdir(mode=0o700)
            payload=store/('a'*64+'.lie');payload.write_bytes(b'checkpoint fixture');payload.chmod(0o600)
            inventory=RUNNER['ssd_inventory'](store)
            results=producer/'results';results.mkdir();receipt=results/'result.json'
            receipt.write_text(json.dumps({'state':'SIMPLIFIED_BENCHMARK_PASS_NOT_INDEPENDENT_QUALIFICATION',
                                           'child_exit_code':0,'ssd_store':record,'ssd_after':inventory}))
            cfg['ssd_store'].update(mode='reuse',source_run=producer.name,source_result_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest())
            bound,record=RUNNER['bind_ssd'](args,consumer,cfg);self.assertEqual(bound[5],str(store))
            bad=copy.deepcopy(cfg);bad['ssd_store']['source_run']='../writer'
            with self.assertRaises(ValueError):RUNNER['bind_ssd'](args,consumer,bad)
            payload.write_bytes(b'changed checkpoint')
            with self.assertRaises(ValueError):RUNNER['bind_ssd'](args,consumer,cfg)
            payload.chmod(0o644)
            with self.assertRaises(ValueError):RUNNER['ssd_inventory'](store)
            link=root/'alias';link.symlink_to(store,target_is_directory=True)
            with self.assertRaises(OSError):RUNNER['ssd_inventory'](link)

    def test_supervisor_thermal_sensor_limits(self):
        with tempfile.TemporaryDirectory(prefix='lie-thermal-admission-') as tmp:
            root=Path(tmp);sensor=root/'hwmon0';sensor.mkdir()
            (sensor/'name').write_text('k10temp\n');(sensor/'temp1_input').write_text('59000\n')
            (sensor/'temp1_max').write_text('60000\n')
            rows=RUNNER['temperatures'](root);RUNNER['require_cool'](rows)
            (sensor/'temp1_input').write_text('61000\n')
            with self.assertRaises(RuntimeError):RUNNER['require_cool'](RUNNER['temperatures'](root))
            with self.assertRaises(ValueError):RUNNER['temperatures'](root,86)
            (sensor/'name').write_text('amdgpu\n')
            with self.assertRaises(ValueError):RUNNER['temperatures'](root)

    def test_port_probe_rejects_listener_but_allows_retired_tcp(self):
        probe=RUNNER['H']['probe_ports']
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            listener.bind(('127.0.0.1',0));listener.listen()
            address=listener.getsockname()
            with self.assertRaises(OSError):probe((address[1],))
            with socket.create_connection(address,timeout=2) as client:
                peer,_=listener.accept();listener.close()
                with peer:
                    peer.shutdown(socket.SHUT_WR)
                    self.assertEqual(client.recv(1),b'')
        # The active closer leaves a TIME_WAIT tuple on this private port.
        with socket.socket() as legacy:
            with self.assertRaises(OSError):legacy.bind(address)
        probe((address[1],))

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'),'optional matplotlib unavailable')
    def test_core_graphs(self):
        with tempfile.TemporaryDirectory(prefix='lie-core-graphs-') as tmp:
            graphs=Path(tmp)/'charts with spaces'
            p,path=self.run_case(tmp,'--graphs',str(graphs))
            self.assertEqual(p.returncode,0,p.stderr)
            for name in ['summary.json','summary.csv','benchmark.svg','benchmark.png']:
                self.assertGreater((graphs/name).stat().st_size,0)
            self.assertEqual(REPORT['read_result'](path)['identity']['suite'],'core')


if __name__=='__main__':unittest.main()
