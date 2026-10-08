#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit corrected sampling and historical completed-token decode accounting."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


shared = module('analyze-q2-shared-overlap.py')
audit = module('analyze-q2-combined.py')
require = shared.require
METRICS = ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')
FIXTURES = ('CMakeLists.txt', 'cmake/hip/CMakeLists.txt', 'tests/q2_model.cpp',
            'tests/q2_argmax.hpp', 'tests/q2_argmax.cpp', 'tests/q2_historical_input.hpp',
            'tests/q2_profile_markers.hip', 'tests/q2_remote_test.py',
            'tools/q2-runner.py', 'tools/q2-remote.py', 'tools/q2_process.py',
            'tools/q2_thermal.py', 'tools/q2_reuse.py', 'config/models-157.inventory.json')
HOST = ROOT / 'evidence/q2-decode-baseline-host-r1'


def validate(path, cpu=False):
    root = path / 'results'
    r = json.loads((root / 'result.json').read_text())
    t = json.loads((path / 'transport.json').read_text())
    c = json.loads((path / 'collection.json').read_text())
    exits = [x['exit_code'] for x in r['commands']]
    require(exits == [0] * (6 if cpu else 4) and t['exit_code'] == 0, 'Failed/incomplete commands')
    require(c['verified_artifacts'] == len(r['artifacts']), 'Collection count mismatch')
    for name, meta in r['artifacts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
        p = root / name
        require(p.stat().st_size == meta['bytes'] and audit.digest(p) == meta['sha256'], 'Artifact changed: ' + name)
    require('finished_at' in r and not any(r.get(k) for k in ('thermal_stop', 'postflight_error', 'error')), 'Unresolved process')
    if cpu:
        require(r['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and not r['model_access'], 'Host scope')
        for name in ('03.log', '06.log'):
            require('100% tests passed out of 17' in (root / name).read_text(), 'Missing host test')
    else:
        require(r['state'] == 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT', 'Model state')
        require(r['locks'] == r['postflight_locks'] and [(x['device'], x['inode']) for x in r['locks']] ==
                [(52, 3232146), (52, 3206482), (52, 3228451), (55, 45067)], 'Lease mismatch')
        require(not r['preflight_kfd'] and not r['postflight_kfd'], 'KFD unresolved')
        require(t['rebuild_mmq'] and not r.get('mmq_reuse'), 'Model requires full source rebuild')
        require(r['binary_sha256'] == r['binary_sha256_after'] and r['models_before'] == r['models_after'], 'Binary/model changed')
    with tarfile.open(path / 'source.tar.gz') as cap, tarfile.open(HOST / 'source.tar.gz') as host:
        for name in FIXTURES:
            require(cap.extractfile(name).read() == host.extractfile(name).read(), 'Unqualified host cohort: ' + name)
    return dict(audit.audit_capsule(path, FIXTURES), state=r['state'], command_exits=exits,
                model_access=r['model_access'], binary_sha256=r.get('binary_sha256'),
                finished_at=r['finished_at'], models=r.get('models_after'))


def model(path, variant):
    root, events, meta = shared.hc.read(path, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
    t = json.loads((path / 'transport.json').read_text())
    require(t['source_variant'] == variant, 'Wrong model source')
    loaded = [e for e in events if e.get('event') == 'loaded']
    require(len(loaded) == 1 and loaded[0]['mtp'] is False and
            loaded[0]['max_context'] == 9216 and loaded[0]['prefill_chunk'] == 2048, 'Changed configuration')
    complete = [e for e in events if e.get('event') == 'complete']
    require(complete == [dict(event='complete', finite_frontiers=True, semantic_smoke=True)], 'Incomplete model')
    scopes = {}
    for label, tokens, steps, completed, idle_key in (
            ('pp2048', 2048, 127, False, 'before_rep'),
            ('historical2042', 2042, 128, True, 'before_historical_rep')):
        samples = [e for e in events if e.get('event') == 'sample' and e['label'] == label]
        idle = [e for e in events if e.get('event') == 'cooldown' and idle_key in e]
        require(len(idle) == 4 and all(e[idle_key] == i and e['seconds'] == 15 for i, e in enumerate(idle)), 'Cooldown mismatch')
        require([e['rep'] for e in samples] == list(range(4)) and
                [e['warmup'] for e in samples] == [True, False, False, False], 'Missing repetitions')
        for e in samples:
            require(e['prompt_tokens'] == tokens and e['decode_steps'] == steps and e['output_tokens'] == 128 and
                    e['completed_output'] is completed and e['final_position'] == tokens + steps and not e['eos'], 'Incomplete work')
            require(all(math.isfinite(e[k]) and e[k] > 0 for k in METRICS), 'Invalid duration/rate')
            require(math.isclose(e['prefill_tok_s'], tokens/e['prefill_s'], rel_tol=1e-8) and
                    math.isclose(e['decode_steps_s'], steps/e['decode_s'], rel_tol=1e-8), 'Incorrect rate denominator')
            require((root / f"{label}-{e['rep']}-output.u32").stat().st_size == 128*4, 'Incomplete saved output')
        replay = [(root / f'{label}-0-{suffix}').read_bytes() == (root / f'{label}-{rep}-{suffix}').read_bytes()
                  for suffix in ('prefill.f32', 'last.f32', 'output.u32') for rep in (1, 2, 3)]
        scopes[label] = dict(samples=samples, measurements={key:shared.common.stats([e[key] for e in samples[1:]]) for key in METRICS},
                             replay=dict(checks=len(replay), exact=sum(replay)))
    files = sorted(p.name for p in root.iterdir() if p.suffix in ('.f32', '.u32', '.i32'))
    require(len(files) == 34, 'Changed evidence inventory')
    finite = []
    for name in files:
        if name.endswith('.f32'):
            b = (root / name).read_bytes()
            require(len(b) == 248320*4 and all(math.isfinite(x[0]) for x in struct.iter_unpack('<f', b)), 'Invalid saved frontier')
            finite.append(name)
    return root, dict(meta, scopes=scopes, files=files, finite_frontiers=finite, validation=validate(path))


def main():
    static = json.loads((ROOT / 'config/q2-decode-baseline-static.json').read_text())
    candidate = ROOT / static['candidate']
    require({str(p.relative_to(candidate)):audit.digest(p) for p in candidate.rglob('*') if p.is_file()} == static['source_file_hashes'], 'Prepared source changed')
    historical = static['historical_baseline']
    old_raw = Path(historical['main_worktree']) / 'evidence/t0-c1-perf-r2/remote-results/measurements.jsonl'
    require(audit.digest(old_raw) == historical['measurement_sha256'], 'Historical receipt changed')
    require(audit.digest(ROOT / 'tests/q2_historical_input.hpp') == historical['header_sha256'], 'Historical input header changed')
    host = validate(HOST, cpu=True)
    roots, models, old_replay, baseline_replay = {}, {}, {}, {}
    for name, label, variant, previous in (
            ('q2', 'q2-decode-baseline-q2-r1', 'library-norm-bound', 'q2-library-norm-model-candidate-r1'),
            ('ud', 'q2-decode-baseline-ud-r1', 'qualified', 'q2-library-norm-model-ud-r1')):
        roots[name], models[name] = model(ROOT / 'evidence' / label, variant)
        root = roots[name]
        old, _, _ = shared.hc.read(ROOT / 'evidence' / previous, 'MODEL_SAMPLES_COMPLETE_NOT_COMPARISON_VERDICT')
        files = sorted(p.name for p in old.iterdir() if p.suffix in ('.f32', '.i32', '.u32'))
        require(len(files) == 21, 'Previous evidence inventory changed')
        old_replay[name] = dict(files=files, changed=[n for n in files if (old/n).read_bytes() != (root/n).read_bytes()])
        ids = list(struct.unpack('<2042i', (root/'historical2042-input.i32').read_bytes()))
        require(ids == historical['input']['physical_ids'], 'Historical physical prompt mismatch')
        baseline_replay[name] = []
        for rep, old_sample in enumerate(historical['samples']):
            prefix = root / f'historical2042-{rep}'
            output = list(struct.unpack('<128I', Path(str(prefix)+'-output.u32').read_bytes()))
            baseline_replay[name].append(dict(rep=rep, output_ids_exact=output == old_sample['output_ids'],
                prefill_logits_exact=audit.digest(Path(str(prefix)+'-prefill.f32')) == old_sample['prefill_logits_sha256'],
                decode_logits_exact=audit.digest(Path(str(prefix)+'-last.f32')) == old_sample['decode_logits_sha256']))
    comparisons = {scope:{metric:100*(models['q2']['scopes'][scope]['measurements'][metric]['median']/
                    models['ud']['scopes'][scope]['measurements'][metric]['median']-1) for metric in METRICS}
                   for scope in ('pp2048', 'historical2042')}
    prior = json.loads((ROOT / 'config/q2-library-norm-model-results.json').read_text())
    harness_change = {name:{metric:100*(models[name]['scopes']['pp2048']['measurements'][metric]['median']/
                      prior['model']['candidate' if name == 'q2' else 'ud']['measurements'][metric]['median']-1)
                      for metric in METRICS} for name in models}
    report = dict(scope='Direct original-model C1; corrected finite-logit validation, current2K and historical physical2042/completed128',
        model=models, host_validation=host, previous_21_file_replay=old_replay,
        original_ud_baseline=historical['summary'], original_ud_baseline_replay=baseline_replay,
        historical_measurement_sha256=historical['measurement_sha256'],
        q2_vs_ud_percent=comparisons, corrected_vs_previous_harness_percent=harness_change,
        numerical_pass=False, promoted=False, goal_met=False,
        limits='Historical prompt/count/timer scope aligned; direct executor lacks original C ABI bookkeeping and retains full finite checks inside sampling. Existing operator failures and KL0.002996>0.002 remain. No HTTP, concurrency, long-context or task-quality acceptance.')
    (ROOT / 'config/q2-decode-baseline-results.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(q2_vs_ud_percent=comparisons, corrected_vs_previous_harness_percent=harness_change,
        previous_changed={n:r['changed'] for n,r in old_replay.items()}, original_ud_baseline_replay=baseline_replay,
        medians={n:{s:{k:v['median'] for k,v in r['measurements'].items()} for s,r in m['scopes'].items()} for n,m in models.items()}),indent=2))


if __name__ == '__main__':
    main()
