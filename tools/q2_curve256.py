# SPDX-License-Identifier: MIT
"""Explicit 256K native curve parameters, retaining the historical workload recipe."""
def client_argv(binary, output, graphs, label, *, point_only=False):
    return [str(binary), '--suite', 'http-curve', '--url', 'http://127.0.0.1:8000/v1',
            '--model', 'bench', '--server-label', 'retained-q2-1587.893545' if label == 'ordered' else label, '--output', str(output),
            '--graphs', str(graphs), '--mode', 'ar', '--endpoint-profile', 'openai',
            '--task', 'prose', '--seed', '1', '--depths', '0' if point_only else '0,4096,8192,12288,16384,32768,65536,131072,196608,262144', '--pp', '2048',
            '--tg', '128', '--context-capacity', '266240', '--warmups', '1',
            '--repetitions', '3' if point_only else '1', '--depth-tolerance', '0.005', '--timeout', '3600']


def check_backend(info, variant):
    build = {'ordered': 'q2-canonical-curve-retained256',
             'norm': 'q2-canonical-point-norm-ragged',
             'scale': 'q2-canonical-curve-iq2-scale-reuse',
             'row': 'q2-canonical-curve-scaled-row-reuse',
             'ud': 'q2-canonical-curve-experiment'}.get(variant)
    if not build or not isinstance(info, dict) or info.get('schema') != 'synapse-lie.llm.v1' or info.get('ready') is not True:
        raise ValueError('Canonical model is not ready')
    b, s, c = [info.get(k, {}) for k in ('backend', 'scheduler', 'cache')]
    if not all(isinstance(x, dict) for x in (b, s, c)):
        raise ValueError('Invalid canonical backend metadata')
    expected = dict(synthetic=False, mtp=False, vision=False, prefix_state=True,
                    model='bench', context_tokens=266240, build_id=build,
                    source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e')
    if any(type(b.get(k)) is not type(v) or b[k] != v for k, v in expected.items()):
        raise ValueError('Endpoint is not the admitted canonical provider')
    if (type(c.get('budget_bytes')) is not int or c['budget_bytes'] <= 0 or
            any(type(s.get(k)) is not int or s[k] != v
                for k, v in dict(queued=0, active=0, max_active=1).items())):
        raise ValueError('Canonical endpoint is busy or RAM prefix cache is disabled')
