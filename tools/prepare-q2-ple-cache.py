#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a bounded 65,536-row BF16 PLE cache; leave IQ4 capacity unchanged."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = Path('src/models/qwen38_flash_next/ngram.cpp')


def main():
    reports = {}
    for name, base_name, out_name in [
            ('raw', 'gufo-q2-bench-hc-moe-fused', 'gufo-q2-bench-ple-cache64k'),
            ('diagnostic', 'gufo-ple-q2', 'gufo-ple-cache64k')]:
        base, out = ROOT / '.deps' / base_name, ROOT / '.deps' / out_name
        shutil.copytree(base, out)
        source = (base / REL).read_text()
        old = '  t->cache_count_ = std::bit_floor(kCacheBytes / t->row_bytes_);'
        if source.count(old) != 1:
            raise ValueError('Unexpected measured source')
        source = source.replace(old, '''  // Equal retained row count for this original BF16 table and IQ4_NL.
  // At 160 columns this allocates 20 MiB of encoded rows (plus metadata),
  // instead of 5 MiB. All other shapes/formats keep the original budget.
  const std::size_t cache_budget =
      type == core::GgmlType::kBF16 && row_dim == 160
          ? 32 * 1024 * 1024 : kCacheBytes;
  t->cache_count_ = std::bit_floor(cache_budget / t->row_bytes_);''')
        (out / REL).write_text(source)
        subprocess.run(['clang-format', '-i', str(out / REL)], check=True)
        changes = [str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()
                   and p.read_bytes() != (out / p.relative_to(base)).read_bytes()]
        if changes != [str(REL)]:
            raise ValueError('Unexpected changed files')
        patch = ROOT / ('experiments/q2-ple-cache64k-' + name + '.patch')
        patch.write_text(''.join(difflib.unified_diff((base / REL).read_text().splitlines(True),
                         (out / REL).read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL))))
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        reports[name] = {'base': base_name, 'out': out_name, 'base_sha256': sha(base / REL),
                         'candidate_sha256': sha(out / REL), 'patch_sha256': sha(patch)}
    (ROOT / 'config/q2-ple-cache64k-source.json').write_text(json.dumps(dict(
        scope='Isolated BF16 capacity experiment; kernels and all row values unchanged',
        original_encoded_bytes=5242880, candidate_encoded_bytes=20971520,
        metadata_entries_before=16384, metadata_entries_after=65536, variants=reports), indent=2) + '\n')


if __name__ == '__main__':
    main()
