#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare complete matched 2K model arms, retaining numerical differences."""
import argparse
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('hc_analysis', Path(__file__).with_name('analyze-q2-hc.py'))
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', action='append', required=True, help='NAME=collected evidence directory')
    parser.add_argument('--numerical-reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference, _, reference_meta = hc.read(args.numerical_reference, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    report = {'scope': 'Same unprofiled C1 2K/128 request protocol, 15s idle outside PP/TG timing; HC and UD controls are historical, not rerun; no long-context or sustained-serving qualification',
              'promotion': False, 'goal': 'Q2 PP/TG parity with UD remains required',
              'numerical_reference': reference_meta, 'arms': {}, 'relative_medians': {}}
    for item in args.arm:
        label, value = item.split('=', 1)
        if label in report['arms']:
            raise ValueError('Duplicate arm label')
        root, events, meta = hc.read(Path(value), 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
        samples = [e for e in events if e.get('event') == 'sample' and e['label'] == 'pp2048']
        idle = [e for e in events if e.get('event') == 'cooldown']
        if len(idle) != 4 or any(e['seconds'] != 15 or e['before_rep'] != i for i, e in enumerate(idle)):
            raise ValueError('Different model idle protocol')
        if len(samples) != 4 or sum(e['warmup'] for e in samples) != 1 or any(
                e['prompt_tokens'] != 2048 or e['decode_steps'] != 127 or
                e['output_tokens'] != 128 or e['eos'] for e in samples):
            raise ValueError('Incomplete or changed model sample scope')
        result = json.loads((root / 'result.json').read_text())
        numerical = {}
        if result['models_before'][0]['path'].endswith('/Qwen3.8-Flash-Next-Q2.gguf'):
            numerical['frontiers'] = hc.frontiers(reference, root, logits=True, subset=True)
            numerical['token_files'] = sorted(p.name for p in root.iterdir() if p.suffix in ('.i32', '.u32'))
            numerical['changed_tokens'] = [name for name in numerical['token_files']
                if (reference / name).read_bytes() != (root / name).read_bytes()]
        replay = [((root / f'pp2048-0-{suffix}').read_bytes() ==
                   (root / f'pp2048-{rep}-{suffix}').read_bytes())
                  for suffix in ('prefill.f32', 'last.f32', 'output.u32') for rep in (1, 2, 3)]
        report['arms'][label] = dict(meta,
            measurements={key: hc.stats([e[key] for e in samples if not e['warmup']]) for key in
                ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')},
            numerical=numerical, replay={'checks': len(replay), 'exact': sum(replay)},
            models=result['models_before'], command_exits=[c['exit_code'] for c in result['commands']])
    for name, arm in report['arms'].items():
        report['relative_medians'][name] = {other: {key:
            arm['measurements'][key]['median'] / ref['measurements'][key]['median']
            for key in ('prefill_tok_s', 'decode_steps_s')}
            for other, ref in report['arms'].items() if other != name}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({label: {key: v['median'] for key, v in arm['measurements'].items()}
                      for label, arm in report['arms'].items()}, indent=2))


if __name__ == '__main__':
    main()
