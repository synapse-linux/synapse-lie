// SPDX-License-Identifier: MIT
#include "iq2_stage_layout.h"

#include <limits.h>
#include <string.h>

enum {
  kRows = 640,
  kSuperblocks = 10,
  kGroupsPerSuperblock = 8,
  kGroupBytes = 8,
  kScaleBytes = 2,
  kBlockBytes = 66,
  kRowBytes = kSuperblocks * kBlockBytes,
  kStagePairs = 40,
  kPairBytes = 16,
  kGroupsPlaneBytes = kStagePairs * kRows * kPairBytes,
  kExpertBytes = kRows * kRowBytes
};

size_t lie_iq2_stage_layout_bytes(size_t experts) {
  if (experts == 0 || experts > SIZE_MAX / kExpertBytes)
    return 0;
  return experts * kExpertBytes;
}

int lie_iq2_stage_layout_pack(const uint8_t *source, size_t source_bytes,
                              uint8_t *destination, size_t destination_bytes,
                              size_t experts) {
  const size_t bytes = lie_iq2_stage_layout_bytes(experts);
  if (!source || !destination || !bytes || source_bytes < bytes ||
      destination_bytes < bytes)
    return 0;
  const uintptr_t first = (uintptr_t)source;
  const uintptr_t second = (uintptr_t)destination;
  if (first > UINTPTR_MAX - bytes || second > UINTPTR_MAX - bytes ||
      (first < second + bytes && second < first + bytes))
    return 0;

  for (size_t expert = 0; expert < experts; ++expert) {
    const uint8_t *in = source + expert * kExpertBytes;
    uint8_t *out = destination + expert * kExpertBytes;
    for (size_t pair = 0; pair < kStagePairs; ++pair) {
      const size_t block = pair / (kGroupsPerSuperblock / 2);
      const size_t group = (pair % (kGroupsPerSuperblock / 2)) * 2;
      for (size_t row = 0; row < kRows; ++row)
        memcpy(out + (pair * kRows + row) * kPairBytes,
               in + row * kRowBytes + block * kBlockBytes + kScaleBytes +
                   group * kGroupBytes,
               kPairBytes);
    }
    for (size_t block = 0; block < kSuperblocks; ++block)
      for (size_t row = 0; row < kRows; ++row)
        memcpy(out + kGroupsPlaneBytes +
                   (block * kRows + row) * kScaleBytes,
               in + row * kRowBytes + block * kBlockBytes, kScaleBytes);
  }
  return 1;
}
