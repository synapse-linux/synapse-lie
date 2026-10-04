#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain independent cache timings and attribution for the audited row campaign."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT/'config/q2-native-row-curve-results.json'
    cache_path = ROOT/'config/q2-native-row-cache-timings.json'
    decision_path = ROOT/'config/q2-native-row-curve-decision.json'
    if cache_path.exists() or decision_path.exists():
        raise ValueError('Refusing to overwrite retained campaign evidence')
    result = read(path)
    if not all(result['history_matches'].values()) or set(result['arms']) != {'before','row','after','ud'}:
        raise ValueError('Incomplete or mismatched model comparison')
    rows = []
    for name, arm in result['arms'].items():
        raw = ROOT/arm['directory']/'results/native-curve.jsonl'
        events = [json.loads(s) for s in raw.read_text().splitlines()]
        requests = [e for e in events if e['event'] == 'request']
        for point in arm['rows']:
            timing = requests[point['request_index']]['observation']['server_timings']
            rows.append(dict(arm=name, depth=point['depth'], raw_sha256=sha(raw),
                **{k: timing[k] for k in ('cache_capture_ms','cache_restore_ms','prefill_calls','decode_calls')}))
    if len(rows) != 32:
        raise ValueError('Expected 32 separate cache observations')
    cache = dict(schema='synapse-lie.q2-native-row-cache-timings.v1', rows=rows,
        scope='Capture/restore durations are outside executor PP/TG timers; included in request wall time.')
    delta = {depth: dict(
        row_vs_before_pp_percent=100*(cell['row']['pp_tps']/cell['before']['pp_tps']-1),
        row_vs_after_pp_percent=100*(cell['row']['pp_tps']/cell['after']['pp_tps']-1),
        row_vs_ud_pp_percent=100*(cell['row']['pp_tps']/cell['ud']['pp_tps']-1),
        row_vs_after_tg_percent=100*(cell['row']['tg_tps']/cell['after']['tg_tps']-1),
        unchanged_control_pp_drift_percent=100*(cell['after']['pp_tps']/cell['before']['pp_tps']-1))
        for depth,cell in result['cells'].items()}
    comparisons = {reference: {metric: {
        depth: 100*(cell['row'][metric]/cell[reference][metric]-1)
        for depth,cell in result['cells'].items()}
        for metric in ('pp_tps','tg_tps','ttft_seconds','wall_seconds')}
        for reference in ('before','after','ud')}
    pp_slower = [int(depth) for depth,change in comparisons['after']['pp_tps'].items()
                 if change < 0]
    tg_slower = [int(depth) for depth,change in comparisons['after']['tg_tps'].items()
                 if change < 0]
    state = ('NOT_PROMOTED_NO_UNIFORM_MODEL_GAIN' if pp_slower or tg_slower else
             'COMPLETE_MODEL_COMPARISON_REQUIRES_ATTRIBUTION_REVIEW')
    previous_path = ROOT/'config/q2-native-scale-curve-results.json'
    previous = read(previous_path)
    if result['native_bench_commit'] != previous['native_bench_commit']:
        raise ValueError('Previous control used a different native client')
    prior_controls = {}
    for name in ('before','after','ud'):
        matched = result['arms'][name]['history'] == previous['arms'][name]['history']
        prior_controls[name] = dict(same_complete_history=matched)
        if matched:
            prior_controls[name]['change_percent'] = {
                depth: {metric: 100*(cell[name][metric]/previous['cells'][depth][name][metric]-1)
                        for metric in ('pp_tps','tg_tps','ttft_seconds','wall_seconds')}
                for depth,cell in result['cells'].items()}
    decision = dict(schema='synapse-lie.q2-native-row-curve-decision.v1',
        state=state,
        result_sha256=sha(path), model_inference=True, history_matches=result['history_matches'],
        candidate_change_percent=delta,
        comparison_percent=comparisons,
        comparison_direction='Positive throughput is faster; positive duration is slower.',
        depths_below_repeated_reference=dict(pp=pp_slower,tg=tg_slower),
        selection_rule='Keep isolated when the canonical model curve has mixed changes. This is a candidate-selection decision, not a statistical proof of regression.',
        previous_control_report_sha256=sha(previous_path),
        previous_control_comparison=prior_controls,
        preflight_linux_cached_gib={k:v['preflight_linux_cached_gib'] for k,v in result['arms'].items()},
        limits='One measured sample per depth and process. Retain both controls and file-cache/order observations. Independent numerical quality remains unresolved.',
        promoted=False, goal_met=False)
    with cache_path.open('x') as stream:
        stream.write(json.dumps(cache,indent=2,allow_nan=False)+'\n')
    with decision_path.open('x') as stream:
        stream.write(json.dumps(decision,indent=2,allow_nan=False)+'\n')
    print(json.dumps(delta,indent=2))


if __name__ == '__main__':
    main()
