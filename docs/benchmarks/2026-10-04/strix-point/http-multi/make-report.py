#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify archived Point HTTP runs and rebuild native tables and charts offline."""

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SEAL_SPEC = importlib.util.spec_from_file_location('point_http_seal', HERE/'seal-data.py')
SEAL = importlib.util.module_from_spec(SEAL_SPEC)
SEAL_SPEC.loader.exec_module(SEAL)
CASES = (('ar', 'prose'), ('mtp', 'prose'), ('mtp', 'repetition'))
LEVELS = (1, 2, 4, 6, 8)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def extract_and_verify(destination):
    manifest = json.loads((HERE/'data/inventory.json').read_text())
    if manifest.get('schema') != 'synapse-lie.point-http-archive.v1':
        raise ValueError('Archive inventory schema drift')
    expected = {'fixed8': SEAL.FIXED, 'fresh': SEAL.FRESH, 'history': SEAL.HISTORY}
    hashes = dict(line.split('  ', 1) for line in (HERE/'data/archives.sha256').read_text().splitlines())
    if set(hashes.values()) != {name+'.tar.gz' for name in expected}:
        raise ValueError('Archive hash list drift')
    count = 0
    for group, labels in expected.items():
        name = group+'.tar.gz'
        archive = HERE/'data'/name
        info = manifest['groups'][name]
        if (sha(archive) != info['sha256'] or info['sha256'] not in hashes or
                hashes[info['sha256']] != name or archive.stat().st_size != info['bytes'] or
                set(info['runs']) != set(labels)):
            raise ValueError('Archive identity drift: '+name)
        with tarfile.open(archive, mode='r:gz') as stream:
            for member in stream:
                parts = Path(member.name).parts
                if (not member.isfile() or len(parts) != 3 or parts[0] != 'evidence' or
                        parts[1] not in labels or parts[2] in ('', '.', '..')):
                    raise ValueError('Unsafe archive member: '+member.name)
                target = destination/member.name
                if target.exists():
                    raise ValueError('Duplicate archive member: '+member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(member) as source, target.open('xb') as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
                count += 1
        for label in labels:
            root = destination/'evidence'/label
            record = json.loads((root/'collection.json').read_text())
            inventory = record['inventory']
            sealed = info['runs'][label]
            if (sha(root/'collection.json') != sealed['collection_sha256'] or
                    len(inventory['files']) != sealed['remote_files'] or
                    inventory.get('result_exit_code') != sealed['exit_code'] or
                    record.get('exit_code') != 0 or
                    inventory.get('service_exit') != 0 or
                    not inventory.get('lease_free') or
                    not inventory.get('supervisor_absent') or
                    not inventory.get('gpu_child_absent') or
                    not inventory.get('owned_child_absent') or
                    'ActiveState=active' not in inventory.get('service', '')):
                raise ValueError('Collected run drift: '+label)
            for relative, file_info in inventory['files'].items():
                path = root/relative
                if (not path.is_file() or path.stat().st_size != file_info['bytes'] or
                        sha(path) != file_info['sha256']):
                    raise ValueError('Collected file drift: '+label+'/'+relative)
            if sealed['exit_code'] == 0:
                result = json.loads((root/'result.json').read_text())
                if (inventory.get('result_state') != 'PASSED' or
                        inventory.get('child_exit_code') != 0 or
                        (group != 'history' and inventory.get('model_stat_unchanged') is not True) or
                        result.get('state') != 'PASSED' or result.get('exit_code') != 0):
                    raise ValueError('Incomplete successful run: '+label)
    return manifest, count


def native(bench, primary, reference, output, label='LIE', reference_label='Gufo'):
    command = [str(bench), '--suite', 'report', str(primary), '--label', label,
               '--compare', str(reference), '--reference-label', reference_label,
               '--output', str(output)]
    subprocess.run(command, check=True)
    result = json.loads((output/'summary.json').read_text())
    if (not result.get('comparison') or
            not all(row.get('eligible') and row.get('output_equal')
                    for row in result['comparison'])):
        raise ValueError('Native comparison did not establish exact complete output')
    return result


def merge(evidence, output, mode, case, impl):
    path = output/'merged'/f'{mode}-{case}-{impl}.jsonl'
    subprocess.run(['python3', '-B', str(ROOT/'tools/strix-point-http-merge-fresh.py'),
                    '--evidence-root', str(evidence), '--mode', mode,
                    '--case', case, '--impl', impl, '--output', str(path)],
                   check=True, stdout=subprocess.DEVNULL)
    return path


def select_level(source, destination, level):
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    cohorts = [row for row in rows if row.get('event') == 'cohort' and row['users'] == level]
    if (rows[0].get('event') != 'identity' or
            rows[-1] != {'event': 'complete', 'exit_code': 0} or
            len(cohorts) != 4 or
            [(row['rep'], row['warmup']) for row in cohorts] !=
            [(0, True), (1, False), (2, False), (3, False)]):
        raise ValueError('Cannot isolate complete native user level')
    identity = rows[0].copy()
    identity['users'] = [level]
    destination.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                   for row in [identity, *cohorts, rows[-1]]))
    return destination


def files_for(evidence, protocol, mode, case, impl, level):
    if protocol == 'fresh':
        label = f'point-http-fresh-r7-{mode}-{case}-c{level}-{impl}'
    elif mode == 'ar' and case == 'repetition':
        label = f'point-http-multi-r7-{impl}-ar-repetition-c1'
    else:
        label = f'point-http-multi-r6-{impl}-{mode}-{case}-full'
    return evidence/label


def warmup_and_drafts(path, level, mode, impl):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    cohorts = [row for row in rows if row.get('event') == 'cohort' and row['users'] == level]
    if (len(cohorts) != 4 or not cohorts[0]['warmup'] or
            any(row['warmup'] for row in cohorts[1:])):
        raise ValueError('Incomplete warmup or measured cohorts: '+str(path))
    tokens = milliseconds = proposed = accepted = output_tokens = 0
    for request in cohorts[0]['preparations']:
        if impl == 'lie':
            timing = request['server_timings']
            tokens += timing['prefill_tokens']
            milliseconds += timing['prefill_ms']
        else:
            timing = request['usage']['gufo']
            tokens += timing['prefill_tokens']
            milliseconds += timing['prefill_ms']
    for cohort in cohorts[1:]:
        for request in cohort['requests']:
            if impl == 'lie':
                timing = request['server_timings']
                proposed += timing['mtp_drafted_tokens']
                accepted += timing['mtp_accepted_tokens']
            else:
                timing = request['usage']
                proposed += timing['draft_tokens']
                accepted += timing['draft_tokens_accepted']
            output_tokens += request['output_tokens']
    if mode == 'ar' and (proposed or accepted):
        raise ValueError('AR unexpectedly used speculative drafts')
    return {'warmup_executed_prefill_tokens': tokens,
            'warmup_executed_pp_tps': tokens * 1000 / milliseconds if tokens and milliseconds else None,
            'draft_proposed': proposed, 'draft_accepted': accepted,
            'measured_output_tokens': output_tokens}


def resources(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows:
        raise ValueError('Missing thermal telemetry')
    result = {name: max(sensor['value_c'] for row in rows
                        for sensor in row['temperatures'] if sensor['name'] == name)
              for name in ('k10temp', 'amdgpu', 'nvme')}
    result['gtt_used_bytes'] = max(row['gpu']['mem_info_gtt_used'] for row in rows)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New output directory')
    parser.add_argument('--bench-binary', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to replace report')
    bench = args.bench_binary.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='lie-point-http-') as temporary:
        extracted = Path(temporary)
        inventory, archived_files = extract_and_verify(extracted)
        evidence = extracted/'evidence'
        output = args.output.absolute()
        output.mkdir(parents=True)
        (output/'merged').mkdir()
        reports = {}
        source = {}
        for protocol in ('fixed8', 'fresh'):
            for mode, case in CASES:
                key = f'{protocol}-{mode}-{case}'
                if protocol == 'fixed8':
                    primary = files_for(evidence, protocol, mode, case, 'lie', 1)/'measurements.jsonl'
                    reference = files_for(evidence, protocol, mode, case, 'gufo', 1)/'measurements.jsonl'
                else:
                    primary = merge(evidence, output, mode, case, 'lie')
                    reference = merge(evidence, output, mode, case, 'gufo')
                reports[key] = native(bench, primary, reference, output/key)
                source[key] = {'lie': str(primary), 'gufo': str(reference)}
            for impl in ('lie', 'gufo'):
                key = f'{protocol}-mtp-vs-ar-prose-{impl}'
                mtp = Path(source[f'{protocol}-mtp-prose'][impl])
                ar = Path(source[f'{protocol}-ar-prose'][impl])
                reports[key] = native(bench, mtp, ar, output/key,
                                      impl.upper()+'-MTP', impl.upper()+'-AR')
                key = f'{protocol}-mtp-vs-ar-repetition-c1-{impl}'
                mtp = files_for(evidence, protocol, 'mtp', 'repetition', impl, 1)/'measurements.jsonl'
                ar = files_for(evidence, protocol, 'ar', 'repetition', impl, 1)/'measurements.jsonl'
                if protocol == 'fixed8':
                    mtp = select_level(mtp, output/'merged'/f'{protocol}-mtp-repetition-c1-{impl}.jsonl', 1)
                reports[key] = native(bench, mtp, ar, output/key,
                                      impl.upper()+'-MTP', impl.upper()+'-AR')
            key = f'{protocol}-ar-repetition-c1'
            ar_lie = files_for(evidence, protocol, 'ar', 'repetition', 'lie', 1)/'measurements.jsonl'
            ar_gufo = files_for(evidence, protocol, 'ar', 'repetition', 'gufo', 1)/'measurements.jsonl'
            reports[key] = native(bench, ar_lie, ar_gufo, output/key)
        rows = []
        for protocol in ('fixed8', 'fresh'):
            for mode, case in CASES + (('ar', 'repetition'),):
                key = f'{protocol}-{mode}-{case}' + ('-c1' if case == 'repetition' and mode == 'ar' else '')
                report = reports[key]
                for lie, gufo, comparison in zip(report['primary']['configurations'],
                                                 report['reference']['configurations'],
                                                 report['comparison'], strict=True):
                    level = lie['users']
                    if level != gufo['users'] or level != comparison['users']:
                        raise ValueError('Mispaired configuration in native report')
                    row = {'protocol': protocol, 'mode': mode, 'case': case, 'users': level,
                           'output_equal': comparison['output_equal'],
                           'eligible': comparison['eligible'],
                           'lie_over_gufo_decode_ratio': comparison['sum_request_decode_ratio']}
                    for impl, configuration in (('lie', lie), ('gufo', gufo)):
                        run = files_for(evidence, protocol, mode, case, impl, level)
                        extra = warmup_and_drafts(run/'measurements.jsonl', level, mode, impl)
                        peaks = resources(run/'telemetry.jsonl')
                        row.update({impl+'_decode_median_tps': configuration['sum_request_decode_tps']['median'],
                                    impl+'_decode_min_tps': configuration['sum_request_decode_tps']['min'],
                                    impl+'_decode_max_tps': configuration['sum_request_decode_tps']['max'],
                                    impl+'_wall_median_tps': configuration['aggregate_output_tps']['median'],
                                    impl+'_first_output_median_s': configuration['first_output_seconds']['median'],
                                    impl+'_measured_pp_median_tps': (
                                        configuration['executed_preparation_pp_tps']['median']
                                        if isinstance(configuration['executed_preparation_pp_tps'], dict)
                                        else None)})
                        row.update({impl+'_'+name: value for name, value in extra.items()})
                        row.update({impl+'_peak_'+name+'_c': peaks[name]
                                    for name in ('k10temp', 'amdgpu', 'nvme')})
                        row[impl+'_peak_gtt_used_bytes'] = peaks['gtt_used_bytes']
                    rows.append(row)
        with (output/'summary.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        summary = {'schema': 'synapse-lie.point-http-comparison-report.v1',
                   'source_commit': '128f490cfff9713f84f658ad17118272a1cd4ad7',
                   'fresh_windows': len(SEAL.FRESH), 'fixed_windows': len(SEAL.FIXED),
                   'archived_remote_files': sum(run['remote_files']
                                                for group in inventory['groups'].values()
                                                for run in group['runs'].values()),
                   'archived_files': archived_files,
                   'archive_sha256': {name: value['sha256']
                                      for name, value in inventory['groups'].items()},
                   'rows': rows,
                   'quality': {key: report['comparison'] for key, report in reports.items()}}
        (output/'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        (output/'verification.json').write_text(json.dumps({
            'schema': 'synapse-lie.point-http-report-verification.v1',
            'archive_sha256': summary['archive_sha256'],
            'archived_files': archived_files,
            'successful_windows': len(SEAL.FIXED) + len(SEAL.FRESH) + 1,
            'retained_failed_windows': 2,
            'native_comparisons': len(reports),
            'all_output_equal_and_eligible': all(row['output_equal'] and row['eligible']
                                                 for row in rows)}, indent=2) + '\n')
        print(json.dumps({'rows': len(rows), 'native_comparisons': len(reports),
                          'archived_files': archived_files}, sort_keys=True))


if __name__ == '__main__':
    main()
