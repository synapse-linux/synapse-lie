#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the new exact-row reader against saved original native requests."""
import importlib.util
import json
from pathlib import Path
import re
from q2_ple_row_bytes_model import inputs, sha, validate_result

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'q2-ple-row-bytes'


def read(path):
    return json.loads(path.read_text())


def telemetry(directory, first, last):
    rows = [json.loads(line) for line in
            (directory/'results/telemetry.jsonl').read_text().splitlines()]
    selected = [r for r in rows if first <= r['at'] <= last]
    memory = lambda r: {line.split(':', 1)[0]: int(line.split()[1])*1024
                        for line in r['meminfo'].splitlines()}
    clocks = [int(m.group(1)) for r in selected for key, value in r.get('sensors', {}).items()
              if key.endswith('/pp_dpm_sclk')
              for m in re.finditer(r'(\d+)Mhz \*', value)]
    temperatures = {}
    for row in selected:
        for sensor in row['thermal']:
            name = sensor['device']
            temperatures[name] = max(temperatures.get(name, 0), sensor['temperature_mc']/1000)
    return dict(samples=len(selected), scope='whole model session including startup',
        thermal_peaks_c=temperatures,
        sampled_gpu_clock_mhz=dict(min=min(clocks), max=max(clocks)) if clocks else None,
        memory=dict(min_available_bytes=min(memory(r)['MemAvailable'] for r in selected),
            max_anonymous_bytes=max(memory(r)['AnonPages'] for r in selected),
            max_cached_bytes=max(memory(r)['Cached'] for r in selected),
            first_cached_bytes=memory(selected[0])['Cached'],
            last_cached_bytes=memory(selected[-1])['Cached']) if selected else None,
        limitation='System memory includes the loaded model and prior reclaimable cache; '
                   'it does not isolate the reader. Runner /proc counters describe the '
                   'session controller, not the GPU server, and are not server I/O evidence.')


def main():
    spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
    curve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(curve)
    plan_path = ROOT/('config/'+PREFIX+'-plan.json')
    release_path = ROOT/('config/'+PREFIX+'-window-release.json')
    plan, release = read(plan_path), read(release_path)
    assert release['state'] == 'Q2_PLE_ROW_BYTES_WINDOW_RELEASED'
    assert not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members']
    assert release['plan_sha256'] == sha(plan_path)
    directory = ROOT/'evidence'/plan['arms'][0]['label']
    result, transport = curve.artifact_integrity(directory)
    assert result['mode'] == transport['mode'] == 'q2-prefill-ple-row-bytes'
    assert result['finished_at'] and result['model_access'] and transport['exit_code'] == 0
    assert all(c['exit_code'] == 0 for c in result['commands'])
    assert result['binary_sha256'] == result['binary_sha256_after']
    assert result['models_before'] == result['models_after']
    assert result['native_bench_reused'] and result['mmq_reuse']['unchanged_after']
    assert result['mmq_reuse']['controls_rebuilt_or_rerun'] is False
    session = read(directory/'results/curve-session.json')
    assert session['client_exit_code'] == session['server_exit_code'] == 0
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
    command = result['commands'][-1]
    report = dict(schema='synapse-lie.'+PREFIX+'-results.v1',
        plan_sha256=sha(plan_path), release_sha256=sha(release_path),
        result_sha256=sha(directory/'results/result.json'), samples_sha256=sha(candidate_path),
        server_binary_sha256=result['binary_sha256'],
        reference_samples_sha256=sha(reference_path), commands=[c['exit_code'] for c in result['commands']],
        launcher_exit_code=transport['exit_code'], verified_artifacts=len(result['artifacts']),
        validation=validation, rows=rows, quality=quality,
        all_streamed_replies_exact=all(q['streamed_pieces_and_reply_exact'] for q in quality),
        telemetry=telemetry(directory, command['started_at'], command['finished_at']),
        native_client_reused=True, retained_mmq_reused=True, controls_rebuilt_or_rerun=False,
        reactive_changed=False, public_ABI_or_state_changed=False, promoted=False,
        limits='One observation per original prefix, same original preparation/history through32K. '
               'Saved control is not contemporaneous. Eight decode calls do not establish TG128. '
               'Greedy reply agreement is not an independent model-quality assessment. '
               'Buffered page-cache behavior differs intentionally; no memory-isolated speedup claim. '
               'The full128K goal is not established by this32K candidate.')
    with (ROOT/('config/'+PREFIX+'-results.json')).open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k in
                     ('commands','verified_artifacts','rows','all_streamed_replies_exact','telemetry')}, indent=2))


if __name__ == '__main__':
    main()
