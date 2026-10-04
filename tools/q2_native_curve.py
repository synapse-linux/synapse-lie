# SPDX-License-Identifier: MIT
"""Frozen native benchmark selection; no prompt generation or model forwarding."""
import hashlib
import json
from pathlib import Path

MODES = ('q2-curve-iq2', 'q2-curve-scale', 'q2-curve-row', 'ud-curve')
DEPTHS = '0,4096,8192,12288,16384,32768,65536,131072'
MANIFEST = 'config/q2-native-bench-source.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source(root, staged=False):
    manifest = json.loads((root/MANIFEST).read_text())
    if manifest.get('schema') != 'synapse-lie.q2-native-bench-source.v1':
        raise ValueError('Invalid native benchmark source receipt')
    relative = Path('native-bench-core' if staged else manifest['source'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe native benchmark source path')
    source = root/relative
    actual = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
    if not actual or actual != manifest['files']:
        raise ValueError('Native benchmark source inventory changed')
    if not {'tools/native/http_curve.c', 'tools/native/gufo_workload.c',
            'tests/test_http_curve_native.c'}.issubset(actual):
        raise ValueError('Native canonical curve implementation missing')
    return source, manifest


def client_argv(binary, output, graphs, label):
    return [str(binary), '--suite', 'http-curve', '--url', 'http://127.0.0.1:8000/v1',
            '--model', 'bench', '--server-label', label, '--output', str(output),
            '--graphs', str(graphs), '--mode', 'ar', '--endpoint-profile', 'openai',
            '--task', 'prose', '--seed', '1', '--depths', DEPTHS, '--pp', '2048',
            '--tg', '128', '--context-capacity', '133760', '--warmups', '1',
            '--repetitions', '1', '--depth-tolerance', '0.005', '--timeout', '1800']


def check_backend(info, variant):
    build = {'ordered': 'q2-canonical-curve-iq2-signs',
             'scale': 'q2-canonical-curve-iq2-scale-reuse',
             'row': 'q2-canonical-curve-scaled-row-reuse',
             'ud': 'q2-canonical-curve-experiment'}.get(variant)
    if not build or not isinstance(info, dict) or info.get('schema') != 'synapse-lie.llm.v1' or info.get('ready') is not True:
        raise ValueError('Canonical model is not ready')
    b, s, c = [info.get(k, {}) for k in ('backend', 'scheduler', 'cache')]
    if not all(isinstance(x, dict) for x in (b, s, c)):
        raise ValueError('Invalid canonical backend metadata')
    expected = dict(synthetic=False, mtp=False, vision=False, prefix_state=True,
                    model='bench', context_tokens=133760, build_id=build,
                    source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e')
    if any(type(b.get(k)) is not type(v) or b[k] != v for k, v in expected.items()):
        raise ValueError('Endpoint is not the admitted canonical provider')
    if (type(c.get('budget_bytes')) is not int or c['budget_bytes'] <= 0 or
            any(type(s.get(k)) is not int or s[k] != v
                for k, v in dict(queued=0, active=0, max_active=1).items())):
        raise ValueError('Canonical endpoint is busy or RAM prefix cache is disabled')
