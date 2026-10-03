/* SPDX-License-Identifier: MIT */
#ifndef LIE_VISION_H
#define LIE_VISION_H
#include "lie/executor.h"
#ifdef __cplusplus
extern "C" {
#endif
#define LIE_VISION_ABI 1u
/* Allocation bounds, independent of any model's image grid or embedding width.
 */
#define LIE_VISION_MAX_IMAGES 16u
#define LIE_VISION_MAX_BYTES (8u * 1024u * 1024u)
#define LIE_VISION_MAX_PIXELS (32u * 1024u * 1024u)
typedef enum { LIE_IMAGE_PNG = 1, LIE_IMAGE_JPEG = 2 } lie_image_format;
typedef struct {
  const unsigned char *data;
  size_t bytes;
  lie_image_format format;
  uint32_t message_index;
  size_t
      text_offset; /* UTF-8 byte boundary; equal offsets retain input order. */
} lie_image_input;
typedef struct {
  uint32_t width, height;
} lie_image_dimensions;
/* Bounded header admission only; provider decoding must also validate pixels.
 */
lie_status lie_image_inspect(const lie_image_input *, lie_image_dimensions *,
                             lie_error *);
/* Host-only base64 data URL conversion, no network/filesystem authority.
 * Output is malloc-owned on success and unchanged on refusal. */
lie_status lie_image_data_url(const char *, size_t, unsigned char **, size_t *,
                              lie_image_format *, lie_error *);
typedef struct {
  uint32_t abi_version, struct_bytes;
  uint32_t max_images, max_pixels, max_encoded_bytes;
  uint32_t format_mask, prefix_state_supported;
} lie_vision_info;
typedef struct lie_vision_prompt lie_vision_prompt;
lie_status lie_backend_open_vision(const char *, const lie_model_options *,
                                   uint32_t, const char *, lie_model **,
                                   lie_error *);
lie_status lie_model_vision_info(lie_model *, lie_vision_info *, lie_error *);
/* Same owner/completed-call contract as executor ABI 2. The prepared object
 * owns pixels, placement and encoder identity; no upstream types escape.
 * Context admission uses expanded physical tokens, never text-only estimates.
 */
lie_status lie_model_prepare_vision(lie_model *, const lie_chat_template *,
                                    const lie_image_input *, size_t, int32_t *,
                                    size_t, size_t *, lie_vision_prompt **,
                                    lie_error *);
lie_status lie_sequence_attach_vision(lie_sequence *, const lie_vision_prompt *,
                                      lie_error *);
lie_status lie_vision_prompt_close(lie_vision_prompt **, lie_error *);
/* Immutable full prepared-prompt key, independent of token frontier. Different
 * future images conservatively prevent prefix reuse, even before their tokens.
 * Never an encoded-file hash supplied by HTTP. */
lie_status lie_vision_prompt_cache_scope(const lie_vision_prompt *, unsigned char out[32], lie_error *);
#ifdef __cplusplus
}
#endif
#endif
