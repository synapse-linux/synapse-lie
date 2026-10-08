#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Instrument PLE host work in isolated Q2/UD sources; no kernel changes."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = Path('src/models/qwen38_flash_next/ngram.cpp')


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Unexpected source: ' + old[:80])
    return source.replace(old, new)


def instrument(source):
    source = once(source, '#include <fcntl.h>', '#include "q2_ple_diag.hpp"\n\n#include <fcntl.h>')
    source = once(source, '  const std::uint32_t n = c.ple_ngram_size;',
                  '  q2ple::Timer timing{q2ple::hash_ns};\n  const std::uint32_t n = c.ple_ngram_size;')
    source = once(source, '  return t;\n}', '''  q2ple::cache_slots = t->cache_count_;
  q2ple::cache_bytes = t->cache_rows_.size();
  q2ple::workers = t->workers_.size();
  q2ple::direct = t->direct_;
  return t;
}''')
    source = once(source, '  if (type_ == core::GgmlType::kIQ4_NL) {',
                  '  q2ple::Timer timing{q2ple::decode_ns};\n  if (type_ == core::GgmlType::kIQ4_NL) {')
    source = once(source, '  if (hit) {\n    DecodeRow(',
                  '  if (hit) {\n    q2ple::Add(q2ple::cache_hits);\n    DecodeRow(')
    source = once(source, '  const std::uint64_t offset = base_offset_ + row * row_bytes_;',
                  '  q2ple::Add(q2ple::io_rows);\n  const std::uint64_t offset = base_offset_ + row * row_bytes_;')
    source = once(source, '    const ssize_t n = ::pread(fd_, base + got, length - got, begin + got);', '''    q2ple::Add(q2ple::pread_calls);
    q2ple::Add(q2ple::requested_bytes, length - got);
    ssize_t n;
    {
      q2ple::Timer timing{q2ple::pread_ns};
      n = ::pread(fd_, base + got, length - got, begin + got);
    }
    if (n > 0) q2ple::Add(q2ple::returned_bytes, n);''')
    source = once(source, '  std::lock_guard<std::mutex> lock(mutex_);\n  if (active_',
                  '  q2ple::Timer timing{q2ple::start_ns};\n  q2ple::Add(q2ple::gathers);\n  q2ple::Add(q2ple::rows, rows.size());\n  std::lock_guard<std::mutex> lock(mutex_);\n  if (active_')
    source = once(source, '  if (jobs_.size() >= kBatchJobs) {',
                  '  q2ple::Add(q2ple::unique_rows, jobs_.size());\n  if (jobs_.size() >= kBatchJobs) {')
    source = once(source, 'bool NgramTable::WaitRead() {',
                  'bool NgramTable::WaitRead() {\n  q2ple::Timer timing{q2ple::wait_ns};')
    source = once(source, '  done_.wait(lock, [&] { return pending_ == 0; });', '''  {
    q2ple::Timer blocked{q2ple::blocked_ns};
    done_.wait(lock, [&] { return pending_ == 0; });
  }''')
    source = once(source, '  if (!failed_) {\n    for (const Copy& copy : copies_) {',
                  '  if (!failed_) {\n    q2ple::Timer copies{q2ple::copies_ns};\n    for (const Copy& copy : copies_) {')
    return source


def main():
    reports = {}
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for name, dirname in [('q2', 'gufo-q2-bench-hc-moe-fused'), ('ud', 'gufo-base')]:
        base = ROOT / '.deps' / dirname
        out = ROOT / '.deps' / ('gufo-ple-' + name)
        shutil.copytree(base, out)
        (out / REL).write_text(instrument((base / REL).read_text()))
        shutil.copyfile(ROOT / 'tests/q2_ple_diag.hpp', out / 'q2_ple_diag.hpp')
        subprocess.run(['clang-format', '-i', str(out / REL), str(out / 'q2_ple_diag.hpp')], check=True)
        changed = [str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()
                   and p.read_bytes() != (out / p.relative_to(base)).read_bytes()]
        if changed != [str(REL)]:
            raise ValueError('Unexpected changes: ' + repr(changed))
        patch = ''.join(difflib.unified_diff((base / REL).read_text().splitlines(True),
                        (out / REL).read_text().splitlines(True), fromfile='a/' + str(REL), tofile='b/' + str(REL)))
        patch += ''.join(difflib.unified_diff([], (out / 'q2_ple_diag.hpp').read_text().splitlines(True),
                         fromfile='/dev/null', tofile='b/q2_ple_diag.hpp'))
        path = ROOT / ('experiments/q2-ple-' + name + '.patch')
        path.write_text(patch)
        reports[name] = dict(base=str(base.relative_to(ROOT)), files=sum(p.is_file() for p in base.rglob('*')),
                             changed={str(REL): {'base': sha(base / REL), 'diagnostic': sha(out / REL)}},
                             added={'q2_ple_diag.hpp': sha(out / 'q2_ple_diag.hpp')}, patch_sha256=sha(path))
    (ROOT / 'config/q2-ple-source.json').write_text(json.dumps(dict(
        scope='Diagnostic timers/counters only; model kernels unchanged; no runtime performance verdict',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e', variants=reports), indent=2) + '\n')


if __name__ == '__main__':
    main()
