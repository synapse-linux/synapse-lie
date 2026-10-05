#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Keep fixed Q2/UD and add the saved 1582 result to the new bounds comparison."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm_followup', ROOT / 'tools/analyze-q2-ssm-followup.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
require, sha, read = base.require, base.sha, base.read


def add_retained_best(report, plan):
    info = plan['retained_best']
    path = ROOT / info['report']
    require(sha(path) == info['sha256'], 'Saved best report changed')
    saved = read(path)
    require(saved['source_variant'] == info['variant'] and saved['original_tester_unchanged'] and
            not saved['controls_rerun'], 'Saved best protocol changed')
    source_path = ROOT / info['source_manifest']
    require(sha(source_path) == info['source_manifest_sha256'], 'Saved best source manifest changed')
    source = read(source_path)['variants'][info['variant']]
    cohort = ROOT / 'evidence' / info['label']
    root, arm = base.hc.prior.shared.arm(cohort, info['variant'])
    base.hc.curve.artifacts(cohort)
    binding = base.hc.capsule(cohort, plan['fixtures'], source['files'])
    require(arm['measurements'] == saved['model']['measurements'] and
            arm['samples'] == saved['model']['samples'] and
            arm['binary_sha256'] == saved['model']['binary_sha256'], 'Saved best differs from raw evidence')
    for key, value in binding.items():
        require(value == saved['model'][key], 'Saved best archive binding changed: ' + key)
    candidate_root = Path(report['model']['path']) / 'results'
    comparison = base.hc.prior.comparison(root, candidate_root)
    require(comparison['input_exact'], 'Saved best input differs')
    key = 'retained_best'
    require(key not in report['references'] and key not in report['checks'], 'Repeated saved reference')
    report['references'][key] = arm
    report['replay'][key] = comparison
    report['checks'][key] = dict(input_exact=comparison['input_exact'],
        output_tokens_exact=comparison['output_tokens_exact'], changed_files=comparison['changed'],
        max_matched_history_kl=max((f['kl_p_to_candidate'] for f in comparison['frontiers']
                                   if f['matched_history']), default=None))
    report['candidate_median_change_percent'].update(base.measurement_changes(report['model'], {key: arm}))
    report['retained_best_report_sha256'] = info['sha256']
    report['retained_best_rerun'] = False
    report['limits'] += ' Saved1582 is an additional historical reference; fixed Q2/UD and construction parent1580 remain.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    args = parser.parse_args()
    variant = 'ssm-fixed-bounds'
    plan, info, source = base.bound_plan(args.plan, variant)
    output = ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'
    require(not output.exists(), 'Refusing to overwrite model results')
    report = add_retained_best(base.model(args.plan, plan, info, source, variant), plan)
    base.hc.write(output, report)
    print(json.dumps(dict(output=str(output.relative_to(ROOT)),
        measurements=report['model']['measurements'], changes=report['candidate_median_change_percent'],
        checks=report['checks'], retained_best_rerun=False, goal_met=False)))


if __name__ == '__main__':
    main()
