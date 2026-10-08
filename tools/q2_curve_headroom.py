# SPDX-License-Identifier: MIT
"""Exact private host-only capacity edit; no numerical/MMQ source exceptions."""
from pathlib import Path

ENGINE = 'src/models/qwen38_flash_next/engine.cpp'
ROOT = Path(__file__).resolve().parents[1]


def extend_engine(text):
    namespace = 'namespace gufo::models::qwen38_flash_next {\n'
    anchor = '  const Config& c = m->weights_->config;\n'
    if text.count(namespace) != 1 or text.count(anchor) != 1:
        raise ValueError('Unexpected model capacity boundary')
    header = (ROOT / 'experiments/q2_curve_headroom.h').read_text()
    text = text.replace(namespace, header + '\n' + namespace)
    return text.replace(anchor, '''  // SPDX-License-Identifier: MIT
  // Apply before DeviceModel upload so indexer masks and sessions share
  // the same effective capacity. Original file metadata stays untouched.
  m->weights_->config.context_length = lie_q2_curve_capacity(
      m->weights_->config.context_length, options.max_context,
      options.mtp_model_path.empty() && options.vision_model_path.empty());
''' + anchor)
