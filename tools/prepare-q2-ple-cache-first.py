#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare cache hits before publishing colliding PLE misses; no capacity change."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/ngram.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT/'config/q2-curve-source.json'
    parent = json.loads(parent_path.read_text())['variants']['q2']
    base = ROOT/parent['source']
    actual = {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()}
    if actual != parent['files']:
        raise ValueError('Canonical Q2 parent changed')
    original = (base/REL).read_text()
    old = '''  if (ReadCached(row, dst)) {
    return true;
  }
'''
    before = '''  if (jobs_.size() >= kBatchJobs) {
    std::sort(jobs_.begin(), jobs_.end(),
              [](const Job& a, const Job& b) { return a.row < b.row; });
  } else {
    // Small cached gathers avoid waking the I/O pool for every decode
    // token. Large prefills still parallelize their row conversions.
    std::erase_if(
        jobs_, [this](const Job& job) { return ReadCached(job.row, job.dst); });
  }'''
    after = '''  // Consume every resident row before publishing misses: an earlier
  // miss must not evict a later hit in the same gather. Rows are unique,
  // and no previous gather is active, so workers need no second lookup.
  std::erase_if(
      jobs_, [this](const Job& job) { return ReadCached(job.row, job.dst); });
  if (jobs_.size() >= kBatchJobs) {
    std::sort(jobs_.begin(), jobs_.end(),
              [](const Job& a, const Job& b) { return a.row < b.row; });
  }'''
    if original.count(old) != 1 or original.count(before) != 1:
        raise ValueError('Unexpected canonical PLE control flow')
    changed = original.replace(old, '').replace(before, after)
    out = ROOT/'.deps/gufo-q2-curve-ple-cache-first'
    if out.exists():
        raise ValueError('Refusing to overwrite cache-first candidate')
    shutil.copytree(base, out)
    (out/REL).write_text(changed)
    files = {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()}
    if files.keys() != actual.keys() or [k for k in actual if actual[k] != files[k]] != [REL]:
        raise ValueError('Unexpected changed source inventory')
    patch = ROOT/'experiments/q2-ple-cache-first.patch'
    patch.write_text(''.join(difflib.unified_diff(
        original.splitlines(True), changed.splitlines(True),
        fromfile='a/'+REL, tofile='b/'+REL)))
    report = dict(schema='synapse-lie.q2-ple-cache-first-source.v1',
        base=parent['source'], candidate=str(out.relative_to(ROOT)),
        files=files, changed_files=[REL], unchanged_files=len(files)-1,
        parent_manifest_sha256=sha(parent_path), patch_sha256=sha(patch),
        hypothesis='Retain all existing hits before colliding misses; same capacity and row bytes. Caller preparation cost and canonical PP/TG must be measured.',
        runtime_validated=False, promoted=False, goal_met=False)
    (ROOT/'config/q2-ple-cache-first-source.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(candidate=report['candidate'], changed_files=[REL])))


if __name__ == '__main__':
    main()
