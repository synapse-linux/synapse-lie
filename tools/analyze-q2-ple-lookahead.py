#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain all native/prepared/lookahead samples; keep first accesses separate."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    receipt = json.loads((args.results / 'result.json').read_text())
    events = []
    for logfile in sorted(args.results.glob('*.log')):
        for line in logfile.read_text().splitlines():
            if line.startswith('{"event":'):
                events.append(json.loads(line))
    rows = [e for e in events if e['event'] == 'prefill']
    comparisons = [e for e in events if e['event'] == 'comparison']
    frontiers = [e for e in events if e['event'] == 'frontier']
    intervals = [e for e in events if e['event'] == 'interval']
    configurations = [e for e in events if e['event'] == 'configuration']
    failures = []
    if len(configurations) != 1:
        failures.append('Configuration event count differs')
    if len(rows) != 12 or len(comparisons) != 12 or len(frontiers) != 432:
        failures.append('Incomplete three-arm, four-repetition comparison')
    if not any(e['event'] == 'complete' and e['all_exact'] for e in events):
        failures.append('Missing byte-exact completion')
    if not any(e['event'] == 'cancellation' and e['input_released'] for e in events):
        failures.append('Missing in-flight cancellation/drain result')
    if any(c.get('exit_code') != 0 for c in receipt['commands']):
        failures.append('A qualification command failed')
    if any(not c['all_exact'] or not c['finite'] for c in comparisons):
        failures.append('Non-finite or different complete model output')
    identities = {(c['mode'], c['rep']) for c in comparisons}
    expected = {(mode, rep) for mode in ('native', 'prepared_serial', 'lookahead')
                for rep in range(4)}
    if identities != expected or {(r['mode'], r['rep']) for r in rows} != expected:
        failures.append('Missing or duplicate mode/repetition coverage')
    if len({c['output_sha256'] for c in comparisons}) != 1:
        failures.append('Complete output hashes differ')
    for frontier in range(36):
        hashes = [e['sha256'] for e in frontiers if e['row'] == frontier]
        if len(hashes) != 12 or len(set(hashes)) != 1:
            failures.append('Frontier hashes differ at row ' + str(frontier))
    # The receipt authenticates saved evidence; full comparisons run in RAM.
    for name, item in receipt.get('artifacts', {}).items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe artifact name')
        data = (args.results / name).read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            failures.append('Artifact integrity differs: ' + name)
    overlap = []
    for row in rows:
        case = sorted((e for e in intervals if e['mode'] == row['mode'] and
                       e['rep'] == row['rep']), key=lambda e: e['chunk'])
        if [e['chunk'] for e in case] != list(range(4)):
            failures.append('Incomplete chunk intervals')
            continue
        if not row['good']:
            failures.append('Failed prefill')
        if row['mode'] == 'native':
            continue
        if row['prepared'] != 4 or row['consumed'] != 4 or row['flow_status']:
            failures.append('Incomplete producer/consumer accounting')
        seconds = 0.0
        for i, entry in enumerate(case):
            if entry['consume_begin'] + 1e-8 < entry['prepare_end']:
                failures.append('Consumption began before preparation completed')
            if i >= 2 and entry['prepare_begin'] + 1e-8 < case[i - 2]['consume_end']:
                failures.append('Slot was reused before its previous consumer drained')
            if i:
                seconds += max(0, min(entry['prepare_end'], case[i - 1]['consume_end']) -
                               max(entry['prepare_begin'], case[i - 1]['consume_begin']))
        overlap.append(dict(mode=row['mode'], rep=row['rep'], seconds=seconds))
        if row['mode'] == 'prepared_serial' and seconds > 1e-8:
            failures.append('Serial control unexpectedly overlaps')
    summary = {}
    for mode in ('native', 'prepared_serial', 'lookahead'):
        pp = [r['seconds'] for r in rows if r['mode'] == mode and r['rep'] > 0]
        tg = [r['decode_seconds'] for r in comparisons if r['mode'] == mode and r['rep'] > 0]
        if len(pp) == len(tg) == 3:
            summary[mode] = dict(prefill_seconds_median=statistics.median(pp),
                                 prefill_tokens_per_second=8192 / statistics.median(pp),
                                 forced_decode_seconds_median=statistics.median(tg),
                                 forced_decode_steps_per_second=32 / statistics.median(tg))
    if len(summary) == 3:
        summary['lookahead_vs_native_rate_percent'] = 100 * (
            summary['native']['prefill_seconds_median'] /
            summary['lookahead']['prefill_seconds_median'] - 1)
    result = dict(scope='Original Q2 8K AR scheduling comparison, synthetic varied inputs; not UD parity, HTTP or long-context acceptance',
                  first_access_scope='Ordered observations only; no controlled cold-cache claim',
                  verdict='MEASURED_EXACT' if not failures else 'FAILED_CHECKS',
                  failures=failures, configurations=configurations, summary=summary,
                  samples=rows, comparisons=comparisons, frontiers=frontiers,
                  intervals=intervals, overlap=overlap,
                  command_exit_codes=[c.get('exit_code') for c in receipt['commands']])
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('verdict', 'failures', 'summary')}, indent=2))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
