#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attribute completed original-128K calls; never publish profiled throughput."""

from bisect import bisect_left
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'evidence/q2-native128-profile-r1'
TRACE = BASE / 'results/profile'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def union_ns(intervals):
    total, end = 0, 0
    for low, high in sorted(intervals):
        assert high >= low
        total += max(0, high - max(end, low))
        end = max(end, high)
    return total


def family(name):
    name = name.replace('::(anonymous namespace)::', '::')
    return re.split(r'[<(]', name, maxsplit=1)[0].rsplit('::', 1)[-1].removeprefix('void ')


def group(name):
    f = family(name)
    if f == 'mul_mat_vec_q8':
        return 'Q8 matrix-vector projections'
    if f == 'DenseF16GEMMKernel':
        return 'Dense GEMM projections'
    if f in ('RoutedIq2FixedBoundsKernel', 'mul_mat_vec_q_moe'):
        return 'IQ2 expert gate/up'
    if f in ('RoutedQ2HalfStorageKernel', 'Q2DownRowsKernel'):
        return 'Q2 expert down'
    if f.startswith('Hc'):
        return 'HC mixing and normalization'
    if f in ('WmmaCausalAttentionKernel', 'AttentionKernel', 'AttentionReduceKernel'):
        return 'Attention'
    if f.startswith('Select'):
        return 'Attention selection'
    if f.startswith(('Gdn', 'SsmConv')):
        return 'GDN and SSM state'
    if f in ('SharedQ8PairKernel', 'W8A8BlockedWmmaGEMMKernel', 'WKQuantA8BlockedWmmaGEMMKernel'):
        return 'Other quantized GEMM projections'
    return 'Other kernels'


def load_csv(kind):
    path = TRACE / ('prefix128k_' + kind + '_trace.csv')
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in row:
            if key in ('Start_Timestamp', 'End_Timestamp', 'Correlation_Id',
                       'Thread_Id', 'Dispatch_Id', 'Grid_Size_X', 'Grid_Size_Y',
                       'Workgroup_Size_X', 'Workgroup_Size_Y'):
                row[key] = int(row[key])
        row['start'], row['end'] = row['Start_Timestamp'], row['End_Timestamp']
    rows.sort(key=lambda row: row['start'])
    durations = [row['end'] - row['start'] for row in rows]
    assert rows and min(durations) > 0
    assert all(row['Correlation_Id'] > 0 for row in rows)
    return rows, dict(records=len(rows), positive_durations=len(rows),
                      min_ns=min(durations), max_ns=max(durations), sha256=sha(path))


def rank(kernels, divisor=1):
    times, counts = Counter(), Counter()
    for row in kernels:
        name = row['Kernel_Name']
        times[name] += row['end'] - row['start']
        counts[name] += 1
    total = sum(times.values())
    return [dict(kernel=name, family=family(name), group=group(name), calls=counts[name],
                 total_ms=ns/1e6, mean_per_forward_ms=ns/1e6/divisor,
                 percent_of_kernel_sum=100*ns/total)
            for name, ns in times.most_common()]


def main():
    inventory = read(BASE/'artifact-hashes.json')
    for name, digest in inventory.items():
        assert sha(BASE/name) == digest, name
    release = read(BASE/'release.json')
    closure_path = ROOT/'evidence/q2-native128-profile-preparation/independent-closure.json'
    closure = read(closure_path)
    assert closure['release_sha256'] == sha(BASE/'release.json')
    assert closure['registry_matches'] and closure['all_identities_and_groups_retired']
    assert closure['kfd_empty'] and closure['unchanged_free_leases'] == 5
    assert release['state'] == 'Q2_NATIVE128_PROFILE_RELEASED' and not release['gpu_reserved']
    command_exits = {mode: read(BASE/(mode+'-command.json'))['exit_code']
                     for mode in ('cpu-test', 'verify', 'admit', 'run', 'release')}
    assert set(command_exits.values()) == {0}
    spec = importlib.util.spec_from_file_location('window', ROOT/'tools/q2-native128-profile-window.py')
    window = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(window)
    cases = [json.loads(line) for line in (BASE/'requests.jsonl').read_text().splitlines()]
    observed = window.validate_output(BASE/'results/00-profile.jsonl', cases)
    reference_paths = [ROOT/'evidence/q2-full-prefill128-final-r1/results/full-prefill.jsonl',
                       ROOT/'evidence/q2-decode-down-rows-native128-r3/results/00-down-rows.jsonl']
    for path in reference_paths:
        assert observed['outputs'] == window.validate_output(path, cases)['outputs']
    kernels, kernel_validation = load_csv('kernel')
    copies, copy_validation = load_csv('memory_copy')
    apis, api_validation = load_csv('hip_api')
    by_correlation = {row['Correlation_Id']: row for row in apis}
    assert len(by_correlation) == len(apis)
    database = TRACE/'prefix128k_results.db'
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True) as db:
        assert db.execute('PRAGMA quick_check').fetchall() == [('ok',)]
        expected = sorted((r['Dispatch_Id'], r['start'], r['end']) for r in kernels)
        assert expected == sorted(db.execute('SELECT dispatch_id,start,end FROM rocpd_kernel_dispatch'))
        assert Counter((r['start'], r['end']) for r in copies) == Counter(
            db.execute('SELECT start,end FROM rocpd_memory_copy'))
        assert Counter((r['start'], r['end']) for r in apis) == Counter(
            db.execute('SELECT start,end FROM rocpd_region'))
    embeds = [row for row in kernels if family(row['Kernel_Name']) == 'EmbedKernel']
    preparation = [13, 1, 2048, 1465, 1, 2048, 7] + [1]*16
    expected_tokens = preparation + [2048]*63 + [1901] + [1]*8
    assert [r['Grid_Size_X']//r['Workgroup_Size_X'] for r in embeds] == expected_tokens
    cpu_by_thread = defaultdict(list)
    for row in apis:
        cpu_by_thread[row['Thread_Id']].append(row)
    cpu_starts = {tid: [r['start'] for r in rows] for tid, rows in cpu_by_thread.items()}
    kernel_starts = [r['start'] for r in kernels]
    copy_starts = [r['start'] for r in copies]
    phases = dict(prefill=[], decode=[])
    selected_kernels = dict(prefill=[], decode=[])
    q8_shapes = defaultdict(lambda: dict(calls=0, total_ns=0))
    position = 0
    for index in range(len(preparation), len(embeds)):
        embed = embeds[index]
        api = by_correlation[embed['Correlation_Id']]
        assert api['Function'] in ('hipLaunchKernel', 'hipGraphLaunch')
        low, tid = api['start'], api['Thread_Id']
        high = by_correlation[embeds[index+1]['Correlation_Id']]['start'] if index+1 < len(embeds) else max(r['end'] for r in apis)
        rows, starts = cpu_by_thread[tid], cpu_starts[tid]
        cpu = rows[bisect_left(starts, low):bisect_left(starts, high)]
        phase = 'prefill' if index < len(preparation)+64 else 'decode'
        waits = [r for r in cpu if r['Function'] == 'hipEventSynchronize']
        assert len(waits) == (48 if phase == 'prefill' else 0)
        completed = next(r for r in cpu if r['Function'] == 'hipStreamSynchronize' and
                         r['start'] >= (waits[-1]['end'] if waits else low))
        end = completed['end']
        ks = kernels[bisect_left(kernel_starts, low):bisect_left(kernel_starts, end)]
        cs = copies[bisect_left(copy_starts, low):bisect_left(copy_starts, end)]
        assert ks and all(r['end'] <= end for r in [*ks, *cs])
        assert sum(family(r['Kernel_Name']) == 'EmbedKernel' for r in ks) == 1
        if phase == 'prefill':
            assert sum(family(r['Kernel_Name']) == 'WmmaCausalAttentionKernel' for r in ks) == 12
            assert sum(family(r['Kernel_Name']) == 'RoutedIq2FixedBoundsKernel' for r in ks) == 96
        else:
            assert sum(family(r['Kernel_Name']) == 'Q2DownRowsKernel' for r in ks) == 48
            for r in ks:
                if family(r['Kernel_Name']) == 'mul_mat_vec_q8':
                    key = (r['Kernel_Name'], r['Grid_Size_X'], r['Grid_Size_Y'], r['Workgroup_Size_X'], r['Workgroup_Size_Y'])
                    q8_shapes[key]['calls'] += 1
                    q8_shapes[key]['total_ns'] += r['end']-r['start']
        groups, families = Counter(), Counter()
        for r in ks:
            groups[group(r['Kernel_Name'])] += r['end']-r['start']
            families[family(r['Kernel_Name'])] += r['end']-r['start']
        ki, ci = [(r['start'], r['end']) for r in ks], [(r['start'], r['end']) for r in cs]
        busy = union_ns(ki+ci)
        phases[phase].append(dict(index=len(phases[phase]), tokens=expected_tokens[index],
            start_position=position, host_start_ns=low, host_end_ns=end,
            completion_ms=(end-low)/1e6, kernel_sum_ms=sum(groups.values())/1e6,
            copy_sum_ms=sum(b-a for a,b in ci)/1e6, kernel_union_ms=union_ns(ki)/1e6,
            copy_union_ms=union_ns(ci)/1e6, traced_busy_union_ms=busy/1e6,
            not_covered_by_traced_kernels_or_copies_ms=(end-low-busy)/1e6,
            next_submit_gap_ms=(high-end)/1e6 if index+1 < len(embeds) else None,
            kernel_count=len(ks), copy_count=len(cs),
            groups_ms={k:v/1e6 for k,v in groups.items()},
            families_ms={k:v/1e6 for k,v in families.items()}))
        selected_kernels[phase].extend(ks)
        position += expected_tokens[index]
    summaries = {}
    for phase, rows in phases.items():
        groups = Counter()
        for row in rows:
            groups.update(row['groups_ms'])
        summaries[phase] = dict(calls=len(rows), tokens=sum(r['tokens'] for r in rows),
            groups_total_ms=dict(groups.most_common()), kernel_ranking=rank(selected_kernels[phase], len(rows)),
            **{key:sum(r[key] for r in rows) for key in ('completion_ms','kernel_sum_ms','copy_sum_ms',
                'kernel_union_ms','copy_union_ms','traced_busy_union_ms',
                'not_covered_by_traced_kernels_or_copies_ms','kernel_count','copy_count')})
    quartiles = []
    for offset in (0, 16, 32, 48):
        rows = phases['prefill'][offset:offset+16]
        groups = Counter()
        for row in rows:
            groups.update(row['groups_ms'])
        quartiles.append(dict(chunks=[offset,offset+15], tokens=sum(r['tokens'] for r in rows),
            mean_completion_ms=sum(r['completion_ms'] for r in rows)/16,
            mean_groups_ms={k:v/16 for k,v in groups.items()}))
    runner = read(BASE/'results/native-result.json')['arms'][0]
    result = dict(schema='synapse-lie.q2-native128-gpu-attribution.v1',
        plan_sha256=sha(BASE/'plan.json'), database_sha256=sha(database),
        release_sha256=sha(BASE/'release.json'), release_at=release['at'], closure=closure,
        command_exits=command_exits, server_exit_code=runner['server_exit_code'],
        client_exit_code=runner['client_exit_code'], clean_server_shutdown=runner['clean_server_shutdown'],
        trace_validation=dict(kernel=kernel_validation, copy=copy_validation, hip_api=api_validation,
            database_quick_check='ok', csv_rocpd_all_timestamps_exact=True),
        original_request_sequence_exact=True, original_and_R3_outputs_exact=True,
        original_cache_tokens=0, matched_embeddings=len(embeds), profile_only=True, headline_eligible=False,
        scope='GPU attribution inside each completed forward. Loading, preparatory requests, between-call gaps and post-forward KV captures are excluded. Kernel sums can overlap; union metrics account for overlap. Uncovered time is not a hardware idle counter. Instrumented rates never replace the unprofiled reference.',
        instrumented_server_ms=dict(prefill=observed['prefill_ms'], decode=observed['decode_ms']),
        summaries=summaries, prefill=phases['prefill'], decode=phases['decode'], quartiles=quartiles,
        decode_q8_geometries=[dict(kernel=k[0], grid=[k[1],k[2]], workgroup=[k[3],k[4]],
            calls=v['calls'], total_ms=v['total_ns']/1e6, mean_per_forward_ms=v['total_ns']/8e6)
            for k,v in sorted(q8_shapes.items(), key=lambda item:-item[1]['total_ns'])])
    output = ROOT/'config/q2-native128-profile-results.json'
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    csv_path = ROOT/'docs/figures/q2-native128-profile-kernels.csv'
    with csv_path.open('w', newline='') as stream:
        fields = ['phase', 'kernel', 'family', 'group', 'calls', 'total_ms', 'mean_per_forward_ms', 'percent_of_kernel_sum']
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        for phase, summary in summaries.items():
            writer.writerows(dict(phase=phase, **row) for row in summary['kernel_ranking'])
    print(json.dumps(dict(server_exit_code=runner['server_exit_code'], summaries={phase:{k:v for k,v in value.items() if k!='kernel_ranking'} for phase,value in summaries.items()}, quartiles=quartiles, decode_q8_geometries=result['decode_q8_geometries']), indent=2))


if __name__ == '__main__':
    main()
