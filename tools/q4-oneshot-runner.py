#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One bounded Q4 comparison using immutable retained LIE binaries; no build."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

from q2_binary_replay import inventory, libraries, sha
from q2_process import supervise
from q2_thermal import sample, enforce

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def stat_model(path):
    st = Path(path).stat()
    return dict(path=path, bytes=st.st_size, device=st.st_dev, inode=st.st_ino,
                mtime_ns=st.st_mtime_ns, ctime_ns=st.st_ctime_ns)


def validate_plan(plan):
    if (plan['schema'] != 'synapse-lie.q4-oneshot-plan.v1' or
            plan['label'] != 'q4-oneshot-model-r1' or
            plan['model']['path'] != '/home/paperboy/ds4-launcher/models/gguf/Qwen3.8-Flash-Next-Q4.gguf' or
            [a['label'] for a in plan['arms']] !=
            ['q2-counting-regression-mixed-r1', 'q2-iq2-raw-prefetch-model-r1'] or
            plan['protocol'] != dict(context_capacity=9216, chunk=2048,
                                    prompt_tokens=2048, output_tokens=128,
                                    timed_decode_calls=127, warmups=1,
                                    repetitions=3, cooldown_seconds=15,
                                    mtp=False, concurrency=1) or
            plan['automatic_repetition'] or plan['build_commands'] != 0):
        raise RuntimeError('One-shot comparison scope changed')
    for name, expected in plan['fixtures'].items():
        if sha(ROOT/name) != expected:
            raise RuntimeError('Frozen runner fixture changed: ' + name)


def verify_arm(arm, sources, env):
    previous = ROOT.parent/arm['label']
    receipt = previous/'results/result.json'
    if sha(receipt) != arm['receipt_sha256']:
        raise RuntimeError('Retained qualification receipt changed')
    data = read(receipt)
    if (data['state'] != 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT' or
            not data.get('finished_at') or any(c['exit_code'] for c in data['commands'])):
        raise RuntimeError('Retained binary has no completed qualification')
    binary = previous/'build/hip/cmake/hip/q2_model'
    if sha(binary) != arm['binary_sha256'] or data['binary_sha256_after'] != arm['binary_sha256']:
        raise RuntimeError('Retained binary changed')
    if inventory(previous/'source') != sources[arm['key']]:
        raise RuntimeError('Retained provider inventory changed')
    for name, digest in arm['original_fixtures'].items():
        if sha(previous/name) != digest:
            raise RuntimeError('Original model tester changed')
    runtime = libraries(binary, env)
    if runtime != read(ROOT/'config/q4-oneshot-libraries.json'):
        raise RuntimeError('Installed runtime library identity changed')
    return binary, dict(binary_sha256=sha(binary), receipt_sha256=sha(receipt),
                        source_files_verified=len(sources[arm['key']]),
                        libraries=runtime, build_commands=0)


def clients():
    return sorted(int(p.name) for p in Path('/sys/class/kfd/kfd/proc').glob('*')
                  if p.name.isdecimal())


def main():
    plan = read(ROOT/'config/q4-oneshot-plan.json')
    validate_plan(plan)
    if ROOT.name != plan['label'] or len(sys.argv) != 1:
        raise RuntimeError('Only the frozen durable job is executable')
    results = ROOT/'results'
    results.mkdir()
    result = dict(schema='synapse-lie.q4-oneshot-runtime.v1', state='RUNNING',
                  mode='q4-oneshot', pid=os.getpid(), started_at=now(), commands=[],
                  model_access=False, locks=[], arms={}, build_commands=0,
                  automatic_repetition=False, source_pin=plan['source_pin'],
                  plan_sha256=sha(ROOT/'config/q4-oneshot-plan.json'))
    held = []
    registered = False

    def save():
        (results/'result.json').write_text(json.dumps(result, indent=2)+'\n')

    def register(event):
        row = dict(event=event, owner='synapse-lie-q2', label=ROOT.name,
                   pid=os.getpid(), at=now(), mode='q4-oneshot', state=result['state'])
        path = Path(plan['registry'])
        with path.open('a') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            stream.write(json.dumps(row)+'\n')
            stream.flush()
            os.fsync(stream.fileno())

    def observe(pid=None):
        row = dict(at=now(), thermal=sample(), kfd=clients())
        if pid:
            for name in ('status', 'io', 'stat'):
                try:
                    row[name] = Path('/proc', str(pid), name).read_text()
                except OSError as error:
                    row[name] = str(error)
        with (results/'telemetry.jsonl').open('a') as stream:
            stream.write(json.dumps(row)+'\n')
        if any(sensor['over_limit'] for sensor in row['thermal']):
            result['thermal_stop'] = row['thermal']
        enforce(row['thermal'])

    env = dict(os.environ, LC_ALL='C', HIP_VISIBLE_DEVICES='0', ROCR_VISIBLE_DEVICES='0')
    save()
    try:
        admission = read(ROOT.parent/'q4-oneshot-window-admission.json')
        launch = read(ROOT/'config/q4-oneshot-launch.json')
        if (sha(ROOT.parent/'q4-oneshot-window-admission.json') !=
                launch['admission_sha256'] or
                sha(ROOT/'config/q4-oneshot-plan.json') != launch['plan_sha256'] or
                admission['state'] != 'Q4_ONESHOT_WINDOW_ADMITTED'):
            raise RuntimeError('Fresh one-shot admission missing')
        for expected in admission['leases']:
            fd = os.open(expected['path'], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            st = os.fstat(fd)
            if (st.st_dev, st.st_ino) != (expected['device'], expected['inode']):
                raise RuntimeError('Original lease identity changed')
            result['locks'].append(expected)
        if clients():
            raise RuntimeError('Foreign KFD client before one-shot')
        rows = [json.loads(line) for line in Path(plan['registry']).read_text().splitlines() if line.strip()]
        if rows[-1].get('receipt_sha256') != sha(ROOT.parent/'q4-oneshot-window-admission.json'):
            raise RuntimeError('Intervening ownership transition')
        if stat_model(plan['model']['path']) != plan['model']:
            raise RuntimeError('Original Q4 model stat identity changed')
        result['models_before'] = [stat_model(plan['model']['path'])]
        sources = read(ROOT/'config/q4-oneshot-sources.json')
        verified = {}
        for arm in plan['arms']:
            binary, binding = verify_arm(arm, sources, env)
            verified[arm['key']] = (binary, binding)
        observe()
        register('start')
        registered = True
        for arm in plan['arms']:
            binary, binding = verified[arm['key']]
            directory = ROOT/'arms'/arm['key']
            (directory/'results').mkdir(parents=True)
            row = dict(argv=[str(binary), plan['model']['path'], 'bench2k'],
                       key=arm['key'], started_at=now())
            result['commands'].append(row)
            result['model_access'] = True
            save()
            with (results/(arm['key']+'.log')).open('xb') as log:
                try:
                    supervise(row['argv'], cwd=directory, env=env, log=log,
                              row=row, timeout=600, save=save, clients=clients, observe=observe)
                finally:
                    row['finished_at'] = now()
                    save()
            binary_after, binding_after = verify_arm(arm, sources, env)
            if binary_after != binary or binding_after != binding:
                raise RuntimeError('Immutable reference changed during run')
            result['arms'][arm['key']] = binding
            print(json.dumps(row), flush=True)
        result['state'] = 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT'
    except Exception as error:
        result['state'], result['error'] = 'FAILED', repr(error)
    finally:
        try:
            result['models_after'] = [stat_model(plan['model']['path'])]
            if result.get('models_before') and result['models_after'] != result['models_before']:
                raise RuntimeError('Q4 model changed during run')
            result['postflight_kfd'] = clients()
            if result['postflight_kfd']:
                raise RuntimeError('KFD client remains after model commands')
            for expected in result['locks']:
                st = os.stat(expected['path'], follow_symlinks=False)
                if (st.st_dev, st.st_ino) != (expected['device'], expected['inode']):
                    raise RuntimeError('Original lease changed during run')
            result['artifacts'] = {
                str(p.relative_to(ROOT)): dict(bytes=p.stat().st_size, sha256=sha(p))
                for base in (results, ROOT/'arms') for p in base.rglob('*')
                if p.is_file() and p != results/'result.json'}
        except Exception as error:
            result['state'], result['postflight_error'] = 'FAILED', repr(error)
        finally:
            try:
                if registered:
                    register('end')
            finally:
                for fd in reversed(held):
                    os.close(fd)
        result['finished_at'] = now()
        save()
        print(json.dumps({k: result.get(k) for k in ('state', 'error', 'finished_at')}), flush=True)
    raise SystemExit(1 if result['state'] == 'FAILED' else 0)


if __name__ == '__main__':
    main()
