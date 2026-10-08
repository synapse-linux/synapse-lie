#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare completed original full prefixes only after collection and release."""
import json
from pathlib import Path
from q2_select_live_grid_model import inputs, sha, validate_result

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'q2-select-live-grid-model'


def read(path):
    return json.loads(path.read_text())


def main():
    plan_path = ROOT/('config/'+PREFIX+'-plan.json')
    release_path = ROOT/('config/'+PREFIX+'-window-release.json')
    plan, release = read(plan_path), read(release_path)
    assert release['state'] == 'Q2_SELECT_LIVE_GRID_MODEL_WINDOW_RELEASED'
    assert not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members']
    assert release['plan_sha256'] == sha(plan_path)
    label = plan['arms'][0]['label']
    directory = ROOT/'evidence'/label
    result = read(directory/'results/result.json')
    transport, collection = read(directory/'transport.json'), read(directory/'collection.json')
    assert sha(directory/'source.tar.gz') == transport['capsule_sha256']
    assert sha(directory/'results.tar.gz') == collection['sha256']
    assert collection['verified_artifacts'] == 0 and 'artifacts' not in result
    assert result['mode'] == transport['mode'] == 'q2-prefill-live-grid'
    assert result['finished_at'] and result['model_access'] and transport['exit_code'] == 1
    assert result['state'] == 'FAILED' and result['postflight_error'] == "KeyError('archive')"
    assert 'error' not in result
    supplemental_path = ROOT/('config/'+PREFIX+'-supplemental.json')
    supplemental = read(supplemental_path)
    assert supplemental['result_sha256'] == sha(directory/'results/result.json')
    assert supplemental['archives_unchanged'] and supplemental['model_stats_unchanged']
    assert not supplemental['kfd'] and not supplemental['model_rerun']
    assert supplemental['original_exit_code'] == 1 and not supplemental['original_receipt_modified']
    for name, binding in supplemental['artifacts'].items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        path = directory/'results'/name
        assert sha(path) == binding['sha256'] and path.stat().st_size == binding['bytes']
    assert all(c['exit_code'] == 0 for c in result['commands'])
    assert result['binary_sha256'] == result['binary_sha256_after']
    assert result['native_bench_reused'] and result['mmq_reuse']['controls_rebuilt_or_rerun'] is False
    candidate_path = directory/'results/full-prefill.jsonl'
    validation = validate_result(ROOT, candidate_path)
    candidate = [json.loads(line) for line in candidate_path.read_text().splitlines()
                 if json.loads(line)['event'] == 'sample']
    saved_path = ROOT/'config/q2-full-prefill128-results.json'
    saved = read(saved_path)
    assert sha(saved_path) == plan['manifests'][str(saved_path.relative_to(ROOT))]
    reference_cohort = next(c for c in saved['cohorts'] if c['label'] == 'q2-full-prefill128-retained-r1')
    reference_path = ROOT/'evidence'/reference_cohort['label']/'results/full-prefill.jsonl'
    assert sha(reference_path) == reference_cohort['samples_sha256']
    reference = {e['case']: e for e in map(json.loads, reference_path.read_text().splitlines())
                 if e['event'] == 'sample'}
    rows, quality = [], []
    for current, (_,binding) in zip(candidate, inputs(ROOT)):
        old = reference[current['case']]
        assert current['request'] == old['request']
        parts = lambda s: [choice['delta'] for chunk in s['response_chunks']
                           for choice in chunk['choices']]
        exact = (current['assistant'] == old['assistant'] and parts(current) == parts(old) and
                 current['usage'] == old['usage'] and current['finish_reason'] == old['finish_reason'])
        quality.append(dict(case=current['case'], streamed_pieces_and_reply_exact=exact))
        if binding['phase'] != 'prefix':
            continue
        a, b = old['server_timings'], current['server_timings']
        assert b['decode_tokens'] == b['decode_calls'] == binding['expected_output_tokens'] == 8
        historical = next(r for r in saved['rows'] if
                          (r['depth'],r['attempt']) == (binding['depth'],binding['attempt']))
        assert abs(a['prefill_ms']/1000-historical['current_prefill_seconds']) < 1e-9
        tokens = binding['expected_prompt_tokens']
        rows.append(dict(case=current['case'], depth=binding['depth'], attempt=binding['attempt'],
            tokens=tokens, calls=b['prefill_calls'], full_chunks=tokens//2048, tail=tokens%2048,
            parent_pp=tokens*1000/a['prefill_ms'], candidate_pp=tokens*1000/b['prefill_ms'],
            pp_change_percent=(a['prefill_ms']/b['prefill_ms']-1)*100,
            parent_prefill_ms=a['prefill_ms'], candidate_prefill_ms=b['prefill_ms'],
            parent_tg=8000/a['decode_ms'], candidate_tg=8000/b['decode_ms'],
            tg_change_percent=(a['decode_ms']/b['decode_ms']-1)*100,
            parent_decode_ms=a['decode_ms'], candidate_decode_ms=b['decode_ms'],
            decode_calls=8, candidate_wall_seconds=current['wall_seconds'],
            candidate_cache_capture_ms=b['cache_capture_ms'], cached_tokens=b['cached_tokens'],
            archived_ud_pp=historical['ud_prefill_tps'], reply_exact=exact))
    report = dict(schema='synapse-lie.'+PREFIX+'-results.v1',
        plan_sha256=sha(plan_path), release_sha256=sha(release_path),
        result_sha256=sha(directory/'results/result.json'), samples_sha256=sha(candidate_path),
        reference_samples_sha256=sha(reference_path), commands=[c['exit_code'] for c in result['commands']],
        original_launcher_exit_code=1, original_postflight_error=result['postflight_error'],
        supplemental_sha256=sha(supplemental_path),
        verified_artifacts=len(supplemental['artifacts']), validation=validation, rows=rows, quality=quality,
        all_streamed_replies_exact=all(q['streamed_pieces_and_reply_exact'] for q in quality),
        native_client_reused=True, retained_mmq_reused=True, controls_rebuilt_or_rerun=False,
        reactive_changed=False, public_ABI_or_state_changed=False, promoted=False,
        limits='One observation per original prefix, same original preparation/history through32K. '
               'Saved control is not contemporaneous. Eight decode calls do not establish TG128. '
               'Greedy reply agreement is not an independent model-quality assessment. '
               'Selector component percentages are not whole-model speedups.')
    with (ROOT/('config/'+PREFIX+'-results.json')).open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k in
                     ('commands','verified_artifacts','rows','all_streamed_replies_exact')}, indent=2))


if __name__ == '__main__':
    main()
