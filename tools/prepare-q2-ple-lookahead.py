#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Add a borrowed, validated PLE input hook to an isolated measured executor."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-moe-fused'
OUT = ROOT / '.deps/gufo-q2-bench-ple-lookahead'
REL = Path('src/models/qwen38_flash_next/kernels/rocm')


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected measured source: ' + before[:100])
    return text.replace(before, after)


def main():
    shutil.copytree(BASE, OUT)
    header = OUT / REL / 'executor.hpp'
    source = OUT / REL / 'executor.cpp'
    text = header.read_text()
    text = once(text, '  struct BatchItem {', '''  /// Experimental AR prefill only. The caller owns pinned PLE embeddings
  /// and their row IDs until input_released is true. IDs are rehashed against
  /// the current session before any mutation; embedding content is trusted.
  /// Exactly one caller may use this executor. The producer alone may read
  /// the table during prepared prefill. No callback or borrowed input escapes.
  /// A failed call invalidates the session. If draining the HIP stream fails,
  /// input_released stays false: quarantine all resources and retire the owned
  /// process; do not release/reuse the slot or attempt another model call.
  [[nodiscard]] bool ForwardPrepared(
      Session& session, std::span<const std::int32_t> tokens,
      std::uint32_t n_logits, float* logits,
      std::span<const std::uint32_t> rows, std::span<const float> embeddings,
      bool* input_released, std::string* error_msg) const;

  struct BatchItem {''')
    text = once(text, '  mutable bool ple_pending_{false};', '''  mutable bool ple_pending_{false};
  mutable const float* prepared_ple_{nullptr};
  mutable NgramHistory prepared_history_;''')
    header.write_text(text)
    text = source.read_text()
    text = once(text, '''  if (ple_pending_ && !WaitPle(error_msg)) {
    return false;
  }
  const Config& c = config();''', '''  if (prepared_ple_ != nullptr) {
    // ForwardPrepared checked the IDs and owns the borrow through GPU drain.
    session.ngram_ = prepared_history_;
    return true;
  }
  if (ple_pending_ && !WaitPle(error_msg)) {
    return false;
  }
  const Config& c = config();''')
    text = once(text, '''      (!WaitPle(error_msg) ||
       !Check(hipMemcpyAsync(s_.ple_emb, host_emb_, emb_count * sizeof(float),''', '''      ((prepared_ple_ == nullptr && !WaitPle(error_msg)) ||
       !Check(hipMemcpyAsync(s_.ple_emb,
                             prepared_ple_ != nullptr ? prepared_ple_ : host_emb_,
                             emb_count * sizeof(float),''')
    at = 'bool Executor::Forward(Session& session, std::span<const std::int32_t> tokens,'
    body = '''bool Executor::ForwardPrepared(
    Session& session, std::span<const std::int32_t> tokens,
    std::uint32_t n_logits, float* logits,
    std::span<const std::uint32_t> rows, std::span<const float> embeddings,
    bool* input_released, std::string* error_msg) const {
  if (input_released == nullptr) {
    AssignError(error_msg, "prepared input release output is required");
    return false;
  }
  *input_released = true;
  const Config& c = config();
  if (session.owner_ != this || session.mtp_enabled_ || c.ple_layer < 0 ||
      ngram_ == nullptr || ple_pending_ || prepared_ple_ != nullptr ||
      tokens.empty() || tokens.size() > options_.max_batch ||
      session.position_ > session.max_context_ ||
      tokens.size() > session.max_context_ - session.position_ ||
      rows.size() != tokens.size() * c.ple_heads ||
      embeddings.size() != tokens.size() * c.PleEmbeddingDim() ||
      n_logits > tokens.size() || n_logits > options_.max_logit_rows) {
    AssignError(error_msg, "invalid prepared AR prefill input or session");
    return false;
  }
  for (const auto token : tokens) {
    if (token < 0 || static_cast<std::uint32_t>(token) >= c.vocab_size) {
      AssignError(error_msg, "prepared token out of range");
      return false;
    }
  }
  auto next = session.ngram_;
  auto expected = std::span(host_rows_).first(rows.size());
  HashNgramRows(c, next, tokens, expected);
  if (!std::equal(rows.begin(), rows.end(), expected.begin())) {
    AssignError(error_msg, "prepared PLE rows do not match session history");
    return false;
  }
  prepared_history_ = next;
  prepared_ple_ = embeddings.data();
  *input_released = false;
  // Also drain on cancellation, an eager launch failure, or an exception.
  // Never turn a failed HIP fence into a claim that the host slot is reusable.
  hipError_t drain = hipSuccess;
  const auto finish = [&] {
    drain = hipStreamSynchronize(stream_);
    prepared_ple_ = nullptr;
    *input_released = drain == hipSuccess;
  };
  bool ok = false;
  try {
    ok = Forward(session, tokens, n_logits, logits, ForwardMode::kPrefill,
                 error_msg);
  } catch (...) {
    finish();
    throw;
  }
  finish();
  if (drain != hipSuccess) {
    if (error_msg != nullptr) {
      if (!error_msg->empty()) *error_msg += "; ";
      *error_msg += std::string("prepared input drain: ") + hipGetErrorString(drain);
    }
    return false;
  }
  return ok;
}

'''
    text = once(text, at, body + at)
    source.write_text(text)
    subprocess.run(['clang-format', '-i', str(header), str(source)], check=True)
    changed = sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file()
                     and p.read_bytes() != (OUT / p.relative_to(BASE)).read_bytes())
    expected = sorted(str(REL / name) for name in ('executor.cpp', 'executor.hpp'))
    if changed != expected:
        raise ValueError('Unexpected source changes')
    patch = ROOT / 'experiments/q2-ple-lookahead.patch'
    patch.write_text(''.join(''.join(difflib.unified_diff(
        (BASE / name).read_text().splitlines(True),
        (OUT / name).read_text().splitlines(True),
        fromfile='a/' + name, tofile='b/' + name)) for name in changed))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(scope='Static preparation; no GPU overlap or speedup qualified',
                  pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
                  patch_sha256=sha(patch), changed_files=changed,
                  files={name: dict(base_sha256=sha(BASE / name),
                                    candidate_sha256=sha(OUT / name)) for name in changed},
                  arithmetic='Unchanged kernels, row decoding and cache capacity',
                  ownership='C17 bounded producer/consumer; borrowed pinned inputs drained by transitional executor')
    (ROOT / 'config/q2-ple-lookahead-source.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared validated AR PLE input:', changed)


if __name__ == '__main__':
    main()
