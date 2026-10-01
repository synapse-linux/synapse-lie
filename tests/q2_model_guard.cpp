// SPDX-License-Identifier: MIT
// Test-only binding/admission and HIP allocation interception, not a provider.
#include "q2_model_memory.h"
#include "src/models/qwen38_flash_next/weights.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/q2_plan.h"
#include <hip/hip_runtime.h>
#include <array>
#include <cstdio>
#include <exception>
#include <limits>
#include <stdexcept>
#include <string>

extern "C" hipError_t __real_hipMalloc(void**, size_t);
extern "C" hipError_t __real_hipHostMalloc(void**, size_t, unsigned int);
extern "C" hipError_t __wrap_hipMalloc(void** p, size_t bytes) {
    if (!lie_q2_test_memory_charge(bytes)) {
        std::fputs("Q2 test allocation before admission or accounting overflow; no retry\n", stderr);
        if (p) *p = nullptr;
        return hipErrorOutOfMemory;
    }
    return __real_hipMalloc(p, bytes);
}
extern "C" hipError_t __wrap_hipHostMalloc(void** p, size_t bytes, unsigned int flags) {
    if (!lie_q2_test_memory_charge(bytes)) {
        std::fputs("Q2 test pinned allocation before admission or accounting overflow; no retry\n", stderr);
        if (p) *p = nullptr;
        return hipErrorOutOfMemory;
    }
    return __real_hipHostMalloc(p, bytes, flags);
}

int lie_q2_model_plan_from_reader(const gufo::core::GgufReader& input,
                                  lie_q2_test_memory* plan, std::string* error) {
    const auto fail = [&](const std::string& message) {
        if (error) *error = message;
        return 0;
    };
    try {
        using namespace gufo::models::qwen38_flash_next;
        using gufo::core::GgmlType;
        std::string message;
        const auto* reader = &input;
        if (reader->GetSize() != UINT64_C(147207127040) || reader->GetTensorCount() != 1256)
            return fail("first Q2 model test requires the inspected single-file layout");
        auto weights = ModelWeights::Bind(*reader, &message);
        if (!weights) return fail(message);
        const auto& c = weights->config;
        if (c.num_layers != 48 || c.num_experts != 512 || c.num_experts_used != 10 ||
            c.vocab_size != 248320 || c.context_length != 262144 ||
            c.hc_count != 4 || c.hc_low_rank != 320 || c.shared_expert_ff != 640 ||
            c.num_heads != 24 || c.num_kv_heads != 2 || c.head_dim != 256 ||
            c.full_attention_interval != 4 || c.compress_ratio != 4 ||
            c.indexer_heads != 4 || c.indexer_head_dim != 128 || c.indexer_top_k != 2048 ||
            c.ssm_num_k_heads != 16 || c.ssm_num_v_heads != 48 || c.ssm_head_dim != 128 ||
            c.ssm_inner_size != 6144 || c.ssm_conv_kernel != 4 ||
            c.ple_layer < 0 || c.ple_heads != 16 || c.ple_head_dim != 160 ||
            c.ple_conv_kernel != 4 || c.ple_ngram_size != 3 || weights->layers.size() != 48)
            return fail("Q2 first-test architecture envelope mismatch");
        std::array<lie_q2_layer, 48> layers{};
        const auto view = [](const TensorRef& t) {
            if (t.cols > UINT32_MAX || t.rows > UINT32_MAX || t.experts > UINT32_MAX)
                throw std::runtime_error("Q2 tensor descriptor narrowing");
            return lie_q2_tensor{int(t.type), uint32_t(t.cols), uint32_t(t.rows),
                                 uint32_t(t.experts), !t.empty()};
        };
        for (size_t i = 0; i < layers.size(); ++i) {
            const auto& l = weights->layers[i];
            layers[i] = {view(l.ffn_gate_exps), view(l.ffn_up_exps), view(l.ffn_down_exps)};
        }
        lie_q2_plan workspace{};
        if (lie_q2_profile_make(2048, c.hidden_size, c.expert_ff, c.num_experts,
                                c.num_experts_used, c.num_layers, 0,
                                layers.data(), layers.size(), &workspace) != LIE_Q2_PROFILE_VALID)
            return fail("Q2 routed upload profile mismatch");
        uint64_t non_ple = 0, f32 = 0, ple = 0, count = 0;
        for (const auto& t : reader->GetTensors()) {
            if (t.name == "per_layer_token_embd.weight") {
                if (t.type != GgmlType::kBF16 || ple) return fail("Q2 PLE role mismatch");
                ple = t.size_bytes;
            } else {
                if (t.size_bytes > (UINT64_C(64) << 30) - non_ple)
                    return fail("Q2 non-PLE encoded size outside format scope");
                non_ple += t.size_bytes;
                if (t.type == GgmlType::kF32) f32 += t.size_bytes;
                ++count;
            }
        }
        if (!lie_q2_test_memory_plan(non_ple, f32, count, ple, plan))
            return fail("Q2 role memory plan refused");
        return 1;
    } catch (const std::exception& ex) { return fail(ex.what()); }
    catch (...) { return fail("unknown Q2 test admission failure"); }
}
extern "C" int lie_q2_model_admit(const char* path, uint64_t available,
                                  lie_q2_test_memory* plan, char* error, size_t size) {
    std::string message;
    try {
        auto reader = gufo::core::GgufReader::OpenFile(path, &message);
        if (reader && reader->GetMappedRegions().size() == 1 &&
            lie_q2_model_plan_from_reader(*reader, plan, &message)) {
            if (lie_q2_test_memory_start(plan, available)) return 1;
            message = "Q2 available RAM below the encoded weight estimate";
        }
    } catch (const std::exception& ex) { message = ex.what(); }
    catch (...) { message = "unknown Q2 test admission failure"; }
    if (error && size) std::snprintf(error, size, "%s", message.c_str());
    return 0;
}
