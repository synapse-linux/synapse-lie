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


def owns_process(pid, leader, start_ticks):
    current_leader = identity(leader)
    if current_leader and current_leader['start_ticks'] != start_ticks:
        return False
    current = identity(pid)
    return bool(current and current['session'] == leader and
                current['group'] == leader)


def members(leader, start_ticks):
    current = identity(leader)
    if current and current['start_ticks'] != start_ticks:
        raise RuntimeError('Owned session leader identity changed')
    result = []
    for path in Path('/proc').glob('[0-9]*'):
        row = identity(int(path.name))
        if row and row['session'] == leader and row['group'] == leader:
            if row['state'] not in ('Z', 'X'):
                result.append(row)
    return result


def stop_owned(child, start_ticks):
    """Keep descendants covered even when a profiler wrapper exits first."""
    for sig, grace in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 2.0)):
        live = members(child.pid, start_ticks)
        if not live:
            break
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            child.poll()
            if not members(child.pid, start_ticks):
                break
            time.sleep(0.02)
    child.wait(timeout=2)
    if members(child.pid, start_ticks):
        raise RuntimeError('Owned command descendants did not retire')


def supervise(argv, *, cwd, env, log, row, timeout, save=lambda: None,
              clients=lambda: (), observe=lambda pid: None, interval=0.5):
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
            foreign = [pid for pid in clients()
                       if identity(pid) and not owns_process(pid, child.pid, start_ticks)]
            if foreign:
                row['foreign_kfd'] = foreign
                raise RuntimeError('Foreign KFD client during run')
            if time.monotonic() >= next_observation:
                observe(child.pid)
                next_observation = time.monotonic() + 2.0
            time.sleep(interval)
        remaining = members(child.pid, start_ticks)
        if remaining:
            row['lingering_descendants'] = remaining
            raise RuntimeError('Owned wrapper exited with live descendants')
    finally:
        try:
            stop_owned(child, start_ticks)
        finally:
            row['exit_code'] = child.returncode
            save()
    if child.returncode:
        raise RuntimeError('Qualification command failed')
