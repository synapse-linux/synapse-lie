/* SPDX-License-Identifier: MIT */
#include "generation.h"
#include <math.h>
#include <string.h>
bool lie_stop_feed(lie_stop_state *s, const lie_core_request *r, char *text,
                   size_t *bytes, size_t capacity, bool end) {
  if (!r->stop_count)
    return true;
  if (s->matched) {
    *bytes = 0;
    return true;
  }
  if (s->bytes > capacity - *bytes)
    return false;
  memmove(text + s->bytes, text, *bytes);
  memcpy(text, s->pending, s->bytes);
  *bytes += s->bytes;
  s->bytes = 0;
  size_t first = *bytes;
  for (size_t k = 0; k < r->stop_count; ++k) {
    size_t n = strlen(r->stop[k]);
    for (size_t i = 0; i + n <= *bytes; ++i)
      if (!memcmp(text + i, r->stop[k], n)) {
        if (i < first)
          first = i;
        break;
      }
  }
  if (first < *bytes) {
    *bytes = first;
    s->matched = true;
    return true;
  }
  if (end)
    return true;
  size_t hold = 0;
  for (size_t k = 0; k < r->stop_count; ++k) {
    size_t n = strlen(r->stop[k]);
    for (size_t i = 1; i < n && i <= *bytes; ++i)
      if (i > hold && !memcmp(text + *bytes - i, r->stop[k], i))
        hold = i;
  }
  if (hold) {
    memcpy(s->pending, text + *bytes - hold, hold);
    s->bytes = hold;
    *bytes -= hold;
  }
  return true;
}
bool lie_logprob_row(const float *row, size_t n, unsigned top,
                     lie_token_logprobs *out) {
  if (!row || !n || !out || top > LIE_TOP_LOGPROBS_MAX)
    return false;
  *out = (lie_token_logprobs){0};
  double peak = -INFINITY;
  for (size_t i = 0; i < n; ++i) {
    if (isnan(row[i]) || row[i] == INFINITY)
      return false;
    if (row[i] > peak)
      peak = row[i];
  }
  if (!isfinite(peak))
    return false;
  double sum = 0;
  for (size_t i = 0; i < n; ++i)
    sum += exp((double)row[i] - peak);
  double norm = peak + log(sum);
  for (size_t i = 0; i < n; ++i) {
    if (!isfinite(row[i]))
      continue;
    double p = (double)row[i] - norm;
    unsigned at = out->top_count;
    if (at == top) {
      if (!top || p <= out->top[top - 1].logprob)
        continue;
      at = top - 1;
    }
    while (at && p > out->top[at - 1].logprob) {
      if (at < top)
        out->top[at] = out->top[at - 1];
      --at;
    }
    out->top[at] = (lie_token_probability){.token = (int32_t)i, .logprob = p};
    if (out->top_count < top)
      ++out->top_count;
  }
  out->token.logprob =
      norm; /* Normalizer until the completed token is known. */
  return true;
}
