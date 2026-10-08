#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read per-dispatch resource metadata in marked GPU phases; no GPU work."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3


def report(database):
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('''SELECT ks.display_name, kd.start, kd.end,
            kd.private_segment_size, kd.group_segment_size,
            kd.workgroup_size_x, kd.workgroup_size_y, kd.workgroup_size_z
            FROM rocpd_kernel_dispatch kd
            JOIN rocpd_info_kernel_symbol ks ON ks.id=kd.kernel_id
            ORDER BY kd.start''').fetchall()
    result = {'scope': 'Static dispatch metadata inside marked phases; private bytes do not measure dynamic spill traffic', 'phases': {}}
    for phase in ('Prefill', 'Decode'):
        begin = [r for r in rows if 'Q2Profile' + phase + 'Begin' in r[0]]
        end = [r for r in rows if 'Q2Profile' + phase + 'End' in r[0]]
        if len(begin) != 1 or len(end) != 1 or end[0][1] <= begin[0][2]:
            raise ValueError('Invalid marker pair')
        groups = defaultdict(lambda: {'calls': 0, 'total_ns': 0})
        for name, start, stop, private, shared, wx, wy, wz in rows:
            if start < begin[0][2] or stop > end[0][1] or name.startswith('Q2Profile'):
                continue
            if stop <= start or private < 0 or shared < 0 or min(wx, wy, wz) <= 0:
                raise ValueError('Invalid dispatch metadata')
            entry = groups[(name, private, shared, wx * wy * wz)]
            entry['calls'] += 1
            entry['total_ns'] += stop - start
        if not groups:
            raise ValueError('Empty marked phase')
        result['phases'][phase.lower()] = [dict(kernel=k[0], private_bytes_per_work_item=k[1],
            shared_bytes_per_work_group=k[2], work_items_per_group=k[3], **v)
            for k, v in sorted(groups.items(), key=lambda item: item[1]['total_ns'], reverse=True)]
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = report(args.database)
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    for phase, rows in data['phases'].items():
        print(phase)
        for row in rows[:8]:
            print(row['calls'], round(row['total_ns'] / 1e6, 3),
                  row['private_bytes_per_work_item'], row['shared_bytes_per_work_group'], row['kernel'][:160])
