# SPDX-License-Identifier: MIT
"""HOST own-child supervision fixtures; no original model or GPU serving."""
import copy
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
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


runner = module('steering_quality_supervision', ROOT/'tools/strix-point-steering-quality-run.py')
fixture = module('steering_quality_HOST', ROOT/'tests/test_strix_point_steering_quality.py')
NATIVE = os.environ.get('LIE_STEERING_NATIVE_CLIENT')


def child(pid, exit_code=0, timeout=False):
    value = Mock(); value.pid = pid; value.returncode = None
    value.poll.side_effect = lambda: value.returncode
    def terminate(): value.returncode = -signal.SIGTERM
    def kill(): value.returncode = -signal.SIGKILL
    value.terminate.side_effect = terminate; value.kill.side_effect = kill
    calls = []
    def wait(**_kwargs):
        calls.append(True)
        if timeout and len(calls) == 1:
            raise subprocess.TimeoutExpired('HOST child', 30)
        if value.returncode is None: value.returncode = exit_code
        return value.returncode
    value.wait.side_effect = wait
    return value


class Supervision(unittest.TestCase):
    def execute(self, *, wrong=False, timeout=False, load_failure=False,
                snapshot_failure=False, retirement_failure=False, bank_replaced=False, interrupt=False):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bank = root/'direction.ffn.f32'; bank.write_bytes(b'HOST')
        config = fixture.config(); config['bank_sha256'] = hashlib.sha256(bank.read_bytes()).hexdigest()
        rows, cases, snapshots = fixture.fixture()
        if wrong:
            row = rows['bank'][1]; answer = json.loads(row['assistant']['content']); answer['answer'] = 'wrong'
            fixture.change_answer(row, json.dumps(answer))
        args = types.SimpleNamespace(directory=root, bank=bank, server='HOST-server',
                                     client='HOST-client', model='HOST-never-opened.gguf', load_timeout=30)
        children, order, signal_handlers = {}, [], {s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP)}
        def launched(argv, **_kwargs):
            phase = 'bank' if '--dir-steering-file' in argv or '/bank/' in ' '.join(argv) else 'absent'
            role = 'server' if argv[0] == args.server else 'client'
            if phase == 'bank' and role == 'server':
                self.assertIsNotNone(children['absent.server'].poll())
                self.assertIsNotNone(children['absent.client'].poll())
            key = phase+'.'+role; order.append(key)
            children[key] = child(1000+len(children), exit_code=17 if retirement_failure and role=='server' else 0,
                                  timeout=timeout and role=='client')
            if role == 'server':
                if retirement_failure:
                    children[key].terminate.side_effect = lambda: setattr(children[key], 'returncode', 17)
            else:
                output = root/'steering-quality'/phase
                (output/'measurements.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows[phase]))
                (output/'requests.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in cases[phase]))
            return children[key]
        def get(_port, path):
            identifier = path.split('/')[-2]
            value = next(v for v in snapshots.values() if v['id'] == identifier)
            return {'status':404 if snapshot_failure else 200,'body':json.dumps(value)}
        def ready(*_args):
            if interrupt: os.kill(os.getpid(), signal.SIGTERM)
            if load_failure: raise RuntimeError('HOST model load refusal')
            if bank_replaced and len(order)==1:
                copy = root/'replacement'; copy.write_bytes(bank.read_bytes()); copy.replace(bank)
        with patch.object(runner.subprocess, 'Popen', side_effect=launched), \
             patch.object(runner.owned, 'process_identity', side_effect=lambda c:{'pid':c.pid,'start_ticks':1,'cgroup':'HOST fixture'}), \
             patch.object(runner.owned, 'private_ports', return_value=(41001,41002)), \
             patch.object(runner, 'ready', side_effect=ready), patch.object(runner, 'get', side_effect=get):
            code = runner.run(args, config, fixture.DATA)
        for s, old in signal_handlers.items(): self.assertEqual(signal.getsignal(s), old)
        result = json.loads((root/'steering-quality-result.json').read_text())
        return root, result, code, children, order

    def test_serial_servers_complete_matrix_and_actual_exits(self):
        root, result, code, children, order = self.execute()
        self.assertEqual((code,result['state']), (0,'PASSED'))
        self.assertEqual(order, ['absent.server','absent.client','bank.server','bank.client'])
        self.assertEqual(result['native_exit_codes'], {'absent':0,'bank':0})
        self.assertEqual(result['quality_review']['samples'],70)
        self.assertTrue(result['bank_identity_unchanged'])
        self.assertEqual(len((root/'steering-quality/snapshots-raw.jsonl').read_text().splitlines()),70)
        for key,c in children.items(): self.assertIsNotNone(c.poll(),key)

    def test_complete_model_quality_failure_keeps_native_success_and_all_scores(self):
        root,result,code,_children,_order=self.execute(wrong=True)
        self.assertEqual((code,result['state']), (1,'QUALITY_FAILED'))
        self.assertEqual(result['native_exit_codes'], {'absent':0,'bank':0})
        self.assertEqual(result['quality_review']['correct_answers'],69)
        self.assertEqual(result['quality_review']['samples'],70)
        self.assertEqual(len(json.loads((root/'steering-quality/snapshots.json').read_text())),70)

    def test_timeout_retires_only_owned_children_and_keeps_partial_native_wire(self):
        root,result,code,children,order=self.execute(timeout=True)
        self.assertEqual((code,result['state']), (1,'FAILED'))
        self.assertEqual(order,['absent.server','absent.client'])
        self.assertEqual(result['native_exit_codes'],{'absent':-signal.SIGTERM})
        self.assertTrue((root/'steering-quality/absent/measurements.jsonl').is_file())
        for c in children.values(): c.terminate.assert_called_once()

    def test_load_failure_never_launches_native_client_or_second_model(self):
        _root,result,code,children,order=self.execute(load_failure=True)
        self.assertEqual((code,result['state']), (1,'FAILED'))
        self.assertEqual(order,['absent.server']); self.assertEqual(result['native_exit_codes'],{})
        children['absent.server'].terminate.assert_called_once()

    def test_missing_snapshot_keeps_actual_status_before_refusal(self):
        root,result,code,_children,order=self.execute(snapshot_failure=True)
        self.assertEqual((code,result['state']), (1,'FAILED'))
        self.assertEqual(order,['absent.server','absent.client'])
        saved=json.loads((root/'steering-quality/snapshots-raw.jsonl').read_text())
        self.assertEqual(saved['response']['status'],404)

    def test_failed_retirement_prevents_overlapping_second_model(self):
        _root,result,code,_children,order=self.execute(retirement_failure=True)
        self.assertEqual((code,result['state']), (1,'FAILED'))
        self.assertEqual(order,['absent.server','absent.client'])
        self.assertEqual(result['phases']['absent']['server_exit_code'],17)
        self.assertTrue(result['cleanup_errors'])

    def test_byte_identical_bank_replacement_does_not_pass_identity_gate(self):
        _root,result,code,_children,_order=self.execute(bank_replaced=True)
        self.assertEqual(result['bank_before']['sha256'],result['bank_after']['sha256'])
        self.assertEqual((code,result['state']), (1,'FAILED'))
        self.assertFalse(result['bank_identity_unchanged'])
        self.assertEqual(result['quality_review']['state'],'PASSED')

    def test_actual_signal_retires_own_server_and_restores_handlers(self):
        _root,result,code,children,order=self.execute(interrupt=True)
        self.assertEqual((code,result['state']), (1,'FAILED')); self.assertEqual(order,['absent.server'])
        self.assertIn('Interrupted by signal',result['error']); children['absent.server'].terminate.assert_called_once()

    def test_deadlines_bound_complete_matrix_and_server_retention(self):
        config=fixture.config(); args=types.SimpleNamespace(server='server',model='not-opened',bank=Path('/HOST-bank'),load_timeout=900)
        self.assertEqual(runner.container_timeout(config,900),4500)
        command=runner.server_command(args,config,'bank',41001,41002)
        self.assertEqual(command[command.index('--response-store-ttl-seconds')+1],'4500')
        self.assertNotIn('--model-mtp',command)
        self.assertNotIn('--dir-steering-file',runner.server_command(args,config,'absent',41001,41002))
        for cfg,load in (({**config,'request_timeout_seconds':1800},1800),(config,True)):
            with self.assertRaises(ValueError): runner.container_timeout(cfg,load)

    def test_deadline_covers_snapshot_reads_client_slack_and_owned_retirement(self):
        config=fixture.config()
        deadline=runner.container_timeout(config,30)
        model_loads_and_requests=2*30+70*config['request_timeout_seconds']
        snapshot_and_client_slack=70*runner.SNAPSHOT_TIMEOUT_SECONDS+2*30
        maximum_owned_retirement=4*30
        self.assertGreaterEqual(deadline-model_loads_and_requests,
                                snapshot_and_client_slack+maximum_owned_retirement+180)

    def test_replay_refuses_before_a_new_process(self):
        root,_result,_code,_children,_order=self.execute()
        args=types.SimpleNamespace(directory=root,bank=root/'direction.ffn.f32',load_timeout=30)
        config=fixture.config();config['bank_sha256']=hashlib.sha256(args.bank.read_bytes()).hexdigest()
        with patch.object(runner.subprocess,'Popen') as popen, self.assertRaises(RuntimeError):
            runner.run(args,config,fixture.DATA)
        popen.assert_not_called()


@unittest.skipUnless(NATIVE,'Optional actual native C HTTP client with simulated model servers')
class NativeSupervisedWire(unittest.TestCase):
    def test_real_native_children_roundtrip_all_requests_and_stored_observations(self):
        snapshots={};counter=[];errors=[];real_popen=subprocess.Popen;real_identity=runner.owned.process_identity
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*_args): pass
            def do_POST(self):
                try:
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));counter.append(body)
                    sample,snap=fixture.synthetic_reply(body,'chat-HOST-'+str(len(counter)));snapshots[snap['id']]=snap
                    payload=(''.join('data: '+json.dumps(c)+'\n\n' for c in sample['response_chunks'])+'data: [DONE]\n\n').encode()
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(payload)))
                    self.end_headers();self.wfile.write(payload)
                except BaseException as error: errors.append(repr(error));self.close_connection=True
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        models=[]
        def launched(argv,**kwargs):
            if argv[0]=='HOST-server':
                if models:self.assertIsNotNone(models[-1].poll())
                models.append(child(9000+len(models)));return models[-1]
            return real_popen(argv,**kwargs)
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);bank=root/'direction.ffn.f32';bank.write_bytes(b'HOST')
                config=fixture.config();config['bank_sha256']=hashlib.sha256(bank.read_bytes()).hexdigest()
                args=types.SimpleNamespace(directory=root,bank=bank,server='HOST-server',client=NATIVE,model='HOST-not-opened',load_timeout=30)
                with patch.object(runner.subprocess,'Popen',side_effect=launched), \
                     patch.object(runner.owned,'private_ports',return_value=(server.server_port,41002)), \
                     patch.object(runner.owned,'process_identity',side_effect=lambda c:{'pid':c.pid,'start_ticks':1,'cgroup':'HOST simulated model'} if c in models else real_identity(c)), \
                     patch.object(runner,'ready'), \
                     patch.object(runner,'get',side_effect=lambda _p,path:{'status':200,'body':json.dumps(snapshots[path.split('/')[-2]])}):
                    self.assertEqual(runner.run(args,config,fixture.DATA),0)
                self.assertFalse(errors,errors);self.assertEqual(len(counter),70)
                result=json.loads((root/'steering-quality-result.json').read_text())
                self.assertEqual(result['native_exit_codes'],{'absent':0,'bank':0})
                self.assertEqual(result['quality_review']['samples'],70)
                for phase in ('absent','bank'):
                    self.assertGreater(result['phases'][phase]['client_identity']['start_ticks'],0)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5);self.assertFalse(thread.is_alive())


if __name__=='__main__':unittest.main()
