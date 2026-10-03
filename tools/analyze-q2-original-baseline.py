#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the unchanged historical C17 benchmark with fresh Q2 and UD receipts."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT/'tools/analyze-q2-combined.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
require = audit.require
FIXTURES = ('CMakeLists.txt', 'cmake/hip/CMakeLists.txt',
            'cmake/original-baseline/CMakeLists.txt', 'tests/q2_remote_test.py',
            'tools/q2-runner.py', 'tools/q2-remote.py', 'tools/q2_process.py',
            'tools/q2_thermal.py', 'tools/q2_reuse.py',
            'config/q2-original-baseline-source.json', 'config/models-157.inventory.json')


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_artifacts(path, receipt):
    collection = json.loads((path/'collection.json').read_text())
    for name,witness in receipt['artifacts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
        p = path/'results'/name
        require(p.stat().st_size == witness['bytes'] and audit.digest(p) == witness['sha256'], 'Artifact changed')
    require(collection['verified_artifacts'] == len(receipt['artifacts']), 'Collection mismatch')


def summarize(rows):
    identities = [r for r in rows if r.get('event') == 'identity']
    require(len(identities) == 1, 'Missing/duplicate identity')
    identity = identities[0]
    require(identity['source_pin'] == 'f783fedb9bea2ec7de941f6da4e02f4a4596b29e' and
            identity['synthetic'] is False and identity['context'] == 9216 and
            identity['chunk'] == 2048 and identity['output_limit'] == 128, 'Changed benchmark scope')
    require(rows[-1] == dict(event='complete', exit_code=0), 'Incomplete benchmark')
    inputs = [r for r in rows if r.get('event') == 'input']
    samples = [r for r in rows if r.get('event') == 'sample']
    require([r['profile'] for r in inputs] == [0,1,2] and
            [r['target'] for r in inputs] == [512,2048,8192], 'Missing/changed prompts')
    require([(r['rep'],r['profile']) for r in samples] ==
            [(rep,profile) for rep in range(4) for profile in ((2,1,0) if rep == 2 else (0,1,2))],
            'Changed sample order/count')
    result = {}
    for prompt in inputs:
        n, vocab = prompt['prompt_tokens'], prompt['vocab']
        require(0 < n <= prompt['target'] and n+128 < 9216 and vocab == 248320 and
                len(prompt['physical_ids']) == n and
                all(type(t) is int and 0 <= t < vocab for t in prompt['physical_ids']), 'Invalid input')
        group = [r for r in samples if r['profile'] == prompt['profile']]
        warm = group[0]
        for r in group:
            count = r['completed_decode_tokens']
            require(r['warmup'] is (r['rep'] == 0) and r['matches_warmup'] is (r['rep'] != 0) and
                    r['finite_logits'] is True, 'Missing original replay/finite gate')
            require(r['prompt_tokens'] == n and r['requested_prompt_target'] == prompt['target'] and
                    type(count) is int and 0 <= count <= 128 and r['stop'] in (0,1) and
                    (count == 128 or r['stop'] == 1) and r['final_position'] == n+count and
                    len(r['output_ids']) == count and
                    all(type(t) is int and 0 <= t < vocab for t in r['output_ids']), 'Invalid completed work')
            require(all(type(r[k]) is int and r[k] > 0 for k in ('prefill_ns','decode_ns')), 'Invalid duration')
            for key in ('prefill_logits_sha256','decode_logits_sha256'):
                require(bool(re.fullmatch('[0-9a-f]{64}',r[key])), 'Invalid frontier hash')
            for key in ('prefill_logits_sha256','decode_logits_sha256','output_ids',
                        'completed_decode_tokens','final_position','stop'):
                require(r[key] == warm[key], 'Original warmup replay changed')
        rates = dict(prefill_tok_s=[n*1e9/r['prefill_ns'] for r in group[1:]],
                     decode_tok_s=[r['completed_decode_tokens']*1e9/r['decode_ns'] for r in group[1:]])
        result[str(prompt['target'])] = dict(input=prompt, samples=group,
            full_128_completed=all(r['completed_decode_tokens'] == 128 and r['stop'] == 0 for r in group),
            rates=rates, medians={k:statistics.median(v) for k,v in rates.items()})
    return dict(identity=identity, profiles=result)


def validate(path, host, mode, variant, frozen):
    receipt = json.loads((path/'results/result.json').read_text())
    transport = json.loads((path/'transport.json').read_text())
    require(receipt['mode'] == mode and transport['source_variant'] == variant and
            receipt['state'] == 'ORIGINAL_C17_BASELINE_COMPLETE_NOT_QUALITY_VERDICT' and
            receipt['model_access'] is True, 'Wrong experiment scope')
    require([c['exit_code'] for c in receipt['commands']] == [0]*5 and transport['exit_code'] == 0,
            'Failed/incomplete commands')
    require(transport['rebuild_mmq'] and not receipt.get('mmq_reuse'), 'Missing full MMQ rebuild')
    require(receipt['binary_sha256'] == receipt['binary_sha256_after'] and
            receipt['models_before'] == receipt['models_after'], 'Binary/model changed')
    require(receipt['locks'] == receipt['postflight_locks'] and
            [(r['device'],r['inode']) for r in receipt['locks']] ==
            [(52,3232146),(52,3206482),(52,3228451),(55,45067)], 'Lease mismatch')
    require(not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'Unretired KFD')
    require('finished_at' in receipt, 'Unfinished runner')
    for row in [receipt,*receipt['commands']]:
        require(not any(row.get(k) for k in ('error','thermal_stop','postflight_error','timeout',
                    'foreign_kfd','lingering_descendants')), 'Process/thermal failure')
    verify_artifacts(path, receipt)
    require('measurements.jsonl' in receipt['artifacts'], 'Missing measurements')
    with tarfile.open(path/'source.tar.gz') as capsule, tarfile.open(host/'source.tar.gz') as hostcap:
        for name in FIXTURES:
            require(capsule.extractfile(name).read() == hostcap.extractfile(name).read(), 'Host cohort changed: '+name)
    fixtures = [*FIXTURES, *('experiments/original-baseline/'+n for n in frozen['files'])]
    return audit.audit_capsule(path, fixtures)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--q2', type=Path, required=True)
    p.add_argument('--ud', type=Path, required=True)
    p.add_argument('--host', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    frozen = json.loads((ROOT/'config/q2-original-baseline-source.json').read_text())
    for name,digest in frozen['files'].items():
        require(audit.digest(ROOT/frozen['source']/name) == digest, 'Frozen historical source changed')
    old = json.loads((ROOT/'config/q2-decode-baseline-static.json').read_text())['historical_baseline']
    oldpath = Path(old['main_worktree'])/'evidence/t0-c1-perf-r2/remote-results/measurements.jsonl'
    require(audit.digest(oldpath) == frozen['historical_measurement_sha256'], 'Historical evidence changed')
    historical = summarize(read_rows(oldpath))
    hr = json.loads((args.host/'results/result.json').read_text())
    ht = json.loads((args.host/'transport.json').read_text())
    require(hr['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not hr['model_access'] and
            [c['exit_code'] for c in hr['commands']] == [0]*6 and ht['exit_code'] == 0, 'Host tests incomplete')
    verify_artifacts(args.host, hr)
    for name in ('03.log','06.log'):
        require('100% tests passed out of 17' in (args.host/'results'/name).read_text(), 'Missing host test')
    host_audit = audit.audit_capsule(args.host, FIXTURES)
    models, comparisons, replay = {}, {}, {}
    for name,path,variant in [('q2',args.q2,'library-norm-bound'),('ud',args.ud,'qualified')]:
        evidence = validate(path,args.host,name+'-original-baseline',variant,frozen)
        models[name] = summarize(read_rows(path/'results/measurements.jsonl'))
        models[name]['validation'] = evidence
        replay[name] = {}
        for target,current in models[name]['profiles'].items():
            reference = historical['profiles'][target]
            require(current['input'] == reference['input'], 'Historical input changed')
            replay[name][target] = [dict(rep=c['rep'], **{k:c[k] == r[k] for k in
                ('output_ids','prefill_logits_sha256','decode_logits_sha256')})
                for c,r in zip(current['samples'],reference['samples'])]
    for target in historical['profiles']:
        comparisons[target] = {arm:{k:(100*(models['q2']['profiles'][target]['medians'][k]/
            reference['profiles'][target]['medians'][k]-1) if reference['profiles'][target]['medians'][k] else None)
            for k in ('prefill_tok_s','decode_tok_s')}
            for arm,reference in [('fresh_ud',models['ud']),('historical_ud',historical)]}
    report = dict(scope='Exact historical C17 benchmark/ABI/adapter with freshly compiled pinned Q2 and UD providers',
        historical=historical, model=models, replay_against_historical=replay,
        q2_change_percent=comparisons, host_validation=host_audit,
        numerical_pass=False, promoted=False, goal_met=False,
        limits='Historical production sampler skips isolated nonfinite logits; the unchanged benchmark verifies complete PP/final TG frontiers outside timers. Diagnostic strict checks and inherited operator/KL rejection remain. No HTTP, concurrency, long-context or task-quality qualification.')
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(q2_change_percent=comparisons, goal_met=False),indent=2))


if __name__ == '__main__':
    main()
