# SPDX-License-Identifier: MIT
"""Bind a static profiler audit to saved evidence; never execute GPU work."""
import collections
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import statistics
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'evidence/q2-retained-counter-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


commands = {}
for label in ('installed-files', 'installed-metrics', 'installed-libraries',
              'upstream-notes', 'upstream-fixes'):
    path = BASE / (label + '-command.json')
    command = read(path)
    assert command['exit_code'] == 0, label
    commands[label] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                           finished_at=command['finished_at'], exit_code=0,
                           stdout_sha256=sha(BASE / (label + '-stdout.txt')),
                           stderr_sha256=sha(BASE / (label + '-stderr.txt')))

installation = read(BASE / 'installed-metrics-stdout.txt')
libraries = read(BASE / 'installed-libraries-stdout.txt')
launcher = read(BASE / 'installed-files-stdout.txt')
assert not installation['gpu_initialized'] and not installation['profiler_executed']
assert not libraries['gpu_initialized'] and not libraries['profiler_executed']
files = {}
for item in installation['files']:
    data = item['text'].encode()
    assert hashlib.sha256(data).hexdigest() == item['sha256']
    assert len(data) == item['bytes']
    files[item['path']] = item
definition = files['/opt/rocm/share/rocprofiler-sdk/counter_defs.yaml']
rows = []
for counter in yaml.safe_load(definition['text'])['rocprofiler-sdk']['counters']:
    definitions = [d for d in counter['definitions'] if 'gfx1151' in d['architectures']]
    assert len(definitions) <= 1
    if definitions:
        rows.append(dict(name=counter['name'], description=counter['description'],
                         **{k: v for k, v in definitions[0].items() if k != 'architectures'}))
names = {r['name'] for r in rows}
assert len(names) == len(rows) == 64
assert hashlib.sha256(launcher['launcher'].encode()).hexdigest() == launcher['launcher_sha256']

upstream = []
for label in ('upstream-notes', 'upstream-fixes'):
    for item in read(BASE / (label + '.json'))['records']:
        assert sha(BASE / item['file']) == item['sha256']
        upstream.append(item)
patch = read(BASE / 'gfx115-counters-files.json')[0]['patch']
new_names = re.findall(r'^\+\s+- name: (\S+)', patch, re.M)
assert len(new_names) == 26 and not (set(new_names) & names)
fixes = []
for label in ('gl2c-fix-pr', 'sq-fix-pr', 'gfx115-counters-pr'):
    item = read(BASE / (label + '.json'))
    fixes.append({k: item[k] for k in ('html_url', 'title', 'merged_at', 'merge_commit_sha')})

# Read only the GPU identity in the earlier trace. Do not relabel its timings
# as belonging to the newer retained binary.
trace_root = ROOT / 'evidence/q2-current-best-profile-r1/results'
trace = trace_root / 'profile/q2_results.db'
receipt = read(trace_root / 'result.json')
assert sha(trace) == receipt['artifacts']['profile/q2_results.db']['sha256']
db = sqlite3.connect('file:' + str(trace) + '?mode=ro', uri=True)
tables = [row[0] for row in db.execute("select name from sqlite_master where type='table'")
          if re.fullmatch(r'rocpd_info_agent_[a-z0-9_]+', row[0])]
assert len(tables) == 1
gpu_rows = db.execute('select extdata from ' + tables[0] + " where type='GPU'").fetchall()
assert len(gpu_rows) == 1
agent = json.loads(gpu_rows[0][0])
db.close()
agent_fields = ('name', 'product_name', 'cu_count', 'simd_count', 'wave_front_size',
                'array_count', 'num_shader_banks', 'simd_arrays_per_engine', 'cu_per_simd_array')

retained_path = ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'
assert sha(retained_path) == 'f11b8e3e7663ce78de183032a924358e8429ea953a66cc0dd86849359852acdd'
retained = read(retained_path)
samples = [s for s in retained['model']['samples'] if not s['warmup']]
assert len(samples) == 3
report = dict(
    schema='synapse-lie.q2-retained-counter-capabilities.v1',
    state='STATIC_INSTALLATION_AUDIT_NOT_RUNTIME_COUNTER_QUALIFICATION',
    architecture='gfx1151', rocm_version=files['/opt/rocm/.info/version']['text'].strip(),
    commands=commands,
    installed_files=[{k: v for k, v in row.items() if k != 'text'} for row in files.values()],
    launcher=dict(path=launcher['launcher_path'], sha256=launcher['launcher_sha256']),
    libraries=libraries['libraries'],
    counters=rows,
    counter_kind_counts=dict(collections.Counter(r.get('block', 'expression') for r in rows)),
    newer_pr_added_names_absent=new_names,
    upstream_evidence=upstream, upstream_fixes=fixes,
    saved_gpu_identity=dict(source=str(trace.relative_to(ROOT)), sha256=sha(trace),
                            fields={k: agent[k] for k in agent_fields}),
    retained=dict(report=str(retained_path.relative_to(ROOT)), sha256=sha(retained_path),
                  binary_sha256=retained['model']['binary_sha256'],
                  prefill_tok_s=statistics.median(s['prefill_tok_s'] for s in samples),
                  decode_steps_s=statistics.median(s['decode_steps_s'] for s in samples)),
    findings=[
        '64 explicit gfx1151 definitions: 31 hardware counters and 33 expressions/constants. Definition presence does not prove collection works.',
        'The installed SDK test skips its positive SQ_WAVES assertion on gfx1151. That skip alone does not prove broken counters.',
        'The installed SDK ELF requires external libhsa-amd-aqlprofile64.so.1 and imports aqlprofile_register_agent, not aqlprofile_register_agent_info. The harvested-WGP V2 route added by PR8229 is not established.',
        'Saved target is Radeon 8060S with 40 CUs; the PR8229 reproduction used harvested parts. Do not assume its failure occurs on this target.',
        'PR3100 changes GL2C instance count from four to eight. The installed YAML formula cannot establish the linked binary includes that fix.',
        'All 26 new counter names added by PR10041 are absent. Do not substitute events from other architectures or modify runtime definitions.',
        'FETCH_SIZE is a byte-weighted request sum divided by 1024, therefore KiB; it is not a byte count. It does not independently identify DRAM traffic beyond the shared cache.',
        'Static VGPR/LDS limits and the prior1571 dispatch trace do not measure active occupancy, stalls or bandwidth of retained1585.',
    ],
    next_diagnostic=dict(
        state='PROPOSED_NOT_ADMITTED_OR_EXECUTED',
        admission='Fresh coordinated four-lease admission after compact-LDS release; no standing reservation.',
        controls='Small owned HIP calibration with deterministic complete output and fixed wave32 launch geometry. No model or benchmark reference rerun.',
        passes=[
            dict(counters=['SQ_WAVES_sum'], check='Known grid/32 per kernel across ten repetitions; all complete output checks pass.'),
            dict(counters=['SQ_WAVES_sum', 'GRBM_COUNT'], check='The same exact wave totals with co-collection; record per-instance data and rejected passes.'),
            dict(counters=['FETCH_SIZE'], check='Coalesced read of known incompressible bytes beyond32MiB; inspect GL2C instance coverage and units. Predeclare calibration tolerance including cache effects.'),
        ],
        after_calibration='Only qualified counter groups may profile the already saved retained1585 binary with exact binary/source/runtime checks. Filter relevant kernels and keep profiled times outside benchmark results.',
        unavailable_counters='Use separate retained dispatch tracing and controlled numerical changes if necessary; no driver, package or profiler patches.',
    ),
    gpu_run=False, model_inference=False, model_build=False, gpu_reserved=False,
    controls_rerun=False, numerical_change=False, throughput_change_claimed=False,
    runtime_counter_qualified=False, goal_met=False,
)
destination = ROOT / 'config/q2-retained-counter-capabilities.json'
encoded = json.dumps(report, indent=2) + '\n'
if sys.argv[1:] == ['--check']:
    assert destination.read_text() == encoded, 'Saved capability report differs'
elif not sys.argv[1:]:
    with destination.open('x') as stream:
        stream.write(encoded)
else:
    raise SystemExit('Expected no arguments or --check')
print(json.dumps(dict(report=str(destination.relative_to(ROOT)), sha256=sha(destination),
                      counters=len(rows), runtime_qualified=False, gpu_run=False)))
