#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compose retained Q8, row-reuse and optional norm probes on the fixed parent."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
KERNEL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
ROW = 'src/models/qwen38_flash_next/kernels/rocm/q2_scaled_input.inc'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob('*') if p.is_file()}


def kernel_span(source, name):
    anchor = '__global__ void '+name+'Kernel('
    if source.count(anchor) != 1:
        raise ValueError('Unexpected kernel anchor')
    start = source.index(anchor)
    end = source.index('\n}\n', start)+3
    return start, end


def compose_norm(base, current, candidate):
    for name in ('HcCombineF32Half', 'HcCombineMoeF32Half'):
        a, b = kernel_span(base, name)
        c, d = kernel_span(current, name)
        e, f = kernel_span(candidate, name)
        if current[c:d] != base[a:b]:
            raise ValueError('Norm preimage differs on the Q8 composition')
        current = current[:c]+candidate[e:f]+current[d:]
    return current


def main():
    names = ('q2-iq2-mixed-model-source.json', 'q2-shared-q8-producer-source.json',
             'q2-scaled-row-reuse-source.json', 'q2-norm-fixed-shape-source.json')
    manifests = {n: json.loads((ROOT/'config'/n).read_text()) for n in names}
    for m in manifests.values():
        if inventory(ROOT/m['candidate']) != m['files']:
            raise ValueError('Retained provider inventory changed')
    mixed, q8, row, norm = (manifests[n] for n in names)
    if q8['base'] != mixed['candidate'] or norm['base'] != mixed['candidate']:
        raise ValueError('Fixed-reference parent differs')
    for name in ('q2-shared-q8-producer-source.json', 'q2-norm-fixed-shape-source.json'):
        if manifests[name]['parent_manifest_sha256'] != sha(ROOT/'config'/names[0]):
            raise ValueError('Fixed-reference parent manifest changed')
    base, q8_root = ROOT/mixed['candidate'], ROOT/q8['candidate']
    if (base/ROW).read_bytes() != (ROOT/row['base']/ROW).read_bytes():
        raise ValueError('Row-reuse preimage differs from the fixed reference')
    result_path = ROOT/'config/q2-reaudit-composition-source.json'
    if result_path.exists():
        raise ValueError('Refusing to overwrite composition manifest')
    variants = {}
    for key, with_norm in [('reaudit-q8-row', False), ('reaudit-q8-row-norm', True)]:
        output = ROOT/'.deps'/('gufo-q2-'+key)
        patch_path = ROOT/'experiments'/('q2-'+key+'.patch')
        if output.exists() or patch_path.exists():
            raise ValueError('Refusing to overwrite a retained composition')
        shutil.copytree(q8_root, output)
        (output/ROW).write_bytes((ROOT/row['candidate']/ROW).read_bytes())
        if with_norm:
            (output/KERNEL).write_text(compose_norm((base/KERNEL).read_text(),
                (output/KERNEL).read_text(), (ROOT/norm['candidate']/KERNEL).read_text()))
        files = inventory(output)
        changed = sorted(n for n in files if files[n] != mixed['files'][n])
        if files.keys() != mixed['files'].keys() or changed != sorted(q8['changed_files']+[ROW]):
            raise ValueError('Unexpected composition delta')
        patch_path.write_text(''.join(''.join(difflib.unified_diff(
            (base/n).read_text().splitlines(True), (output/n).read_text().splitlines(True),
            fromfile='a/'+n, tofile='b/'+n)) for n in changed))
        variants[key] = dict(source=str(output.relative_to(ROOT)), files=files,
            changed_files=changed, unchanged_files=len(files)-len(changed),
            patch_sha256=sha(patch_path), norm_composed=with_norm,
            mechanisms=['shared-Q8 producer', 'bounded640-column row input reuse']+
                       (['retained fixed-shape paired norm'] if with_norm else []),
            runtime_validated=False, promoted=False)
    report = dict(schema='synapse-lie.q2-reaudit-composition-source.v1',
        base=mixed['candidate'], parent_manifest_sha256=sha(ROOT/'config'/names[0]),
        retained_manifests={str(Path('config')/n): sha(ROOT/'config'/n) for n in names},
        variants=variants, fixed_reference='config/q2-fixed-prefill-reference.json',
        arithmetic='Exact arm adds only the previously byte-exact row-reuse body to the model-exact Q8 producer. Norm arm replaces only the two retained norm bodies; its known logit changes remain open.',
        unchanged='Original weights, mixed IQ2 routing, activation scale/max order, output layout, stream/buffer policy, decode dispatch and MTP.',
        scope='Owner-authorized exploratory fixed-model rechecks after component numeric rejections; only new candidates, no controls rerun or context curve.',
        independent_thresholds_changed=False, model_inference=False, goal_met=False)
    result_path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:{n:v[n] for n in ('source','changed_files','norm_composed')}
                      for k,v in variants.items()}))


if __name__ == '__main__':
    main()
