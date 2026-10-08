#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare isolated per-descriptor I/O advice and row-cache capacity probes."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = Path('src/models/qwen38_flash_next/ngram.cpp')


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected source: ' + before[:80])
    return text.replace(before, after)


def main():
    reports = {}
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ('q2', 'ud'):
        base = ROOT / ('.deps/gufo-ple-' + name)
        out = ROOT / ('.deps/gufo-ple-io-' + name)
        shutil.copytree(base, out)
        text = once((out / REL).read_text(), '#include "q2_ple_diag.hpp"',
                    '#include "q2_ple_diag.hpp"\n#include "q2_ple_io.hpp"')
        text = once(text, '  t->cache_count_ = std::bit_floor(kCacheBytes / t->row_bytes_);',
                    '''  const std::size_t cache_budget =
      type == core::GgmlType::kBF16 && row_dim == 160
          ? q2pleio::bf16_cache_budget : kCacheBytes;
  t->cache_count_ = std::bit_floor(cache_budget / t->row_bytes_);''')
        text = once(text, '  const std::size_t workers = std::min(',
                    '''  // Advice applies to this separately opened reader descriptor only.
  // No DONTNEED/WILLNEED, cache eviction, file mutation or global tuning.
  q2pleio::advice_result = ::posix_fadvise(t->fd_, 0, 0, q2pleio::advice);
  const std::size_t workers = std::min(''')
        (out / REL).write_text(text)
        shutil.copyfile(ROOT / 'tests/q2_ple_io.hpp', out / 'q2_ple_io.hpp')
        subprocess.run(['clang-format', '-i', str(out / REL), str(out / 'q2_ple_io.hpp')], check=True)
        changes = [str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()
                   and p.read_bytes() != (out / p.relative_to(base)).read_bytes()]
        if changes != [str(REL)]:
            raise ValueError('Unexpected source changes')
        patch = ''.join(difflib.unified_diff((base / REL).read_text().splitlines(True),
                        (out / REL).read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL)))
        patch += ''.join(difflib.unified_diff([], (out / 'q2_ple_io.hpp').read_text().splitlines(True),
                         fromfile='/dev/null', tofile='b/q2_ple_io.hpp'))
        p = ROOT / ('experiments/q2-ple-io-' + name + '.patch')
        p.write_text(patch)
        reports[name] = dict(base=str(base.relative_to(ROOT)), base_ngram_sha256=sha(base / REL),
                            ngram_sha256=sha(out / REL), added_header_sha256=sha(out / 'q2_ple_io.hpp'),
                            patch_sha256=sha(p))
    (ROOT / 'config/q2-ple-io-source.json').write_text(json.dumps(dict(
        scope='Diagnostic-only per-descriptor advice and BF16 cache budgets; no model arithmetic changes',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', variants=reports), indent=2) + '\n')


if __name__ == '__main__':
    main()
