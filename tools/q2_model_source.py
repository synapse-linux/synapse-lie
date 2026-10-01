#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Isolated first-model-test overlay. Never changes the production Q2 recipes.
Base: the retained, successful c0d6c6d executor-preflight candidate build.
Source identity is Git commit + captured diff; no repeated whole-tree hash scan.
"""
import json
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
BASE = 'q2-admission-linked-r1'

def replace(data, old, new):
    if data.count(old) != 1:
        raise ValueError('Q2 model-test overlay anchor mismatch')
    return data.replace(old, new)

def edits(name, data):
    if name.endswith('/device_model.cpp'):
        data = replace(data, '#include <hip/hip_runtime.h>',
                       '#include <hip/hip_runtime.h>\n#include "q2_model_memory.h"')
        data = replace(data, 'const auto supported = [&](const TensorRef& t) {',
                       'const auto supported = [&](const TensorRef& t, bool routed = false) {')
        data = replace(data, 'if (t.type == core::GgmlType::kIQ2_XXS || t.type == core::GgmlType::kQ2_K) {',
                       'if ((t.type == core::GgmlType::kIQ2_XXS || t.type == core::GgmlType::kQ2_K) &&\n        (!routed || !lie_q2_test_memory_active())) {')
        data = replace(data, 'supported(l.ffn_gate_exps) && supported(l.ffn_up_exps) &&\n           supported(l.ffn_down_exps)',
                       'supported(l.ffn_gate_exps, true) && supported(l.ffn_up_exps, true) &&\n           supported(l.ffn_down_exps, true)')
    elif name.endswith('/weight_upload.cpp'):
        data = replace(data, '    if (!read) {\n      // Some filesystems',
                       '    if (!read) return "Q2 test requires direct weight reads; no buffered fallback";\n    if (!read) {\n      // Some filesystems')
        data = replace(data, '    shard.direct_fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_DIRECT);',
                       '    shard.direct_fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_DIRECT);\n    if (shard.direct_fd < 0) {\n      s.Fail("Q2 test requires O_DIRECT weight upload");\n      s.Status(error);\n      return nullptr;\n    }')
    elif name.endswith('/ngram.cpp'):
        data = replace(data, '    t->fd_ = ::open(path.c_str(), O_RDONLY | O_CLOEXEC);',
                       '    if (error_msg) *error_msg = "Q2 test requires O_DIRECT PLE; no buffered fallback";\n    return nullptr;')
    elif name.endswith('/engine.cpp'):
        data = replace(data, '#include "src/models/qwen38_flash_next/engine.hpp"',
                       '#include "src/models/qwen38_flash_next/engine.hpp"\n#include "q2_model_memory.h"')
        data = replace(data, '  std::shared_ptr<Model> m(new Model());',
                       '  if (!lie_q2_test_memory_active() || options.max_context != 9216 ||\n      options.decode_concurrency != 1 || options.max_draft_tokens != 1 ||\n      !options.mtp_model_path.empty() || !options.vision_model_path.empty()) {\n    AssignError(error_msg, "Q2 test admission/options required before model load");\n    return nullptr;\n  }\n  std::shared_ptr<Model> m(new Model());')
        data = replace(data, '''  try {
    m->vision_ = qwen::vision::Encoder::Open(
        model_path, options.vision_model_path, c.hidden_size);
  } catch (const std::exception& e) {
    AssignError(error_msg, e.what());
    return nullptr;
  }''', '  // Text-only first test: no automatic vision sidecar discovery/open.')
    else:
        raise ValueError('unexpected test overlay target')
    return data

TARGETS = ['src/models/qwen38_flash_next/kernels/rocm/device_model.cpp',
           'src/core/hip/weight_upload.cpp', 'src/models/qwen38_flash_next/ngram.cpp',
           'src/models/qwen38_flash_next/engine.cpp']

def prepare(destination):
    base = ROOT / 'build' / BASE / 'source'
    receipt = json.loads((ROOT / 'evidence' / BASE / 'result.json').read_text())
    if (receipt['state'] != 'Q2_HIP_BUILD_HOST_REFUSALS_PASS_NOT_GPU_OR_MODEL_QUALIFICATION'
            or receipt['runtime_link_allowed'] is not False):
        raise ValueError('invalid private base build')
    if any(p.is_symlink() for p in [base, *base.parents, destination, *destination.parents]):
        raise ValueError('symlink source/destination refused')
    if any(p.is_symlink() for p in base.rglob('*')):
        raise ValueError('symlink base member refused')
    expected = (ROOT / 'adapters/gufo-q2/q2_plan.h').read_bytes()
    if (base / 'src/models/qwen38_flash_next/kernels/rocm/q2_plan.h').read_bytes() != expected:
        raise ValueError('base Q2 planner differs from selected source')
    changed = {name: edits(name, (base / name).read_text()) for name in TARGETS}
    shutil.copytree(base, destination)
    # Preserve old receipts as BASE receipts, never mislabel modified files.
    name = 'LIE-Q2-HIP-SOURCE.json'
    (destination / name).rename(destination / ('BASE-' + name))
    for name, data in changed.items():
        (destination / name).write_text(data)
    result = {'schema': 'synapse-lie.q2-model-test-source.v1', 'base_build': BASE,
              'test_link_only': True, 'runtime_link_allowed': False,
              'production_recipes_unchanged': True, 'modified_relative_to_base': TARGETS,
              'gpu_execution': False, 'model_qualification': False}
    with (destination / 'LIE-Q2-MODEL-TEST-SOURCE.json').open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    return result
