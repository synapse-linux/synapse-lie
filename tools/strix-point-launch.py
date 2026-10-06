#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage and execute one explicitly handed-over .161 campaign; preserve receipts."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SSH = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'pop@192.168.5.161']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--tokens-file', type=Path,
                        help='Stage a pinned physical-token JSON file as tokens.json')
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,48}', args.label): parser.error('Invalid exclusive campaign label')
    manifest = json.loads(args.manifest.read_text())
    tokens = None
    if args.tokens_file:
        tokens = args.tokens_file.read_bytes()
        if hashlib.sha256(tokens).hexdigest() != manifest.get('tokens_sha256'):
            parser.error('Physical-token file SHA-256 differs from manifest')
    out = ROOT/'evidence'/args.label
    out.mkdir(parents=True, exist_ok=False)
    files = {'manifest.json': (json.dumps(manifest, indent=2)+'\n').encode(),
             'runner.py': (ROOT/'tools/strix-point-campaign.py').read_bytes()}
    if manifest['action'] == 'download': files['download.py'] = (ROOT/'tools/strix-point-download.py').read_bytes()
    if manifest.get('build_flavor') == 'gufo-point-server':
        helper = (ROOT/'tools/strix-point-gufo-port-build.py').read_bytes()
        if hashlib.sha256(helper).hexdigest() != manifest.get('gufo_build_helper_sha256'):
            parser.error('Point Gufo build helper SHA-256 differs from manifest')
        files['gufo-build.py'] = helper
    if tokens is not None:
        files['tokens.json'] = tokens
    if manifest.get('bench_profile') == 'modern-http':
        helper = (ROOT/'tools/strix-point-http-gate.py').read_bytes()
        if hashlib.sha256(helper).hexdigest() != manifest.get('http_gate_sha256'):
            parser.error('HTTP gate helper SHA-256 differs from manifest')
        files['http-gate.py'] = helper
        if manifest.get('http_control_gate', False):
            controls = (ROOT/'tools/strix-point-openai-controls.py').read_bytes()
            if hashlib.sha256(controls).hexdigest() != manifest.get('http_controls_sha256'):
                parser.error('HTTP controls helper SHA-256 differs from manifest')
            files['http-controls.py'] = controls
        if manifest.get('http_output_budget_gate', False):
            budget = (ROOT/'tools/strix-point-output-budget-gate.py').read_bytes()
            if hashlib.sha256(budget).hexdigest() != manifest.get('http_output_budget_sha256'):
                parser.error('HTTP output-budget helper SHA-256 differs from manifest')
            files['http-output-budget.py'] = budget
    if manifest.get('bench_profile') == 'modern-http-multi':
        case = manifest.get('http_case')
        if case not in ('prose', 'repetition'):
            parser.error('Prepared HTTP corpus must be prose or repetition')
        helper = (ROOT/'tools/strix-point-http-multi-gate.py').read_bytes()
        corpus = (ROOT/'config/bench/gufo-qwen38'/f'{case}.jsonl').read_bytes()
        if (hashlib.sha256(helper).hexdigest() != manifest.get('http_multi_gate_sha256') or
                hashlib.sha256(corpus).hexdigest() != manifest.get('corpus_sha256')):
            parser.error('Prepared HTTP helper or corpus SHA-256 differs from manifest')
        files['http-multi-gate.py'] = helper
        files['corpus.jsonl'] = corpus
    if manifest.get('bench_profile') == 'modern-http-depth':
        helper = (ROOT/'tools/strix-point-http-depth-gate.py').read_bytes()
        if hashlib.sha256(helper).hexdigest() != manifest.get('http_depth_gate_sha256'):
            parser.error('HTTP depth helper SHA-256 differs from manifest')
        files['http-depth-gate.py'] = helper
    if manifest.get('bench_profile') == 'modern-core-ssd-text-restart':
        helper = (ROOT/'tools/strix-point-ssd-text-restart-gate.py').read_bytes()
        if hashlib.sha256(helper).hexdigest() != manifest.get('ssd_text_restart_gate_sha256'):
            parser.error('SSD text restart helper SHA-256 differs from manifest')
        files['ssd-text-restart-gate.py'] = helper
    if manifest.get('bench_profile') == 'modern-core-steering-restart':
        helper = (ROOT/'tools/strix-point-steering-restart-gate.py').read_bytes()
        if hashlib.sha256(helper).hexdigest() != manifest.get('steering_restart_gate_sha256'):
            parser.error('Steering restart helper SHA-256 differs from manifest')
        files['steering-restart-gate.py'] = helper
    for name, data in files.items(): (out/name).write_bytes(data)
    encoded = {name: base64.b64encode(data).decode() for name, data in files.items()}
    program = '''import base64,os,pathlib,sys
base=pathlib.Path('/home/pop/workspace/synapse-lie')
if base.resolve()!=base or base.stat().st_uid!=os.getuid(): raise SystemExit('Unsafe LIE staging root')
'''
    program += 'root=base/'+repr(args.label)+'\nroot.mkdir()\nfiles='+repr(encoded)+'\n'
    program += '''for name,data in files.items():
    with (root/name).open('xb') as output: output.write(base64.b64decode(data))
os.execv(sys.executable,[sys.executable,'-B',str(root/'runner.py'),str(root)])
'''
    record = {'argv': SSH+['python3 -'], 'remote_root': '/home/pop/workspace/synapse-lie/'+args.label,
              'source_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
              'stager_sha256': hashlib.sha256(program.encode()).hexdigest()}
    (out/'plan.json').write_text(json.dumps(record, indent=2)+'\n')
    with (out/'controller-stdout.log').open('w') as stdout, (out/'controller-stderr.log').open('w') as stderr:
        p = subprocess.run(record['argv'], input=program, text=True, stdout=stdout, stderr=stderr)
    record['exit_code'] = p.returncode
    (out/'controller-result.json').write_text(json.dumps(record, indent=2)+'\n')
    try:
        result = json.loads((out/'controller-stdout.log').read_text())
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k: v for k, v in result.items() if k in ('state', 'error', 'exit_code', 'probe',
                         'service_before', 'service_after', 'cleanup_failures', 'lease_released_at', 'child_exit_code')}))
    except (OSError, ValueError):
        print(json.dumps({'exit_code': p.returncode, 'error': 'Remote result unavailable; inspect retained controller logs'}))
    return p.returncode

if __name__ == '__main__': raise SystemExit(main())
