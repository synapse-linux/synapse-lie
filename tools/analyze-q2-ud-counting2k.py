#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the saved native Q2/UD 2K samples without rerunning either model."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import struct

ROOT = Path(__file__).resolve().parents[1]
INPUT_SHA = '75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35'
ARMS = [('Q2', 'q2-counting-full-prefill-r1', '01-short-133760'),
        ('UD-Q4_K_XL', 'q2-ud-counting2k-r1', '00-ud-2k')]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows, arms, identities, prompts, binaries, outputs = [], [], [], [], [], []
    for model, cohort, tag in ARMS:
        directory = ROOT/'evidence'/cohort
        path = directory/'results'/(tag+'.jsonl')
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert read(directory/'run-command.json')['exit_code'] == 0
        assert read(directory/'results/native-result.json')['state'] == 'COMPLETE'
        assert read(directory/'results'/(tag+'.child.json'))['exit_code'] == 0
        assert records[-1] == {'event': 'complete', 'exit_code': 0}
        identities.append(records[0])
        identity = records[0]
        assert identity['synthetic'] is False and identity['suite'] == 'fresh'
        assert identity['measurement_contract'] == 'full-prefill-v1'
        assert identity['decode_contract'] == 'completed-forward-per-emitted-token-v1'
        assert identity['warmups'] == 1 and identity['repetitions'] == 3
        assert identity['prefill_chunk'] == 2048
        assert identity['execution'] == 'LIE-reactive-ready-batch'
        prompt, = [r for r in records if r['event'] == 'input']
        source, = [r for r in records if r['event'] == 'prompt_source']
        prompts.append(prompt)
        assert prompt['context_capacity'] == 133760 and prompt['users'] == 1
        assert prompt['target_prompt_tokens'] == prompt['prompt_tokens'] == 2048
        assert len(prompt['physical_ids']) == 2048
        digest = hashlib.sha256(struct.pack('<2048i', *prompt['physical_ids'])).hexdigest()
        assert digest == prompt['physical_ids_sha256'] == source['physical_ids_sha256'] == INPUT_SHA
        binary_sha = sha(directory/'synapse-lie-bench')
        assert binary_sha == read(directory/'plan.json')['staged_sha256']['synapse-lie-bench']
        binaries.append(binary_sha)
        samples = [r for r in records if r['event'] == 'sample']
        assert len(samples) == 4 and [s['warmup'] for s in samples] == [1, 0, 0, 0]
        for rep, sample in enumerate(samples):
            assert sample['rep'] == rep and sample['depth'] == sample['cache_tokens'] == 0
            assert sample['prefill_tokens_per_user'] == 2048
            assert sample['prefill_calls_per_user'] == 1 and sample['prefill_tail_tokens'] == 0
            assert sample['full_output_budget'] == sample['finite_frontiers'] == 1
            assert sample['output_tokens_per_user'] == sample['decode_single_calls'] == 128
            assert len(sample['output_ids']) == 128
            values = {}
            for phase, count in [('prefill', 2048), ('decode', 128)]:
                elapsed = sample[phase+'_end_monotonic_ns']-sample[phase+'_begin_monotonic_ns']
                assert elapsed == sample[phase+'_ns'] and elapsed > 0
                rate = count*1e9/elapsed
                assert abs(rate-sample[phase+'_tps']) < 1e-7
                values[phase+'_seconds'] = elapsed/1e9
                values[phase+'_tps'] = rate
            outputs.append(sample['output_ids'])
            rows.append(dict(model=model, rep=rep, warmup=bool(sample['warmup']),
                             prompt_tokens=2048, chunk=2048, context_capacity=133760,
                             output_tokens=128, **values))
        measured = [r for r in rows if r['model'] == model and not r['warmup']]
        arms.append(dict(model=model, evidence=str(path.relative_to(ROOT)),
                         evidence_sha256=sha(path), samples=measured,
                         prefill_median_tps=statistics.median(r['prefill_tps'] for r in measured),
                         decode_median_tps=statistics.median(r['decode_tps'] for r in measured)))
    assert identities[0] == identities[1] and prompts[0] == prompts[1]
    assert binaries[0] == binaries[1]
    ud_dir = ROOT/'evidence/q2-ud-counting2k-r1'
    release, strong = read(ud_dir/'release.json'), read(ud_dir/'strong-closure.json')
    assert release['gpu_reserved'] is False and strong['release_sha256'] == sha(ud_dir/'release.json')
    assert strong['kfd_empty'] and strong['original_five_leases_free']
    result = dict(schema='synapse-lie.q2-ud-counting2k-comparison.v1',
                  binary_sha256=binaries[0], input_sha256=INPUT_SHA,
                  identical_harness_and_input=True, q2_rerun=False,
                  old_reference_replaced=False, full_128k_curve=False,
                  output_ids_equal=all(x == outputs[0] for x in outputs), arms=arms,
                  ud_relative_to_q2_percent={phase: 100*(arms[1][phase+'_median_tps']/arms[0][phase+'_median_tps']-1)
                                            for phase in ('prefill', 'decode')},
                  release_sha256=sha(ud_dir/'release.json'), strong_closure=strong)
    (ROOT/'config/q2-ud-counting2k-results.json').write_text(json.dumps(result, indent=2)+'\n')
    with (ROOT/'docs/figures/q2-ud-counting2k.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    lines = ['<!-- SPDX-License-Identifier: MIT -->', '', '# Native Q2 and UD comparison at 2048 tokens', '',
             'Owner-requested UD model check on .157 using the same retained `synapse-lie-bench`',
             'executable as the saved Q2 arm. No standalone Gufo application and no Q2 rerun.',
             'Physical input: 2048 identical counting-chat token IDs, one 2048-token prefill call',
             'from an empty sequence, allocated capacity 133760, C1 reactive greedy AR, MTP off.',
             'Each model has one warmup and three measured repetitions, with no pause between them.',
             'PP times the whole input; TG times 128 completed calls and emits 128 tokens.',
             'Model load, tokenization and sequence allocation are outside these phase timestamps.',
             'IOMMU remains enabled. These sequential model runs are not interleaved repetitions.', '',
             '| Model | Repetition | Prefill (token/s) | Full prefill (s) | Decode (token/s) | Decode (s) |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        if not row['warmup']:
            lines.append(f"| {row['model']} | {row['rep']} | {row['prefill_tps']:.6f} | "
                         f"{row['prefill_seconds']:.9f} | {row['decode_tps']:.6f} | {row['decode_seconds']:.9f} |")
    lines += ['', 'All warmups and measured values: [CSV](figures/q2-ud-counting2k.csv).', '',
              '| Model | Prefill median (token/s) | Decode median (token/s) |', '| --- | ---: | ---: |']
    for arm in arms:
        lines.append(f"| {arm['model']} | {arm['prefill_median_tps']:.6f} | {arm['decode_median_tps']:.6f} |")
    delta = result['ud_relative_to_q2_percent']
    lines += ['', f"Observed UD minus Q2: {delta['prefill']:+.4f}% PP; {delta['decode']:+.4f}% TG.",
              f"All eight 128-token continuations identical: {result['output_ids_equal']}.",
              'This single counting task does not establish general model quality or numerical equivalence.',
              'UD uses the current embedded provider and its UD loader/kernel dispatch; this result',
              'does not claim an unmodified upstream Gufo executable. Only the 2K point was run.', '',
              '## Historical Q2 difference remains open', '',
              'The saved best fixed-2K prefill observation remains 1587.893545 token/s.',
              'The later scalar-HC executable already measured 1571.380247 on 7 October.',
              'That historical comparison also changed Release versus RelWithDebInfo compilation,',
              'so it does not isolate a scalar-kernel regression. The current same-capacity 9216',
              'native observation is 1574.899595; the 133760-capacity arm above is 1572.143839.',
              'These are observed differences of -12.993950 and -15.749706 token/s from the saved best.',
              'The 1542.547201 observation belongs to the full 8192-token prompt, not the 2048-token point;',
              'subtracting it from 1587.893545 gives -45.346344 while changing input length.',
              'The historical harness also pauses 15 seconds between samples and times 127 decode',
              'forwards. Neither the historical best nor the lower observations are discarded,',
              'but no causal attribution or directly comparable historical TG delta is established.',
              '[Earlier HC evidence and compilation correction](Q2-HC-SCALAR-UP-MIX.md),',
              '[current Q2 full-prefill samples](Q2-COUNTING-FULL-PREFILL.md).', '',
              '## Closure', '',
              f"UD run/child exit 0. Release: `{result['release_sha256']}` at {release['at']}.",
              f"Strong closure at {strong['at']} verifies empty KFD, five free original leases,",
              f"{strong['retired_identities']} retired identities/groups and unchanged model stats.",
              'No model mutation, remote build, cleanup, service change, tuning or reboot occurs.', '']
    (ROOT/'docs/Q2-UD-COUNTING2K.md').write_text('\n'.join(lines))
    print(json.dumps({k: v for k, v in result.items() if k != 'arms'}))
    for arm in arms:
        print(json.dumps(arm))


if __name__ == '__main__':
    main()
