/* SPDX-License-Identifier: MIT */
/* Gufo f783fedb workload port; copyright (c) 2026 gufo contributors.
 * See third_party/gufo-LICENSE and gufo-bench-source.json.
 * Independently implemented MT19937 with Python integer-seed/draw semantics.
 * No interpreter, upstream module or external generator is executed. */
#include "bench_native.h"
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  uint32_t state[624];
  unsigned at;
} rng;
static uint32_t draw(rng *r) {
  if (r->at == 624) {
    for (unsigned i = 0; i < 624; ++i) {
      uint32_t pair = (r->state[i] & UINT32_C(0x80000000)) |
                      (r->state[(i + 1) % 624] & UINT32_C(0x7fffffff));
      r->state[i] = r->state[(i + 397) % 624] ^ (pair >> 1) ^
                    ((pair & 1) ? UINT32_C(0x9908b0df) : 0);
    }
    r->at = 0;
  }
  uint32_t n = r->state[r->at++];
  n ^= n >> 11;
  n ^= (n << 7) & UINT32_C(0x9d2c5680);
  n ^= (n << 15) & UINT32_C(0xefc60000);
  return n ^ (n >> 18);
}
static void seed_rng(rng *r, uint64_t seed) {
  uint32_t key[2] = {(uint32_t)seed, (uint32_t)(seed >> 32)};
  unsigned keys = key[1] ? 2 : 1;
  r->state[0] = 19650218;
  for (unsigned i = 1; i < 624; ++i)
    r->state[i] =
        UINT32_C(1812433253) * (r->state[i - 1] ^ (r->state[i - 1] >> 30)) + i;
  unsigned i = 1, j = 0;
  for (unsigned k = 0; k < 624; ++k) {
    r->state[i] = (r->state[i] ^ ((r->state[i - 1] ^ (r->state[i - 1] >> 30)) *
                                  UINT32_C(1664525))) +
                  key[j] + j;
    if (++i == 624) {
      r->state[0] = r->state[623];
      i = 1;
    }
    if (++j == keys)
      j = 0;
  }
  for (unsigned k = 0; k < 623; ++k) {
    r->state[i] = (r->state[i] ^ ((r->state[i - 1] ^ (r->state[i - 1] >> 30)) *
                                  UINT32_C(1566083941))) -
                  i;
    if (++i == 624) {
      r->state[0] = r->state[623];
      i = 1;
    }
  }
  r->state[0] = UINT32_C(0x80000000);
  r->at = 624;
}
static unsigned below(rng *r, unsigned bound) {
  unsigned bits = 0, n = bound;
  do {
    ++bits;
    n >>= 1;
  } while (n);
  do {
    n = draw(r) >> (32 - bits);
  } while (n >= bound);
  return n;
}
static double uniform(rng *r) {
  uint32_t a = draw(r) >> 5, b = draw(r) >> 6;
  return (a * 67108864.0 + b) / 9007199254740992.0;
}
static const char vocabulary[] =
    "the river bends past a quiet town where old mills once ground wheat for "
    "every family along the valley and children still climb the stone bridge "
    "to watch boats carry timber salt and wool toward distant markets while "
    "farmers mend fences count sheep and argue about rain clouds that gather "
    "over the western hills each autumn evening before the harvest festival "
    "brings music lanterns and long tables of bread cheese apples and cider "
    "shared by neighbours who remember older winters when snow closed the "
    "road for weeks and stories were traded by firelight instead of coins";
static const struct {
  const char *name, *instruction;
} tasks[] = {
    {"prose", "\n\nSummarize the passage above in detail, then write a short "
              "story inspired by it. Write at least 500 words."},
    {"repetition",
     "\n\nRepeat the passage above word for word, from the beginning."},
    {"copy", "\n\nCopy ONLY the passage in this message verbatim. Start with "
             "its first word, preserve every word and punctuation mark, and "
             "continue until the complete passage has been copied. Do not "
             "comment, summarize, or use ellipses."},
    {"story", "\n\nUse the passage only as inspiration for an original story "
              "about a river town. Do not analyze or summarize the passage. "
              "Begin the story immediately and write at least 1000 words, with "
              "detailed scenes, dialogue, and a developing plot."},
    {"thinking",
     "\n\nHow many distinct words appear in the passage above, and which three "
     "are the most frequent? Work through it carefully before answering."}};
const char *nb_gufo_instruction(const char *task) {
  for (size_t i = 0; i < sizeof(tasks) / sizeof(*tasks); ++i)
    if (!strcmp(task, tasks[i].name))
      return tasks[i].instruction;
  return NULL;
}
size_t nb_gufo_word_count(const char *s) {
  size_t n = 0;
  bool word = false;
  for (; *s; ++s) {
    bool space = *s == ' ' || *s == '\n' || *s == '\r' || *s == '\t' ||
                 *s == '\v' || *s == '\f';
    if (!space && !word)
      ++n;
    word = !space;
  }
  return n;
}
/* round() in the upstream recipe is ties-to-even, independent of the process
 * floating-point rounding mode. Negative prefix targets still select one word.
 */
size_t nb_gufo_words(double tokens, double ratio) {
  if (!isfinite(tokens) || !isfinite(ratio) || ratio <= 0)
    return 0;
  double x = tokens / ratio;
  if (!isfinite(x) || x > NB_LIMIT / 10)
    return 0;
  if (x <= 1)
    return 1;
  double n = floor(x), part = x - n;
  if (part > .5 || (part == .5 && fmod(n, 2) != 0))
    ++n;
  return (size_t)n;
}
char *nb_gufo_text(uint64_t seed, size_t words, nb_error *e) {
  if (!words || words > (NB_LIMIT - 1) / 12) {
    nb_fail(e, "Gufo workload word count exceeds the bounded text capacity");
    return NULL;
  }
  char dictionary[sizeof(vocabulary)];
  memcpy(dictionary, vocabulary, sizeof(dictionary));
  const char *list[128];
  unsigned count = 0;
  char *save = NULL;
  for (char *w = strtok_r(dictionary, " ", &save); w;
       w = strtok_r(NULL, " ", &save))
    list[count++] = w;
  char *out = malloc(words * 12 + 1);
  if (!out) {
    nb_fail(e, "Gufo workload allocation failed");
    return NULL;
  }
  rng r;
  seed_rng(&r, seed);
  size_t used = 0, pos = 0;
  bool paragraph = false;
  while (used < words) {
    unsigned sentence = 6 + below(&r, 9);
    if (sentence > words - used)
      sentence = (unsigned)(words - used);
    if (pos) {
      if (paragraph) {
        out[pos++] = '\n';
        out[pos++] = '\n';
      } else
        out[pos++] = ' ';
    }
    for (unsigned i = 0; i < sentence; ++i) {
      const char *w = list[below(&r, count)];
      if (i)
        out[pos++] = ' ';
      size_t len = strlen(w);
      memcpy(out + pos, w, len);
      if (!i)
        out[pos] = (char)toupper((unsigned char)out[pos]);
      pos += len;
    }
    out[pos++] = '.';
    used += sentence;
    paragraph = uniform(&r) < .2;
  }
  out[pos] = 0;
  return out;
}
char *nb_gufo_turn(double target, double ratio, const char *task,
                   uint64_t depth, unsigned rep, unsigned attempt,
                   nb_error *e) {
  const char *instruction = nb_gufo_instruction(task);
  size_t words = nb_gufo_words(target, ratio);
  if (!instruction || !words ||
      depth > (UINT64_MAX - 100000 - rep * 100u - attempt) / 10) {
    nb_fail(e, "Invalid Gufo turn recipe");
    return NULL;
  }
  size_t tail_words = nb_gufo_word_count(instruction);
  words = words > tail_words ? words - tail_words : 1;
  char *prefix =
      nb_gufo_text(100000 + depth * 10 + rep * 100u + attempt, words, e);
  if (!prefix)
    return NULL;
  size_t n = strlen(prefix), k = strlen(instruction);
  char *out = realloc(prefix, n + k + 1);
  if (!out) {
    free(prefix);
    nb_fail(e, "Gufo turn allocation failed");
    return NULL;
  }
  memcpy(out + n, instruction, k + 1);
  return out;
}
