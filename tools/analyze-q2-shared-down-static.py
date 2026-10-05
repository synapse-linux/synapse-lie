#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify both component providers and retain resource regressions alongside ISA."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('group', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
group = importlib.util.module_from_spec(spec)
spec.loader.exec_module(group)
ssm, old = group.ssm, group.old


def main():
    saved = json.loads((ROOT / 'config/q2-down-register-scatter-static.json').read_text())
    parent_asm = ROOT / saved['candidate_assembly_path']
    assert ssm.sha(parent_asm) == saved['candidate_assembly_sha256']
    a = old.isa.parse(parent_asm)
    before = parent_asm.read_text()
    control = next(s for s in a if 'DenseF16GEMMKernelILi256ELi128ELi1ELi4ELi2ELi1ELb0ELb0ELb0ELb0ELb0' in s)
    models = {}
    for name, total in (('shared-down-mirror', 164), ('shared-down-fixed', 166)):
        manifest = ROOT / ('config/q2-' + name + '-source.json')
        source = json.loads(manifest.read_text())['variants'][name]
        base = ROOT / source['source']
        assert ssm.inventory(base) == source['files']
        for key in ('parent_manifest', 'measured_parent', 'patch', 'conversion_source'):
            assert ssm.sha(ROOT / source[key]) == source[key + '_sha256'], key
        parent = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['down-register-scatter']
        assert ssm.inventory(ROOT / parent['source']) == parent['files']
        with TemporaryDirectory(dir=ROOT / 'evidence', prefix='shared-down-reconstruct-') as tmp:
            for rel in source['changed_files']:
                target = Path(tmp) / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if rel in parent['files']:
                    target.write_bytes((ROOT / parent['source'] / rel).read_bytes())
            p = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT / source['patch'])],
                               cwd=tmp, text=True, capture_output=True)
            assert p.returncode == 0, p.stderr
            for rel in source['changed_files']:
                assert ssm.sha(Path(tmp) / rel) == source['files'][rel], rel
        out = ROOT / ('evidence/q2-' + name + '-preparation')
        candidate_asm = out / 'candidate.s'
        b = old.isa.parse(candidate_asm)
        after = candidate_asm.read_text()
        assert len(a) == 162 and len(b) == total and a.keys() <= b.keys()
        for symbol in a:
            assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
            assert a[symbol]['resources'] == b[symbol]['resources'], symbol
        new = {s: dict(**b[s], compiler_comments=group.static.compiler_comments(after, s))
               for s in b.keys() - a.keys()}
        for symbol, kernel in new.items():
            if 'WeightsKernel' not in symbol:
                # Fixed-shape compilation peels the last matrix stage into
                # the epilogue: static opcode totals are not dynamic work.
                expected_wmma = 64 if 'SharedDownFixedKernel' in symbol else 32
                assert kernel['mnemonics']['v_wmma_f32_16x16x16_f16'] == expected_wmma
                assert kernel['resources']['group_segment_fixed_size'] == 24576
        labels = ('generation', 'assembly')
        if name == 'shared-down-fixed':
            labels += ('fixture-host', 'fixture-device')
            assert ssm.sha(ROOT / source['preceding_local_manifest']) == source['preceding_local_manifest_sha256']
        commands = {label: json.loads((out / (label + '-command.json')).read_text()) for label in labels}
        assert all(c['exit_code'] == 0 for c in commands.values())
        models[name] = dict(source_manifest=str(manifest.relative_to(ROOT)), source_manifest_sha256=ssm.sha(manifest),
            candidate_assembly_path=str(candidate_asm.relative_to(ROOT)), candidate_assembly_sha256=ssm.sha(candidate_asm),
            original_kernels_instruction_operand_resource_exact=162, new_kernels=new, commands=commands,
            source_reconstruction_exact=True, model_dispatch_changed=False)
    initial_path = ROOT / models['shared-down-mirror']['candidate_assembly_path']
    final_path = ROOT / models['shared-down-fixed']['candidate_assembly_path']
    for symbol in models['shared-down-mirror']['new_kernels']:
        assert old.instructions(initial_path.read_text(), symbol) == old.instructions(final_path.read_text(), symbol)
    conversion = next(s for s in models['shared-down-mirror']['new_kernels'] if 'Q8MirrorWeightsKernel' in s)
    qualified_asm = ROOT / 'evidence/q2-q8-mirror-preparation/candidate.s'
    qualified = json.loads((ROOT / 'config/q2-q8-mirror-static.json').read_text())
    assert ssm.sha(qualified_asm) == qualified['assembly_hashes']['candidate']
    assert old.instructions(qualified_asm.read_text(), conversion) == old.instructions(final_path.read_text(), conversion)
    fixture = ROOT / 'tests/q2_shared_down_mirror.hip'
    old_fixture = ROOT / 'tests/q2_q8_mirror.hip'
    formula = 'static std::uint16_t ExactProduct('
    normalize = lambda s: re.sub(r'\s+', '', s)
    assert normalize(ssm.function(fixture.read_text(), formula)) == normalize(ssm.function(old_fixture.read_text(), formula))
    frozen_path = ROOT / 'config/q2-ssm-row-group-plan.json'
    frozen = json.loads(frozen_path.read_text())
    for p, digest in {**frozen['fixtures'], **frozen['manifests'],
                      frozen['window_helper']: frozen['window_helper_sha256']}.items():
        assert ssm.sha(ROOT / p) == digest, p
    contract = dict(fixture=str(fixture.relative_to(ROOT)), fixture_sha256=ssm.sha(fixture),
        numerical_shapes=[96, 97, 127, 129, 1025, 2048, 2049],
        arms=['original-q8', 'generic-f16', 'fixed-q8', 'fixed-f16'],
        full_output_pairs=126, sampled_fp64_checks=168, samples_per_fp64_check=24,
        fp64_relative_rms_limit=.002, fp64_scaled_error_limit=.002,
        full_format_checks=42, full_format_values=42 * 2560 * 640,
        independent_integer_product_matches_qualified_formula=True,
        timing_rows=28, warmup_rows=8, measured_rows=20, iterations_per_timing=24,
        timed_shape=dict(M=2560, N=2048, K=640),
        rotated_q8_weight_bytes=24 * 2560 * 640 // 32 * 34,
        rotated_half_weight_bytes=24 * 2560 * 640 * 2,
        timing_excludes_conversion_allocation_and_checking=True,
        post_timing_output_replay=True, input_and_mirror_immutability=True,
        numerical_exit=1, unsafe_runtime_exit=2, timing_after_safe_numerical_rejection=True,
        completed_gpu_checks=0, launcher_wired=False, model_integrated=False)
    report = dict(schema='synapse-lie.q2-shared-down-static.v1',
        parent_assembly_path=str(parent_asm.relative_to(ROOT)), parent_assembly_sha256=ssm.sha(parent_asm),
        parent_kernel=dict(symbol=control, **a[control], compiler_comments=group.static.compiler_comments(before, control)),
        variants=models, fixture_contract=contract,
        converter_instruction_operand_exact_to_qualified_large_mirror=True,
        preserved_initial_analysis_failure=dict(
            command='evidence/q2-shared-down-fixed-preparation/static-command.json', exit_code=1,
            checker_sha256=ssm.sha(ROOT / 'evidence/q2-shared-down-fixed-preparation/static-checker-initial.py'),
            reason='The checker assumed32 static WMMA opcodes in all arms. Fixed-shape compilation '
                   'retains32 in the loop and peels32 into the final stage/epilogue. Source and '
                   'assembly were unchanged; no GPU numerical failure occurred.'),
        frozen_ssm_plan_sha256=ssm.sha(frozen_path), frozen_ssm_fixtures=88, frozen_ssm_manifests=5,
        frozen_ssm_campaign_unchanged=True, parent_recompiled=False,
        limits='Fewer static instructions coexist with register spills and increased F16 weight bytes. '
               'No bandwidth, GPU numerical, dynamic-instruction or throughput conclusion is established.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, performance_gain=False, goal_met=False)
    with (ROOT / 'config/q2-shared-down-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(original_kernels_exact=162, variants=2,
        fixture_pairs=126, oracle_checks=168, timing_rows=28, frozen_ssm_unchanged=True, gpu_run=False)))


if __name__ == '__main__':
    main()
