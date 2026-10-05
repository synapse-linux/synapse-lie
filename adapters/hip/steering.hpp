// SPDX-License-Identifier: MIT
#ifndef LIE_HIP_STEERING_HPP
#define LIE_HIP_STEERING_HPP
#include <hip/hip_runtime.h>
#include "lie/steering_activation.h"
// Private numerical binding. Pointers are device spans whose capacities were
// checked by the C17 descriptor. Borrowed data survives through stream drain.
// Positive scale removes a direction; negative scale amplifies it. No rescale.
hipError_t lie_hip_direction_remove(float* activations, const float* direction,
  const lie_steering_activation&, hipStream_t);
#endif
