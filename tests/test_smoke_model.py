#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only regression for the original-model runner's HTTP transport.
No model, GPU, SSH, manifest, admission lock or runner main() is executed.
"""
import hashlib
import http.server
from pathlib import Path
import runpy
import threading
import tempfile
import unittest

SMOKE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools/smoke-model.py'))


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        payload = b'x' * (1024 * 1024 + 1) if self.path == '/oversized' else b'{"ready":false}'
        self.send_response(503 if self.path == '/unavailable' else 200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        payload = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class SmokeHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=lambda: cls.server.serve_forever(poll_interval=0.01))
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        if cls.thread.is_alive():
            raise AssertionError('Synthetic HTTP server did not retire')

    def test_readiness_get(self):
        reply = SMOKE['http'](self.port, '/ready', timeout=2)
        self.assertEqual(reply['status'], 200)
        self.assertEqual(reply['body'], '{"ready":false}')

    def test_utf8_post_roundtrip(self):
        body = '{"message":"caffè 🙂"}'
        reply = SMOKE['http'](self.port, '/echo', body.encode('utf-8'), timeout=2)
        self.assertEqual(reply['status'], 200)
        self.assertEqual(reply['body'], body)
        self.assertEqual(reply['headers']['Content-Type'], 'application/json')

    def test_non_success_status_is_preserved(self):
        reply = SMOKE['http'](self.port, '/unavailable', timeout=2)
        self.assertEqual(reply['status'], 503)
        self.assertEqual(reply['body'], '{"ready":false}')

    def test_response_bound(self):
        with self.assertRaisesRegex(RuntimeError, 'response bound'):
            SMOKE['http'](self.port, '/oversized', timeout=2)


class ServingIdentityTest(unittest.TestCase):
    def test_lifecycle_settings_are_explicit_and_matched(self):
        settings={'context':4096,'prefill_chunk':2048,'max_active':2,'temperature':0,
                  'thinking':False,'mtp':False,'vision':False}
        SMOKE['validate_lifecycle_settings']({'request_settings':settings})
        for bad in ({},dict(settings,max_active=1),dict(settings,context=8192),
                    dict(settings,mtp=True),dict(settings,thinking=0),dict(settings,unknown=1)):
            with self.assertRaisesRegex(RuntimeError,'settings mismatch'):
                SMOKE['validate_lifecycle_settings']({'request_settings':bad})

    def test_valid_pinned_helper_has_no_execution_on_import(self):
        source=Path(__file__).resolve().parents[1]/'tools/serving_checks.py'
        with tempfile.TemporaryDirectory(prefix='lie-checks-identity-') as d:
            data=source.read_bytes(); (Path(d)/'serving_checks.py').write_bytes(data)
            module=SMOKE['load_serving_checks'](d,hashlib.sha256(data).hexdigest())
            self.assertEqual(module.SCHEMA,'synapse-lie.serving-checks.v1')

    def test_drift_refused_before_import(self):
        with tempfile.TemporaryDirectory(prefix='lie-checks-identity-') as d:
            (Path(d)/'serving_checks.py').write_text('raise AssertionError("must not execute")\n')
            with self.assertRaisesRegex(RuntimeError,'identity mismatch'):
                SMOKE['load_serving_checks'](d,'0'*64)

    def test_missing_or_symlink_refused(self):
        source=Path(__file__).resolve().parents[1]/'tools/serving_checks.py'
        with tempfile.TemporaryDirectory(prefix='lie-checks-identity-') as d:
            with self.assertRaisesRegex(RuntimeError,'identity mismatch'):
                SMOKE['load_serving_checks'](d,'0'*64)
            (Path(d)/'serving_checks.py').symlink_to(source)
            with self.assertRaisesRegex(RuntimeError,'identity mismatch'):
                SMOKE['load_serving_checks'](d,hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
