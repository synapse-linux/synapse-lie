#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit paired cold HTTP evidence and render a compact comparison report."""

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
SIZES = (8192, 32768, 131072, 258794)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_run(mode, size, impl, evidence):
    label = f'point-http-depth-r2-{mode}-p{size}-{impl}'
    path = evidence/label
    collection = json.loads((path/'collection.json').read_text())
    inventory = collection['inventory']
    if (collection['exit_code'] or inventory['result_state'] != 'PASSED' or
            inventory['result_exit_code'] != 0 or inventory['child_exit_code'] != 0 or
            not inventory['model_stat_unchanged'] or
            inventory['service_exit'] != 0 or
            'ActiveState=active' not in inventory['service'] or
            not all(inventory[k] for k in ('supervisor_absent', 'gpu_child_absent',
                                           'owned_child_absent', 'lease_free'))):
        raise ValueError(f'Incomplete remote closure: {label}')
    for name, witness in inventory['files'].items():
        if sha(path/name) != witness['sha256']:
            raise ValueError(f'Collected hash drift: {label}/{name}')
    supervisor = json.loads((path/'result.json').read_text())
    gate = json.loads((path/'http-depth-result.json').read_text())
    rows = [json.loads(line) for line in (path/'measurements.jsonl').read_text().splitlines()]
    if (supervisor['state'] != 'PASSED' or gate['state'] != 'PASSED' or
            gate['implementation'] != impl or gate['mode'] != mode or
            gate['size'] != size or gate['samples'] != 2 or
            gate['measurements_sha256'] != sha(path/'measurements.jsonl') or
            gate['requests_sha256'] != sha(path/'requests.jsonl') or
            rows[-1] != {'event': 'complete', 'exit_code': 0}):
        raise ValueError(f'Run result drift: {label}')
    samples = [row for row in rows if row.get('event') == 'sample']
    if len(samples) != 2:
        raise ValueError(f'Sample count drift: {label}')
    identity = rows[0]
    if (identity['cache_policy'] != 'off' or identity['context_capacity_declared'] != 262144 or
            identity['target_prompt_tokens'] != [size] or
            identity['request_options'] != ({'cache_prompt': False} if impl == 'gufo' else {})):
        raise ValueError(f'Cache/context policy drift: {label}')
    for row in samples:
        phase = row['server_timings'] if impl == 'lie' else row['usage']['gufo']
        if (row['cached_tokens'] != 0 or row['output_tokens'] != 128 or
                row['full_output_budget'] is not True or row['stream_complete'] is not True or
                phase['prefill_tokens'] != row['prompt_tokens'] or
                phase['prefill_ms'] <= 0 or phase['decode_ms'] <= 0):
            raise ValueError(f'Physical prefill/output drift: {label}')
    telemetry = [json.loads(line) for line in (path/'telemetry.jsonl').read_text().splitlines()]
    peaks = {'cpu_c': max(t['value_c'] for row in telemetry for t in row['temperatures']
                          if t['name'] == 'k10temp'),
             'gpu_c': max(t['value_c'] for row in telemetry for t in row['temperatures']
                          if t['name'] == 'amdgpu'),
             'nvme_c': max(t['value_c'] for row in telemetry for t in row['temperatures']
                           if t['name'] == 'nvme'),
             'gtt_bytes': max(row['gpu']['mem_info_gtt_used'] for row in telemetry)}
    return {'label': label, 'rows': rows, 'samples': samples,
            'manifest_sha256': sha(path/'manifest.json'),
            'measurements_sha256': sha(path/'measurements.jsonl'),
            'gate_sha256': sha(path/'http-depth-result.json'),
            'resource_peaks': peaks}


def normalized(request, impl):
    body = dict(request)
    if impl == 'gufo':
        if body.pop('cache_prompt', None) is not False:
            raise ValueError('Gufo cold-cache control absent')
    elif 'cache_prompt' in body:
        raise ValueError('Unexpected LIE cache request option')
    return body


def median(values):
    return round(statistics.median(values), 3)


def metrics(run, impl):
    samples = run['samples']
    phases = [row['server_timings'] if impl == 'lie' else row['usage']['gufo']
              for row in samples]
    drafted = [int(phase.get('mtp_drafted_tokens', row['usage'].get('draft_tokens', 0)))
               for row, phase in zip(samples, phases)]
    accepted = [int(phase.get('mtp_accepted_tokens', row['usage'].get('draft_tokens_accepted', 0)))
                for row, phase in zip(samples, phases)]
    return {'prompt_tokens': samples[0]['prompt_tokens'],
            'prefill_tps': median([1000*p['prefill_tokens']/p['prefill_ms'] for p in phases]),
            'prefill_ms': median([p['prefill_ms'] for p in phases]),
            'decode_tps': median([1000*r['output_tokens']/p['decode_ms']
                                  for r, p in zip(samples, phases)]),
            'decode_ms': median([p['decode_ms'] for p in phases]),
            'ttft_ms': median([r['first_output_ms'] for r in samples]),
            'wall_ms': median([r['wall_ms'] for r in samples]),
            'prefill_tps_samples': [round(1000*p['prefill_tokens']/p['prefill_ms'], 3)
                                    for p in phases],
            'decode_tps_samples': [round(1000*r['output_tokens']/p['decode_ms'], 3)
                                   for r, p in zip(samples, phases)],
            'mtp_drafted_tokens': drafted, 'mtp_accepted_tokens': accepted,
            'mtp_acceptance_rate': round(sum(accepted)/sum(drafted), 4) if sum(drafted) else None}


def svg(rows, field, title, target):
    width, height, left, right, top, bottom = 760, 400, 80, 30, 55, 65
    values = [row[impl][field] for row in rows for impl in ('lie', 'gufo')]
    limit = max(values)*1.15 if values else 1
    plot_w, plot_h = width-left-right, height-top-bottom
    colors = {'lie': '#2563eb', 'gufo': '#d97706'}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{left}" y="30" font-family="sans-serif" font-size="18">{html.escape(title)}</text>']
    for i in range(5):
        y = top+plot_h*(1-i/4)
        parts += [f'<line x1="{left}" x2="{width-right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#ddd"/>',
                  f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{limit*i/4:.0f}</text>']
    for n, row in enumerate(rows):
        x = left+(n+.5)*plot_w/len(rows)
        for impl, shift in (('lie', -12), ('gufo', 12)):
            value = row[impl][field]
            y = top+plot_h*(1-value/limit)
            parts.append(f'<circle cx="{x+shift:.1f}" cy="{y:.1f}" r="6" fill="{colors[impl]}"/>')
        label = {8192: '8K', 32768: '32K', 131072: '128K',
                 258794: '~256K'}[row['size']]
        parts.append(f'<text x="{x:.1f}" y="{height-bottom+20}" text-anchor="middle" font-family="sans-serif" font-size="11">{label}</text>')
    for impl, x in (('lie', left), ('gufo', left+110)):
        parts += [f'<circle cx="{x}" cy="{height-17}" r="5" fill="{colors[impl]}"/>',
                  f'<text x="{x+11}" y="{height-13}" font-family="sans-serif" font-size="12">{impl.upper()}</text>']
    parts.append('</svg>')
    target.write_text('\n'.join(parts)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, default=ROOT/'evidence')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    comparisons = []
    missing = []
    for mode in ('ar', 'mtp'):
        for size in SIZES:
            try:
                lie = checked_run(mode, size, 'lie', args.evidence_root)
                gufo = checked_run(mode, size, 'gufo', args.evidence_root)
                matching = True
                output_matching = True
                for a, b in zip(lie['samples'], gufo['samples']):
                    if (normalized(a['request'], 'lie') != normalized(b['request'], 'gufo') or
                            a['prompt_tokens'] != b['prompt_tokens'] or a['rep'] != b['rep']):
                        matching = False
                    if a['assistant'] != b['assistant']:
                        output_matching = False
                if not matching:
                    raise ValueError('Normalized request or physical prompt mismatch')
                comparisons.append({'mode': mode, 'size': size, 'lie': metrics(lie, 'lie'),
                                    'gufo': metrics(gufo, 'gufo'),
                                    'same_assistant_outputs': output_matching,
                                    'normalized_request_sha256': [hashlib.sha256(
                                        json.dumps(normalized(row['request'], 'lie'),
                                                   sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                                        for row in lie['samples']],
                                    'assistant_sha256': {impl: [hashlib.sha256(
                                        row['assistant']['content'].encode()).hexdigest()
                                        for row in run['samples']]
                                                         for impl, run in (('lie', lie), ('gufo', gufo))},
                                    'evidence': {impl: {k: run[k] for k in
                                              ('label', 'manifest_sha256', 'measurements_sha256',
                                               'gate_sha256', 'resource_peaks')}
                                                 for impl, run in (('lie', lie), ('gufo', gufo))}})
            except (FileNotFoundError, KeyError, ValueError, TypeError) as error:
                missing.append({'mode': mode, 'size': size, 'reason': str(error)})
    mode_effect = []
    for size in SIZES:
        ar = next((row for row in comparisons if row['mode'] == 'ar' and row['size'] == size), None)
        mtp = next((row for row in comparisons if row['mode'] == 'mtp' and row['size'] == size), None)
        if ar and mtp:
            for impl in ('lie', 'gufo'):
                mode_effect.append({'size': size, 'implementation': impl,
                                    'prefill_mtp_over_ar': round(mtp[impl]['prefill_tps']/ar[impl]['prefill_tps'], 4),
                                    'decode_mtp_over_ar': round(mtp[impl]['decode_tps']/ar[impl]['decode_tps'], 4),
                                    'mtp_acceptance_rate': mtp[impl]['mtp_acceptance_rate']})
    summary = {'schema': 'synapse-lie.point-http-depth-comparison.v1',
               'scope': 'Point original-weight C1 cold HTTP, two measured repetitions per engine; Gufo only adds cache_prompt:false',
               'rows': comparisons, 'mode_effect': mode_effect,
               'unpaired_or_failed': missing}
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    with (args.output/'comparison.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('mode', 'target_prompt_tokens', 'implementation', 'actual_prompt_tokens',
                         'prefill_tps', 'prefill_ms', 'decode_tps', 'decode_ms',
                         'ttft_ms', 'wall_ms', 'same_assistant_outputs'))
        for row in comparisons:
            for impl in ('lie', 'gufo'):
                m = row[impl]
                writer.writerow((row['mode'], row['size'], impl, m['prompt_tokens'],
                                 m['prefill_tps'], m['prefill_ms'], m['decode_tps'],
                                 m['decode_ms'], m['ttft_ms'], m['wall_ms'],
                                 row['same_assistant_outputs']))
    with (args.output/'mode-effect.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('target_prompt_tokens', 'implementation', 'prefill_mtp_over_ar',
                         'decode_mtp_over_ar', 'mtp_acceptance_rate'))
        for row in mode_effect:
            writer.writerow((row['size'], row['implementation'],
                             row['prefill_mtp_over_ar'], row['decode_mtp_over_ar'],
                             row['mtp_acceptance_rate']))
    for mode in ('ar', 'mtp'):
        subset = [row for row in comparisons if row['mode'] == mode]
        if subset:
            svg(subset, 'prefill_tps', f'{mode.upper()} cold HTTP prefill, tokens/s',
                args.output/f'{mode}-prefill.svg')
            svg(subset, 'decode_tps', f'{mode.upper()} HTTP decode, tokens/s',
                args.output/f'{mode}-decode.svg')
    print(json.dumps({'paired': len(comparisons), 'unpaired_or_failed': missing}))
    return 0 if len(comparisons) == len(SIZES)*2 else 1


if __name__ == '__main__':
    raise SystemExit(main())
