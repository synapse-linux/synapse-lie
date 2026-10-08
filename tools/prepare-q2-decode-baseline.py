#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the historical LIE input and bind the paired producer to its measured shape."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parent.parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    evidence = MAIN / 'evidence/t0-c1-perf-r2/remote-results'
    receipt = json.loads((evidence / 'result.json').read_text())
    assert receipt['child_exit_code'] == 0
    assert sha(evidence / 'measurements.jsonl') == receipt['measurements_sha256']
    events = [json.loads(line) for line in (evidence / 'measurements.jsonl').read_text().splitlines()]
    physical = next(x for x in events if x['event'] == 'input' and x['prompt_tokens'] == 2042)
    assert len(physical['physical_ids']) == 2042
    samples = [x for x in events if x['event'] == 'sample' and x['profile'] == physical['profile']]
    assert len(samples) == 4 and all(x['completed_decode_tokens'] == 128 and x['final_position'] == 2170 for x in samples)
    header = '// SPDX-License-Identifier: MIT\n// Generated from hash-verified first-party LIE baseline; token data only.\n#pragma once\n#include <array>\n#include <cstdint>\ninline constexpr std::array<std::int32_t, 2042> kHistoricalInput{\n'
    for i in range(0, 2042, 12):
        header += '  ' + ', '.join(map(str, physical['physical_ids'][i:i+12])) + ',\n'
    header += '};\n'
    hp = ROOT / 'tests/q2_historical_input.hpp'
    with hp.open('x') as stream: stream.write(header)
    base = ROOT / '.deps/gufo-q2-bench-library-norm-cycle'
    out = ROOT / '.deps/gufo-q2-bench-library-norm-bound'
    original = json.loads((ROOT / 'config/q2-library-norm-cycle-static.json').read_text())['source_file_hashes']
    assert {str(p.relative_to(base)):sha(p) for p in base.rglob('*') if p.is_file()} == original
    shutil.copytree(base, out)
    rel = 'src/models/qwen38_flash_next/kernels/rocm/executor.cpp'
    p = out / rel; text = p.read_text()
    old = '!wide_mixer_ && n_tokens >= 96 && n_tokens <= options_.max_batch &&'
    assert text.count(old) == 1
    text = text.replace(old, '!wide_mixer_ && n_tokens == 2048 && n_tokens <= options_.max_batch &&')
    p.write_text(text)
    current = {str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
    assert [k for k in current if current[k] != original[k]] == [rel]
    report = dict(scope='Static preparation; no runtime acceptance',
        base=str(base.relative_to(ROOT)), candidate=str(out.relative_to(ROOT)),
        changed_file=rel, base_sha256=original[rel], candidate_sha256=current[rel],
        unchanged_files=len(current)-1, source_file_hashes=current,
        historical_baseline=dict(main_worktree=str(MAIN), measurement_sha256=receipt['measurements_sha256'],
            header_sha256=sha(hp), input=physical, samples=samples, summary=receipt['summary']['profiles'][1]),
        contract='Pair only n2048, where the measured library consumer is selected; other shapes use the original producer. All GPU kernels unchanged.',
        promoted=False, goal_met=False)
    (ROOT / 'config/q2-decode-baseline-static.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(unchanged_files=len(current)-1, historical_tokens=len(physical['physical_ids']))))

if __name__ == '__main__': main()
