#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare one C17-owned shared/routed GPU fork for original Q2 prefill."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '.deps/gufo-q2-bench-hc-up-chains'
OUT = ROOT / '.deps/gufo-q2-bench-shared-overlap'
DIR = Path('src/models/qwen38_flash_next/kernels/rocm')


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected source anchor: ' + before[:90])
    return text.replace(before, after)


def main():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(BASE / DIR / 'kernels.hip.cpp') != 'a5ccc81f7762beae74cf0bbb06e6aeebd44edf1c804c1473b63619af023a6cd5':
        raise ValueError('Retained kernel source changed')
    cpp = (BASE / DIR / 'executor.cpp').read_text()
    hpp = (BASE / DIR / 'executor.hpp').read_text()
    cmake_rel = Path('src/models/qwen38_flash_next/CMakeLists.txt')
    cmake = (BASE / cmake_rel).read_text()
    hpp = once(hpp, '#include <hip/hip_fp16.h>',
               '#include "gpu_fork.h"\n\n#include <hip/hip_fp16.h>')
    hpp = once(hpp, '  ~Executor();', '''  ~Executor();
  const lie_gpu_fork& SharedForkStats() const noexcept { return shared_fork_; }''')
    hpp = once(hpp, '  hipEvent_t counts_ready_{nullptr};', '''  hipEvent_t counts_ready_{nullptr};
  hipStream_t shared_stream_{nullptr};
  hipEvent_t shared_ready_{nullptr}, shared_done_{nullptr};
  mutable lie_gpu_fork shared_fork_{};''')
    cpp = '#include "q2_shared_fork.hpp"\n' + cpp
    cpp = once(cpp, 'Executor::~Executor() {', '''Executor::~Executor() {
  // A nonblocking branch is not covered by implicit legacy-stream ordering.
  // Drain both owners before freeing any shared input or output allocation.
  if (shared_stream_ != nullptr) {
    (void)hipStreamSynchronize(shared_stream_);
    (void)hipStreamSynchronize(stream_);
  }
  if (shared_ready_ != nullptr) (void)hipEventDestroy(shared_ready_);
  if (shared_done_ != nullptr) (void)hipEventDestroy(shared_done_);
  if (shared_stream_ != nullptr) (void)hipStreamDestroy(shared_stream_);''')
    cpp = once(cpp, '  const std::size_t T = e->options_.max_batch;', '''  const std::size_t T = e->options_.max_batch;
  if (T >= 96 && !model.layers().empty() &&
      model.layers()[0].ffn_down_exps.type == GgmlType::kQ2_K) {
    if (!Check(hipStreamCreateWithFlags(&e->shared_stream_, hipStreamNonBlocking),
               "shared branch stream", error_msg) ||
        !Check(hipEventCreateWithFlags(&e->shared_ready_, hipEventDisableTiming),
               "shared branch input event", error_msg) ||
        !Check(hipEventCreateWithFlags(&e->shared_done_, hipEventDisableTiming),
               "shared branch completion event", error_msg)) return nullptr;
  }''')
    start = cpp.index('  // The shared expert (gated by the last router row)')
    end = cpp.index('  if (last_only &&', start)
    previous = cpp[start:end]
    new = '''  // Bound this experiment to the original Q2 prefill geometry and the
  // exact existing Q8 W8A8 -> SwiGLU-half -> Q8/F16 shared-expert route.
  const bool overlap = shared_stream_ != nullptr && prefill_phase &&
      n_tokens >= 96 && n_tokens <= options_.max_batch && !last_only &&
      !wide_mixer_ && out == s_.block_out && c.hc_count == 4 &&
      c.hidden_size == 2560 && c.expert_ff == 640 &&
      c.shared_expert_ff == 640 && c.num_experts_used == 10 &&
      l.ffn_gate_exps.type == GgmlType::kIQ2_XXS &&
      l.ffn_up_exps.type == GgmlType::kIQ2_XXS &&
      l.ffn_down_exps.type == GgmlType::kQ2_K && l.ffn_down_exps.cols == 768 &&
      l.shexp_gate.type == GgmlType::kQ8_0 &&
      l.shexp_up.type == GgmlType::kQ8_0 &&
      l.shexp_gate.rows == 640 && l.shexp_up.rows == 640 &&
      l.shexp_gate.cols == 2560 && l.shexp_up.cols == 2560 &&
      l.shexp_down.rows == 2560 && l.shexp_down.cols == 640 &&
      DenseF16Route(l.shexp_down, n_tokens);
  LieSharedFork fork{&shared_fork_, stream_, shared_stream_, shared_ready_,
      shared_done_, l.shexp_gate.data, l.shexp_up.data, l.shexp_down.data,
      s_.x_q8t, s_.shexp_up, s_.shexp_gate, s_.shexp_out, s_.shexp_half,
      n_tokens, c.hidden_size, c.shared_expert_ff};
  if (overlap) {
    shexp_half_ready_ = false;
    if (!(q8t_src_ == x && q8t_rows_ == n_tokens && q8t_cols_ == c.hidden_size)) {
      QuantizeQ8Tiled(x, s_.x_q8t, n_tokens, c.hidden_size, stream_);
      q8t_src_ = x;
      q8t_rows_ = n_tokens;
      q8t_cols_ = c.hidden_size;
    }
    if (fork.Begin() != LIE_GPU_OK) {
      AssignError(error_msg, "shared branch start or drain failed");
      return false;
    }
  } else {
''' + previous + '''  }
'''
    cpp = cpp[:start] + new + cpp[end:]
    cpp = once(cpp, '''  if (wmma_experts) {
    // The combine that follows folds this epilogue''', '''  // Transfer the branch's output lifetime back to the parent stream before
  // any weighted sum/HC consumer. No host wait is added on the success path.
  if (shared_fork_.state != LIE_GPU_IDLE &&
      lie_gpu_fork_join(&shared_fork_) != LIE_GPU_OK) {
    AssignError(error_msg, "shared branch join or drain failed");
    return false;
  }
  if (wmma_experts) {
    // The combine that follows folds this epilogue''')
    cmake = once(cmake, '  target_sources(gufo_qwen38_flash_next PRIVATE ${QFN_HIP_SOURCES})',
        '''  target_sources(gufo_qwen38_flash_next PRIVATE ${QFN_HIP_SOURCES}
    ${QFN_ROCM_DIR}/gpu_fork.c)
  set_source_files_properties(${QFN_ROCM_DIR}/gpu_fork.c PROPERTIES
    COMPILE_OPTIONS "-std=c17;-Wall;-Wextra;-Werror;-Wpedantic")
  target_compile_definitions(gufo_qwen38_flash_next PUBLIC LIE_Q2_SHARED_FORK=1)''')
    shutil.copytree(BASE, OUT)
    (OUT / DIR / 'executor.cpp').write_text(cpp)
    (OUT / DIR / 'executor.hpp').write_text(hpp)
    (OUT / cmake_rel).write_text(cmake)
    for name in ['gpu_fork.c', 'gpu_fork.h', 'q2_shared_fork.hpp']:
        shutil.copyfile(ROOT / 'experiments' / name, OUT / DIR / name)
    subprocess.run(['clang-format', '-i', str(OUT / DIR / 'executor.cpp'),
                    str(OUT / DIR / 'executor.hpp')], check=True)
    files = sorted(p.relative_to(OUT) for p in OUT.rglob('*') if p.is_file())
    changed = [p for p in files if not (BASE/p).exists() or (BASE/p).read_bytes() != (OUT/p).read_bytes()]
    patch = ''
    for p in changed:
        old = (BASE/p).read_text().splitlines(True) if (BASE/p).exists() else []
        patch += ''.join(difflib.unified_diff(old, (OUT/p).read_text().splitlines(True),
            fromfile='a/'+str(p) if old else '/dev/null', tofile='b/'+str(p)))
    patch_path = ROOT / 'experiments/q2-shared-overlap.patch'
    patch_path.write_text(patch)
    report = dict(scope='Prepared C17 fork/join with HIP adapter; runtime exactness and gain unproven',
        pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        base=str(BASE.relative_to(ROOT)), candidate=str(OUT.relative_to(ROOT)),
        changed_files=[dict(path=str(p),base_sha256=sha(BASE/p) if (BASE/p).exists() else None,
                           sha256=sha(OUT/p)) for p in changed],
        patch_sha256=sha(patch_path), kernel_sha256=sha(OUT/DIR/'kernels.hip.cpp'),
        tensor_allocation_bytes_added=0, gpu_streams_added=1, gpu_events_added=2,
        activation_contract='Original Q8 shared gate/up, F16 shared down input, original routed high/residual representation',
        guard='Q2 prefill only, n>=96, exact original model geometry; decode and other shapes sequential',
        lifecycle='One outstanding branch, input event, completion join before consumers; C17 drain/poison on failure')
    (ROOT/'config/q2-shared-overlap-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
