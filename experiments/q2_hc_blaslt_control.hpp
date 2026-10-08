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
#ifndef LIE_Q2_HC_BLASLT_CONTROL_HPP_
#define LIE_Q2_HC_BLASLT_CONTROL_HPP_

#include <hip/hip_runtime.h>
#include <hipblaslt/hipblaslt.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>
#include <string>

namespace gufo::models::qwen38_flash_next::rocm {

/// Dense 16-bit projections with F32 accumulation and output. Plans depend
/// only on tensor geometry and the pinned HIP library, never runtime timing.
class HcBlasLtControl {
public:
  ~HcBlasLtControl();
  HcBlasLtControl(const HcBlasLtControl&) = delete;
  HcBlasLtControl& operator=(const HcBlasLtControl&) = delete;

  [[nodiscard]] static std::unique_ptr<HcBlasLtControl> Create(hipStream_t stream,
                                                      std::string* error_msg);

  /// Row-major out[n][m] = input[n][k] * weights[m][k]^T.
  [[nodiscard]] bool Gemm(const void* weights, const void* input, float* out,
                          hipDataType type, int m, int n, int k,
                          std::string* error_msg);

private:
  HcBlasLtControl() = default;

  struct Plan;
  std::unique_ptr<Plan> MakePlan(hipDataType type, int m, int n, int k,
                                 std::string* error_msg) const;

  hipblasLtHandle_t handle_{nullptr};
  hipStream_t stream_{nullptr};
  std::map<std::array<int, 4>, std::unique_ptr<Plan>> plans_;
};

}  // namespace gufo::models::qwen38_flash_next::rocm

#endif  // LIE_Q2_HC_BLASLT_CONTROL_HPP_
