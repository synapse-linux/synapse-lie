#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the original64K/128K row-reader observations after window closure."""
import importlib.util
import json
from pathlib import Path
from q2_ple_row_bytes_model import inputs, sha, validate_result

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    curve=module('curve',ROOT/'tools/analyze-q2-curve.py')
    first=module('reader',ROOT/'tools/analyze-q2-ple-row-bytes.py')
    pp=ROOT/'config/q2-ple-row-bytes-long-plan.json'
    rp=ROOT/'config/q2-ple-row-bytes-long-window-release.json'
    plan,release=read(pp),read(rp)
    assert release['state']=='Q2_PLE_ROW_BYTES_LONG_WINDOW_RELEASED'
    assert not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members']
    assert release['plan_sha256']==sha(pp)
    saved_path=ROOT/'config/q2-full-prefill128-results.json'
    assert sha(saved_path)==plan['manifests'][str(saved_path.relative_to(ROOT))]
    saved=read(saved_path)
    bindings={65536:'q2-full-prefill64-recovery-r1',131072:'q2-full-prefill128-final-r1'}
    rows,cohorts=[],[]
    for arm in plan['arms']:
        depth=arm['depth']; directory=ROOT/'evidence'/arm['label']
        result,transport=curve.artifact_integrity(directory)
        assert result['mode']==transport['mode']=='q2-prefill-ple-row-bytes'
        assert result['finished_at'] and transport['exit_code']==0 and result['model_access']
        assert len(result['commands'])==4 and all(c['exit_code']==0 for c in result['commands'])
        assert result['binary_sha256']==result['binary_sha256_after']==read(ROOT/'config/q2-ple-row-bytes-binaries.json')['binary_sha256']
        assert result['models_before']==result['models_after']
        assert result['curve_server_reuse']['no_build'] and result['native_bench_reused']
        session=read(directory/'results/curve-session.json')
        assert session['client_exit_code']==session['server_exit_code']==0
        path=directory/'results/full-prefill.jsonl'
        validation=validate_result(ROOT,path,depth)
        current=[x for x in map(json.loads,path.read_text().splitlines()) if x['event']=='sample']
        binding=next(c for c in saved['cohorts'] if c['label']==bindings[depth])
        old_path=ROOT/'evidence'/binding['label']/'results/full-prefill.jsonl'
        assert sha(old_path)==binding['samples_sha256']
        old={e['case']:e for e in map(json.loads,old_path.read_text().splitlines()) if e['event']=='sample'}
        quality=[]
        for sample,(_,inp) in zip(current,inputs(ROOT,depth)):
            previous=old[sample['case']]
            assert sample['request']==previous['request']
            pieces=lambda r:[c['delta'] for chunk in r['response_chunks'] for c in chunk['choices']]
            exact=(sample['assistant']==previous['assistant'] and pieces(sample)==pieces(previous)
                   and sample['usage']==previous['usage'] and sample['finish_reason']==previous['finish_reason'])
            quality.append(dict(case=sample['case'],streamed_pieces_and_reply_exact=exact))
            if inp['phase']!='prefix':continue
            a,b=previous['server_timings'],sample['server_timings']
            tokens=inp['expected_prompt_tokens']
            assert a['decode_calls']==b['decode_calls']==b['decode_tokens']==8
            historical=next(row for row in saved['rows'] if row['depth']==depth)
            rows.append(dict(case=sample['case'],depth=depth,attempt=inp['attempt'],tokens=tokens,
                calls=b['prefill_calls'],full_chunks=tokens//2048,tail=tokens%2048,
                parent_pp=tokens*1000/a['prefill_ms'],candidate_pp=tokens*1000/b['prefill_ms'],
                pp_change_percent=(a['prefill_ms']/b['prefill_ms']-1)*100,
                parent_prefill_ms=a['prefill_ms'],candidate_prefill_ms=b['prefill_ms'],
                parent_tg=8000/a['decode_ms'],candidate_tg=8000/b['decode_ms'],
                tg_change_percent=(a['decode_ms']/b['decode_ms']-1)*100,
                parent_decode_ms=a['decode_ms'],candidate_decode_ms=b['decode_ms'],decode_calls=8,
                candidate_wall_seconds=sample['wall_seconds'],candidate_cache_capture_ms=b['cache_capture_ms'],
                cached_tokens=b['cached_tokens'],archived_ud_pp=historical['ud_prefill_tps'],reply_exact=exact))
        cmd=result['commands'][-1]
        cohorts.append(dict(label=arm['label'],result_sha256=sha(directory/'results/result.json'),
            samples_sha256=sha(path),reference_samples_sha256=sha(old_path),
            commands=[c['exit_code'] for c in result['commands']],artifacts=len(result['artifacts']),
            validation=validation,quality=quality,telemetry=first.telemetry(directory,cmd['started_at'],cmd['finished_at'])))
    report=dict(schema='synapse-lie.q2-ple-row-bytes-long-results.v1',plan_sha256=sha(pp),release_sha256=sha(rp),
        rows=rows,cohorts=cohorts,all_streamed_replies_exact=all(q['streamed_pieces_and_reply_exact'] for c in cohorts for q in c['quality']),
        controls_rebuilt_or_rerun=False,candidate_rebuilt=False,promoted=False,
        limits='Original single observations versus saved controls, cooled separate64K/128K sessions. '
               'Eight decode calls are not TG128. Greedy agreement is not independent task quality. '
               'No causal correction for temperature/clocks or page-cache residency.')
    with (ROOT/'config/q2-ple-row-bytes-long-results.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
