// SPDX-License-Identifier: MIT
// No GPU execution entry here: argument refusals and host planning only.
#include "src/models/qwen38_flash_next/kernels/rocm/q2_routed.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>

int main(int argc, char **argv) {
  if (argc != 2 || std::strcmp(argv[1], "--contract-only") != 0) {
    std::fputs("Usage: q2-route-probe --contract-only (NO GPU EXECUTION)\n",
               stderr);
    return 2;
  }
  lie_q2_workspace ws{};
  assert(lie_q2_workspace_prepare(nullptr) == -1);
  assert(lie_q2_workspace_prepare(&ws) == -1);
  assert(lie_q2_plan_make(2048, 512, 10, &ws.plan));
  assert(lie_q2_workspace_prepare(&ws) == -1);
  assert(lie_q2_project(nullptr, 16, 0, 0, nullptr, nullptr, nullptr, nullptr,
                        nullptr, nullptr, 640, 2560, 2560, 1, 10, 0, 0,
                        nullptr) == -1);
  // Fake non-null tokens are used only on paths that refuse before any HIP
  // call.
  int token = 0;
  ws.storage = &token;
  ws.context = &token;
  const void *w = &token;
  const float *x = reinterpret_cast<const float *>(&token);
  float *out = reinterpret_cast<float *>(&token);
  for (int type : {0, 8, 12, 39})
    assert(lie_q2_project(&ws, type, 0, 0, w, nullptr, x, &token, out, nullptr,
                          640, 2560, 2560, 1, 10, 0, 0, nullptr) == -1);
  assert(lie_q2_project(&ws, 10, 0, 0, w, nullptr, x, &token, out, nullptr,
                        2560, 768, 768, 10, 1, 0, 0, nullptr) == -1);
  assert(lie_q2_project(&ws, 16, 0, 1, w, w, x, &token, out, nullptr, 640, 2560,
                        2560, 9, 10, 0, 0, nullptr) == -1);
  assert(lie_q2_project(&ws, 16, 1, 0, w, nullptr, x, &token, out, nullptr, 640,
                        2560, 2560, 2049, 10, 0, 0, nullptr) == -1);
  assert(lie_q2_project(&ws, 16, 1, 0, w, nullptr, x, &token, out, nullptr, 640,
                        2560, 2560, 1, 10, 0, 81, nullptr) == -1);
  std::puts("Q2_HIP_LINKED_HOST_REFUSALS_PASS_NOT_GPU_EXECUTION");
  return 0;
}
