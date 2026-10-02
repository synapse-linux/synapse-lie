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
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,48}', args.label): parser.error('Invalid exclusive campaign label')
    manifest = json.loads(args.manifest.read_text())
    out = ROOT/'evidence'/args.label
    out.mkdir(parents=True, exist_ok=False)
    files = {'manifest.json': (json.dumps(manifest, indent=2)+'\n').encode(),
             'runner.py': (ROOT/'tools/strix-point-campaign.py').read_bytes()}
    if manifest['action'] == 'download': files['download.py'] = (ROOT/'tools/strix-point-download.py').read_bytes()
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
