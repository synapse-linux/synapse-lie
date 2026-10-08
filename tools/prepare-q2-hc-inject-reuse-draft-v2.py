#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exclude duplicate parent dispatchers before compiling the isolated HC probe."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    initial_path = ROOT/'config/q2-hc-inject-reuse-draft.json'
    initial = json.loads(initial_path.read_text())
    original = ROOT/initial['include']
    assert sha(original) == initial['include_sha256']
    text = original.read_text()
    first = text.index('bool HcCombineMoeDeferredNorm(')
    last = text.index('// These private launchers exist only to instantiate the compiler probes.')
    removed = text[first:last]
    assert removed.count('bool HcCombineMoeDeferredNorm(') == 1
    assert removed.count('bool ReconstructHcNorm(') == 1
    text = text[:first]+text[last:]
    assert 'bool HcCombineMoeDeferredNorm(' not in text
    assert 'bool ReconstructHcNorm(' not in text
    out = ROOT/'experiments/q2-hc-inject-reuse-draft-v2.inc'
    with out.open('x') as f:
        f.write(text)
    prep = ROOT/'evidence/q2-hc-inject-reuse-draft-preparation'
    wrapper = prep/'probe-v2.hip'
    wrapper.write_text((ROOT/initial['compiler_probe']).read_text().replace(str(original),str(out)))
    args = json.loads((prep/'assembly-argv.json').read_text())
    args[args.index('-S')+1] = str(wrapper)
    args[-1] = str(prep/'candidate-v2.s')
    (prep/'assembly-v2-argv.json').write_text(json.dumps(args,indent=2)+'\n')
    report = dict(initial)
    report.update(schema='synapse-lie.q2-hc-inject-reuse-draft.v2',
        initial_manifest_sha256=sha(initial_path),initial_include_sha256=sha(original),
        initial_compile_attempted=False,
        correction='Source inspection excluded two duplicate parent dispatchers before any compiler invocation',
        include=str(out.relative_to(ROOT)),include_sha256=sha(out),
        generator_sha256=sha(Path(__file__)),compiler_probe=str(wrapper.relative_to(ROOT)),
        compiler_probe_sha256=sha(wrapper))
    with (ROOT/'config/q2-hc-inject-reuse-draft-v2.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(include=report['include'],removed_parent_dispatchers=2,GPU_run=False)))


if __name__ == '__main__':
    main()
