#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an unapplied launcher patch; preserve the frozen row-group campaign."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'evidence/q2-ssm-followup-runtime-preparation'
VARIANTS = ('ssm-fixed-shape', 'ssm-fixed-bounds', 'ssm-compact-lds', 'ssm-pingpong')
PATCH = 'experiments/q2-ssm-followup-runtime.patch'
BINDING = 'config/q2-ssm-followup-runtime-source.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen():
    plan = json.loads((ROOT / 'config/q2-ssm-row-group-plan.json').read_text())
    bindings = {**plan['fixtures'], **plan['manifests'],
                plan['window_helper']: plan['window_helper_sha256']}
    for path, digest in bindings.items():
        if sha(ROOT / path) != digest:
            raise ValueError('Frozen campaign changed: ' + path)
    return bindings


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Unexpected patch anchor count: ' + old[:100])
    return text.replace(old, new)


def patched_files():
    remote = (ROOT / 'tools/q2-remote.py').read_text()
    constants = """SSM_FOLLOWUP_MANIFEST = 'config/q2-ssm-followup-runtime-source.json'
SSM_FOLLOWUP_VARIANTS = ('ssm-fixed-shape', 'ssm-fixed-bounds', 'ssm-compact-lds', 'ssm-pingpong')
SSM_FOLLOWUP_SOURCES = {'q2-counting-' + v: v for v in SSM_FOLLOWUP_VARIANTS}
SSM_FOLLOWUP_MODES = {v + '-check': v for v in SSM_FOLLOWUP_VARIANTS}
"""
    remote = replace(remote, "DOWN_REGISTER_SCATTER_MANIFEST =", constants + "DOWN_REGISTER_SCATTER_MANIFEST =")
    remote = replace(remote, '**SSM_ROW_GROUP_SOURCES,', '**SSM_ROW_GROUP_SOURCES, **SSM_FOLLOWUP_SOURCES,')
    remote = replace(remote, 'SSM_ROW_GROUP_MODE: 8 * 1024**3,',
                     'SSM_ROW_GROUP_MODE: 8 * 1024**3, **{mode: 8 * 1024**3 for mode in SSM_FOLLOWUP_MODES},')
    remote = replace(remote, 'HALF_CONSUMER_EIGHT_MODE, SSM_ROW_GROUP_MODE,',
                     'HALF_CONSUMER_EIGHT_MODE, SSM_ROW_GROUP_MODE, *SSM_FOLLOWUP_MODES,')
    remote = replace(remote, '*SSM_ROW_GROUP_SOURCES.values(),',
                     '*SSM_ROW_GROUP_SOURCES.values(), *SSM_FOLLOWUP_VARIANTS,', count=2)
    guard = """    if args.source_variant in SSM_FOLLOWUP_VARIANTS or args.mode in SSM_FOLLOWUP_MODES:
        if SSM_FOLLOWUP_MODES.get(args.mode) == args.source_variant:
            if args.rebuild_mmq:
                p.error('Q2 SSM follow-up component builds its numerical kernels directly')
        elif SSM_FOLLOWUP_SOURCES.get(args.mode) != args.source_variant:
            p.error('Historical counting requires its matched provider' if args.mode in COUNTING_SOURCES
                    else 'Q2 SSM follow-up requires its component or matched historical counting provider')
"""
    remote = replace(remote, '    if args.source_variant in SSM_ROW_GROUP_SOURCES.values() or args.mode == SSM_ROW_GROUP_MODE:',
                     guard + '    if args.source_variant in SSM_ROW_GROUP_SOURCES.values() or args.mode == SSM_ROW_GROUP_MODE:')
    helper = """def ssm_followup_source(parser, name):
    info = json.loads((ROOT / SSM_FOLLOWUP_MANIFEST).read_text())['variants'][name]
    for path, digest in info['bindings'].items():
        if file_sha256(ROOT / path) != digest:
            parser.error('Q2 SSM follow-up source or fixture binding changed')
    variant = json.loads((ROOT / info['manifest']).read_text())['variants'][name]
    for key, digest in variant.items():
        if key.endswith('_sha256'):
            if file_sha256(ROOT / variant[key[:-7]]) != digest:
                parser.error('Q2 SSM follow-up measured source reference changed')
    source = variant['source']
    actual = {str(f.relative_to(ROOT / source)): file_sha256(f)
              for f in (ROOT / source).rglob('*') if f.is_file()}
    if actual != variant['files'] or len(actual) != 1027:
        parser.error('Q2 SSM follow-up provider inventory changed')
    return source


"""
    remote = replace(remote, 'def main():\n', helper + 'def main():\n')
    remote = replace(remote, "'experiments/q2-ssm-row-group-oracle.inc',",
                     "'experiments/q2-ssm-row-group-oracle.inc', 'experiments/q2-ssm-compact-lds-oracle.inc',")
    remote = replace(remote, '        if args.source_variant in SSM_ROW_GROUP_SOURCES.values():',
                     '        if args.source_variant in SSM_FOLLOWUP_VARIANTS:\n'
                     '            source = ssm_followup_source(p, args.source_variant)\n'
                     '        if args.source_variant in SSM_ROW_GROUP_SOURCES.values():')

    runner = (ROOT / 'tools/q2-runner.py').read_text()
    model_modes = ', '.join(repr('q2-counting-' + v) for v in VARIANTS)
    component_modes = ', '.join(repr(v + '-check') for v in VARIANTS)
    runner = replace(runner, "'q2-counting-ssm-row-group',", "'q2-counting-ssm-row-group', " + model_modes + ',')
    runner = replace(runner, "'ssm-row-group-check',", "'ssm-row-group-check', " + component_modes + ',', count=2)
    runner = replace(runner, "    hc_target = 'q2_ssm_row_group'",
                     "    hc_target = 'q2_ssm_compact_lds' if mode in ('ssm-compact-lds-check', 'ssm-pingpong-check') else 'q2_ssm_row_group' if mode in ('ssm-fixed-shape-check', 'ssm-fixed-bounds-check') else 'q2_ssm_row_group'")

    cmake = (ROOT / 'cmake/hip/CMakeLists.txt').read_text()
    start = cmake.index('# SSM row-group4 composition;')
    end = cmake.index('\n\n', start)
    block = cmake[start:end].replace('q2_ssm_row_group', 'q2_ssm_compact_lds')
    block = block.replace('# SSM row-group4 composition; literal retained1580 projection control.',
                          '# Compact-LDS and alternating-slot SSM; retained1580 control and resource limits.')
    cmake = cmake[:end] + '\n\n' + block + cmake[end:]
    return {'tools/q2-remote.py': remote, 'tools/q2-runner.py': runner,
            'cmake/hip/CMakeLists.txt': cmake}


def main():
    original_bindings = frozen()
    changes = patched_files()
    PREP.mkdir(exist_ok=True)
    overlay = PREP / 'overlay'
    overlay.mkdir()
    registry = {}
    for variant in VARIANTS:
        manifest = 'config/q2-' + variant + '-source.json'
        family = 'row_group' if variant in VARIANTS[:2] else 'compact_lds'
        fixture = 'tests/q2_ssm_' + family + '.hip'
        oracle = 'experiments/q2-ssm-' + family.replace('_', '-') + '-oracle.inc'
        bindings = [manifest, fixture, oracle, 'experiments/q2-ssm-row-group-control.inc']
        registry[variant] = dict(manifest=manifest, fixture=fixture,
                                 event_prefix='ssm_' + family,
                                 component_mode=variant + '-check',
                                 model_mode='q2-counting-' + variant,
                                 bindings={p: sha(ROOT / p) for p in bindings})
    with (ROOT / BINDING).open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-ssm-followup-runtime-source.v1',
                       variants=registry, applied=False, gpu_run=False), stream, indent=2)
        stream.write('\n')
    # Durable, local-only copy. The intermediate .deps link preserves all provider
    # paths; archive.add(source directory) still archives regular source files.
    for directory in ('tools', 'tests', 'config', 'cmake', 'experiments'):
        shutil.copytree(ROOT / directory, overlay / directory,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(ROOT / 'CMakeLists.txt', overlay / 'CMakeLists.txt')
    (overlay / '.deps').symlink_to(ROOT / '.deps', target_is_directory=True)
    (overlay / 'evidence').mkdir()
    diff = []
    for name, text in changes.items():
        before = (ROOT / name).read_text()
        diff.extend(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                                         fromfile='a/' + name, tofile='b/' + name))
        (overlay / name).write_text(text)
    with (ROOT / PATCH).open('x') as stream:
        stream.writelines(diff)
    if frozen() != original_bindings:
        raise ValueError('Frozen binding set changed')
    receipt = dict(schema='synapse-lie.q2-ssm-followup-runtime-preparation.v1',
                   patch=PATCH, patch_sha256=sha(ROOT / PATCH),
                   registry=BINDING, registry_sha256=sha(ROOT / BINDING),
                   original_files={p: sha(ROOT / p) for p in changes},
                   prepared_files={p: sha(overlay / p) for p in changes},
                   frozen_fixtures=88, frozen_manifests=5, window_helper_unchanged=True,
                   patch_applied=False, remote_run=False, gpu_run=False, goal_met=False)
    with (PREP / 'preparation.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
