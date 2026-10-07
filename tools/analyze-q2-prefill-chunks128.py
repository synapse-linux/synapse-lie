#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the three original-input, enabled-IOMMU prefill chunk curves."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-prefill-chunks128-r1'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def tables(report):
    lines = ['<!-- SPDX-License-Identifier: MIT -->', '',
             '# Enabled-IOMMU prefill chunk measurements', '',
             'One original eleven-request curve per chunk on .157, in 2048/4096/8192 order.',
             'The same server and native `synapse-lie-bench` run C1 AR at context capacity',
             '133760 with performance/120 W, unchanged fan settings and zero KV/SSD prefix reuse.',
             'No reboot, boot-configuration change, request padding or weight requantization.', '',
             'Prompt lengths below are actual tokenizer counts. The original 2055-token',
             'preparation point uses 16 generated tokens; each prefix uses eight.',
             'It is not the separate fixed2048/tg128 benchmark. Calibration points are',
             'reported separately and are not included in the graph.', '']
    for title, metric in [('Prefill (token/s)', 'prefill_tps'),
                          ('AR decode (token/s)', 'decode_tps')]:
        lines.extend(['## ' + title, '', '| Actual prompt tokens | Chunk 2048 | Chunk 4096 | Chunk 8192 |',
                      '| ---: | ---: | ---: | ---: |'])
        for i in range(2, len(report['curves']['2048'])):
            rows = [report['curves'][arm][i] for arm in report['order']]
            label = str(rows[0]['tokens']) + (' (preparation)' if i == 2 else '')
            values = [f'{row[metric]:.2f}' if row[metric] is not None else 'n/a' for row in rows]
            lines.append('| ' + ' | '.join([label, *values]) + ' |')
        lines.append('')
    lines.extend(['## Calibration observations', '',
                  '| Prompt tokens | Chunk | Prefill token/s | Decode token/s | Outputs |',
                  '| ---: | ---: | ---: | ---: | ---: |'])
    for arm in report['order']:
        for row in report['curves'][arm][:2]:
            tg = f"{row['decode_tps']:.2f}" if row['decode_tps'] is not None else 'n/a'
            lines.append(f"| {row['tokens']} | {arm} | {row['prefill_tps']:.2f} | {tg} | {row['output_tokens']} |")
    lines.extend(['', '## Output and observation limits', '',
                  'Short-output mismatches relative to chunk2048:', ''])
    for arm, cases in report['output_mismatch_cases'].items():
        lines.append(f"- Chunk {arm}: " + (', '.join(cases) if cases else 'none (all eleven exact).'))
    lines.extend(['', 'Eight decode calls do not qualify sustained TG128 or independent task quality.',
                  'Chunk partitioning can change arithmetic reduction order even with identical',
                  'compiled kernels. No weight precision is reduced.', '',
                  'OS page-cache state is not reset. Fixed execution order and whole-corpus',
                  'telemetry limit causal attribution of small differences to chunk size alone.',
                  'IOMMU remains enabled throughout; this is not an IOMMU on/off comparison.', '',
                  '[Graph](figures/q2-prefill-chunks128.png) ·',
                  '[Full-precision CSV](figures/q2-prefill-chunks128.csv) ·',
                  '[Machine-readable audit](../config/q2-prefill-chunks128-results.json)', ''])
    (ROOT / 'docs/Q2-PREFILL-CHUNKS-RESULTS.md').write_text('\n'.join(lines))


def main():
    window = module('chunk_window', 'tools/q2-prefill-chunks128-window.py')
    helper = module('prior_audit', 'tools/analyze-q2-decode-down-rows-native128-performance.py')
    plan_path = ROOT / 'config/q2-prefill-chunks128-plan.json'
    plan = read(plan_path)
    require(sha(EVIDENCE / 'plan.json') == sha(plan_path), 'Frozen plan differs')
    require(sha(ROOT / 'tools/q2-prefill-chunks128-window.py') == plan['runner_sha256'],
            'Measured validator differs')
    artifacts = read(EVIDENCE / 'artifact-hashes.json')
    for name, digest in artifacts.items():
        require(sha(EVIDENCE / name) == digest, 'Collected artifact differs: ' + name)
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE / name) == digest, 'Staged artifact differs: ' + name)
    for name in ('cpu-test', 'verify', 'admit', 'run', 'release'):
        require(read(EVIDENCE / (name + '-command.json'))['exit_code'] == 0,
                'Command failed: ' + name)
    build = read(ROOT / 'config/q2-prefill-chunks-build.json')
    require(build['server_sha256'] == plan['candidate_server']['sha256'] and
            build['device_functions'] == build['device_functions_byte_exact'] == 923,
            'Build contract differs')
    require(sha(ROOT / 'evidence/q2-prefill-chunks-preparation/device-code.json') ==
            plan['prior_device_code_check']['sha256'], 'Device code audit differs')
    release = read(EVIDENCE / 'release.json')
    result = read(EVIDENCE / 'results/native-result.json')
    closure = read(EVIDENCE / 'release-registry-check.json')
    require(result['state'] == release['pair_state'] == 'COMPLETE' and
            result['plan_sha256'] == release['plan_sha256'] == sha(plan_path) and
            release['pair_result_sha256'] == sha(EVIDENCE / 'results/native-result.json') and
            release['boot_id'] == plan['boot_id'] and
            all(release[k] for k in ('kfd_empty', 'original_model_stats_unchanged',
                                     'original_leases_free')) and
            not release['gpu_reserved'] and closure['registry_matches'] and
            closure['release_sha256'] == sha(EVIDENCE / 'release.json'), 'Closure differs')
    collection = read(EVIDENCE / 'local-collection-check.json')
    require(collection['all_sha256_verified'] and collection['at'] < release['at'],
            'Collection did not precede release')
    host = read(EVIDENCE / 'results/host-configuration.json')
    require('amd_iommu=off' not in host['cmdline'] and host['iommu_groups'] > 0 and
            plan['iommu_mode'] == 'on', 'IOMMU enabled contract differs')
    for phase in ('before', 'after'):
        window.validate_power(read(EVIDENCE / ('results/power-' + phase + '.json')))
    cases = [json.loads(line) for line in (EVIDENCE / 'requests.jsonl').read_text().splitlines()]
    curves, telemetry, outputs = {}, {}, {}
    require(result['order'] == plan['order'] == ['2048', '4096', '8192'] and
            len(result['arms']) == 3, 'Curve order differs')
    for index, arm in enumerate(plan['order']):
        tag = f'{index:02d}-{arm}'
        children = read(EVIDENCE / ('results/' + tag + '.children.json'))
        require(children['server_exit_code'] == children['client_exit_code'] == 0,
                'Child failed: ' + arm)
        raw = EVIDENCE / ('results/' + tag + '.jsonl')
        checked = window.validate_output(raw, cases, int(arm))
        saved = result['arms'][index]
        require(saved['arm'] == arm and saved['output_sha256'] == sha(raw) and
                saved['server_sha256'] == plan['candidate_server']['sha256'] and
                saved['client_sha256'] == plan['client']['sha256'], 'Arm identity differs')
        for key, value in checked.items():
            require(json.loads(json.dumps(value)) == saved[key], 'Persisted value differs: ' + key)
        curves[arm] = checked['rows']
        outputs[arm] = checked['outputs']
        telemetry[arm] = helper.telemetry(raw.with_suffix('.telemetry.jsonl'))
        require(telemetry[arm]['sampled_peak_cpu_mc'] <= 98000, 'Thermal gate exceeded')
    comparisons = {}
    for arm in ('4096', '8192'):
        comparisons[arm] = [dict(case=new['case'], tokens=new['tokens'],
            prefill_change_percent=100 * (new['prefill_tps'] / old['prefill_tps'] - 1),
            decode_change_percent=(100 * (new['decode_tps'] / old['decode_tps'] - 1)
                                   if new['decode_tps'] and old['decode_tps'] else None),
            output_exact=(outputs[arm][i] == outputs['2048'][i]))
            for i, (old, new) in enumerate(zip(curves['2048'], curves[arm]))]
    report = dict(schema='synapse-lie.q2-prefill-chunks128-audit.v1',
        source_commit=plan['source_commit'], plan_sha256=sha(plan_path),
        server_sha256=plan['candidate_server']['sha256'], client_sha256=plan['client']['sha256'],
        requests_sha256=plan['requests']['sha256'], boot_id=plan['boot_id'],
        iommu_mode='on', iommu_groups=host['iommu_groups'], cmdline=host['cmdline'],
        order=plan['order'], context_capacity=plan['capacity'], curves=curves,
        comparisons_to_2048=comparisons, telemetry=telemetry,
        output_mismatch_cases={arm: [row['case'] for row in comparisons[arm]
                                    if not row['output_exact']] for arm in comparisons},
        cached_tokens=0, ssd_cached_tokens=0, all_commands_exit_zero=True,
        release_at=release['at'], release_sha256=sha(EVIDENCE / 'release.json'),
        artifact_count=len(artifacts), boot_changed=False, new_weight_quantization=False,
        sustained_tg128_measured=False, independent_task_quality_qualified=False,
        limits=['One full original eleven-request curve per chunk, in fixed 2K/4K/8K order.',
                'Cold inference state, not an OS-page-cache flush; zero prefix/SSD reuse.',
                'Prefix cases use eight AR calls; 2055-token preparation uses sixteen.',
                'Preparation and calibration points are not the separate fixed2048/tg128 test.',
                'IOMMU groups establish enabled state, not translated versus passthrough mode.',
                'Telemetry spans each full corpus, not isolated prefill kernels.',
                'Exact short replies do not establish independent task quality.'])
    (ROOT / 'config/q2-prefill-chunks128-results.json').write_text(json.dumps(report, indent=2) + '\n')
    directory = ROOT / 'docs/figures'
    directory.mkdir(exist_ok=True)
    with (directory / 'q2-prefill-chunks128.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(curves['2048'][0]))
        writer.writeheader()
        for curve in curves.values():
            writer.writerows(curve)
    tables(report)
    print(json.dumps(dict(final={arm: curve[-1] for arm, curve in curves.items()},
                          output_mismatch_cases=report['output_mismatch_cases']), indent=2))


if __name__ == '__main__':
    main()
