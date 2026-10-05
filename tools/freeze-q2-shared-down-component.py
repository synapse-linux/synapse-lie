#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the component-only shared-down campaign to its new qualified host."""
import importlib.util
import json
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_down', ROOT/'tools/analyze-q2-shared-down-component.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
sha, read, require = analysis.sha, analysis.read, analysis.require


def main(narrow=False):
    prefix = 'q2-shared-down-n64-component' if narrow else 'q2-shared-down-component'
    variant = 'shared-down-n64' if narrow else 'shared-down-fixed'
    prior = read(ROOT/'config/q2-ssm-fixed-bounds-plan.json')
    names = [*prior['fixtures'], 'tests/q2_shared_down_mirror.hip', 'tests/q2_shared_down_runtime_test.py']
    fixtures = {n: sha(ROOT/n) for n in names}
    host_label = 'q2-shared-down-n64-host-r1' if narrow else 'q2-shared-down-host-r1'
    host_path = ROOT/'evidence'/host_label
    host, _ = analysis.hc.curve.artifact_integrity(host_path)
    require(host['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE' and
            len(host['commands']) == 6 and all(c['exit_code'] == 0 for c in host['commands']),
            'Fresh host gate incomplete')
    for name in ('03.log', '06.log'):
        require('100% tests passed out of 27' in (host_path/'results'/name).read_text(), 'Wrong host count')
    host_binding = analysis.hc.capsule(host_path, fixtures)
    previous = ('config/q2-shared-down-component-window-release.json' if narrow else
                'config/q2-ssm-fixed-bounds-window-release.json')
    expected_previous = ('c4efdddb7bad7a90977ef0d4fe09a70dc18f8916a81562156126a3a945179122' if narrow else
                         'fc00b067802482077ab97819fc02547a1fdbd055ea5066dbfe58c5c4391c08cd')
    require(sha(ROOT/previous) == expected_previous,
            'Previous release changed')
    manifest_names = ['config/q2-shared-down-fixed-source.json', 'config/q2-shared-down-static.json',
                      'config/q2-shared-down-runtime-source.json', 'config/q2-ssm-fixed-bounds-model-results.json',
                      'config/q2-fixed-prefill-reference.json', 'tools/analyze-q2-shared-down-component.py',
                      'tests/q2_shared_down_analysis_test.py', 'tools/freeze-q2-shared-down-component.py']
    if narrow:
        manifest_names[:3] = ['config/q2-shared-down-n64-source.json', 'config/q2-shared-down-n64-static.json',
                              'config/q2-shared-down-n64-runtime-source.json']
        manifest_names.append('config/q2-shared-down-component-results.json')
    helper = 'tools/' + prefix + '-window.py'
    plan = dict(schema='synapse-lie.q2-shared-down-component-plan.v1', fixtures=fixtures,
                manifests={n: sha(ROOT/n) for n in manifest_names}, source_manifest=manifest_names[0],
                host=host_label, host_reused=False, host_test_counts={'debug': 27, 'sanitize': 27},
                host_binding=host_binding, host_result_sha256=sha(host_path/'results/result.json'),
                component=dict(label=prefix+'-r1', mode=variant+'-check', variant=variant),
                window_helper=helper, window_helper_sha256=sha(ROOT/helper),
                previous_release=previous, previous_release_sha256=sha(ROOT/previous),
                release_path='config/'+prefix+'-window-release.json',
                timing_scope='M2560/N2048/K640 shared-down projection only, four arms; two warmups '
                    'and five measured repetitions in rotating order, 24 weight rotations beyond32MiB. '
                    'Conversion, allocations, checking and readback excluded. Not model throughput.',
                required_output_pairs=126, required_fp64_checks=168, required_format_checks=42,
                required_format_values=68812800, required_timing_samples=28,
                safe_numeric_rejection_keeps_timings=True, model_dispatch_unchanged=True,
                saved_best={'prefill_tok_s': 1585.308983, 'decode_steps_s': 25.16079073},
                fixed_q2={'prefill_tok_s': 1443.672867, 'decode_steps_s': 25.09595499},
                fixed_ud={'prefill_tok_s': 1685.777092, 'decode_steps_s': 24.34174251},
                model_controls_rerun=False, model_inference=False, gpu_run=False, goal_met=False)
    analysis.hc.write(ROOT/'config'/(prefix+'-plan.json'), plan)
    print(json.dumps(dict(fixtures=len(fixtures), manifests=len(manifest_names), host=host_label,
                         host_reused=False, host_binding=host_binding)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n64', action='store_true')
    main(parser.parse_args().n64)
