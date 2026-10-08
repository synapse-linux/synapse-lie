#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare an LDS-free half-output epilogue from the retained 1574 provider."""
import argparse
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/q2_down_half_storage.inc'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair-exchange', action='store_true')
    args = parser.parse_args()
    suffix = '-pair' if args.pair_exchange else ''
    parent_path = ROOT/'config/q2-scaled-wave-pack-source.json'
    parent = json.loads(parent_path.read_text())['variants']['scaled-wave-pack']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Saved1574 provider inventory changed')
    out = ROOT/('.deps/gufo-q2-down-register-scatter'+suffix+'-run')
    manifest = ROOT/('config/q2-down-register-scatter'+suffix+'-source.json')
    patch = ROOT/('experiments/q2-down-register-scatter'+suffix+'.patch')
    control = ROOT/('experiments/q2-down-register-scatter'+suffix+'-control.inc')
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite an experiment')
    original = (base/REL).read_text()
    kernel = function(original,
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    fragment_path = ROOT/('experiments/q2-down-register-scatter'+suffix+'-epilogue.inc')
    fragment = fragment_path.read_text()
    anchor = '  if (out_half == nullptr) {\n'
    replacement = once(kernel, anchor, anchor + fragment)
    # Format the changed template only. Preserve every other source body.
    fmt = subprocess.run(['/opt/rocm/llvm/bin/clang-format', '--sort-includes=false',
                          '--style=file:'+str(base/'.clang-format'),
                          '--assume-filename='+str(base/REL)],
                         input=replacement, text=True, capture_output=True)
    if fmt.returncode:
        raise ValueError('Template formatting failed: '+fmt.stderr)
    changed = once(original, kernel, fmt.stdout.rstrip())
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1027 and delta == [REL]
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal retained1574 down; only renamed for the new component fixture.\n'+
        kernel.replace('RoutedQ2HalfStorageKernel', 'RoutedQ2RegisterScatterControlKernel')+'\n')
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
    measured = ROOT/'config/q2-scaled-wave-pack-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)), measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        fragment=str(fragment_path.relative_to(ROOT)), fragment_sha256=sha(fragment_path),
        mechanism='Exchange '+('two selected' if args.pair_exchange else 'four')+' already-rounded half-pair words between corresponding half-wave lanes; interleave even/odd columns into one128-bit store per lane without epilogue LDS loads/stores or wave barriers.',
        exchanged_words_per_lane=2 if args.pair_exchange else 4,
        numerical_contract='Retain each original F32 inverse-scale product, explicit F32 rounding anchor and RN-even F16 conversion. Transpose only raw half bits. Preserve WMMA, K order, routing, slot-major output and consumer.',
        dispatch='Only aligned output with m divisible by8; original LDS epilogue remains literal fallback for every other width/base. Scalar decode and executor dispatch unchanged.',
        additional_allocations=0, additional_streams=0, additional_block_barriers=0,
        lds_allocation_capacity_unchanged=True, parent_rebuilt=False,
        risks='Permlane and selection instructions, different lane-to-store mapping and register scheduling may cost more than LDS; static simplification is not GPU throughput evidence.',
        inherited_quality='Saved1574 inherits the measured F16 expert-output precision change; independent Core19 task quality remains open.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as f:
        json.dump(dict(schema='synapse-lie.q2-down-register-scatter-source.v1',
                       variants={'down-register-scatter':variant}, gpu_run=False, goal_met=False), f, indent=2)
        f.write('\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta, gpu_run=False)))


if __name__ == '__main__':
    main()
