#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the HC candidate priority to saved fixed-model and static evidence."""
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = {key: ROOT / 'config' / name for key, name in (
        ('previous_queue', 'q2-target-priorities-update.json'),
        ('fixed_reference', 'q2-fixed-prefill-reference.json'),
        ('retained_model', 'q2-ssm-fixed-bounds-model-results.json'),
        ('down_model', 'q2-down-register-palette-model-results.json'),
        ('historical_profile', 'q2-current-best-profile-results.json'),
        ('private_draft', 'q2-hc-inject-reuse-draft-v3.json'),
        ('private_static', 'q2-hc-inject-reuse-draft-static-v3.json'),
        ('producer_boundary', 'q2-producer-fusion-boundary.json'),
        ('last_release', 'q2-down-register-palette-v2-window-release.json'))}
    data = {k: json.loads(p.read_text()) for k, p in paths.items()}
    reference = data['fixed_reference']
    pp = data['retained_model']['model']['measurements']['prefill_tok_s']['median']
    tg = data['retained_model']['model']['measurements']['decode_steps_s']['median']
    ud = reference['arms']['ud']['measurements']['prefill_tok_s']['median']
    assert (pp, tg, ud) == (1585.308983, 25.16079073, 1685.777092)
    assert reference['protocol']['physical_prompt_tokens'] == 2048
    assert reference['protocol']['timed_decode_calls'] == 127
    assert reference['input']['sha256'] == data['retained_model']['model']['input_sha256']
    assert sha(paths['last_release']) == data['previous_queue']['release_sha256']
    static = data['private_static']
    assert static['draft_manifest_sha256'] == sha(paths['private_draft'])
    assert static['original_kernel_bodies_instruction_operand_resource_exact'] == 162
    assert static['coefficient_address_vectors_checked'] == 10240
    assert not static['GPU_run'] and not static['production_provider']
    assert static['extra_lds_bytes'] == static['extra_barriers'] == 0
    kernels = data['historical_profile']['phases']['prefill']['kernels']
    def total(match):
        return sum(k['total_ns'] for k in kernels if match(k['kernel'])) / 1e6
    regions = dict(
        injection_ms=total(lambda k: 'HcMixEpilogueVec4Kernel<float, false>' in k or
                           'HcInjectDeferredNormKernel<float, false>' in k),
        affected_mix_ms=total(lambda k: 'HcMixDeferredNormKernel' in k or
            'DenseF16GEMMKernel<256, 128, 1, 4, 2, 8, true, false, false, true, true>' in k),
        packing_ms=total(lambda k: 'PackQ2ScaledRowsKernel' in k),
        IQ2_gate_up_ms=total(lambda k: 'RoutedF16GEMMKernel' in k and 'WeightType)16' in k))
    assert abs(regions['injection_ms'] - 39.548835) < 1e-9
    assert abs(regions['affected_mix_ms'] - 85.284003) < 1e-9
    assert abs(regions['packing_ms'] - 17.096259) < 1e-9
    assert abs(regions['IQ2_gate_up_ms'] - 239.499759) < 1e-9
    gap_ms = (data['retained_model']['model']['measurements']['prefill_s']['median'] -
              reference['arms']['ud']['measurements']['prefill_s']['median']) * 1000
    prep = ROOT / 'evidence/q2-hc-inject-reuse-draft-preparation'
    commands = []
    for label, expected in (
        ('lds-draft-v3-generation', 0), ('lds-draft-v3-assembly', 0),
        ('lds-draft-v3-static-audit', 1), ('lds-draft-v3-static-audit-v2', 0)):
        path = prep / (label + '-command.json')
        result = json.loads(path.read_text())
        assert result['exit_code'] == expected
        commands.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                             actual_exit=expected))
    report = dict(schema='synapse-lie.q2-target-priorities-hc-lds.v1',
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        inputs={k: dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for k, p in paths.items()},
        retained_variant='ssm-fixed-bounds', retained_PP=pp, retained_TG=tg,
        fixed_UD_PP=ud, required_PP_increase_percent=(ud / pp - 1) * 100,
        required_prefill_saving_ms=gap_ms,
        current_regions_from_saved1571_profile=regions,
        profile_is_fresh1585=False,
        first='HC normalized-input reuse plus once-per-CTA injection coefficient staging',
        first_next_step='New guarded full raw/raw-Q8/deferred mix/inject cycle with validated timing; qualify borrowed scratch before candidate-only original2048 model',
        first_new_lds_or_persistent_allocation=False, first_extra_block_barriers=0,
        second='Whole640 producer/packing ownership preserving the whole-row scale and live producer reuse',
        second_implementation_prepared=False,
        injection_alone_cannot_close_gap=regions['injection_ms'] < gap_ms,
        projected_model_rate=None, numerical_probability_estimated=False,
        old_negative_trials_queued_for_rerun=False,
        saved_comparators_rebuilt_or_rerun=False, full_curve=False, Q4=False,
        GPU_run=False, GPU_reserved=False, production_provider_changed=False,
        remote_cleanup=False, commands=commands,
        user_report='docs/Q2-HC-INJECTION-REUSE-DRAFT.md',
        user_report_sha256=sha(ROOT / 'docs/Q2-HC-INJECTION-REUSE-DRAFT.md'),
        independent_quality=False, performance_increment_found=False, goal_met=False)
    with (ROOT / 'config/q2-target-priorities-hc-lds-update.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(retained_PP=pp, fixed_UD_PP=ud,
        required_PP_increase_percent=report['required_PP_increase_percent'],
        required_prefill_saving_ms=gap_ms, first=report['first'],
        historical_regions=regions, GPU_run=False, goal_met=False)))


if __name__ == '__main__':
    main()
