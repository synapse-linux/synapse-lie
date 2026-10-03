/* SPDX-License-Identifier: MIT */
#include "lie/vision.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static lie_status invalid(lie_error *e, const char *s) {
  if (e)
    snprintf(e->message, sizeof(e->message), "%s", s);
  return LIE_INVALID;
}
static uint32_t be32(const unsigned char *p) {
  return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 |
         p[3];
}
static unsigned be16(const unsigned char *p) {
  return (unsigned)p[0] << 8 | p[1];
}
lie_status lie_image_inspect(const lie_image_input *in,
                             lie_image_dimensions *out, lie_error *e) {
  if (!in || !out || !in->data || !in->bytes ||
      in->bytes > LIE_VISION_MAX_BYTES)
    return invalid(e, "invalid image byte budget");
  const unsigned char *p = in->data;
  size_t n = in->bytes;
  uint32_t w = 0, h = 0;
  if (in->format == LIE_IMAGE_PNG) {
    if (n < 33 || memcmp(p, "\x89PNG\r\n\x1a\n", 8) || be32(p + 8) != 13 ||
        memcmp(p + 12, "IHDR", 4))
      return invalid(e, "invalid PNG header");
    w = be32(p + 16);
    h = be32(p + 20);
  } else if (in->format == LIE_IMAGE_JPEG) {
    if (n < 4 || p[0] != 255 || p[1] != 216)
      return invalid(e, "invalid JPEG header");
    size_t at = 2;
    while (at < n) {
      if (p[at++] != 255)
        return invalid(e, "invalid JPEG marker");
      while (at < n && p[at] == 255)
        ++at;
      if (at == n)
        return invalid(e, "truncated JPEG marker");
      unsigned tag = p[at++];
      if (!tag || tag == 218 || tag == 217)
        break;
      if (tag == 216 || (tag >= 208 && tag <= 215) || tag == 1)
        continue;
      if (n - at < 2)
        return invalid(e, "truncated JPEG length");
      size_t len = be16(p + at);
      if (len < 2 || len > n - at)
        return invalid(e, "invalid JPEG segment length");
      bool sof =
          (tag >= 192 && tag <= 207 && tag != 196 && tag != 200 && tag != 204);
      if (sof) {
        if (len < 8)
          return invalid(e, "invalid JPEG frame");
        h = be16(p + at + 3);
        w = be16(p + at + 5);
        break;
      }
      at += len;
    }
  } else
    return invalid(e, "unsupported image encoding");
  if (!w || !h || (uint64_t)w * h > LIE_VISION_MAX_PIXELS)
    return invalid(e, "image pixel budget exceeded");
  *out = (lie_image_dimensions){w, h};
  return LIE_OK;
}
static int sextet(unsigned char c) {
  if (c >= 'A' && c <= 'Z')
    return c - 'A';
  if (c >= 'a' && c <= 'z')
    return c - 'a' + 26;
  if (c >= '0' && c <= '9')
    return c - '0' + 52;
  if (c == '+')
    return 62;
  if (c == '/')
    return 63;
  return -1;
}
lie_status lie_image_data_url(const char *url, size_t n, unsigned char **out,
                              size_t *bytes, lie_image_format *format,
                              lie_error *e) {
  if (!url || !out || *out || !bytes || !format)
    return invalid(e, "invalid image output");
  const char *prefixes[] = {"data:image/png;base64,",
                            "data:image/jpeg;base64,"};
  size_t offset = 0;
  lie_image_format kind = 0;
  for (unsigned i = 0; i < 2; ++i) {
    size_t k = strlen(prefixes[i]);
    if (n >= k && !memcmp(url, prefixes[i], k)) {
      offset = k;
      kind = (lie_image_format)(i + 1);
      break;
    }
  }
  if (!offset)
    return invalid(
        e, "image input requires an inline PNG or JPEG base64 data URL");
  size_t count = n - offset;
  if (!count || count % 4 || count / 4 > (LIE_VISION_MAX_BYTES + 2) / 3)
    return invalid(e, "invalid image base64 budget");
  unsigned char *data = malloc(count / 4 * 3);
  if (!data)
    return invalid(e, "image allocation failed");
  size_t used = 0;
  for (size_t i = offset; i < n; i += 4) {
    int a = sextet((unsigned char)url[i]),
        b = sextet((unsigned char)url[i + 1]);
    int c = url[i + 2] == '=' ? -2 : sextet((unsigned char)url[i + 2]);
    int d = url[i + 3] == '=' ? -2 : sextet((unsigned char)url[i + 3]);
    if (a < 0 || b < 0 || c == -1 || d == -1 || (c == -2 && d != -2) ||
        ((c == -2 || d == -2) && i + 4 != n) || (c == -2 && (b & 15)) ||
        (d == -2 && c >= 0 && (c & 3))) {
      free(data);
      return invalid(e, "invalid canonical image base64");
    }
    data[used++] = (unsigned char)((a << 2) | (b >> 4));
    if (c >= 0)
      data[used++] = (unsigned char)((b << 4) | (c >> 2));
    if (d >= 0)
      data[used++] = (unsigned char)((c << 6) | d);
  }
  lie_image_input input = {.data = data, .bytes = used, .format = kind};
  lie_image_dimensions dims;
  if (lie_image_inspect(&input, &dims, e) != LIE_OK) {
    free(data);
    return LIE_INVALID;
  }
  *out = data;
  *bytes = used;
  *format = kind;
  return LIE_OK;
}
