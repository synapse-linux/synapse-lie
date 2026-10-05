#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an isolated SSM fixture without modifying the frozen GPU launcher."""
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT/'tools/prepare-q2-ssm-row-group.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def main():
    manifest_path = ROOT/'config/q2-ssm-row-group-source.json'
    candidate = json.loads(manifest_path.read_text())['variants']['ssm-row-group']
    parent = json.loads((ROOT/candidate['parent_manifest']).read_text())['variants']['scaled-wave-pack']
    assert prepare.inventory(ROOT/parent['source']) == parent['files']
    source = (ROOT/parent['source']/prepare.REL).read_text()
    kernel = prepare.function(source, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    wrapper = prepare.function(source, 'bool DenseF16SsmGemm(')
    control_text = (kernel+wrapper).replace('DenseF16GEMMKernel', 'DenseSsmRowGroupControlKernel').replace(
        'DenseF16SsmGemm', 'DenseSsmRowGroupControl')
    fixture_path = ROOT/'tests/q2_ssm_row_group.hip'
    control_path = ROOT/'experiments/q2-ssm-row-group-control.inc'
    report_path = ROOT/'config/q2-ssm-row-group-fixture.json'
    if any(p.exists() for p in (fixture_path, control_path, report_path)):
        raise ValueError('Refusing to overwrite a prepared fixture')
    old_path = ROOT/'tests/q2_ssm_row128.hip'
    original = old_path.read_text()
    changed = original.replace('ssm_row128', 'ssm_row_group').replace('ssm-row128-', 'ssm-row-group-')
    changed = prepare.once(changed, 'New SSM row-tile candidate', 'New SSM row-group candidate')
    changed = prepare.once(changed, '#include <array>', '#include <algorithm>\n#include <array>')
    changed = prepare.once(changed, 'experiments/q2-q8-grouped-control.inc', 'experiments/q2-ssm-row-group-control.inc')
    start = changed.index('  bool good;\n', changed.index('static void Launch('))
    stop = changed.index('  Require(good,', start)
    changed = changed[:start]+'''  auto call = candidate ? q::DenseF16SsmGemm : q::DenseSsmRowGroupControl;
  const bool good = call(w, x, static_cast<const float*>(inputs.conv.data),
      static_cast<const float*>(inputs.past.data), out,
      static_cast<float*>(state.convolved.data), inputs.n, inputs.m,
      inputs.k, 10240, 4, stream);
'''+changed[stop:]
    oracle = ROOT/'experiments/q2-ssm-row-group-oracle.inc'
    changed = prepare.once(changed, 'static bool Case(',
        '#include "experiments/q2-ssm-row-group-oracle.inc"\n\nstatic bool Case(')
    changed = prepare.once(changed, '''  }
  if (bench) {''', '''    pass = Oracle(in, reference, index, stream, label, "reference") && pass;
    pass = Oracle(in, candidate, index, stream, label, "candidate") && pass;
  }
  if (bench) {''')
    changed = prepare.once(changed,
        '    pass = Case("ssm2048", 2048, 16384, 2560, true, true, stream) && pass;',
        '''    pass = Case("ssm2048", 2048, 16384, 2560, true, true, stream) && pass;
    pass = Case("ssm2049", 2049, 16384, 2560, true, false, stream) && pass;''')
    changed = prepare.once(changed, '''    return 1;
  }
}''', '''    return 2;
  }
}''')
    fmt = subprocess.run(['/opt/rocm/llvm/bin/clang-format', '--sort-includes=false',
        '--style=file:'+str(ROOT/parent['source']/'.clang-format'),
        '--assume-filename='+str(fixture_path)], input=changed, text=True, capture_output=True)
    assert fmt.returncode == 0, fmt.stderr
    fixture_path.write_text(fmt.stdout)
    control_path.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal retained1574 dense template and SSM wrapper; test-only renames.\n'+control_text)
    report = dict(schema='synapse-lie.q2-ssm-row-group-fixture.v1',
        source_manifest=str(manifest_path.relative_to(ROOT)), source_manifest_sha256=prepare.sha(manifest_path),
        fixture=str(fixture_path.relative_to(ROOT)), fixture_sha256=prepare.sha(fixture_path),
        control_include=str(control_path.relative_to(ROOT)), control_include_sha256=prepare.sha(control_path),
        oracle=str(oracle.relative_to(ROOT)), oracle_sha256=prepare.sha(oracle),
        derived_from=str(old_path.relative_to(ROOT)), derived_from_sha256=prepare.sha(old_path),
        control_literal_parent_exact=True, numerical_shapes=[1024,1025,1057,2048,2049],
        full_output_pairs=30, sampled_fp64_checks=60, samples_per_fp64_check=24,
        timing_rows=14, timed_shape=dict(M=16384,N=2048,K=2560),
        weight_rotations=3, rotated_weight_bytes=133693440,
        numerical_exit=1, unsafe_runtime_exit=2, timing_after_safe_numerical_rejection=True,
        launchers_changed=False, frozen_register_scatter_fixtures_changed=False,
        gpu_run=False, model_inference=False, numerical_acceptance=False, goal_met=False)
    with report_path.open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(output_pairs=30, sampled_fp64_checks=60, timing_rows=14,
                         launchers_changed=False, gpu_run=False)))


if __name__ == '__main__':
    main()
