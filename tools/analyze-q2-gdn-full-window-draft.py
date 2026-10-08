#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare a new GDN full-window draft with saved retained-parent ISA only."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('group', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
    group = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(group)
    parent = json.loads((ROOT / 'config/q2-iq2-fixed-bounds-static.json').read_text())
    before = ROOT / parent['candidate_assembly_path']
    after = ROOT / 'evidence/q2-gdn-full-window-draft-preparation/candidate.s'
    assert sha(before) == parent['candidate_assembly_sha256']
    a, b = [group.old.isa.parse(path) for path in (before, after)]
    at, bt = before.read_text(), after.read_text()
    assert len(a) == 164 and len(b) == 165 and set(a) <= set(b)
    for name in a:
        assert a[name]['resources'] == b[name]['resources'], name
        assert group.old.instructions(at, name) == group.old.instructions(bt, name), name
    extra = sorted(set(b) - set(a))
    assert len(extra) == 1
    new = extra[0]
    previous_name, new_name = 'GdnRowSplitKernel', 'GdnFullWindowDraftKernel'
    old = new.replace(str(len(new_name)) + new_name, str(len(previous_name)) + previous_name)
    assert old in a, old
    report = dict(schema='synapse-lie.q2-gdn-full-window-draft-static.v1',
        draft_sha256=sha(ROOT / 'config/q2-gdn-full-window-draft.json'),
        parent_assembly=str(before.relative_to(ROOT)), parent_assembly_sha256=sha(before),
        candidate_assembly=str(after.relative_to(ROOT)), candidate_assembly_sha256=sha(after),
        retained_bodies_exact=164, private_bodies=1,
        parent=dict(symbol=old, **a[old]), candidate=dict(symbol=new, **b[new]),
        parent_recompiled=False, provider_created=False, GPU_run=False,
        arithmetic_qualified=False, performance_claim=False, model_plan=False,
        source_arithmetic_order_unchanged=True,
        scope='Complete four-token windows; unroll the recurrence within a window without changing its source operation order. Tail/shape dispatch and runtime qualification are not implemented.')
    path = ROOT / 'config/q2-gdn-full-window-draft-static.json'
    with path.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(retained_bodies_exact=164,
        instructions=[a[old]['instructions'], b[new]['instructions']],
        parent_resources=a[old]['resources'], candidate_resources=b[new]['resources'],
        GPU_run=False, performance_claim=False)))


if __name__ == '__main__':
    main()
