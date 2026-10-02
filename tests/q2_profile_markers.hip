// SPDX-License-Identifier: MIT
// Diagnostic-only GPU markers delimit request work in rocprof kernel traces.
#include <hip/hip_runtime.h>

#include <stdexcept>

__global__ void Q2ProfilePrefillBegin() {}
__global__ void Q2ProfilePrefillEnd() {}
__global__ void Q2ProfileDecodeBegin() {}
__global__ void Q2ProfileDecodeEnd() {}

void Q2ProfileMarker(int phase) {
  if (hipDeviceSynchronize() != hipSuccess)
    throw std::runtime_error("Profile boundary synchronization failed");
  switch (phase) {
  case 0:
    hipLaunchKernelGGL(Q2ProfilePrefillBegin, dim3(1), dim3(1), 0, nullptr);
    break;
  case 1:
    hipLaunchKernelGGL(Q2ProfilePrefillEnd, dim3(1), dim3(1), 0, nullptr);
    break;
  case 2:
    hipLaunchKernelGGL(Q2ProfileDecodeBegin, dim3(1), dim3(1), 0, nullptr);
    break;
  case 3:
    hipLaunchKernelGGL(Q2ProfileDecodeEnd, dim3(1), dim3(1), 0, nullptr);
    break;
  default:
    throw std::runtime_error("Invalid profile boundary");
  }
  if (hipGetLastError() != hipSuccess || hipDeviceSynchronize() != hipSuccess)
    throw std::runtime_error("Profile marker failed");
}
