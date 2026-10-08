/* SPDX-License-Identifier: MIT */
#include "lie/steering_activation.h"
#include <limits.h>
#include <math.h>
#include <stdio.h>

static lie_status refuse(lie_error *error, const char *message) {
  if (error) snprintf(error->message, sizeof(error->message), "%s", message);
  return LIE_INVALID;
}
lie_status lie_steering_activation_prepare(uint32_t width, uint32_t tokens,
  uint32_t branches, float scale, uint64_t activation_capacity,
  uint64_t direction_capacity, lie_steering_activation *out, lie_error *error) {
  if (!out || out->abi_version != LIE_STEERING_ACTIVATION_ABI ||
      out->struct_bytes != sizeof(*out))
    return refuse(error, "Invalid steering activation ABI");
  if (!width || !tokens || !branches || !isfinite(scale) ||
      scale < -100.0f || scale > 100.0f)
    return refuse(error, "Invalid steering activation geometry or scale");
  const uint64_t rows = (uint64_t)tokens * branches;
  /* One GPU block per row. Keep the count inside the portable signed grid
   * limit and check byte arithmetic before multiplying or addressing spans. */
  if (rows > INT32_MAX || rows > SIZE_MAX / sizeof(float) / width)
    return refuse(error, "Steering activation geometry exceeds address limits");
  const uint64_t elements = rows * width;
  const uint64_t bytes = elements * sizeof(float);
  const uint64_t direction = (uint64_t)width * sizeof(float);
  if (activation_capacity < bytes || direction_capacity < direction)
    return refuse(error, "Steering activation span is too small");
  const lie_steering_activation prepared = {
    .abi_version = LIE_STEERING_ACTIVATION_ABI, .struct_bytes = sizeof(*out),
    .width = width, .tokens = tokens, .branches = branches,
    .rows = (uint32_t)rows, .scale = scale == 0.0f ? 0.0f : scale,
    .elements = elements, .activation_bytes = bytes, .direction_bytes = direction
  };
  *out = prepared;
  return LIE_OK;
}
