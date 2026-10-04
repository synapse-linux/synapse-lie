#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the ordered IQ2 candidate with its Q2 control and pristine UD."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


common = module('analyze-q2-curve.py')
require, read, sha = common.require, common.read, common.sha
METRICS = ('prefill_tokens_per_second', 'decode_tokens_per_second')
COUNTS = ('prompt_tokens', 'cached_prompt_tokens', 'prefill_tokens',
          'completion_tokens', 'decode_calls')


def history(reference, candidate, client):
    paths = [sorted(root.glob('request-*.json')) for root in (reference,candidate)]
    require(all(group for group in paths), 'Missing complete request history')
    for group in paths:
        require([p.name for p in group] == [f'request-{i:04d}.json' for i in range(len(group))],
                'Missing/reordered request history')
    rows = []
    for i in range(max(map(len,paths))):
        if any(i >= len(group) for group in paths):
            rows.append(dict(index=i,missing_request=True,payload_exact=False,
                             output_exact=False,counts_exact=False))
            continue
        a,b = [read(group[i]) for group in paths]
        for r in (a,b):
            require(r.get('index') == i and 'error' not in r and hashlib.sha256(json.dumps(r['payload']).encode()).hexdigest()
                    == r['payload_sha256'], 'Incomplete/changed raw request')
        x,xt = client.parse_reply(a['response'],a['payload']['stream'])
        y,yt = client.parse_reply(b['response'],b['payload']['stream'])
        rows.append(dict(index=i,payload_exact=a['payload']==b['payload'],
                         output_exact=xt==yt and x.finish_reason==y.finish_reason,
                         counts_exact=all(getattr(x,k)==getattr(y,k) for k in COUNTS),
                         reference_completion_sha256=x.completion_sha256,
                         candidate_completion_sha256=y.completion_sha256))
    return dict(requests_reference=len(paths[0]),requests_candidate=len(paths[1]),rows=rows,
                exact=all(r['payload_exact'] and r['output_exact'] and r['counts_exact'] for r in rows))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','ud','host','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--baseline-repeat', type=Path,
                   help='Unchanged Q2 control after candidate; retain both baselines')
    composition = p.add_mutually_exclusive_group()
    composition.add_argument('--ple-cache-first', action='store_true',
                   help='Compare composed PLE reader against ordered IQ2 control, retaining UD')
    composition.add_argument('--iq2-mixed', action='store_true',
                   help='Compare mixed128/64 map against ordered IQ2 control, retaining UD')
    args = p.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite a result')
    host = common.artifacts(args.host)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not host['model_access'],
            'Host qualification incomplete')
    tests = 22 if args.iq2_mixed else 21 if args.ple_cache_first else 19
    for name in ('03.log','06.log'):
        require(f'100% tests passed out of {tests}' in (args.host/'results'/name).read_text(),
                'Missing complete Debug/ASan host cohort')
    base = read(ROOT/'config/q2-curve-source.json')
    candidate = read(ROOT/'config/q2-iq2-signs-ordered-asm-source.json')
    require(set(base['variants']['q2']['files']) == set(candidate['files']) and
            [name for name in candidate['files'] if candidate['files'][name] !=
             base['variants']['q2']['files'][name]] ==
            ['src/models/qwen38_flash_next/kernels/rocm/mmq/vecdotq.hpp'],
            'More than the isolated IQ2 header changed')
    composed = copy.deepcopy(base)
    composed['variants']['q2'] = dict(source=candidate['candidate'],files=candidate['files'])
    baseline_experiment, experiment = None, 'iq2-signs-ordered'
    candidate_manifest = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    if args.ple_cache_first:
        require(args.baseline_repeat is not None and host['mode'] == 'ple-cache-first-cpu',
                'PLE comparison requires the paired host suite and unchanged order control')
        ple_host = module('analyze-q2-ple-cache-first.py')
        for name in ('03.log','06.log'):
            ple_host.observations((args.host/'results'/name).read_text())
        candidate_manifest = ROOT/'config/q2-ple-ordered-source.json'
        ple = read(candidate_manifest)
        donor = read(ROOT/'config/q2-ple-cache-first-source.json')
        require(ple['parent_manifest_sha256'] == sha(ROOT/'config/q2-iq2-signs-ordered-asm-source.json')
                and ple['ple_manifest_sha256'] == sha(ROOT/'config/q2-ple-cache-first-source.json')
                and ple['curve_manifest_sha256'] == sha(ROOT/'config/q2-curve-source.json')
                and ple['host_result_sha256'] == sha(ROOT/'config/q2-ple-cache-first-host-results.json'),
                'PLE composition provenance changed')
        reader = 'src/models/qwen38_flash_next/ngram.cpp'
        require(ple['files'].keys() == candidate['files'].keys() and
                [name for name in ple['files'] if ple['files'][name] != candidate['files'][name]] == [reader]
                and ple['files'][reader] == donor['files'][reader],
                'PLE candidate changes more than the host-qualified reader')
        base = composed
        composed = copy.deepcopy(base)
        composed['variants']['q2'] = dict(source=ple['candidate'], files=ple['files'])
        baseline_experiment, experiment = 'iq2-signs-ordered', 'ple-cache-first-ordered'
    if args.iq2_mixed:
        require(args.baseline_repeat is not None and host['mode'] == 'cpu',
                'Mixed IQ2 comparison requires the host suite and unchanged order control')
        candidate_manifest = ROOT/'config/q2-iq2-mixed-model-source.json'
        mixed = read(candidate_manifest)
        component_path = ROOT/'config/q2-iq2-mixed-results.json'
        component = read(component_path)
        require(mixed['parent_manifest_sha256'] == sha(ROOT/'config/q2-iq2-signs-ordered-asm-source.json')
                and mixed['component_result_sha256'] == sha(component_path)
                and component['exact'] is True and component['numerical_pass'] is True,
                'Mixed IQ2 component provenance changed')
        prefix = 'src/models/qwen38_flash_next/'
        changed = {prefix+'CMakeLists.txt', prefix+'kernels/rocm/executor.cpp',
                   prefix+'kernels/rocm/executor.hpp'}
        added = {prefix+'kernels/rocm/iq2_mixed_tiles.'+suffix for suffix in ('c','h')}
        require(set(mixed['changed_files']) == changed and set(mixed['added_files']) == added and
                set(mixed['files']) == set(candidate['files']) | added and
                {n for n in candidate['files'] if mixed['files'][n] != candidate['files'][n]} == changed,
                'Mixed IQ2 candidate changed numerical kernels or unrelated provider files')
        qualified_host = read(ROOT/'config/q2-iq2-mixed-host-results.json')
        for name in added:
            local = 'experiments/'+Path(name).name
            require(mixed['files'][name] == sha(ROOT/local) == qualified_host['fixtures'][local],
                    'Model map differs from the component-qualified C17 helper')
        base = composed
        composed = copy.deepcopy(base)
        composed['variants']['q2'] = dict(source=mixed['candidate'], files=mixed['files'])
        baseline_experiment, experiment = 'iq2-signs-ordered', 'iq2-mixed-ordered'
    client = module('q2-canonical-http.py')
    upstream,_ = client.load_upstream(ROOT/'.deps/gufo-base')
    models = dict(baseline=common.model(args.baseline,'q2',args.host,base,client,upstream,
                                      experiment=baseline_experiment),
                  q2=common.model(args.candidate,'q2',args.host,composed,client,upstream,
                                  experiment=experiment),
                  ud=common.model(args.ud,'ud',args.host,base,client,upstream))
    replay = history(args.baseline/'results/canonical-curve',args.candidate/'results/canonical-curve',client)
    repeated_replay = None
    if args.baseline_repeat:
        models['baseline_repeat'] = common.model(
            args.baseline_repeat, 'q2', args.host, base, client, upstream,
            experiment=baseline_experiment)
        repeated_replay = history(args.baseline/'results/canonical-curve',
                                  args.baseline_repeat/'results/canonical-curve', client)
    matched = replay['exact'] and (repeated_replay is None or repeated_replay['exact'])
    cells = []
    for index,(baseline,q2,ud) in enumerate(zip(*(models[k]['rows'] for k in ('baseline','q2','ud')))):
        require(baseline['depth'] == q2['depth'] == ud['depth'], 'Depth order differs')
        counts = all(baseline[k] == q2[k] for k in COUNTS)
        ratios = {m:q2[m]/ud[m] for m in METRICS}
        cell = dict(depth=q2['depth'],candidate_vs_baseline_ratios={m:q2[m]/baseline[m] for m in METRICS},
            candidate_vs_ud_ratios=ratios,baseline_vs_ud_ratios={m:baseline[m]/ud[m] for m in METRICS},
            physical_counts_exact=counts,parity_observed=matched and counts and all(v>=1 for v in ratios.values()))
        if args.baseline_repeat:
            repeat = models['baseline_repeat']['rows'][index]
            require(repeat['depth'] == q2['depth'], 'Repeated baseline depth order differs')
            repeated_counts = all(repeat[k] == q2[k] for k in COUNTS)
            cell.update(repeated_physical_counts_exact=repeated_counts,
                candidate_vs_repeated_baseline_ratios={m:q2[m]/repeat[m] for m in METRICS},
                repeated_vs_initial_baseline_ratios={m:repeat[m]/baseline[m] for m in METRICS})
            cell['parity_observed'] = cell['parity_observed'] and repeated_counts
        cells.append(cell)
    report = dict(schema='synapse-lie.q2-iq2-canonical-comparison.v1',
        scope='Unchanged Gufo prose context curve over the same C17 HTTP core and timers; baseline Q2, ordered IQ2 Q2, pristine UD',
        provider_manifest_sha256=sha(candidate_manifest),
        models=models,history_replay=replay,cells=cells,matched_history=matched,
        full_curve_parity_observed=all(r['parity_observed'] for r in cells),
        repetition_needed_before_acceptance=True,numerical_qualified=False,promoted=False,goal_met=False)
    if repeated_replay is not None:
        report.update(baseline_repeat_history=repeated_replay,
            order_control_scope='Unchanged Q2 after candidate; both baseline observations retained. Filesystem coldness is not controlled or asserted.')
    if args.ple_cache_first:
        report.update(schema='synapse-lie.q2-ple-canonical-comparison.v1',
            scope='Unchanged Gufo prose context curve and C17 timers; ordered IQ2 Q2 control, same Q2 plus PLE cache-first, pristine UD',
            baseline_experiment=baseline_experiment, candidate_experiment=experiment)
    if args.iq2_mixed:
        report.update(schema='synapse-lie.q2-iq2-mixed-canonical-comparison.v1',
            scope='Unchanged Gufo prose context curve and C17 timers; ordered IQ2 Q2 control, same kernels with mixed128/64 dispatch, pristine UD',
            baseline_experiment=baseline_experiment, candidate_experiment=experiment)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(matched_history=matched,cells=cells,goal_met=False)))
    raise SystemExit(0 if matched else 1)


if __name__ == '__main__':
    main()
