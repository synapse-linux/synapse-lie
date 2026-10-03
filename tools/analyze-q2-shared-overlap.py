#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit fixed Q2 shared-stream model timings and complete saved replay files."""
import argparse
import importlib.util
import json
from pathlib import Path


def module(filename):
    spec = importlib.util.spec_from_file_location(filename, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


hc = module('analyze-q2-hc.py')
common = module('analyze-q2-hc-input.py')
require = common.require


def arm(path, variant):
    root, events, meta = hc.read(path, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    receipt = json.loads((root / 'result.json').read_text())
    transport = json.loads((path / 'transport.json').read_text())
    require(transport['exit_code'] == 0 and transport['rebuild_mmq']
            and transport['source_variant'] == variant, 'Source/rebuild changed')
    require(receipt['binary_sha256'] == receipt['binary_sha256_after'], 'Binary changed')
    require(receipt['models_before'] == receipt['models_after'], 'Model witness changed')
    require(receipt['locks'] == receipt['postflight_locks'] and len(receipt['locks']) == 4
            and not receipt['preflight_kfd'] and not receipt['postflight_kfd'], 'GPU admission unresolved')
    loaded = [e for e in events if e.get('event') == 'loaded']
    require(len(loaded) == 1 and loaded[0]['mtp'] is False
            and loaded[0]['max_context'] == 9216 and loaded[0]['prefill_chunk'] == 2048,
            'Changed model configuration')
    samples = [e for e in events if e.get('event') == 'sample' and e['label'] == 'pp2048']
    idle = [e for e in events if e.get('event') == 'cooldown']
    require(len(idle) == 4 and all(e['seconds'] == 15 and e['before_rep'] == i
                                  for i, e in enumerate(idle)), 'Changed idle protocol')
    require([e['rep'] for e in samples] == list(range(4))
            and [e['warmup'] for e in samples] == [True, False, False, False]
            and all(e['prompt_tokens'] == 2048 and e['decode_steps'] == 127
                    and e['output_tokens'] == 128 and not e['eos'] for e in samples),
            'Incomplete model samples')
    forks = [e for e in events if e.get('event') == 'shared_fork']
    if variant == 'shared-overlap':
        require(len(forks) == 1 and forks[0]['started'] > 0
                and forks[0]['started'] == forks[0]['joined']
                and forks[0]['drained'] == 0 and forks[0]['state'] == 'idle',
                'Shared branch was not exercised cleanly')
    else:
        require(not forks, 'Reference unexpectedly uses shared fork')
    replay = [(root / f'pp2048-0-{suffix}').read_bytes() ==
              (root / f'pp2048-{i}-{suffix}').read_bytes()
              for suffix in ('prefill.f32', 'last.f32', 'output.u32') for i in (1, 2, 3)]
    return root, dict(meta, samples=samples, shared_fork=forks,
        within_arm_replay=dict(checks=len(replay), exact=sum(replay)),
        measurements={key: common.stats([e[key] for e in samples if not e['warmup']])
            for key in ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')})


def compare(a, b):
    files = lambda root: {p.name for p in root.iterdir() if p.suffix in ('.f32', '.i32', '.u32')}
    require(files(a) == files(b) and len(files(a)) == 21, 'Changed model file inventory')
    return dict(files=sorted(files(a)), changed=[n for n in sorted(files(a))
        if (a / n).read_bytes() != (b / n).read_bytes()], frontiers=hc.frontiers(a, b, logits=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    a, ref = arm(args.reference, 'hc-up-chains')
    b, cand = arm(args.candidate, 'shared-overlap')
    retained, _ = arm(args.retained, 'hc-up-chains')
    report = dict(scope='C1 pp2048/tg128, complete original Q2, one warmup/three samples',
        goal_met=False, promoted=False, reference=ref, candidate=cand,
        replay=compare(a, b), retained_reference_replay=compare(retained, a),
        median_change_percent={key:100 * (cand['measurements'][key]['median'] /
            ref['measurements'][key]['median'] - 1)
            for key in ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')},
        limits='15s idle outside timing; no long-context, concurrency, independent quality or hardware fault qualification')
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('median_change_percent', 'limits')}))
    print(json.dumps(dict(changed=report['replay']['changed'],
        retained_changed=report['retained_reference_replay']['changed'])))


if __name__ == '__main__':
    main()
