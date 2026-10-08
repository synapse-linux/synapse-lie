  // SPDX-License-Identifier: MIT
  // Private upload-time preparation. Publish only after all conversions finish.
  const auto cache_start = std::chrono::steady_clock::now();
  std::size_t cache_bytes = 0;
  unsigned cache_layers = 0;
  for (unsigned index = 0; index < m->layers_.size(); ++index) {
    auto& layer = m->layers_[index];
    const bool supported = layer.ffn_gate_exps.type == core::GgmlType::kIQ2_XXS &&
        layer.ffn_up_exps.type == core::GgmlType::kIQ2_XXS &&
        layer.ffn_down_exps.type == core::GgmlType::kQ2_K &&
        layer.ffn_gate_exps.rows == 640 && layer.ffn_gate_exps.cols == 2560 &&
        layer.ffn_up_exps.rows == 640 && layer.ffn_up_exps.cols == 2560 &&
        layer.ffn_down_exps.rows == 2560 && layer.ffn_down_exps.cols == 768 &&
        layer.ffn_gate_exps.experts == 512 && layer.ffn_up_exps.experts == 512 &&
        layer.ffn_down_exps.experts == 512;
    if (!supported || index % 8) continue;
    std::size_t free_bytes = 0, total_bytes = 0;
    if (hipMemGetInfo(&free_bytes, &total_bytes) != hipSuccess) {
      (void)hipGetLastError();
      break;
    }
    lie_q2_expert_cache_plan plan;
    const int admitted = lie_q2_expert_cache_admit(index, m->layers_.size(),
        m->config_.num_experts, m->config_.hidden_size, m->config_.expert_ff,
        supported, cache_bytes, free_bytes, &plan);
    if (admitted == 0) continue;
    if (admitted < 0 || plan.layer_allocation_bytes >
        std::numeric_limits<std::size_t>::max() - m->bytes_) {
      up.Fail("Q2 expert cache accounting failed");
      return nullptr;
    }
    void* buffers[3] = {};
    unsigned allocated = 0;
    for (; allocated < 3; ++allocated) {
      if (hipMalloc(&buffers[allocated], plan.tensor_allocation_bytes) != hipSuccess)
        break;
    }
    if (allocated != 3) {
      for (unsigned i = 0; i < allocated; ++i) (void)hipFree(buffers[i]);
      (void)hipGetLastError();
      break; // Original compressed path remains valid for this and later layers.
    }
    DeviceTensor* tensors[3] = {&layer.ffn_gate_exps, &layer.ffn_up_exps,
                               &layer.ffn_down_exps};
    for (void* p : buffers) m->allocations_.push_back(p);
    m->bytes_ += plan.layer_allocation_bytes;
    cache_bytes = plan.next_cache_bytes;
    for (unsigned i = 0; i < 3; ++i) {
      if (hipMemsetAsync(static_cast<std::uint8_t*>(buffers[i]) + plan.tensor_payload_bytes,
              0, LIE_Q2_EXPERT_CACHE_TAIL, nullptr) != hipSuccess ||
          !ConvertExpertCache(tensors[i]->data, buffers[i], i != 2, 512,
              i == 2 ? 2560 : 640, i == 2 ? 640 : 2560, nullptr)) {
        (void)hipDeviceSynchronize();
        up.Fail("Q2 expert cache conversion launch failed");
        return nullptr;
      }
      tensors[i]->prefill_cache = buffers[i];
    }
    ++cache_layers;
  }
  if (hipDeviceSynchronize() != hipSuccess) {
    up.Fail("Q2 expert cache conversion failed");
    return nullptr;
  }
  const double cache_seconds = std::chrono::duration<double>(
      std::chrono::steady_clock::now() - cache_start).count();
  std::fprintf(stderr, "{\"event\":\"q2_expert_cache_ready\",\"layers\":%u,"
      "\"bytes\":%zu,\"budget_bytes\":%zu,\"prepare_s\":%.9f}\n",
      cache_layers, cache_bytes, LIE_Q2_EXPERT_CACHE_BUDGET, cache_seconds);
