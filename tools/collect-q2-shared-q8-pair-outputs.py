#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read the new component's complete output arrays without remote mutation."""
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    plan_path = ROOT/'config/q2-shared-q8-pair-plan.json'
    plan = json.loads(plan_path.read_text())
    label = plan['component']['label']
    local = ROOT/'evidence'/label
    result = json.loads((local/'results/result.json').read_text())
    assert result['finished_at'] and result['commands'][-1]['exit_code'] in (0, 1)
    log = local/'results/03.log'
    rows = [json.loads(s) for s in log.read_text().splitlines() if s.startswith('{"type"')]
    comparisons = [r for r in rows if r['type'] == 'comparison']
    assert len(comparisons) == plan['component_expected_output_pairs']
    expected = {}
    for row in comparisons:
        for arm in ('parent', 'candidate'):
            name = row['id']+'-'+arm+'.bin'
            assert Path(name).name == name and name not in expected
            expected[name] = dict(bytes=row['bytes'], sha256=row[arm+'_sha256'])
    root = '/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'+label
    receipt_sha = hashlib.sha256((local/'results/result.json').read_bytes()).hexdigest()
    code = '''import hashlib,io,json,pathlib,sys,tarfile
root=pathlib.Path(ROOT)
expected=EXPECTED
assert hashlib.sha256((root/'results/result.json').read_bytes()).hexdigest()==RECEIPT
for name,meta in expected.items():
 p=root/name
 assert p.is_file() and not p.is_symlink() and p.stat().st_size==meta['bytes']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==meta['sha256']
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for name in expected: archive.add(root/name,arcname=name,recursive=False)
 payload=(json.dumps(expected,indent=2)+'\\n').encode()
 info=tarfile.TarInfo('output-manifest.json');info.size=len(payload)
 archive.addfile(info,io.BytesIO(payload))
assert hashlib.sha256((root/'results/result.json').read_bytes()).hexdigest()==RECEIPT
'''.replace('ROOT', repr(root)).replace('EXPECTED', repr(expected)).replace('RECEIPT', repr(receipt_sha))
    archive_path = local/'output-arrays.tar.gz'
    argv = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            'paperboy@192.168.5.157', 'python3 -c '+shlex.quote(code)]
    with archive_path.open('xb') as out:
        process = subprocess.run(argv, stdout=out)
    if process.returncode:
        raise SystemExit(process.returncode)
    destination = local/'output-arrays'
    destination.mkdir(exist_ok=False)
    with tarfile.open(archive_path) as archive:
        assert {m.name for m in archive} == set(expected) | {'output-manifest.json'}
        for member in archive:
            assert member.isfile() and Path(member.name).name == member.name
            payload = archive.extractfile(member).read()
            if member.name in expected:
                meta = expected[member.name]
                assert len(payload) == meta['bytes'] and hashlib.sha256(payload).hexdigest() == meta['sha256']
            else:
                assert json.loads(payload) == expected
            with (destination/member.name).open('xb') as out:
                out.write(payload)
    report = dict(plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        receipt_sha256=receipt_sha, comparison_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        output_arrays=len(expected), outputs=expected, exit_code=0, remote_mutations=False)
    with (local/'output-collection.json').open('x') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
    print(json.dumps(dict(output_arrays=len(expected), archive_sha256=report['archive_sha256'], remote_mutations=False)))


if __name__ == '__main__':
    main()
