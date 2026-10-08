#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One coordinated new Q2 down candidate on the original 128K request on .157.

The script never builds, installs, changes a model, or terminates a foreign
process. `run` owns only the server and client it creates. Collect
the result directory before `release`.
"""

import argparse
import contextlib
import datetime as dt
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
import urllib.error
import urllib.request

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
EXPECTED_BOOT = '8b9cbb46-c7d4-47c3-b5cc-32e1fdad0653'
EPOCH = ROOT / 'gpu-coordination/epochs' / EXPECTED_BOOT
REGISTRY = EPOCH / 'runs.jsonl'
HERE = Path(__file__).resolve().parent
PLAN = HERE / 'plan.json'
ADMISSION = HERE / 'admission.json'
RELEASE = HERE / 'release.json'
LABEL = 'q2-decode-down-rows-native128-r3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def validate_power(receipt):
    require(receipt['exit_code'] == 0, 'APU readback command failed')
    settings = json.loads(receipt['stdout'])
    require(settings['apu_power_mode'] == 'performance' and
            settings['tdp_watts'] == 120, 'Original performance/120 W mode differs')
    for fan in ('fan1', 'fan2', 'fan3'):
        require(settings[fan]['mode'] == 'curve' and
                settings[fan]['rampup_curve'] == '40,50,60,70,82' and
                settings[fan]['rampdown_curve'] == '35,45,55,65,78',
                'Qualified fan curve differs: ' + fan)
    return settings


def power_check(path=None):
    argv = ['/usr/bin/axb35-ctl', 'get', 'all']
    process = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    receipt = dict(at=now(), argv=argv, exit_code=process.returncode,
                   stdout=process.stdout, stderr=process.stderr,
                   read_only=True, boot_id=BOOT_ID.read_text().strip())
    if path is not None:
        write_new(path, receipt)
    validate_power(receipt)
    return receipt


def source(plan):
    require(BOOT_ID.read_text().strip() == plan['boot_id'] == EXPECTED_BOOT,
            'A new boot requires separate coordination')
    require(plan['schema'] == 'synapse-lie.q2-decode-down-rows-native128-performance-plan.v1', 'Plan schema differs')
    require(sha(__file__) == plan['runner_sha256'], 'Runner source differs')
    require(plan['order'] == ['down-rows'] and plan['label'] == LABEL and
            HERE == ROOT / LABEL, 'Only one new Q2 down candidate is admitted')
    require(plan['capacity'] == 133760 and plan['chunk'] == 2048 and
            plan['prefix_tokens'] == 130925 and plan['output_tokens'] == 8 and
            plan['port'] == 8000,
            'Original 128K shape differs')
    require(plan['previous_release'] == 'q2-decode-down-rows-native128-r2/release.json',
            'Previous release path differs')
    previous_path = ROOT / plan['previous_release']
    require(sha(previous_path) == plan['previous_release_sha256'], 'Previous release differs')
    previous = read(previous_path)
    require(previous['boot_id'] == EXPECTED_BOOT and
            previous['state'] == 'Q2_DECODE_DOWN_ROWS_NATIVE128_RELEASED',
            'Wrong coordination epoch')
    require(not previous['gpu_reserved'] and not previous['remote_cleanup'],
            'Prior window not released')
    for key in ('candidate_server', 'client', 'requests'):
        item = plan[key]
        require(sha(item['path']) == item['sha256'], key + ' binary/input differs')
    for name, expected in plan['staged_sha256'].items():
        require(Path(name).name == name and sha(HERE / name) == expected,
                'Staged source or evidence differs: ' + name)
    require(plan['requests']['sha256'] ==
            'fcee51efeebfcbd25209ba90d09064d37aead6d3b0c6bbe7a9f97f328a4f24ef',
            'Original selected request digest differs')
    require(plan['model_stats'] == previous['models'], 'Model identities differ')
    return previous


def registry_rows():
    return [json.loads(line) for line in REGISTRY.read_text().splitlines() if line.strip()]


def assert_retired(previous, own=None):
    require(all(row['boot_id'] == EXPECTED_BOOT for row in
                [*previous['retired_identities'], *(own or [])]),
            'Process identities belong to another boot')
    identities = {row['pid']: row['start_ticks'] for row in previous['retired_identities']}
    groups = set(previous['retired_groups'])
    if own:
        for row in own:
            identities[row['pid']] = row['start_ticks']
            groups.add(row['process_group'])
    for process in Path('/proc').glob('[0-9]*'):
        try:
            fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            continue
        pid, group, start = int(process.name), int(fields[2]), int(fields[19])
        require(pid not in identities or identities[pid] not in (None, start),
                'Recorded process remains live')
        require(group not in groups, 'Owned process group remains live')


@contextlib.contextmanager
def leases(previous):
    held = []
    try:
        for row in [previous['core_cpu_lease'], *previous['leases']]:
            fd = os.open(row['path'], os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            held.append(fd)
            stat = os.fstat(fd)
            require((stat.st_dev, stat.st_ino) == (row['device'], row['inode']),
                    'Original lease identity differs')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for fd in reversed(held):
            os.close(fd)


def clear(previous, own=None):
    require(not list(Path('/sys/class/kfd/kfd/proc').glob('*')), 'KFD client remains')
    assert_retired(previous, own)
    for row in previous['models']:
        stat = Path(row['path']).stat()
        require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                 stat.st_ctime_ns) == tuple(row[key] for key in
                    ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns')),
                'Original model stat differs')


def emit_event(kind, receipt):
    row = dict(event=kind, owner='synapse-lie-q2', label='q2-decode-down-rows-native128-r3',
               at=receipt['at'], boot_id=EXPECTED_BOOT, receipt=str(receipt['path']),
               receipt_sha256=sha(receipt['path']), state=receipt['state'])
    with REGISTRY.open('a') as stream:
        stream.write(json.dumps(row) + '\n')
    return row


def admit(plan, previous):
    require(not ADMISSION.exists() and not RELEASE.exists(), 'Window receipt exists')
    with leases(previous):
        rows = registry_rows()
        require(rows and rows[-1].get('event') == 'window_release' and
                rows[-1].get('receipt_sha256') == plan['previous_release_sha256'],
                'Intervening ownership event')
        clear(previous)
        power = power_check(HERE / 'admission-power.json')
        receipt = dict(schema='synapse-lie.q2-decode-down-rows-native128-window.v3',
                       boot_id=EXPECTED_BOOT,
                       state='Q2_DECODE_DOWN_ROWS_NATIVE128_ADMITTED', at=now(),
                       plan_sha256=sha(PLAN), previous_release_sha256=plan['previous_release_sha256'],
                       original_model_stats_unchanged=True, kfd_empty=True,
                       original_leases_free=True, gpu_reserved=True,
                       planned_label=LABEL, remote_cleanup=False,
                       power_readback=power)
        write_new(ADMISSION, receipt)
        emit_event('window_admit', dict(receipt, path=ADMISSION))
        print(json.dumps(receipt))


def active(plan):
    require(ADMISSION.exists() and not RELEASE.exists(), 'No active admission')
    admission = read(ADMISSION)
    require(admission['state'] == 'Q2_DECODE_DOWN_ROWS_NATIVE128_ADMITTED' and
            admission['plan_sha256'] == sha(PLAN), 'Admission plan differs')
    rows = registry_rows()
    require(rows and rows[-1].get('event') == 'window_admit' and
            rows[-1].get('receipt_sha256') == sha(ADMISSION), 'Window is not active')
    return admission


def identity(process):
    fields = Path('/proc', str(process.pid), 'stat').read_text().rsplit(')', 1)[1].split()
    return dict(boot_id=EXPECTED_BOOT, pid=process.pid, start_ticks=int(fields[19]),
                process_group=os.getpgid(process.pid))


def sensor():
    base = Path('/sys/class/drm/card1/device')
    hwmon = next(base.glob('hwmon/hwmon*'))
    return dict(at=now(), gpu_busy=(base/'gpu_busy_percent').read_text().strip(),
                gpu_clock=(base/'pp_dpm_sclk').read_text().strip(),
                gpu_temp_mc=(hwmon/'temp1_input').read_text().strip(),
                gpu_power_uw=(hwmon/'power1_average').read_text().strip())


def cpu_temp_mc():
    temperatures = []
    for hwmon in Path('/sys/class/hwmon').glob('hwmon*'):
        try:
            if (hwmon/'name').read_text().strip() == 'k10temp':
                temperatures.extend(int(p.read_text()) for p in hwmon.glob('temp*_input'))
        except FileNotFoundError:
            continue
    require(temperatures, 'CPU thermal sensor unavailable')
    return max(temperatures)


def cool():
    deadline = time.monotonic() + 600
    while cpu_temp_mc() > 60000:
        require(time.monotonic() < deadline, 'CPU did not return to 60 C before next arm')
        time.sleep(5)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def validate_output(path, cases):
    events = [json.loads(line) for line in path.read_text().splitlines()]
    samples = [event for event in events if event.get('event') == 'sample']
    require(events and events[-1].get('event') == 'complete' and
            events[-1].get('exit_code') == 0 and len(samples) == 4,
            'Native 128K client did not complete four saved cases')
    for sample, case in zip(samples, cases):
        strip = lambda body: {key: value for key, value in body.items()
                              if key not in ('stream', 'stream_options')}
        require(sample['case'] == case['id'] and
                strip(sample['request']) == strip(case['body']) and
                sample['usage']['prompt_tokens'] == case['expected_prompt_tokens'],
                'Original request changed')
        timing = sample['server_timings']
        require(timing['valid'] is True and timing['scope'] == 'synchronous_executor_calls' and
                timing['decode_mode'] == 'ar' and timing['mtp_drafted_tokens'] == 0 and
                timing['mtp_accepted_tokens'] == 0 and timing['ssd_cached_tokens'] == 0 and
                timing['cached_tokens'] == 0, 'Inference timing or cache contract differs')
    last = samples[-1]
    timing = last['server_timings']
    require(last['usage']['prompt_tokens'] == 130925 and timing['prefill_tokens'] == 130925 and
            timing['prefill_calls'] == 64 and timing['prefill_ms'] > 0 and
            timing['decode_tokens'] == 8 and timing['decode_calls'] == 8 and
            last['usage']['completion_tokens'] == 8 and timing['decode_ms'] > 0,
            'Original full prefill count differs')
    return dict(prefill_ms=timing['prefill_ms'], prefill_tps=130925000/timing['prefill_ms'],
                decode_ms=timing['decode_ms'], decode_tps=8000/timing['decode_ms'],
                outputs=[dict(case=s['case'], content=s['content'], assistant=s['assistant'],
                              finish_reason=s['finish_reason'], usage=s['usage'],
                              token_pieces=[(chunk['choices'][0]['delta'].get('content'),
                                             chunk['choices'][0]['finish_reason'])
                                            for chunk in s['response_chunks']
                                            if chunk.get('choices')]) for s in samples])


def one_arm(plan, index, arm, result, own):
    cool()
    port = plan['port']
    # A closed server can leave a loopback TIME_WAIT socket. Test with the
    # HTTP server's reuse policy and allow its owned listener to retire.
    deadline = time.monotonic() + 60
    while True:
        try:
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('127.0.0.1', port))
            break
        except OSError as error:
            if error.errno != errno.EADDRINUSE or time.monotonic() >= deadline:
                raise
            time.sleep(.5)
    management = free_port()
    server = plan['candidate_server']['path']
    model = plan['model_stats'][0]['path']
    argv = [server, '--host', '127.0.0.1', '--port', str(port), '--management-host', '127.0.0.1',
            '--management-port', str(management), '--model', model, '--model-id', 'bench',
            '--context', '133760', '--prefill-chunk', '2048', '--max-active', '1',
            '--request-timeout-ms', '1800000', '--kv-cache-ram-mb', '16384',
            '--kv-cache-policy', 'ds4', '--kv-cache-min-tokens', '32',
            '--kv-cache-cold-max-tokens', '0', '--kv-cache-continued-interval-tokens', '0',
            '--kv-cache-boundary-trim-tokens', '0', '--kv-cache-boundary-align-tokens', '0',
            '--kv-cache-text-prefix', 'off', '--kv-cache-capture-finish', 'on']
    tag = f'{index:02d}-{arm}'
    sample_path = result / (tag + '.jsonl')
    telemetry = result / (tag + '.telemetry.jsonl')
    child = client = None
    client_argv = None
    env = dict(os.environ, HIP_VISIBLE_DEVICES='0', ROCR_VISIBLE_DEVICES='0')
    try:
        with (result/(tag+'.server.log')).open('x') as log:
            child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                     cwd=ROOT, env=env, start_new_session=True)
            own.append(identity(child))
            write_new(result/(tag+'.server-start.json'), dict(own[-1], at=now(), argv=argv))
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                require(child.poll() is None, 'Owned server exited before readiness')
                try:
                    with urllib.request.urlopen(
                        f'http://127.0.0.1:{management}/actuator/llm', timeout=3) as response:
                        ready = json.load(response)
                    if ready.get('ready') is True:
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError('Owned server readiness timeout')
            client_argv = [plan['client']['path'], '--suite', 'http', '--url',
                           f'http://127.0.0.1:{port}/v1', '--model', 'bench', '--output',
                           str(sample_path), '--server-label', tag, '--server-kv-cache', 'on',
                           '--requests', plan['requests']['path'], '--context-capacity', '133760',
                           '--rope-scaling', 'native', '--warmups', '0', '--repetitions', '1',
                           '--timeout', '1800']
            with (result/(tag+'.client.log')).open('x') as client_log, telemetry.open('x') as samples:
                client = subprocess.Popen(client_argv, stdout=client_log,
                                          stderr=subprocess.STDOUT, cwd=ROOT,
                                          env=env, start_new_session=True)
                own.append(identity(client))
                write_new(result/(tag+'.client-start.json'),
                          dict(own[-1], at=now(), argv=client_argv))
                client_deadline = time.monotonic() + 1800
                while client.poll() is None:
                    require(time.monotonic() < client_deadline,
                            'Owned client exceeded the original 1800-second timeout')
                    require(child.poll() is None, 'Owned server exited while client ran')
                    samples.write(json.dumps(dict(sensor(), cpu_temp_mc=cpu_temp_mc()))+'\n')
                    samples.flush()
                    require(cpu_temp_mc() <= 98000, 'CPU exceeded qualified 98 C gate')
                    time.sleep(2)
                require(client.returncode == 0, 'Owned client failed')
    finally:
        for process in (client, child):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        write_new(result / (tag + '.children.json'), {
            'server_argv': argv,
            'server_exit_code': child.returncode if child is not None else None,
            'client_argv': client_argv,
            'client_exit_code': client.returncode if client is not None else None,
            'owned_identities': list(own), 'finished_at': now(),
        })
    report = validate_output(sample_path, [json.loads(line) for line in
                                           Path(plan['requests']['path']).read_text().splitlines()])
    report.update(arm=arm, index=index, server_sha256=sha(server),
                  client_sha256=sha(plan['client']['path']), output_sha256=sha(sample_path),
                  telemetry_sha256=sha(telemetry))
    return report


def run(plan, previous):
    active(plan)
    result = ROOT / LABEL / 'results'
    require(not result.exists(), 'Previous pair result exists')
    with leases(previous):
        clear(previous)
        result.mkdir(parents=True)
        own = []
        write_new(result/'supervisor-start.json',
                  dict(identity(SimpleNamespace(pid=os.getpid())), at=now()))
        summary = dict(schema='synapse-lie.q2-decode-down-rows-native128-results.v1',
                       plan_sha256=sha(PLAN), order=plan['order'], started_at=now(),
                       arms=[], owned_identities=own, state='RUNNING')
        try:
            power_check(result / 'power-before.json')
            for index, arm in enumerate(plan['order']):
                summary['arms'].append(one_arm(plan, index, arm, result, own))
                write_new(result/f'{index:02d}-receipt.json', summary['arms'][-1])
                print(json.dumps(dict(index=index, arm=arm,
                    prefill_tps=summary['arms'][-1]['prefill_tps'])), flush=True)
            power_check(result / 'power-after.json')
            summary['state'] = 'COMPLETE'
        except Exception as error:
            summary.update(state='FAILED', error=str(error))
            raise
        finally:
            summary['finished_at'] = now()
            write_new(result/'native-result.json', summary)


def release(plan, previous):
    active(plan)
    result = ROOT / LABEL / 'results' / 'native-result.json'
    require(result.exists(), 'Pair result was not collected')
    summary = read(result)
    with leases(previous):
        clear(previous, summary['owned_identities'])
        receipt = dict(schema='synapse-lie.q2-decode-down-rows-native128-window.v3',
                       boot_id=EXPECTED_BOOT,
                       state='Q2_DECODE_DOWN_ROWS_NATIVE128_RELEASED', at=now(), plan_sha256=sha(PLAN),
                       admission_sha256=sha(ADMISSION), pair_result_sha256=sha(result),
                       pair_state=summary['state'], kfd_empty=True,
                       original_model_stats_unchanged=True, original_leases_free=True,
                       retired_owned_identities=summary['owned_identities'],
                       retired_identities=[*previous['retired_identities'],
                                           *summary['owned_identities']],
                       retired_groups=sorted(set(previous['retired_groups']) |
                                             {row['process_group'] for row in
                                              summary['owned_identities']}),
                       models=previous['models'], leases=previous['leases'],
                       core_cpu_lease=previous['core_cpu_lease'],
                       historical_release=previous['historical_release'],
                       historical_release_sha256=previous['historical_release_sha256'],
                       remote_cleanup=False, gpu_reserved=False, next_window_owner='core')
        write_new(RELEASE, receipt)
        emit_event('window_release', dict(receipt, path=RELEASE))
        print(json.dumps(receipt))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('verify', 'admit', 'run', 'release'))
    args = parser.parse_args()
    plan = read(PLAN)
    previous = source(plan)
    if args.mode == 'verify':
        rows = registry_rows()
        require(rows and rows[-1].get('event') == 'window_release' and
                rows[-1].get('receipt_sha256') == plan['previous_release_sha256'],
                'Intervening ownership event')
        with leases(previous):
            clear(previous)
            power_check(HERE / 'verify-power.json')
        print(json.dumps(dict(verified=True, gpu_admitted=False, at=now())))
    elif args.mode == 'admit':
        admit(plan, previous)
    elif args.mode == 'run':
        run(plan, previous)
    else:
        release(plan, previous)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print('Q2 down native128 trial failed: ' + str(error), file=sys.stderr)
        sys.exit(2)
