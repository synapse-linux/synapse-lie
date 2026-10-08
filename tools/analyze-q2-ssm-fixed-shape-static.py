#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare fixed-shape SSM compilation with the saved 1580 assembly."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'group', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
group = importlib.util.module_from_spec(spec)
spec.loader.exec_module(group)
ssm, old = group.ssm, group.old


def main():
    variant = sys.argv[1] if len(sys.argv) == 2 else 'ssm-fixed-shape'
    assert len(sys.argv) <= 2 and variant in ('ssm-fixed-shape', 'ssm-fixed-bounds')
    out = ROOT / ('evidence/q2-' + variant + '-preparation')
    manifest_path = ROOT / ('config/q2-' + variant + '-source.json')
    source = json.loads(manifest_path.read_text())['variants'][variant]
    for key in ('parent_manifest', 'measured_parent', 'patch', 'control_include', 'fixture', 'oracle'):
        assert ssm.sha(ROOT / source[key]) == source[key + '_sha256'], key
    parent = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['down-register-scatter']
    for provider in (source, parent):
        assert ssm.inventory(ROOT / provider['source']) == provider['files']
    saved = json.loads((ROOT / 'config/q2-down-register-scatter-static.json').read_text())
    parent_path = ROOT / saved['candidate_assembly_path']
    assert ssm.sha(parent_path) == saved['candidate_assembly_sha256']
    if variant == 'ssm-fixed-bounds':
        assert ssm.sha(ROOT / source['preceding_local_manifest']) == source['preceding_local_manifest_sha256']
    candidate_path = out / 'candidate.s'
    a, b = old.isa.parse(parent_path), old.isa.parse(candidate_path)
    before, after = parent_path.read_text(), candidate_path.read_text()
    assert set(a) == set(b) and len(a) == 162
    changed = [name for name in a if old.instructions(before, name) != old.instructions(after, name)
               or a[name]['resources'] != b[name]['resources']]
    assert len(changed) == 1
    symbol = changed[0]
    assert 'ILi256ELi128ELi2ELi8ELi1ELi1ELb0ELb1' in symbol
    control_source = (ROOT / parent['source'] / ssm.REL).read_text()
    literal = (ssm.function(control_source, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,') +
               ssm.function(control_source, 'bool DenseF16SsmGemm('))
    control = (ROOT / source['control_include']).read_text().split('\n', 2)[2]
    control = control.replace('DenseSsmRowGroupControlKernel', 'DenseF16GEMMKernel').replace(
        'DenseSsmRowGroupControl', 'DenseF16SsmGemm')
    assert literal == control
    with TemporaryDirectory(dir=out, prefix='reconstruct-') as tmp:
        dest = Path(tmp) / ssm.REL
        dest.parent.mkdir(parents=True)
        dest.write_text(control_source)
        result = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT / source['patch'])],
                                cwd=tmp, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert ssm.sha(dest) == source['files'][ssm.REL]
    commands = {name: json.loads((out / (name + '-command.json')).read_text())
                for name in ('generation', 'assembly', 'fixture-host', 'fixture-device')}
    assert all(row['exit_code'] == 0 for row in commands.values())
    frozen_path = ROOT / 'config/q2-ssm-row-group-plan.json'
    frozen = json.loads(frozen_path.read_text())
    for path, digest in {**frozen['fixtures'], **frozen['manifests'],
                         frozen['window_helper']: frozen['window_helper_sha256']}.items():
        assert ssm.sha(ROOT / path) == digest, path
    kept_mnemonics = ('v_wmma_f32_16x16x16_f16', 's_barrier', 'global_load_b128',
                      'global_store_b128', 'ds_store_b128')
    if variant == 'ssm-fixed-shape':
        kept_mnemonics += ('global_load_u16', 'ds_load_b128')
    assert all(a[symbol]['mnemonics'][k] == b[symbol]['mnemonics'][k] for k in kept_mnemonics)
    loads16 = [sum(kernel['mnemonics'].get(k, 0) for k in
                   ('global_load_u16', 'global_load_d16_b16')) for kernel in (a[symbol], b[symbol])]
    assert loads16 == [4, 4]
    report = dict(schema='synapse-lie.q2-' + variant + '-static.v1',
                  source_manifest_sha256=ssm.sha(manifest_path), provider_files=1027,
                  parent_assembly_path=str(parent_path.relative_to(ROOT)),
                  parent_assembly_sha256=ssm.sha(parent_path),
                  candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
                  candidate_assembly_sha256=ssm.sha(candidate_path),
                  parent_recompiled=False, source_reconstruction_exact=True,
                  other_kernels_instruction_operand_resource_exact=161,
                  literal_control_current_parent_exact=True,
                  parent_kernel=dict(symbol=symbol, **a[symbol],
                      compiler_comments=group.static.compiler_comments(before, symbol)),
                  candidate_kernel=dict(symbol=symbol, **b[symbol],
                      compiler_comments=group.static.compiler_comments(after, symbol)),
                  instruction_count_change_percent=100 * (b[symbol]['instructions'] / a[symbol]['instructions'] - 1),
                  retained_instruction_counts={k: a[symbol]['mnemonics'][k] for k in kept_mnemonics},
                  global_16bit_load_counts=loads16,
                  lds_128bit_load_counts=[kernel['mnemonics'].get('ds_load_b128', 0)
                                         for kernel in (a[symbol], b[symbol])],
                  frozen_ssm_row_group_plan_sha256=ssm.sha(frozen_path),
                  frozen_ssm_row_group_plan_unchanged=True, commands=commands,
                  cpu_checks_are_not_gpu_or_model_evidence=True,
                  compiled_arithmetic_equivalence_proven=False,
                  limits='Static instruction counts include scheduling instructions and are not dynamic '
                  'work or throughput. Floating instruction scheduling/packing changes; source formulas '
                  'and WMMA counts alone do not prove numerical equivalence. Existing guarded SSM '
                  'fixture compiles against this candidate, but GPU/component/model runs are pending.',
                  gpu_run=False, model_inference=False, numerical_acceptance=False, goal_met=False)
    if variant == 'ssm-fixed-bounds':
        report['symbolic_bounds'] = source['symbolic_bounds']
        initial_command = out / 'static-command.json'
        initial_checker = out / 'static-checker-initial.py'
        assert json.loads(initial_command.read_text())['exit_code'] == 1
        report['preserved_initial_checker_failure'] = dict(
            command=str(initial_command.relative_to(ROOT)), command_sha256=ssm.sha(initial_command),
            checker=str(initial_checker.relative_to(ROOT)), checker_sha256=ssm.sha(initial_checker),
            reason='Checker wrongly required identical load mnemonics; candidate substitutes two '
                   '16-bit load opcodes and adds 24 static LDS b128 loads. Candidate unchanged. '
                   'Also fixed checker loop-variable shadowing before writing the report.',
            numerical_failure=False)
        report['load_tradeoff'] = ('Fewer total static instructions coexist with 208 to 232 LDS b128 '
                                  'loads. Static occupancy is unchanged; hardware timing must decide.')
    with (ROOT / ('config/q2-' + variant + '-static.json')).open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(other_kernels_exact=161,
        instructions=[a[symbol]['instructions'], b[symbol]['instructions']],
        change_percent=report['instruction_count_change_percent'],
        resources=b[symbol]['resources'], frozen_campaign_unchanged=True, gpu_run=False)))


if __name__ == '__main__':
    main()
