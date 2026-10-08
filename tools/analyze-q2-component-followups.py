#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit saved vector-conversion and scaled-tile component evidence."""
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('component', ROOT / 'tools/analyze-q2-hc-input.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
require = common.require


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(label, variant, exit_code, fixtures):
    path = ROOT / 'evidence' / label
    root, result, events = common.read(path)
    transport = json.loads((path / 'transport.json').read_text())
    collection = json.loads((path / 'collection.json').read_text())
    require(result['mode'] == variant + '-check' and not result['model_access'], 'Wrong scope')
    require(transport['source_variant'] == variant and transport['exit_code'] == exit_code,
            'Source/transport mismatch')
    require([c['exit_code'] for c in result['commands']] == [0, 0, exit_code], 'Changed exits')
    require(result['state'] == ('FAILED' if exit_code else 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED'),
            'Changed runtime verdict')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4
            and not result['preflight_kfd'] and not result['postflight_kfd'], 'Unresolved admission')
    require(collection['verified_artifacts'] == len(result['artifacts']), 'Artifact count differs')
    require(digest(path / 'source.tar.gz') == transport['capsule_sha256'], 'Capsule changed')
    require(digest(path / 'results.tar.gz') == collection['sha256'], 'Results archive changed')
    source = ROOT / transport['source_path']
    source_files = [p for p in source.rglob('*') if p.is_file()]
    with tarfile.open(path / 'source.tar.gz') as capsule:
        for local, member in [(ROOT / f, f) for f in fixtures] + [
                (p, 'source/' + str(p.relative_to(source))) for p in source_files]:
            require(hashlib.sha256(capsule.extractfile(member).read()).hexdigest() == digest(local),
                    'Frozen source differs: ' + member)
    temperatures = {}
    for line in (root / 'telemetry.jsonl').read_text().splitlines():
        sensors = json.loads(line)['thermal']
        require({s['device'] for s in sensors} == {'amdgpu', 'k10temp'}, 'Sensor coverage differs')
        for s in sensors:
            require(not s['over_limit'], 'Thermal failure')
            temperatures[s['device']] = max(temperatures.get(s['device'], -273), s['temperature_mc'] / 1000)
    meta = dict(label=label, state=result['state'], command_exits=[0, 0, exit_code],
                source_variant=variant, source_files_verified=len(source_files),
                source_capsule_sha256=transport['capsule_sha256'], binary_sha256=result['binary_sha256'],
                artifacts_verified=len(result['artifacts']), archive_sha256=collection['sha256'],
                temperature_max_c=temperatures, model_access=False, promoted=False,
                fixture_sha256={f:digest(ROOT / f) for f in fixtures})
    return root, events, meta


def paired(rows, candidate, field):
    arms = []
    for wanted in (False, True):
        chosen = [r for r in rows if candidate(r) == wanted]
        require([r['rep'] for r in chosen] == list(range(5)), 'Missing/duplicate paired sample')
        require(all(r['launches'] == 8 for r in chosen), 'Timing scope differs')
        arms.append(common.stats([r[field] for r in chosen]))
    reference, changed = arms
    changes = [100 * (b/a-1) for a, b in zip(reference['samples'], changed['samples'])]
    return dict(reference=reference, candidate=changed,
                time_change_percent=100*(changed['median']/reference['median']-1),
                paired_time_change_percent=changes, median_paired_time_change_percent=statistics.median(changes),
                ranges_overlap=max(reference['min'], changed['min']) <= min(reference['max'], changed['max']))


def narrow():
    root, events, out = load('q2-narrow-vector-r1', 'narrow-vector', 0,
                            ['tests/q2_narrow_vector.cpp', 'cmake/hip/CMakeLists.txt'])
    cases = [e for e in events if e['event'] == 'narrow_conversion']
    summaries = [e for e in events if e['event'] == 'narrow_summary']
    require(summaries == [dict(event='narrow_summary', conversion_cases=192,
                              special_input_values=321536, consumer_shapes=2)], 'Incomplete summary')
    require(len(cases) == 192 and len({(e['count'], e['input_offset'], e['output_offset']) for e in cases}) == 192
            and all(e['exact'] and e['independent_oracle'] for e in cases), 'Conversion failure')
    checks = [e for e in events if e['event'] == 'narrow_consumer_check']
    require([(e['m'], e['k'], e['exact_values']) for e in checks] ==
            [(320, 10240, 2621440), (513, 2560, 4202496)], 'Consumer coverage differs')
    require(all(e['n'] == 2048 and e['copies'] == 4 and e['oracle_samples'] == 128 and
                0 <= e['relative_rms'] <= 2e-5 and 0 <= e['error_over_peak'] <= 2e-5 for e in checks),
            'Consumer oracle failed')
    timings = [e for e in events if e['event'] == 'narrow_timing']
    require(len(timings) == 40, 'Missing conversion timing')
    cohorts = []
    for m, k in ((320, 10240), (513, 2560)):
        for scope in ('conversion_only', 'conversion_and_consumer'):
            rows = [e for e in timings if (e['m'], e['k'], e['scope']) == (m, k, scope)]
            require(all(e['n'] == 2048 and e['copies'] == 4 and e['activation_bytes'] > 32*1024**2
                        for e in rows), 'Memory rotation differs')
            cohorts.append(dict(m=m, k=k, scope=scope, **paired(rows, lambda e:e['vector'], 'us_per_cycle')))
    out.update(summary=summaries[0], checks=checks, cohorts=cohorts, numerical_component_pass=True,
               decision='No model dispatch: full consumer samples overlap and paired changes have mixed signs.')
    return out


def tiles():
    root, events, out = load('q2-scaled-tiles-r1', 'scaled-tiles', 1,
                            ['tests/q2_scaled_tiles.cpp', 'tests/q2_scaled_fixture.hpp',
                             'tests/q2_routed.cpp', 'tests/q2_packed_bench.cpp', 'cmake/hip/CMakeLists.txt'])
    text = (root / '03.log').read_text()
    expected = {f'n{n}-m129-tile48-shift0-{kind}' for n in (17,63,64,65,127,128,129,257)
                for kind in ('normal','tiny')}
    errors = {m[1]:dict(relative_rms=float(m[2]), error_over_peak=float(m[3])) for m in
              re.finditer(r'^scaled (\S+) rrms=(\S+) scaled_max=(\S+)$', text, re.M)}
    require(set(errors) == {s+t for s in expected for t in ('-ref48','-wide64','-wide128')},
            'Missing original-input numerical results')
    require(all(e['relative_rms'] > .002 or e['error_over_peak'] > .002 for e in errors.values())
            and text.count('NUMERICAL_FAILURE: independent operator tolerance exceeded') == 48,
            'Numerical rejection inventory changed')
    replays = [e for e in events if e['event'] == 'scaled_tile_operator_replay']
    require(len(replays) == 32 and {(e['label'], e['candidate_tile']) for e in replays} ==
            {(s,w) for s in expected for w in (64,128)}, 'Missing operator replay')
    for e in replays:
        a = (root / ('scaled-' + e['label'] + '-ref48.f32')).read_bytes()
        b = (root / ('scaled-' + e['label'] + '-wide' + str(e['candidate_tile']) + '.f32')).read_bytes()
        require(e['exact'] and a == b and len(a) == e['values']*4, 'Saved tile output differs')
    cohorts = []
    for e in events:
        if e['event'] == 'tile_geometry':
            cohorts.append(dict(geometry=e, timings=[]))
        elif e['event'] == 'tile_microbench':
            cohorts[-1]['timings'].append(e)
        elif e['event'] == 'tile_replay':
            cohorts[-1]['replay'] = e
    require([(c['geometry']['active_experts'],c['geometry']['candidate_tile']) for c in cohorts] ==
            [(a,w) for a in (512,128,64) for w in (64,128)], 'Incomplete timing cohorts')
    for c in cohorts:
        g, rows, r = c['geometry'], c['timings'], c['replay']
        require(g['active_weight_bytes'] > 32*1024**2 and g['tokens'] == 2048 and g['used'] == 10,
                'Changed benchmark shape')
        require(len(rows) == 10 and all(e['active_experts'] == g['active_experts'] and
                    e['tile'] in (48,g['candidate_tile']) and
                    bool(e['position'] ^ (e['rep'] & 1)) == (e['tile'] != 48) for e in rows),
                'Pair order/identity differs')
        require(r['exact'] and r['reference_sha256'] == r['candidate_sha256'] and
                r['values'] == 52428800 and r['independent_samples'] == 1024, 'Full shaped replay differs')
        samples = [json.loads(line) for line in (root / (
            f"packed-tiles-{g['candidate_tile']}-samples-{g['active_experts']}.jsonl")).read_text().splitlines()]
        require(len(samples) == 1024, 'Missing FP64 dot samples')
        error2 = sum((s['value']-s['reference'])**2 for s in samples)
        rrms = math.sqrt(error2 / max(sum(s['reference']**2 for s in samples),1e-30))
        peak = max(abs(s['value']-s['reference']) for s in samples) / max(max(abs(s['reference']) for s in samples),1e-20)
        require(math.isclose(rrms,r['relative_rms'],rel_tol=1e-9) and
                math.isclose(peak,r['error_over_peak'],rel_tol=1e-9) and rrms <= .002 and peak <= .002,
                'Independent shaped oracle differs')
        c.update(paired(rows, lambda e:e['tile'] != 48, 'us_per_launch'))
    summary = [e for e in events if e['event'] == 'scaled_tile_summary']
    require(summary == [dict(event='scaled_tile_summary',operator_cases=16,candidate_tiles=[64,128],
                            benchmark_cohorts=6,independent_failures=48,tile_mismatches=0,
                            benchmark_failures=0,packing_timed_in_both_arms=True)], 'Incomplete verdict')
    out.update(summary=summary[0], operator_errors=errors, operator_replays=replays, cohorts=cohorts,
               numerical_component_pass=False,
               decision='Reject universal tile64/128; only tile64 with 64 active experts improves. No model dispatch.')
    return out


def main():
    for name, report in [('narrow-vector', narrow()), ('scaled-tiles', tiles())]:
        report['scope'] = 'Synthetic component under fan82 policy; no model throughput or cooling speedup claim'
        output = ROOT / 'config' / ('q2-' + name + '-results')
        output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
        with output.with_suffix('.csv').open('w', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['cohort','arm','rep','microseconds_per_cycle'])
            for c in report['cohorts']:
                cohort = (f"m{c['m']}-k{c['k']}-{c['scope']}" if name == 'narrow-vector' else
                          f"active{c['geometry']['active_experts']}-tile{c['geometry']['candidate_tile']}")
                for arm in ('reference','candidate'):
                    for rep, value in enumerate(c[arm]['samples']):
                        writer.writerow([cohort,arm,rep,value])
        print(json.dumps(dict(experiment=name, artifacts=report['artifacts_verified'],
                             numerical_pass=report['numerical_component_pass'], promoted=False)))


if __name__ == '__main__':
    main()
