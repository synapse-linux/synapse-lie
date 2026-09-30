#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only regression for the original-model runner's HTTP transport.
No model, GPU, SSH, manifest, admission lock or runner main() is executed.
"""
import http.server
from pathlib import Path
import runpy
import threading
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


if __name__ == '__main__':
    unittest.main()
