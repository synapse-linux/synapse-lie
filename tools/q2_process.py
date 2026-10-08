# SPDX-License-Identifier: MIT
"""Bounded supervision of a command and descendants in its private session."""
import os
from pathlib import Path
import signal
import subprocess
import time


def identity(pid):
    try:
        # comm may itself contain spaces and closing parentheses.
        fields = Path('/proc', str(pid), 'stat').read_text().rsplit(') ', 1)[1].split()
        return {'pid': pid, 'state': fields[0], 'group': int(fields[2]),
                'session': int(fields[3]), 'start_ticks': int(fields[19])}
    except (FileNotFoundError, ProcessLookupError):
        return None


def owns_process(pid, leader, start_ticks, allow_child_groups=False):
    current_leader = identity(leader)
    if current_leader and current_leader['start_ticks'] != start_ticks:
        return False
    current = identity(pid)
    return bool(current and current['session'] == leader and
                (allow_child_groups or current['group'] == leader))


def members(leader, start_ticks, allow_child_groups=False):
    current = identity(leader)
    if current and current['start_ticks'] != start_ticks:
        raise RuntimeError('Owned session leader identity changed')
    result = []
    for path in Path('/proc').glob('[0-9]*'):
        row = identity(int(path.name))
        if row and row['session'] == leader and (allow_child_groups or row['group'] == leader):
            if row['state'] not in ('Z', 'X'):
                result.append(row)
    return result


def stop_owned(child, start_ticks, allow_child_groups=False):
    """Keep descendants covered even when a profiler wrapper exits first."""
    for sig, grace in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 2.0)):
        live = members(child.pid, start_ticks, allow_child_groups)
        if not live:
            break
        if allow_child_groups:
            # GDB puts its inferior in a distinct group within our private
            # session. Pin each owned task before signaling: never signal an
            # arbitrary group or trust a reused numeric PID.
            for row in live:
                fd = None
                try:
                    fd = os.pidfd_open(row['pid'])
                    current = identity(row['pid'])
                    if (current and current['start_ticks'] == row['start_ticks'] and
                            current['session'] == child.pid):
                        signal.pidfd_send_signal(fd, sig)
                except ProcessLookupError:
                    pass
                finally:
                    if fd is not None:
                        os.close(fd)
        else:
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                break
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            child.poll()
            if not members(child.pid, start_ticks, allow_child_groups):
                break
            time.sleep(0.02)
    child.wait(timeout=2)
    if members(child.pid, start_ticks, allow_child_groups):
        raise RuntimeError('Owned command descendants did not retire')


def supervise(argv, *, cwd, env, log, row, timeout, save=lambda: None,
              clients=lambda: (), observe=lambda pid: None, interval=0.5,
              allow_child_groups=False):
    if allow_child_groups and not (hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')):
        raise RuntimeError('Owned debugger children require pidfd support')
    child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True)
    # The child remains unreaped here, so its /proc identity is stable even if
    # it exited immediately after Popen returned.
    start_ticks = identity(child.pid)['start_ticks']
    row.update(pid=child.pid, start_ticks=start_ticks)
    try:
        save()
        deadline = time.monotonic() + timeout
        next_observation = 0.0
        while child.poll() is None:
            if time.monotonic() >= deadline:
                row['timeout'] = True
                raise RuntimeError('Owned command timed out')
            client_ids = [identity(pid) for pid in clients()]
            foreign = [r['pid'] for r in client_ids if r and
                       not owns_process(r['pid'], child.pid, start_ticks, allow_child_groups)]
            if foreign:
                row['foreign_kfd'] = foreign
                raise RuntimeError('Foreign KFD client during run')
            if allow_child_groups:
                known = row.setdefault('owned_kfd_identities', [])
                for r in client_ids:
                    if r and not any((v['pid'], v['start_ticks']) == (r['pid'], r['start_ticks']) for v in known):
                        known.append(r)
            if time.monotonic() >= next_observation:
                observe(child.pid)
                next_observation = time.monotonic() + 2.0
            time.sleep(interval)
        remaining = members(child.pid, start_ticks, allow_child_groups)
        if remaining:
            row['lingering_descendants'] = remaining
            raise RuntimeError('Owned wrapper exited with live descendants')
    finally:
        try:
            stop_owned(child, start_ticks, allow_child_groups)
        finally:
            row['exit_code'] = child.returncode
            save()
    if child.returncode:
        raise RuntimeError('Qualification command failed')
