#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a BF16 row-sized read trial on the retained numerical provider."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PARENT='config/q2-iq2-fixed-bounds-source.json'
NAME='q2-ple-row-bytes'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {p.relative_to(path).as_posix():sha(p) for p in path.rglob('*') if p.is_file()}


def main():
    parent=json.loads((ROOT/PARENT).read_text())['variants']['iq2-fixed-bounds']
    base=ROOT/parent['source']
    assert inventory(base)==parent['files']
    target=ROOT/'.deps/gufo-q2-ple-row-bytes-run'
    assert not target.exists(), 'Preserve existing candidate'
    shutil.copytree(base,target)
    name='src/models/qwen38_flash_next/ngram.cpp'
    old=(base/name).read_text()
    before='''  t->fd_ = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_DIRECT);
  t->direct_ = t->fd_ >= 0;'''
    after='''  // BF16/160 rows contain only320 bytes. On the tested compressed file,
  // O_DIRECT already falls back to buffered I/O, but our aligned window
  // still copies4096/8192 bytes. Use the existing exact-row read path.
  // This private descriptor permits reclaimable file-cache residency; it
  // changes neither the encoded row cache nor any embedding arithmetic.
  const bool exact_row = type == core::GgmlType::kBF16 && row_dim == 160;
  t->fd_ = ::open(path.c_str(), O_RDONLY | O_CLOEXEC |
                                  (exact_row ? 0 : O_DIRECT));
  t->direct_ = !exact_row && t->fd_ >= 0;'''
    assert old.count(before)==1
    new=old.replace(before,after)
    (target/name).write_text(new)
    # Compile this exact translation unit in private host fixtures too. All
    # declarations/quantization support come from the pinned unchanged source.
    fixture='experiments/'+NAME+'-ngram.cpp'
    (ROOT/fixture).write_text(new)
    patch='experiments/'+NAME+'.patch'
    (ROOT/patch).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),
        fromfile='a/'+name,tofile='b/'+name)))
    files=inventory(target)
    assert {n for n in files if files[n]!=parent['files'][n]}=={name}
    report=dict(schema='synapse-lie.'+NAME+'-source.v1',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',candidate=str(target.relative_to(ROOT)),
        parent_manifest=PARENT,parent_manifest_sha256=sha(ROOT/PARENT),
        patch=patch,patch_sha256=sha(ROOT/patch),generator='tools/'+NAME.replace('q2-','prepare-q2-',1)+'.py',
        fixture=fixture,fixture_sha256=sha(ROOT/fixture),files=files,
        changed_files=[name],unchanged_files=len(files)-1,numerical_kernels_changed=False,
        cache_capacity_changed=False,model_files_changed=False,
        caveat='Buffered BF16 reads use reclaimable filesystem cache. No eviction or residency control; measure complete requests and record memory/I/O.',
        GPU_qualified=False,performance_qualified=False)
    report['generator_sha256']=sha(ROOT/report['generator'])
    output=ROOT/('config/'+NAME+'-source.json')
    with output.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(files=len(files),changed=[name],manifest_sha256=sha(output))))


if __name__=='__main__':main()
