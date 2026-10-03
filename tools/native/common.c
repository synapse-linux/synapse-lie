/* SPDX-License-Identifier: MIT */
#include "bench_native.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <math.h>
#include <openssl/evp.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

bool nb_fail(nb_error *e, const char *s) {
  if (e && s != e->message)
    snprintf(e->message, sizeof(e->message), "%s", s);
  return false;
}
json_object *nb_get(json_object *o, const char *k) {
  json_object *v = NULL;
  if (o && json_object_is_type(o, json_type_object))
    json_object_object_get_ex(o, k, &v);
  return v;
}
const char *nb_string(json_object *o, const char *k) {
  json_object *v = nb_get(o, k);
  return json_object_is_type(v, json_type_string) ? json_object_get_string(v)
                                                  : "";
}
int64_t nb_number(json_object *o, const char *k) {
  return json_object_get_int64(nb_get(o, k));
}
bool nb_count(json_object *o, const char *k, int64_t lo, int64_t hi,
              int64_t *out) {
  json_object *v = nb_get(o, k);
  if (!json_object_is_type(v, json_type_int))
    return false;
  int64_t n = json_object_get_int64(v);
  if (n == INT64_MAX && json_object_get_uint64(v) > INT64_MAX)
    return false;
  if (n < lo || n > hi)
    return false;
  if (out)
    *out = n;
  return true;
}
bool nb_same(json_object *a, json_object *b, const char *k) {
  return json_object_equal(nb_get(a, k), nb_get(b, k));
}
void nb_add(json_object *o, const char *k, json_object *v) {
  json_object_object_add(o, k, json_object_get(v));
}
void nb_str(json_object *o, const char *k, const char *v) {
  json_object_object_add(o, k, v ? json_object_new_string(v) : NULL);
}
void nb_num(json_object *o, const char *k, int64_t v) {
  json_object_object_add(o, k, json_object_new_int64(v));
}
void nb_real(json_object *o, const char *k, double v) {
  json_object_object_add(o, k, isfinite(v) ? json_object_new_double(v) : NULL);
}
json_object *nb_event(const char *s) {
  json_object *o = json_object_new_object();
  nb_str(o, "event", s);
  return o;
}
json_object *nb_copy(json_object *o) {
  json_object *v = NULL;
  if (o && json_object_deep_copy(o, &v, NULL))
    return NULL;
  return v;
}
const char *nb_encoded(json_object *o) {
  return json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN |
                                               JSON_C_TO_STRING_NOSLASHESCAPE);
}
bool nb_hash(const void *p, size_t n, char out[65]) {
  unsigned char h[32];
  unsigned count = 0;
  if (!EVP_Digest(p, n, h, &count, EVP_sha256(), NULL) || count != 32)
    return false;
  for (unsigned i = 0; i < 32; i++)
    snprintf(out + 2 * i, 3, "%02x", h[i]);
  return true;
}
bool nb_json_hash(json_object *o, char out[65]) {
  const char *s = nb_encoded(o);
  return s && nb_hash(s, strlen(s), out);
}
bool nb_file_hash(const char *path, char out[65]) {
  FILE *f = fopen(path, "rb");
  if (!f)
    return false;
  EVP_MD_CTX *ctx = EVP_MD_CTX_new();
  bool ok = ctx && EVP_DigestInit_ex(ctx, EVP_sha256(), NULL);
  unsigned char buf[65536], hash[32];
  size_t n;
  while (ok && (n = fread(buf, 1, sizeof(buf), f)))
    ok = EVP_DigestUpdate(ctx, buf, n);
  unsigned size = 0;
  ok = ok && !ferror(f) && EVP_DigestFinal_ex(ctx, hash, &size) && size == 32;
  EVP_MD_CTX_free(ctx);
  fclose(f);
  if (ok)
    for (unsigned i = 0; i < 32; i++)
      snprintf(out + 2 * i, 3, "%02x", hash[i]);
  return ok;
}
bool nb_ids_hash(json_object *ids, char out[65]) {
  if (!json_object_is_type(ids, json_type_array))
    return false;
  size_t n = json_object_array_length(ids);
  if (n > 1048576)
    return false;
  unsigned char *p = malloc(n * 4 + 1);
  if (!p)
    return false;
  bool ok = true;
  for (size_t i = 0; i < n; i++) {
    json_object *v = json_object_array_get_idx(ids, i);
    int64_t x = json_object_get_int64(v);
    if (!json_object_is_type(v, json_type_int) || x < 0 || x > INT32_MAX) {
      ok = false;
      break;
    }
    for (unsigned k = 0; k < 4; k++)
      p[4 * i + k] = (unsigned char)((uint64_t)x >> (k * 8));
  }
  if (ok)
    ok = nb_hash(p, n * 4, out);
  free(p);
  return ok;
}
uint64_t nb_now(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t))
    return 0;
  return (uint64_t)t.tv_sec * 1000000000u + (uint64_t)t.tv_nsec;
}
static bool json_values_valid(json_object *o) {
  if (json_object_is_type(o, json_type_double))
    return isfinite(json_object_get_double(o));
  if (json_object_is_type(o, json_type_string))
    return strlen(json_object_get_string(o)) ==
           (size_t)json_object_get_string_len(o);
  if (json_object_is_type(o, json_type_array)) {
    for (size_t i = 0; i < json_object_array_length(o); ++i)
      if (!json_values_valid(json_object_array_get_idx(o, i)))
        return false;
  } else if (json_object_is_type(o, json_type_object)) {
    json_object_object_foreach(o, key, value) {
      (void)key;
      if (!json_values_valid(value))
        return false;
    }
  }
  return true;
}
json_object *nb_parse(const char *s, size_t n, nb_error *e) {
  if (n > NB_LIMIT || n > INT_MAX) {
    nb_fail(e, "JSON size limit");
    return NULL;
  }
  json_tokener *t = json_tokener_new_ex(64);
  if (!t) {
    nb_fail(e, "JSON allocation failed");
    return NULL;
  }
  json_tokener_set_flags(t, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
  json_object *o = json_tokener_parse_ex(t, s, (int)n);
  bool ok = json_tokener_get_error(t) == json_tokener_success;
  size_t used = json_tokener_get_parse_end(t);
  while (used < n && (s[used] == ' ' || s[used] == '\n' || s[used] == '\r' ||
                      s[used] == '\t'))
    used++;
  json_tokener_free(t);
  if (!ok || used != n || !json_values_valid(o)) {
    json_object_put(o);
    nb_fail(e, "Malformed/trailing JSON, invalid UTF-8, embedded NUL or "
               "nonfinite number");
    return NULL;
  }
  return o;
}
json_object *nb_read(const char *path, bool lines, nb_error *e) {
  int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
  struct stat st;
  if (fd < 0) {
    nb_fail(e, "Cannot open input");
    return NULL;
  }
  if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size < 1 ||
      st.st_size > 256 * 1024 * 1024) {
    close(fd);
    nb_fail(e, "Input must be a bounded regular file");
    return NULL;
  }
  FILE *f = fdopen(fd, "r");
  if (!f) {
    close(fd);
    return NULL;
  }
  json_object *out = NULL;
  if (lines) {
    out = json_object_new_array();
    char *line = NULL;
    size_t cap = 0, total = 0;
    ssize_t n;
    while ((n = getline(&line, &cap, f)) >= 0) {
      total += (size_t)n;
      if ((size_t)n > NB_LIMIT || total > 256 * 1024 * 1024) {
        nb_fail(e, "JSONL size limit");
        json_object_put(out);
        out = NULL;
        break;
      }
      if (strspn(line, " \r\n\t") == (size_t)n)
        continue;
      json_object *row = nb_parse(line, (size_t)n, e);
      if (!row || json_object_array_length(out) >= 200000) {
        json_object_put(row);
        json_object_put(out);
        out = NULL;
        break;
      }
      json_object_array_add(out, row);
    }
    free(line);
  } else {
    size_t n = (size_t)st.st_size;
    char *s = malloc(n + 1);
    if (s && fread(s, 1, n, f) == n) {
      s[n] = 0;
      out = nb_parse(s, n, e);
    }
    free(s);
  }
  if (ferror(f)) {
    json_object_put(out);
    out = NULL;
    nb_fail(e, "Input read failed");
  }
  fclose(f);
  return out;
}
bool nb_emit(FILE *f, json_object *o) {
  const char *s = nb_encoded(o);
  return s && fputs(s, f) >= 0 && fputc('\n', f) != EOF && fflush(f) == 0;
}
FILE *nb_exclusive(const char *path, nb_error *e) {
  int fd =
      open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (fd < 0) {
    nb_fail(e, "Output exists or cannot be created");
    return NULL;
  }
  FILE *f = fdopen(fd, "w");
  if (!f) {
    close(fd);
    nb_fail(e, "Output stream failed");
  }
  return f;
}
bool nb_mkdir(const char *path, nb_error *e) {
  if (!path || !*path || strlen(path) >= PATH_MAX)
    return nb_fail(e, "Invalid output directory");
  char copy[PATH_MAX];
  strcpy(copy, path);
  for (char *p = copy + 1;; p++) {
    if (*p && *p != '/')
      continue;
    char save = *p;
    *p = 0;
    struct stat st;
    if (mkdir(copy, 0700) && errno != EEXIST)
      return nb_fail(e, "Cannot create output directory");
    if (lstat(copy, &st) || !S_ISDIR(st.st_mode))
      return nb_fail(e, "Output directory must not be a symlink");
    *p = save;
    if (!save)
      break;
  }
  return true;
}
static int number_cmp(const void *a, const void *b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}
json_object *nb_distribution(const double *values, size_t n) {
  if (!n)
    return NULL;
  double *v = malloc(n * sizeof(*v));
  if (!v)
    return NULL;
  memcpy(v, values, n * sizeof(*v));
  json_object *all = json_object_new_array();
  double sum = 0;
  for (size_t i = 0; i < n; i++) {
    if (!isfinite(v[i]) || v[i] < 0) {
      free(v);
      json_object_put(all);
      return NULL;
    }
    sum += v[i];
    json_object_array_add(all, json_object_new_double(v[i]));
  }
  qsort(v, n, sizeof(*v), number_cmp);
  json_object *o = json_object_new_object();
  nb_real(o, "median", n % 2 ? v[n / 2] : (v[n / 2 - 1] + v[n / 2]) / 2);
  nb_real(o, "mean", sum / n);
  nb_real(o, "min", v[0]);
  nb_real(o, "max", v[n - 1]);
  nb_num(o, "n", (int64_t)n);
  for (unsigned p = 50; p <= 99; p += (p == 50 ? 45 : 4)) {
    char key[8];
    snprintf(key, sizeof(key), "p%u", p);
    size_t at = (n * p + 99) / 100;
    nb_real(o, key, v[at - 1]);
  }
  json_object_object_add(o, "all", all);
  free(v);
  return o;
}
bool nb_write_json(const char *path, json_object *o, nb_error *e) {
  FILE *f = nb_exclusive(path, e);
  if (!f)
    return false;
  const char *s = json_object_to_json_string_ext(
      o, JSON_C_TO_STRING_PRETTY | JSON_C_TO_STRING_NOSLASHESCAPE);
  bool ok = s && fputs(s, f) >= 0 && fputc('\n', f) != EOF;
  if (fclose(f))
    ok = false;
  return ok ? true : nb_fail(e, "JSON output failed");
}
