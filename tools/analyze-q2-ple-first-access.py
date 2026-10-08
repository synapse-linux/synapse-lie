#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare balanced new-input PLE observations, keeping replay positions separate."""
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
    events = [json.loads(line) for path in sorted(args.results.glob('*.log'))
              for line in path.read_text().splitlines() if line.startswith('{"event":')]
    kinds = {kind: [e for e in events if e['event'] == kind]
             for kind in ('configuration', 'warmup', 'input', 'prefill', 'io',
                          'comparison', 'frontier', 'interval', 'cancellation', 'complete')}
    failures = []

    def check(good, message):
        if not good:
            failures.append(message)

    expected_counts = dict(configuration=1, warmup=1, input=8, prefill=16, io=16,
                           comparison=16, frontier=576, interval=64, cancellation=1, complete=1)
    for kind, count in expected_counts.items():
        check(len(kinds[kind]) == count, 'Event count differs: ' + kind)
    check(all(c.get('exit_code') == 0 for c in receipt['commands']), 'Remote command failed')
    check(kinds['configuration'] and kinds['configuration'][0].get('protocol') == 'first-access-v1',
          'Wrong protocol')
    if kinds['configuration']:
        config = kinds['configuration'][0]
        check(config['prompt'] == 8192 and config['chunk'] == 2048 and
              config['forced_decode'] == 32 and config['sets'] == 8 and
              not config['global_cache_flush'], 'Geometry/cache policy differs')
    check(all(e['all_exact'] for e in kinds['complete']), 'Complete buffers differ')
    check(all(e['finite'] and e['all_exact'] for e in kinds['comparison']), 'Output mismatch/non-finite')
    check(all(e['input_released'] and e['checks'] >= 3 for e in kinds['cancellation']),
          'Cancellation did not drain')
    check(all(e['finite'] for e in kinds['warmup']), 'Warmup is non-finite')
    check({e['rep'] for e in kinds['input']} == set(range(8)), 'Input set coverage differs')
    check(len({e['input_sha256'] for e in kinds['input']}) == 8, 'Input sets repeat')
    check(len({e['rows_sha256'] for e in kinds['input']}) == 8, 'Row sets repeat')
    expected = {(mode, rep) for mode in ('native', 'lookahead') for rep in range(8)}
    for kind in ('prefill', 'io', 'comparison'):
        check({(e['mode'], e['rep']) for e in kinds[kind]} == expected, 'Coverage differs: ' + kind)
    # Authenticate every saved original artifact before deriving a verdict.
    for name, meta in receipt.get('artifacts', {}).items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe artifact name')
        data = (args.results / name).read_bytes()
        check(len(data) == meta['bytes'] and hashlib.sha256(data).hexdigest() == meta['sha256'],
              'Artifact integrity differs: ' + name)
    first_modes = ('native', 'lookahead', 'lookahead', 'native') * 2
    for rep in range(8):
        pair = [e for e in kinds['comparison'] if e['rep'] == rep]
        check(len(pair) == 2 and len({e['output_sha256'] for e in pair}) == 1,
              'Complete pair output differs at set ' + str(rep))
        for row in range(36):
            values = [e for e in kinds['frontier'] if e['rep'] == rep and e['row'] == row]
            check(len(values) == 2 and {e['mode'] for e in values} == {'native', 'lookahead'}
                  and len({e['sha256'] for e in values}) == 1,
                  f'Frontier differs at set {rep}, row {row}')
        values = [e for e in kinds['input'] if e['rep'] == rep]
        check(len(values) == 1 and values[0]['first_mode'] == first_modes[rep],
              'First-order assignment differs at set ' + str(rep))
    observations = []
    for row in kinds['prefill']:
        mode, rep = row['mode'], row['rep']
        check(rep in range(8) and mode in ('native', 'lookahead'), 'Invalid observation identity')
        if rep not in range(8) or mode not in ('native', 'lookahead'):
            continue
        first = mode == first_modes[rep]
        check(row['order_position'] == (0 if first else 1) and row['first_access_observation'] == first,
              'Order metadata differs')
        check(row['good'] and row['seconds'] > 0, 'Failed/invalid prefill')
        case = sorted((e for e in kinds['interval'] if e['mode'] == mode and e['rep'] == rep),
                      key=lambda e: e['chunk'])
        check([e['chunk'] for e in case] == list(range(4)), 'Incomplete intervals')
        overlap = 0.0
        if mode == 'lookahead':
            check(row['prepared'] == row['consumed'] == 4 and row['flow_status'] == 0 and
                  row['peak_owned_slots'] <= 2, 'Incomplete/beyond-budget flow')
        for i, interval in enumerate(case):
            check(0 <= interval['consume_begin'] <= interval['consume_end'] <= row['seconds'] + 1e-8,
                  'Invalid consumer interval')
            if mode == 'native':
                continue
            check(0 <= interval['prepare_begin'] <= interval['prepare_end'] <= interval['consume_begin'],
                  'Consumption precedes readiness')
            if i >= 2:
                check(interval['prepare_begin'] >= case[i - 2]['consume_end'], 'Slot reused before drain')
            if i:
                overlap += max(0, min(interval['prepare_end'], case[i - 1]['consume_end']) -
                               max(interval['prepare_begin'], case[i - 1]['consume_begin']))
        io = [e for e in kinds['io'] if e['mode'] == mode and e['rep'] == rep]
        if len(io) != 1:
            continue
        io = io[0]
        comparison = [e for e in kinds['comparison'] if e['mode'] == mode and e['rep'] == rep]
        if len(comparison) != 1:
            continue
        decode = comparison[0]['decode_seconds']
        check(decode > 0, 'Invalid forced decode duration')
        check(io['requested_pages'] > 0 and 0 <= io['resident_before'] <= io['requested_pages'] and
              0 <= io['resident_after'] <= io['requested_pages'] and io['process_read_bytes'] >= 0,
              'Invalid I/O observation')
        observations.append(dict(row, **{key: value for key, value in io.items()
                                         if key not in ('event', 'mode', 'rep')},
                                 overlap_seconds=overlap,
                                 forced_decode_seconds=decode,
                                 forced_decode_steps_per_second=32 / decode,
                                 resident_before_percent=100 * io['resident_before'] / io['requested_pages'],
                                 read_mib=io['process_read_bytes'] / 1048576))
    summary = {}
    for position in (0, 1):
        group = {}
        for mode in ('native', 'lookahead'):
            samples = [e for e in observations if e['order_position'] == position and e['mode'] == mode]
            check(len(samples) == 4, 'Incomplete balanced observations')
            if not samples:
                continue
            seconds = statistics.median(e['seconds'] for e in samples)
            group[mode] = dict(count=len(samples), prefill_seconds_median=seconds,
                               prefill_seconds_min=min(e['seconds'] for e in samples),
                               prefill_seconds_max=max(e['seconds'] for e in samples),
                               prefill_tokens_per_second=8192 / seconds,
                               forced_decode_seconds_median=statistics.median(e['forced_decode_seconds'] for e in samples),
                               resident_before_percent_median=statistics.median(e['resident_before_percent'] for e in samples),
                               read_mib_mean=statistics.mean(e['read_mib'] for e in samples),
                               overlap_seconds_median=statistics.median(e['overlap_seconds'] for e in samples))
        if len(group) == 2:
            group['lookahead_vs_native_rate_percent'] = 100 * (
                group['native']['prefill_seconds_median'] / group['lookahead']['prefill_seconds_median'] - 1)
        summary['first_position' if position == 0 else 'replay_position'] = group
    result = dict(scope='Original Q2 8K synthetic AR inputs; balanced observed first access, not controlled cold cache or UD parity',
                  verdict='MEASURED_EXACT' if not failures else 'FAILED_CHECKS', failures=failures,
                  summary=summary, observations=observations, events=kinds,
                  command_exit_codes=[c.get('exit_code') for c in receipt['commands']])
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('verdict', 'failures', 'summary')}, indent=2))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
