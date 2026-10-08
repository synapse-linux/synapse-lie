#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind optimization priorities to the saved comparison and actual preparation."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(name):return json.loads((ROOT/name).read_text())
def sha(name):return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()


def main():
    parent_name='config/q2-ssm-fixed-bounds-model-results.json'
    reference_name='config/q2-fixed-prefill-reference.json'
    profile_name='config/q2-current-best-profile-results.json'
    parent=read(parent_name)['model']['measurements']
    reference=read(reference_name)['arms']
    profile=read(profile_name)['phases']['prefill']
    pp=parent['prefill_tok_s']['median'];ud=reference['ud']['measurements']['prefill_tok_s']['median']
    gap_ms=1000*(2048/pp-2048/ud)
    down=next(x for x in profile['stages'] if x['stage']=='routed_down_q2')
    inject=[x for x in profile['kernels'] if any(s in x['kernel'] for s in
        ('HcMixEpilogueVec4Kernel<float, false>','HcInjectDeferredNormKernel<float, false>'))]
    assert len(inject)==2 and sum(x['calls'] for x in inject)==96
    down_static=read('config/q2-down-register-palette-static.json')
    hc_static=read('config/q2-hc-inject-reuse-draft-static.json')
    assert down_static['other_kernels_instruction_operand_resource_exact']==161
    assert hc_static['original_kernel_bodies_instruction_operand_resource_exact']==162
    prep=ROOT/'evidence/q2-down-register-palette-preparation'
    commands={p.name:json.loads(p.read_text()) for p in sorted(prep.glob('*-command.json'))}
    failure={n:c['exit_code'] for n,c in commands.items() if c['exit_code']}
    expected={'admission-command.json':255,'admission-publish-command.json':1,
        'component-launch-command.json':255,'connectivity-audit-command.json':255,
        'connectivity-audit-2-command.json':255,'connectivity-audit-3-command.json':255}
    assert failure==expected,failure
    last=commands['connectivity-audit-3-command.json']
    assert last['exit_code']==255 and 'No route to host' in (prep/'connectivity-audit-3-stderr.txt').read_text()
    host=read('config/q2-down-register-palette-host-results.json')
    assert host['debug']==host['asan_ubsan']==33 and host['command_exits']==[0]*6
    names=[parent_name,reference_name,profile_name,'config/q2-down-register-palette-source.json',
        'config/q2-down-register-palette-static.json','config/q2-down-register-palette-host-results.json',
        'config/q2-down-register-palette-network-failure.json','config/q2-hc-inject-reuse-draft-v2.json',
        'config/q2-hc-inject-reuse-draft-static.json',
        'tools/q2-down-register-palette-phase.py','tests/q2_down_register_palette_phase_test.py',
        'tools/freeze-q2-down-register-palette-plan-v2.py',
        'tools/prepare-q2-down-register-palette-window-v2.py',
        'tools/analyze-q2-hc-inject-reuse-draft.py']
    report=dict(schema='synapse-lie.q2-target-priorities.v1',evidence={n:sha(n) for n in names},
        fixed_comparison=dict(prompt_tokens=2048,output_tokens=128,timed_decode_calls=127,
            saved_q2_pp=reference['mixed']['measurements']['prefill_tok_s']['median'],
            retained_pp=pp,retained_tg=parent['decode_steps_s']['median'],ud_pp=ud,
            ud_tg=reference['ud']['measurements']['decode_steps_s']['median'],
            needed_pp_increase_percent=100*(ud/pp-1),needed_prefill_reduction_ms=gap_ms),
        profile_scope='Saved1571 provider, exact2048 workload; historical attribution, not fresh1585 measurement',
        priority_basis='Measured stage cost, specific removable work, isolation and static resource cost; no numerical probability or forecast',
        priorities=[dict(rank=1,variant='down-register-palette',historical_stage_ms=down['total_ns']/1e6,
            mechanism='Elide wave-private Q2 weight/affine LDS stage, form exact half palette once',
            prepared='Isolated1028-file production provider and123-pair/70-timing guarded fixture',
            static_lds_bytes=[18560,8320],static_vgpr=[96,102],private_bytes=0,
            risks='More static instructions and VGPRs; reduced LDS did not help the completed IQ2 trial',
            runtime_result=None),
            dict(rank=2,variant='hc-inject-reuse-draft-v2',historical_inject_ms=sum(x['total_ns'] for x in inject)/1e6,
            historical_inject_calls=96,mechanism='Compute the original ordered injection dot while mix already holds normalized values; retain second-stage reduction',
            prepared='Three private compiler probes; no production selector or GPU fixture yet',
            proposed_dead_workspace_bytes=2048*2560*4,persistent_allocation_added=False,
            static_producer_vgpr=[242,242],static_producer_lds_bytes=[24576,24576],private_bytes=0,
            risks='Producer instructions/SGPRs increase; extra dot traffic and weights can offset the removed pass; lifetime needs executor qualification',
            runtime_result=None)],
        budget_limits=dict(down_required_saved_fraction_if_alone=gap_ms/(down['total_ns']/1e6),
            injection_full_removal_ms=sum(x['total_ns'] for x in inject)/1e6,
            launch_gap_ms=profile['inter_kernel_gap_ns']/1e6,
            caveat='Diagnostic region time is not removable in full. Fusion moves required arithmetic and adds dot storage. Budget arithmetic predicts no model speed.'),
        preparation_command_exits={n:c['exit_code'] for n,c in commands.items()},
        classified_failures=failure,last_connectivity=last,
        host_r1_passed=dict(debug=33,asan_ubsan=33),
        current_host_r2_required=dict(debug=34,asan_ubsan=34,executed=False,
            reason='New phase validation and five refusal/sequencing cases changed host scope'),
        blocked_runtime='SSH .157 unreachable before remote connection; no new admission, model run or GPU build',
        last_verified_release_sha256='57b67078e073f09c2aeb73b2ed2f6c288781131029c8267b840d6bcc77b2f04b',
        fresh_global_closure_claimed=False,gpu_reserved=False,controls_rerun=False,
        deferred=['Full context curve and Q4','Already rejected IQ2 tail16/register-stage and compact SSM LDS reruns'],
        independent_quality_qualification=False,goal_met=False)
    with (ROOT/'config/q2-target-priorities.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(priorities=2,retained_pp=pp,ud_pp=ud,gap_ms=gap_ms,
        preparation_commands=len(commands),classified_failures=failure,GPU_run=False)))


if __name__=='__main__':main()
