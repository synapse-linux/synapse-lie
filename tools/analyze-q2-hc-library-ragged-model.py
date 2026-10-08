#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare ragged HC dispatch with fresh original-C17 Q2 and pristine UD."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('original', ROOT/'tools/analyze-q2-original-baseline.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
require = original.require


def replay(left, right):
    result = {}
    for target, current in left['profiles'].items():
        reference = right['profiles'][target]
        require(current['input'] == reference['input'], 'Physical input changed')
        result[target] = [dict(rep=c['rep'], **{k: c[k] == r[k] for k in
            ('output_ids', 'prefill_logits_sha256', 'decode_logits_sha256')})
            for c, r in zip(current['samples'], reference['samples'])]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('control', 'candidate', 'ud', 'host', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads((ROOT/'config/q2-original-baseline-source.json').read_text())
    for name, digest in frozen['files'].items():
        require(original.audit.digest(ROOT/frozen['source']/name) == digest, 'Historical source changed')
    previous = json.loads((ROOT/'config/q2-decode-baseline-static.json').read_text())['historical_baseline']
    oldpath = Path(previous['main_worktree'])/'evidence/t0-c1-perf-r2/remote-results/measurements.jsonl'
    require(original.audit.digest(oldpath) == frozen['historical_measurement_sha256'], 'Historical data changed')
    historical = original.summarize(original.read_rows(oldpath))
    host = json.loads((args.host/'results/result.json').read_text())
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'] and
            [c['exit_code'] for c in host['commands']] == [0]*6 and
            json.loads((args.host/'transport.json').read_text())['exit_code'] == 0, 'Host failed')
    original.verify_artifacts(args.host, host)
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 17' in (args.host/'results'/name).read_text(), 'Missing host tests')
    host_audit = original.audit.audit_capsule(args.host, original.FIXTURES)
    manifest = json.loads((ROOT/'config/q2-hc-library-ragged-source.json').read_text())
    parent = json.loads((ROOT/'config/q2-decode-baseline-static.json').read_text())['source_file_hashes']
    for path, hashes in [(ROOT/manifest['candidate'], manifest['source_file_hashes']),
                         (ROOT/manifest['base'], parent)]:
        require({str(p.relative_to(path)): original.audit.digest(p) for p in path.rglob('*')
                 if p.is_file()} == hashes, 'Measured provider source changed')
    decision = json.loads((ROOT/'config/q2-hc-library-ragged-model-decision.json').read_text())
    require(decision['state'] == 'Q2_HC_LIBRARY_RAGGED_MODEL_DECISION' and
            decision['analyzer_integrity_pass'] and not decision['numerical_pass'], 'Missing component decision')
    require(original.audit.digest(ROOT/'config/q2-hc-library-ragged-results.json') ==
            decision['component_result_sha256'], 'Component evidence changed after admission')
    models, receipts = {}, {}
    for name, mode, variant in [('control', 'q2-original-baseline', 'library-norm-bound'),
                                ('candidate', 'q2-original-baseline', 'hc-library-ragged'),
                                ('ud', 'ud-original-baseline', 'qualified')]:
        path = getattr(args, name)
        validation = original.validate(path, args.host, mode, variant, frozen)
        models[name] = original.summarize(original.read_rows(path/'results/measurements.jsonl'))
        require(all(p['full_128_completed'] for p in models[name]['profiles'].values()), 'Incomplete 128 steps')
        models[name]['validation'] = validation
        receipts[name] = json.loads((path/'results/result.json').read_text())
        require(receipts[name]['started_at'] > decision['at'], 'Model predates component decision')
    require(receipts['control']['models_before'] == receipts['candidate']['models_before'], 'Different Q2 model')
    witnesses = dict(candidate_vs_control=replay(models['candidate'], models['control']),
                     control_vs_historical=replay(models['control'], historical),
                     candidate_vs_historical=replay(models['candidate'], historical),
                     ud_vs_historical=replay(models['ud'], historical))
    changes = {target: {name: {metric: 100*(models['candidate']['profiles'][target]['medians'][metric]/
                    reference['profiles'][target]['medians'][metric]-1)
                    for metric in ('prefill_tok_s', 'decode_tok_s')}
                    for name, reference in [('control', models['control']), ('ud', models['ud']),
                                            ('historical_ud', historical)]}
               for target in historical['profiles']}
    report = dict(scope='Original-C17 C1 AR, original weights, physical502/2042/8191, 128 completed steps',
        historical=historical, model=models, replay=witnesses, candidate_change_percent=changes,
        host_validation=host_audit, decision_sha256=original.audit.digest(ROOT/'config/q2-hc-library-ragged-model-decision.json'),
        numerical_pass=False, promoted=False, goal_met=False,
        limits='Only HC-down prefill dispatch changes. Decode arithmetic unchanged, but changed prefill logits can alter subsequent state. Same-build replay is not quality acceptance. Component FP64/position failures and inherited KL rejection remain. No HTTP, concurrency, long-context or task-quality qualification.')
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(medians={name: {target: p['medians'] for target, p in model['profiles'].items()}
                                  for name, model in models.items()},
                          candidate_change_percent=changes, goal_met=False), indent=2))


if __name__ == '__main__':
    main()
