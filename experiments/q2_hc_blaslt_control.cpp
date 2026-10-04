// SPDX-License-Identifier: MIT
/*
MIT License

Copyright (c) 2026 gufo contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
// Test-only original library control from this workstream's measured Gufo provider.
#include "experiments/q2_hc_blaslt_control.hpp"

#include <array>
#include <hipblaslt/hipblaslt-ext.hpp>

#include "src/models/qwen38_flash_next/kernels/rocm/kernels.hpp"

namespace gufo::models::qwen38_flash_next::rocm {
namespace {

void AssignError(std::string* error, const char* message) {
  if (error != nullptr) {
    *error = message;
  }
}

}  // namespace

struct HcBlasLtControl::Plan {
  hipblasLtMatmulDesc_t operation{nullptr};
  hipblasLtMatrixLayout_t weights{nullptr};
  hipblasLtMatrixLayout_t input{nullptr};
  hipblasLtMatrixLayout_t output{nullptr};
  hipblasLtMatmulAlgo_t algorithm{};

  ~Plan() {
    if (output != nullptr)
      (void)hipblasLtMatrixLayoutDestroy(output);
    if (input != nullptr)
      (void)hipblasLtMatrixLayoutDestroy(input);
    if (weights != nullptr)
      (void)hipblasLtMatrixLayoutDestroy(weights);
    if (operation != nullptr)
      (void)hipblasLtMatmulDescDestroy(operation);
  }
};

HcBlasLtControl::~HcBlasLtControl() {
  plans_.clear();
  if (handle_ != nullptr) {
    (void)hipblasLtDestroy(handle_);
  }
}

std::unique_ptr<HcBlasLtControl> HcBlasLtControl::Create(hipStream_t stream, std::string* error) {
  std::unique_ptr<HcBlasLtControl> blas(new HcBlasLtControl());
  blas->stream_ = stream;
  if (hipblasLtCreate(&blas->handle_) != HIPBLAS_STATUS_SUCCESS) {
    AssignError(error, "hipblasLtCreate failed");
    return nullptr;
  }
  return blas;
}

std::unique_ptr<HcBlasLtControl::Plan> HcBlasLtControl::MakePlan(hipDataType type, int m, int n,
                                               int k,
                                               std::string* error) const {
  auto p = std::make_unique<Plan>();
  const hipblasOperation_t transpose = HIPBLAS_OP_T;
  const hipblasOperation_t normal = HIPBLAS_OP_N;
  if (hipblasLtMatmulDescCreate(&p->operation, HIPBLAS_COMPUTE_32F,
                                HIP_R_32F) != HIPBLAS_STATUS_SUCCESS ||
      hipblasLtMatmulDescSetAttribute(
          p->operation, HIPBLASLT_MATMUL_DESC_TRANSA, &transpose,
          sizeof(transpose)) != HIPBLAS_STATUS_SUCCESS ||
      hipblasLtMatmulDescSetAttribute(
          p->operation, HIPBLASLT_MATMUL_DESC_TRANSB, &normal,
          sizeof(normal)) != HIPBLAS_STATUS_SUCCESS ||
      hipblasLtMatrixLayoutCreate(&p->weights, type, k, m, k) !=
          HIPBLAS_STATUS_SUCCESS ||
      hipblasLtMatrixLayoutCreate(&p->input, type, k, n, k) !=
          HIPBLAS_STATUS_SUCCESS ||
      hipblasLtMatrixLayoutCreate(&p->output, HIP_R_32F, m, n, m) !=
          HIPBLAS_STATUS_SUCCESS) {
    AssignError(error, "hipBLASLt descriptor creation failed");
    return nullptr;
  }

  const float one = 1.0F;
  const float zero = 0.0F;
  // Isolated performance exploration from the synthetic .157 sweep.
  // The unchanged F16 values use a different accumulation order; numerical
  // failures are retained. No live search, workspace or global tuning cache.
  const int preferred =
      type == HIP_R_16F && m == 320 && n >= 96 && n <= 2048 && k == 10240 ? 7526
                                                                          : -1;
  const auto usable = [&](hipblasLtMatmulAlgo_t& algorithm) {
    std::size_t workspace = 0;
    return hipblaslt_ext::matmulIsAlgoSupported(
               handle_, p->operation, &one, p->weights, p->input, &zero,
               p->output, p->output, algorithm,
               workspace) == HIPBLAS_STATUS_SUCCESS &&
           workspace == 0;
  };

  // Initialize the solution library and keep a deterministic fallback for
  // other tensor geometries. No trial GEMMs run on model activations.
  hipblasLtMatmulPreference_t preference = nullptr;
  if (hipblasLtMatmulPreferenceCreate(&preference) != HIPBLAS_STATUS_SUCCESS) {
    AssignError(error, "hipBLASLt preference creation failed");
    return nullptr;
  }
  constexpr std::size_t workspace = 0;
  (void)hipblasLtMatmulPreferenceSetAttribute(
      preference, HIPBLASLT_MATMUL_PREF_MAX_WORKSPACE_BYTES, &workspace,
      sizeof(workspace));
  std::array<hipblasLtMatmulHeuristicResult_t, 16> candidates{};
  int count = 0;
  const auto status = hipblasLtMatmulAlgoGetHeuristic(
      handle_, p->operation, p->weights, p->input, p->output, p->output,
      preference, candidates.size(), candidates.data(), &count);
  (void)hipblasLtMatmulPreferenceDestroy(preference);

  if (status == HIPBLAS_STATUS_SUCCESS) {
    for (int i = 0; i < count; ++i) {
      if (candidates[i].state == HIPBLAS_STATUS_SUCCESS &&
          candidates[i].workspaceSize == 0 && usable(candidates[i].algo)) {
        if (preferred >= 0 &&
            hipblaslt_ext::getIndexFromAlgo(candidates[i].algo) != preferred)
          continue;
        p->algorithm = candidates[i].algo;
        return p;
      }
    }
  }
  AssignError(error, "no workspace-free hipBLASLt kernel for the GEMM shape");
  return nullptr;
}

bool HcBlasLtControl::Gemm(const void* weights, const void* input, float* out,
                  hipDataType type, int m, int n, int k, std::string* error) {
  if (m <= 0 || n <= 0 || k <= 0) {
    AssignError(error, "hipBLASLt dimensions must be positive");
    return false;
  }
  // Library edge tiles change the accumulation order when the same token
  // moves within a batch. Router and recurrent-gate errors then amplify across
  // layers. Keep one K reduction for every row and prefill chunk size.
  const bool hc_library_down =
      type == HIP_R_16F && m == 320 && n >= 96 && n <= 2048 && k == 10240;
  const bool hc_half = !hc_library_down && n >= 96 &&
                       ((m == 320 && k == 10240) || (m == 10240 && k == 320));
  if (type == HIP_R_16F && ((k == 2560 && (m == 96 || m == 513)) || hc_half)) {
    return UnquantizedF16Gemm(weights, static_cast<const __half*>(input), out,
                              n, m, k, stream_);
  }
  // Exact dimensions prevent the first ragged request from determining
  // which kernel later requests in the same size bucket receive.
  const std::array<int, 4> key{static_cast<int>(type), m, n, k};
  auto& p = plans_[key];
  if (!p) {
    p = MakePlan(type, m, n, k, error);
    if (!p) {
      return false;
    }
  }
  const float one = 1.0F;
  const float zero = 0.0F;
  if (hipblasLtMatmul(handle_, p->operation, &one, weights, p->weights, input,
                      p->input, &zero, out, p->output, out, p->output,
                      &p->algorithm, nullptr, 0,
                      stream_) != HIPBLAS_STATUS_SUCCESS) {
    AssignError(error, "hipBLASLt GEMM failed");
    return false;
  }
  return true;
}

}  // namespace gufo::models::qwen38_flash_next::rocm
