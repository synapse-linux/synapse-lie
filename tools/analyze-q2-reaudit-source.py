#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record measured rechecks and mechanisms already present in the fixed Q2 source."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = Path('src/models/qwen38_flash_next/kernels/rocm')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def body(text, name):
    start = text.index('__global__ void '+name+'(')
    cursor = text.index('{', start)+1
    depth = 1
    while depth:
        depth += (text[cursor] == '{') - (text[cursor] == '}')
        cursor += 1
    return text[start:cursor]


def main():
    output = ROOT/'config/q2-rejected-test-reaudit-progress.json'
    if output.exists():
        raise ValueError('Refusing to overwrite source audit')
    inventory_path = ROOT/'config/q2-rejected-test-reaudit.json'
    inventory = read(inventory_path)
    for row in inventory['candidates']:
        if sha(ROOT/row['result']) != row['source_sha256']:
            raise ValueError('Original rejected report changed: '+row['result'])
    manifests = ['config/q2-iq2-mixed-model-source.json',
                 'config/q2-hc-library-ragged-source.json',
                 'config/q2-scaled-input-source.json',
                 'config/q2-reaudit-composition-results.json']
    fixed = read(ROOT/manifests[0])
    ragged = read(ROOT/manifests[1])
    if (ragged['base'] != '.deps/gufo-q2-bench-library-norm-bound' or
            ragged['changed_files'] != [str(REL/'blaslt.cpp')]):
        raise ValueError('Retained paired-norm ancestry changed')
    providers = [('fixed', fixed['candidate'], fixed['files']),
                 ('library_ragged', ragged['candidate'], ragged['source_file_hashes'])]
    verified = {}
    for key, path, expected in providers:
        source = ROOT/path
        actual = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
        if actual != expected:
            raise ValueError('Retained source changed: '+path)
        verified[key] = dict(path=path, files=len(actual))
    current = ROOT/fixed['candidate']/REL
    previous_ragged = ROOT/ragged['candidate']/REL
    packed = current/'q2_scaled_input.inc'
    scaled = read(ROOT/manifests[2])
    old_scaled = next(r['sha256'] for r in scaled['changed_files']
                      if r['path'] == str(REL/'q2_scaled_input.inc'))
    if sha(packed) != old_scaled:
        raise ValueError('Fixed source no longer carries retained scaled-input packing')
    exact_norm = {}
    for name in ('HcCombineF32HalfKernel', 'HcCombineMoeF32HalfKernel'):
        a = body((current/'kernels.hip.cpp').read_text(), name)
        b = body((previous_ragged/'kernels.hip.cpp').read_text(), name)
        if a != b:
            raise ValueError('Paired norm body differs: '+name)
        exact_norm[name] = hashlib.sha256(a.encode()).hexdigest()
    if (current/'blaslt.cpp').read_bytes() != (previous_ragged/'blaslt.cpp').read_bytes():
        raise ValueError('Retained HC library dispatch differs')
    executor = (current/'executor.cpp').read_text()
    blas = (current/'blaslt.cpp').read_text()
    if ('!wide_mixer_ && n_tokens == 2048' not in executor or
            'm == 320 && n >= 96 && n <= 2048 && k == 10240 ? 7526' not in blas):
        raise ValueError('Expected bounded fixed-parent dispatch absent')
    observations = dict(scaled_input_inc_exact_sha256=old_scaled,
        paired_norm_kernel_bodies_exact_sha256=exact_norm,
        paired_norm_fixed_point_dispatch_already_present=True,
        hc_library_ragged_blaslt_exact_sha256=sha(current/'blaslt.cpp'),
        hc_library_algorithm_7526_already_present=True)
    families = {
        'shared-q8': 'New candidate and both compositions measured; exact production/model replay. Oracle cause remains unproven.',
        'scaled-row': 'New fixed-model Q8+row composition measured; all21 Q2 replay files exact.',
        'norm-fixed': 'New Q8+row+norm composition measured; exact replay to prior norm model with preserved logit differences.',
        'scaled-input': 'Identical packing include already in fixed parent; earlier arithmetic change is not an additional missing improvement.',
        'scaled-library': 'Packing and the original-F16 HC library route are already in fixed parent; prior component/model timing exists.',
        'library-norm': 'Both paired norm bodies and the fixed2048 dispatch are already in fixed parent; prior complete timing exists.',
        'hc-library-ragged': 'Entire blaslt.cpp exactly matches fixed parent; prior component/model timing exists.',
        'norm-ragged': 'The existing2048 pairing is already in fixed parent; broader ragged dispatch does not add a new mechanism at this fixed point.',
        'scaled-tiles': 'Performance already collected despite numeric rejection; tile128 slows every measured routing and tile64 benefits only highly shared routing.',
        'hc-sequence': 'Performance already collected despite numeric rejection; both measured geometries slow the complete cycle.',
        'hc-deferred-norm': 'Performance already collected; ordinary cycle slows, MoE cycle has a marginal gain with real feedback differences. New integration against the current library consumer remains pending.'}
    report = dict(schema='synapse-lie.q2-rejected-test-reaudit-progress.v1',
        original_inventory_sha256=sha(inventory_path),
        original_reports_verified=len(inventory['candidates']),
        manifest_sha256={p:sha(ROOT/p) for p in manifests},
        source_inventories_verified=verified, source_observations=observations,
        families=families, new_model_compositions='config/q2-reaudit-composition-results.json',
        controls_rerun=False, confirmed_false_failures_not_inferred=True,
        original_failures_preserved=True, independent_quality_complete=False,
        entire_reaudit_complete=False, goal_met=False,
        limits='Source presence and saved performance do not establish numeric acceptance, a false oracle, or independent additive gains. Nineteen records remain eleven candidate families plus four host/status records. No GPU run in this source audit.')
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(original_reports_verified=report['original_reports_verified'],
        providers=verified,observations=observations,goal_met=False)))


if __name__ == '__main__':
    main()
