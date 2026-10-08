#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate exact fixed-input routes from the saved1585 executable, without timing claims."""
from collections import Counter
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('curve', ROOT/'tools/analyze-q2-curve.py')
curve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curve)
read, sha, require = curve.read, curve.sha, curve.require


def main():
    plan = read(ROOT/'config/q2-current-routing-v2-plan.json')
    for name, digest in {**plan['fixtures'], **plan['manifests']}.items():
        require(sha(ROOT/name) == digest, 'Frozen input changed: '+name)
    evidence = ROOT/'evidence/q2-current-routing-v2-r1'
    result, transport = curve.artifact_integrity(evidence)
    require(result['state'] == 'DIAGNOSTIC_ROUTING_COMPLETE_NOT_WALL_BENCHMARK' and
            result['mode'] == 'q2-current-routing' and transport['exit_code'] == 0 and
            len(result['commands']) == 2 and all(c['exit_code'] == 0 for c in result['commands']),
            'Routing collection incomplete')
    require(result['qualified_binary_replay']['build_commands'] == 0 and
            result['binary_sha256'] == result['binary_sha256_after'] == plan['binary_sha256'] and
            result['headline_eligible'] is False, 'Saved binary replay changed')
    directory = evidence/'results'
    capture = read(directory/'routing-capture.json')
    require(capture['state'] == 'COMPLETE' and capture['captures'] == 96 and
            capture['inferior_exit_codes'] == [0] and not capture['signals'] and not capture['errors'],
            'Debugger did not complete normally')
    rows = [json.loads(line) for line in (directory/'routing-counts.jsonl').read_text().splitlines()]
    require(len(rows) == 96, 'Incomplete routing rows')
    for index, row in enumerate(rows):
        counts = row['counts']
        require((row['index'], row['layer'], row['phase'], row['experts'], row['tokens'], row['used']) ==
                (index, index % 48, 'warm' if index < 48 else 'profile', 512, 2048, 10), 'Changed capture order')
        require(len(counts) == 512 and all(type(n) is int and 0 <= n <= 2048 for n in counts) and
                sum(counts) == 20480, 'Invalid expert distribution')
    require(all(a['counts'] == b['counts'] for a, b in zip(rows[:48], rows[48:])), 'Warm/profile routes differ')
    parent = ROOT/'evidence/q2-ssm-fixed-bounds-model-r1/results'
    require(sha(directory/'profile2048-input.i32') == plan['input_sha256'] == sha(parent/'pp2048-input.i32'),
            'Fixed prompt identity changed')
    comparisons = []
    for label in ('arithmetic', 'counting'):
        for suffix in ('input.i32', '0-prefill.f32', '0-last.f32', '0-output.u32'):
            name = label+'-'+suffix
            require((directory/name).read_bytes() == (parent/name).read_bytes(), 'Saved smoke changed: '+name)
            comparisons.append(name)
    for label in ('warm2048', 'profile2048'):
        require((directory/(label+'-0-prefill.f32')).read_bytes() ==
                (parent/'pp2048-0-prefill.f32').read_bytes(), 'Fixed-input logits changed')
        output = (directory/(label+'-0-output.u32')).read_bytes()
        require(len(output) == 64 and output == (parent/'pp2048-0-output.u32').read_bytes()[:64],
                'Saved first16 greedy tokens changed')
    for suffix in ('prefill.f32', 'last.f32', 'output.u32'):
        require((directory/('warm2048-0-'+suffix)).read_bytes() ==
                (directory/('profile2048-0-'+suffix)).read_bytes(), 'Warm/profile output changed')
    prior = read(ROOT/'config/q2-current-best-profile-results.json')['routing']['layers']
    histograms = {name: Counter() for name in ('wide128_live_rows', 'tail64_live_rows', 'down48_live_rows')}
    layers = []
    for row, old in zip(rows[48:], prior):
        counts = row['counts']
        wide, tail, down = [], [], []
        for n in counts:
            groups = (n+63)//64
            wide.extend(min(128, n-128*j) for j in range(groups//2))
            if groups % 2:
                tail.append(n-64*(groups-1))
            down.extend(min(48, n-48*j) for j in range((n+47)//48))
        require(sum(wide)+sum(tail) == sum(down) == 20480, 'Tile mapping loses routes')
        for key, values in zip(histograms, (wide, tail, down)):
            histograms[key].update(values)
        geometry = dict(iq2_128_tiles=len(wide), iq2_64_tiles=len(tail), q2_48_tiles=len(down))
        layers.append(dict(layer=row['layer'], active_experts=sum(n > 0 for n in counts),
            max_rows=max(counts), **geometry,
            previous1571_geometry_exact=all(geometry[k] == old[k] for k in geometry),
            tail_live16_fragments=dict(sorted(Counter((n+15)//16 for n in tail).items())),
            counts=counts))
    summaries = {}
    for key, hist in histograms.items():
        # Explicit capacity avoids drawing geometry from kernel-name conventions.
        capacity = {'wide128_live_rows':128, 'tail64_live_rows':64, 'down48_live_rows':48}[key]
        total = sum(hist.values())
        summaries[key] = dict(tiles=total, full_tiles=hist[capacity],
            live_rows=sum(n*v for n, v in hist.items()), allocated_rows=total*capacity,
            row_utilization=sum(n*v for n, v in hist.items())/(total*capacity),
            live16_fragments=dict(sorted(Counter({j:sum(v for n, v in hist.items() if (n+15)//16==j)
                for j in range(1, capacity//16+1)}).items())), histogram=dict(sorted(hist.items())))
    report = dict(schema='synapse-lie.q2-current-routing.v1',
        plan_sha256=sha(ROOT/'config/q2-current-routing-v2-plan.json'),
        result_sha256=sha(directory/'result.json'), archive_sha256=sha(evidence/'results.tar.gz'),
        binary_sha256=result['binary_sha256_after'], source_variant='ssm-fixed-bounds',
        input_sha256=plan['input_sha256'], warm_profile_counts_exact=True, captures=96,
        source_files_verified=result['qualified_binary_replay']['source_files_verified'],
        unchanged_libraries=len(result['runtime_libraries']), artifact_count=len(result['artifacts']),
        saved_smoke_exact=comparisons, prefill_full_logits_exact=True,
        first16_greedy_tokens_exact=True, warm_profile_full_outputs_exact=True,
        geometry_matches_saved1571=all(r['previous1571_geometry_exact'] for r in layers),
        summaries=summaries, layers=layers, headline_eligible=False, gpu_builds=0,
        performance_control_rerun=False, full_curve=False, goal_met=False,
        limits='Host breakpoint pauses the inferior; no collected timings establish throughput. '
            'Counts describe the exact fixed2048 input only. Saved1571 kernel times remain historical '
            'attribution, not timings of saved1585. No new kernel or performance improvement is tested.')
    with (ROOT/'config/q2-current-routing-v2-results.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k:report[k] for k in ('captures', 'geometry_matches_saved1571', 'summaries',
                                          'prefill_full_logits_exact', 'first16_greedy_tokens_exact')}))


if __name__ == '__main__':
    main()
