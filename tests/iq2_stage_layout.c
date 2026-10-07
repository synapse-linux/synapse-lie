// SPDX-License-Identifier: MIT
#include "iq2_stage_layout.h"

#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum { kRows = 640, kRowBytes = 660, kBlockBytes = 66, kGroupBytes = 8,
       kGroupsPlaneBytes = 40 * 640 * 16, kExperts = 2 };

int main(void) {
  const size_t bytes = lie_iq2_stage_layout_bytes(kExperts);
  assert(bytes == kExperts * kRows * kRowBytes);
  assert(lie_iq2_stage_layout_bytes(0) == 0);
  assert(lie_iq2_stage_layout_bytes(SIZE_MAX) == 0);
  uint8_t *input = malloc(bytes + 32);
  uint8_t *packed = malloc(bytes + 32);
  uint8_t *decoded = malloc(bytes);
  assert(input && packed && decoded);
  memset(input, 0xA5, bytes + 32);
  memset(packed, 0x5A, bytes + 32);
  uint32_t state = 0xC0FFEE17u;
  for (size_t i = 0; i < bytes; ++i) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    input[i] = (uint8_t)state;
  }
  assert(!lie_iq2_stage_layout_pack(input, bytes - 1, packed, bytes, kExperts));
  assert(!lie_iq2_stage_layout_pack(input, bytes, packed, bytes - 1, kExperts));
  assert(!lie_iq2_stage_layout_pack(input, bytes, input, bytes, kExperts));
  assert(!lie_iq2_stage_layout_pack(input, bytes, input + 1, bytes, kExperts));
  for (size_t i = 0; i < bytes + 32; ++i)
    assert(packed[i] == 0x5A);
  assert(lie_iq2_stage_layout_pack(input, bytes, packed, bytes, kExperts));
  for (size_t i = bytes; i < bytes + 32; ++i) {
    assert(input[i] == 0xA5);
    assert(packed[i] == 0x5A);
  }
  for (size_t expert = 0; expert < kExperts; ++expert) {
    const uint8_t *in = packed + expert * kRows * kRowBytes;
    uint8_t *out = decoded + expert * kRows * kRowBytes;
    for (size_t row = 0; row < kRows; ++row)
      for (size_t block = 0; block < 10; ++block) {
        memcpy(out + row * kRowBytes + block * kBlockBytes,
               in + kGroupsPlaneBytes + (block * kRows + row) * 2, 2);
        for (size_t group = 0; group < 8; ++group) {
          const size_t pair = block * 4 + group / 2;
          memcpy(out + row * kRowBytes + block * kBlockBytes + 2 +
                     group * kGroupBytes,
                 in + (pair * kRows + row) * 16 +
                     (group % 2) * kGroupBytes,
                 kGroupBytes);
        }
      }
    // One 32-lane stage pair reads 16 consecutive rows of 16 bytes each.
    for (size_t pair = 0; pair < 40; ++pair)
      for (size_t first_row = 0; first_row < kRows; first_row += 16)
        for (size_t lane = 0; lane < 32; ++lane) {
          const size_t row = first_row + lane / 2;
          const size_t group = (pair % 4) * 2 + lane % 2;
          assert(memcmp(in + (pair * kRows + row) * 16 + (lane % 2) * 8,
                        input + expert * kRows * kRowBytes +
                            row * kRowBytes + (pair / 4) * kBlockBytes + 2 +
                            group * kGroupBytes,
                        8) == 0);
        }
  }
  assert(memcmp(decoded, input, bytes) == 0);
  free(decoded);
  free(packed);
  free(input);
  return 0;
}
