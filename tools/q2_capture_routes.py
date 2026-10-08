# SPDX-License-Identifier: MIT
"""GDB host-entry capture for the frozen x86-64 Q2 counting executable.

Loaded with gdb -nx -nh -iex 'set auto-load off' -x this-file --args ... .
The inferior is always launched here, never attached to an existing process.
No inference time obtained under this debugger is a benchmark result.
"""
import json
import os
from pathlib import Path


def validate_counts(raw, experts, tokens, used):
    if (experts, tokens, used) != (512, 2048, 10) or len(raw) != 2048:
        raise ValueError('Unexpected routing shape')
    counts = [int.from_bytes(raw[i:i+4], 'little', signed=True)
              for i in range(0, len(raw), 4)]
    if any(n < 0 or n > tokens for n in counts) or sum(counts) != tokens*used:
        raise ValueError('Invalid expert counts')
    return counts


def capture():
    import gdb
    directory = Path(os.environ['LIE_Q2_ROUTING_OUTPUT']).resolve(strict=True)
    rows = []
    errors = []
    exits = []
    signals = []
    owned_pid = None

    def exited(event):
        exits.append(getattr(event, 'exit_code', None))

    def stopped(event):
        if isinstance(event, gdb.SignalEvent):
            signals.append(event.stop_signal)

    class Counts(gdb.Breakpoint):
        def stop(self):
            try:
                if len(rows) >= 96:
                    raise ValueError('Too many routing captures')
                frame = gdb.selected_frame()
                if frame.architecture().name() != 'i386:x86-64':
                    raise ValueError('Unsupported calling convention')
                experts, tokens, used = [int(frame.read_register(r))
                                        for r in ('esi', 'edx', 'ecx')]
                if (experts, tokens, used) != (512, 2048, 10):
                    raise ValueError('Unexpected routing shape')
                pointer = int(frame.read_register('rdi'))
                raw = bytes(gdb.selected_inferior().read_memory(pointer, 2048))
                row = dict(index=len(rows), phase='warm' if len(rows) < 48 else 'profile',
                           layer=len(rows) % 48, experts=experts, tokens=tokens, used=used,
                           counts=validate_counts(raw, experts, tokens, used))
                stream.write(json.dumps(row)+'\n')
                stream.flush()
                rows.append(row)
                return False
            except Exception as error:
                errors.append(str(error))
                return True

    gdb.events.exited.connect(exited)
    gdb.events.stop.connect(stopped)
    # The address breakpoint is before the optimized function's prologue.
    # Only read state in stop(); execution control is outside the callback.
    with (directory/'routing-counts.jsonl').open('x') as stream:
        try:
            if gdb.selected_inferior().pid:
                raise RuntimeError('Refusing to use a preexisting inferior')
            Counts('*lie_iq2_mixed_tiles', internal=True)
            gdb.execute('run')
            owned_pid = gdb.selected_inferior().pid
            if owned_pid:
                errors.append('Inferior stopped before normal exit')
                gdb.execute('kill')
        except Exception as error:
            errors.append(str(error))
            # This debugger creates exactly one inferior, through run above.
            # An exception before run must never terminate an attached process.
            if not any('preexisting inferior' in e for e in errors):
                owned_pid = gdb.selected_inferior().pid
                if owned_pid:
                    gdb.execute('kill')
    complete = not errors and not signals and exits == [0] and len(rows) == 96
    report = dict(schema='synapse-lie.q2-host-routing-capture.v1',
                  state='COMPLETE' if complete else 'FAILED', captures=len(rows),
                  inferior_exit_codes=exits, errors=errors, signals=signals,
                  terminated_owned_pid=owned_pid or None, headline_eligible=False,
                  gpu_builds=0, on_disk_binary_modified=False)
    with (directory/'routing-capture.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    gdb.execute('quit '+('0' if complete else '2'))


if __name__ == '__main__':
    capture()
