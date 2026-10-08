#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply/restore one explicitly authorized temporary Limine entry on .157."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path('/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run')
HERE = ROOT / 'q2-counting-iommu-boot-r1'
CONFIG = Path('/boot/limine.conf')
BOOT = Path('/proc/sys/kernel/random/boot_id')
VARIABLE = Path('/sys/firmware/efi/efivars/LoaderEntryOneShot-4a67b082-0a4c-41cf-b6c7-440b29bb8c4f')
ENTRY = 'Synapse-LIE-IOMMU-off'
SHADOW_CONFIGS = ('/boot/EFI/limine/limine.conf', '/boot/EFI/BOOT/limine.conf',
                  '/boot/boot/limine/limine.conf', '/boot/boot/limine.conf',
                  '/boot/limine/limine.conf')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def boot_event(window, event, path, receipt):
    with window.REGISTRY.open('a') as stream:
        stream.write(json.dumps(dict(event=event, owner='synapse-lie-q2',
            boot_id=receipt['boot_id'], at=receipt['at'], receipt=str(path),
            receipt_sha256=sha(path), gpu_reserved=event == 'host_reboot_admission'))+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def replace_config(source, expected):
    require(not CONFIG.is_symlink() and sha(CONFIG) == expected,
            'Boot configuration changed; preserve concurrent edits')
    target = CONFIG.with_name('.synapse-lie-iommu-next.conf')
    original_mode = stat.S_IMODE(CONFIG.stat().st_mode)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, original_mode)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), original_mode)
        stream.write(source.read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(target, CONFIG)
    directory = os.open(CONFIG.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    require(sha(CONFIG) == sha(source), 'Boot configuration readback differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('qualify', 'apply', 'restore', 'rollback', 'reboot'))
    mode = parser.parse_args().mode
    require(mode == 'qualify' or os.geteuid() == 0, 'Explicit root execution is required')
    plan = json.loads((HERE / 'plan.json').read_text())
    require(plan['schema'] == 'synapse-lie.q2-counting-iommu-boot.v1', 'Wrong boot plan')
    require(plan['user_authorized'] is True and
            plan['boot_parameter'] == 'amd_iommu=off' and
            plan['before_window'] == 'q2-counting-curve128-r1' and
            plan['restore_exact_original_after_reconnect'] is True,
            'Authorized boot scope differs')
    require(sha(Path(__file__)) == plan['helper_sha256'], 'Boot helper changed')
    for name, expected in plan['files'].items():
        require(Path(name).name == name and sha(HERE / name) == expected,
                'Staged boot input changed: ' + name)
    original = HERE / 'limine.original.conf'
    candidate = HERE / 'limine.iommu-off.conf'
    completion = json.loads((HERE / 'curve-completion.json').read_text())
    require(completion['measured_points'] == 176 and
            completion['total_samples'] == 352 and
            completion['full_128k_curve'] is True and
            completion['analysis_exit_code'] == 0 and
            completion['tables_presented_to_user'] is True,
            'Complete measured curves and presented tables are required before reboot')
    boot = BOOT.read_text().strip()
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt = dict(mode=mode, at=stamp, boot_id=boot,
                   plan_sha256=sha(HERE / 'plan.json'))
    if mode in ('qualify', 'apply', 'reboot'):
        require(boot == plan['before_boot_id'], 'Unexpected boot before transition')
        source = ROOT / plan['before_window']
        release = source / 'release.json'
        require(sha(release) == plan['before_release_sha256'], 'Baseline release differs')
        require(sha(source / 'q2-counting-curve128-window.py') == plan['window_helper_sha256'],
                'Coordination helper differs')
        spec = importlib.util.spec_from_file_location('window', source / 'q2-counting-curve128-window.py')
        window = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(window)
        previous = json.loads(release.read_text())
        with window.leases(previous):
            window.clear(previous)
            expected_receipt = release if mode in ('qualify', 'apply') else HERE / 'applied.json'
            require(window.registry_rows()[-1]['receipt_sha256'] == sha(expected_receipt),
                    'New ownership after baseline release')
            if mode == 'qualify':
                scratch = HERE / 'cpu-fixtures'
                scratch.mkdir(exist_ok=False)
                command = subprocess.run([sys.executable, str(HERE/'q2_counting_iommu_boot_test.py')],
                    capture_output=True, text=True,
                    env=dict(os.environ, TMPDIR=str(scratch), LC_ALL='C', PYTHONDONTWRITEBYTECODE='1'))
                receipt.update(exit_code=command.returncode, stdout=command.stdout,
                               stderr=command.stderr, gpu_access=False,
                               helper_sha256=sha(Path(__file__)))
                write_new(HERE/'cpu-qualification.json', receipt)
                require(command.returncode == 0 and 'Ran 7 tests' in command.stderr,
                        'CPU boot-transition fixtures failed')
            elif mode == 'apply':
                qualification = json.loads((HERE/'cpu-qualification.json').read_text())
                require(qualification['exit_code'] == 0 and
                        qualification['plan_sha256'] == sha(HERE/'plan.json') and
                        qualification['helper_sha256'] == sha(Path(__file__)),
                        'Fresh CPU boot-transition qualification is required')
                require(not VARIABLE.exists(), 'Preserve an existing one-shot boot request')
                for path in SHADOW_CONFIGS:
                    require(not Path(path).exists(), 'A configuration could shadow /boot/limine.conf')
                replace_config(candidate, sha(original))
                try:
                    command = subprocess.run(['bootctl', 'set-oneshot', ENTRY],
                                             capture_output=True, text=True)
                    receipt.update(exit_code=command.returncode, stdout=command.stdout,
                                   stderr=command.stderr)
                    require(command.returncode == 0, 'One-shot selection failed')
                    require(VARIABLE.read_bytes()[4:].decode('utf-16-le').rstrip('\0') == ENTRY,
                            'One-shot selection readback differs')
                except Exception as error:
                    receipt['error'] = str(error)
                    # Restore only the owned change; preserve any concurrent request.
                    if VARIABLE.exists() and VARIABLE.read_bytes()[4:].decode('utf-16-le').rstrip('\0') == ENTRY:
                        cleared = subprocess.run(['bootctl', 'set-oneshot', ''],
                                                 capture_output=True, text=True)
                        receipt['clear_owned_oneshot'] = dict(exit_code=cleared.returncode,
                            stdout=cleared.stdout, stderr=cleared.stderr)
                    replace_config(original, sha(candidate))
                    write_new(HERE / 'apply-failed.json', receipt)
                    raise
                receipt.update(configuration_sha256=sha(CONFIG), one_shot=ENTRY,
                               original_default_preserved=True)
                write_new(HERE / 'applied.json', receipt)
                boot_event(window, 'host_reboot_admission', HERE / 'applied.json', receipt)
            else:
                require((HERE / 'applied.json').exists() and sha(CONFIG) == sha(candidate),
                        'Temporary boot entry is not armed')
                require(VARIABLE.read_bytes()[4:].decode('utf-16-le').rstrip('\0') == ENTRY,
                        'One-shot selection changed')
                write_new(HERE / 'reboot-requested.json', receipt)
                command = subprocess.run(['systemctl', 'reboot', '--no-block'],
                                         capture_output=True, text=True)
                receipt.update(exit_code=command.returncode, stdout=command.stdout,
                               stderr=command.stderr)
                write_new(HERE / 'reboot-command.json', receipt)
                require(command.returncode == 0, 'Reboot command failed')
    else:
        require((HERE / 'applied.json').exists(), 'No owned boot change to restore')
        if mode == 'restore':
            require(boot != plan['before_boot_id'], 'Host has not rebooted')
            require(not VARIABLE.exists(), 'One-shot boot request was not consumed')
        else:
            require(boot == plan['before_boot_id'], 'Use restore after a reboot')
            command = subprocess.run(['bootctl', 'set-oneshot', ''],
                                     capture_output=True, text=True)
            require(command.returncode == 0, 'Could not clear the owned one-shot request')
        replace_config(original, sha(candidate))
        receipt.update(configuration_sha256=sha(CONFIG),
                       exact_original_restored=True,
                       cmdline=Path('/proc/cmdline').read_text().strip(),
                       iommu_groups=len(list(Path('/sys/kernel/iommu_groups').glob('*'))))
        write_new(HERE / (mode + '.json'), receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
