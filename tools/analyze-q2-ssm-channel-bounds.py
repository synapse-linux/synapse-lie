#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the new channel-predicate experiment to fixed SSM checks and controls."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


# This private analysis instance admits only this experiment. The historical
# registry and its analyzer retain their original source identities.
base = module('analyze-q2-ssm-followup.py')
base.REGISTRY = 'config/q2-ssm-channel-bounds-runtime-source.json'
base.VARIANTS = ('ssm-channel-bounds',)
retained = module('analyze-q2-ssm-compact-lds.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('component', 'model'))
    parser.add_argument('--plan', required=True, type=Path)
    args = parser.parse_args()
    variant = 'ssm-channel-bounds'
    plan, info, source = base.bound_plan(args.plan, variant)
    output = ROOT / ('config/q2-' + variant + '-' + args.phase + '-results.json')
    base.require(not output.exists(), 'Refusing to overwrite retained results')
    if args.phase == 'component':
        report = base.component(args.plan, plan, info, source, variant)
        summary = {name: report[name] for name in
                   ('parent_exact', 'independent_operator_pass', 'summaries')}
    else:
        report = retained.add_retained_best(base.model(args.plan, plan, info, source, variant), plan)
        report['limits'] = report['limits'].replace(
            'construction parent1580', 'older component control1580; construction parent is retained1585')
        summary = dict(measurements=report['model']['measurements'],
                       changes=report['candidate_median_change_percent'], checks=report['checks'])
    base.hc.write(output, report)
    print(json.dumps(dict(output=str(output.relative_to(ROOT)), phase=args.phase,
                         **summary, goal_met=False)))


if __name__ == '__main__':
    main()
