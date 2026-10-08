/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Attributed registry/range/identity port from official Gufo f783fedb.
 * ICU property/set/conversion behavior is used through its public C API. */
#include "lie/grammar_unicode.h"
#include <stdlib.h>
#include <string.h>
#include <unicode/uchar.h>
#include <unicode/uset.h>
#include <unicode/ustring.h>
#include <unicode/uversion.h>
#define CLASSES 32768u
#define BYTES 16384u
_Static_assert(sizeof(UChar) == sizeof(uint16_t),
               "ICU UTF16 units must be 16 bit");
typedef struct set_handle {
  USet *value;
  struct set_handle *next;
} set_handle;
struct lie_grammar_unicode {
  lie_regex_compiler *compiler;
  lie_grammar_allocator allocator;
  USet **classes;
  size_t count, capacity, max_classes;
  set_handle *temporary;
};
typedef lie_regex_compile_status status;
static void *ordinary_allocate(void *ctx, size_t n) {
  (void)ctx;
  return malloc(n);
}
static void ordinary_release(void *ctx, void *p) {
  (void)ctx;
  free(p);
}
static void *alloc(lie_grammar_unicode *c, size_t n) {
  return c->allocator.allocate(c->allocator.context, n);
}
static void drop(lie_grammar_unicode *c, void *p) {
  if (p)
    c->allocator.release(c->allocator.context, p);
}
void lie_grammar_unicode_description_init(lie_grammar_unicode_description *d) {
  if (!d)
    return;
  memset(d, 0, sizeof(*d));
  d->abi_version = LIE_GRAMMAR_UNICODE_ABI;
  d->struct_bytes = sizeof(*d);
  d->max_classes = CLASSES;
  lie_regex_compiler_description_init(&d->compiler);
}
static status grow(lie_grammar_unicode *c, size_t need) {
  if (need > c->max_classes)
    return LIE_REGEX_COMPILE_CLASS_LIMIT;
  if (need <= c->capacity)
    return LIE_REGEX_COMPILE_OK;
  size_t n = c->capacity ? c->capacity : 8;
  if (n > c->max_classes)
    n = c->max_classes;
  while (n < need)
    n = n > c->max_classes / 2 ? c->max_classes : n * 2;
  USet **p = alloc(c, n * sizeof(*p));
  if (!p)
    return LIE_REGEX_COMPILE_RESOURCE;
  if (c->count)
    memcpy(p, c->classes, c->count * sizeof(*p));
  drop(c, c->classes);
  c->classes = p;
  c->capacity = n;
  return LIE_REGEX_COMPILE_OK;
}
status lie_grammar_unicode_create(const lie_grammar_unicode_description *d,
                                  lie_grammar_unicode **out) {
  if (!d || !out || d->abi_version != LIE_GRAMMAR_UNICODE_ABI ||
      d->struct_bytes != sizeof(*d) || !d->max_classes ||
      d->max_classes > CLASSES ||
      ((d->compiler.allocator.allocate == NULL) !=
       (d->compiler.allocator.release == NULL)))
    return LIE_REGEX_COMPILE_INVALID;
  lie_grammar_allocator a = d->compiler.allocator;
  if (!a.allocate) {
    a.allocate = ordinary_allocate;
    a.release = ordinary_release;
  }
  lie_grammar_unicode *c = a.allocate(a.context, sizeof(*c));
  if (!c)
    return LIE_REGEX_COMPILE_RESOURCE;
  *c = (lie_grammar_unicode){.allocator = a, .max_classes = d->max_classes};
  status rc = lie_regex_compiler_create(&d->compiler, &c->compiler);
  if (rc == LIE_REGEX_COMPILE_OK)
    rc = grow(c, 1);
  if (rc == LIE_REGEX_COMPILE_OK) {
    USet *scalars = uset_open(0, 0x10ffff);
    if (!scalars)
      rc = LIE_REGEX_COMPILE_RESOURCE;
    else {
      uset_removeRange(scalars, 0xd800, 0xdfff);
      c->classes[c->count++] = scalars;
    }
  }
  if (rc != LIE_REGEX_COMPILE_OK) {
    lie_grammar_unicode_release(c);
    return rc;
  }
  *out = c;
  return LIE_REGEX_COMPILE_OK;
}
void lie_grammar_unicode_release(lie_grammar_unicode *c) {
  if (!c)
    return;
  set_handle *s = c->temporary;
  while (s) {
    set_handle *next = s->next;
    uset_close(s->value);
    drop(c, s);
    s = next;
  }
  for (size_t i = 0; i < c->count; ++i)
    uset_close(c->classes[i]);
  lie_regex_compiler_release(c->compiler);
  drop(c, c->classes);
  lie_grammar_allocator a = c->allocator;
  a.release(a.context, c);
}
lie_regex_compiler *lie_grammar_unicode_compiler(lie_grammar_unicode *c) {
  return c ? c->compiler : NULL;
}
static status handle(lie_grammar_unicode *c, USet *value, void **out) {
  if (!value)
    return LIE_REGEX_COMPILE_RESOURCE;
  set_handle *p = alloc(c, sizeof(*p));
  if (!p) {
    uset_close(value);
    return LIE_REGEX_COMPILE_RESOURCE;
  }
  *p = (set_handle){value, c->temporary};
  c->temporary = p;
  *out = p;
  return LIE_REGEX_COMPILE_OK;
}
static status range(void *ctx, int32_t lo, int32_t hi, void **out) {
  return handle(ctx, uset_open(lo, hi), out);
}
static status property(void *ctx, const char *text, size_t n, void **out) {
  if (n > 136)
    return LIE_REGEX_COMPILE_INVALID;
  UChar pattern[136];
  for (size_t i = 0; i < n; ++i) {
    if ((unsigned char)text[i] > 127)
      return LIE_REGEX_COMPILE_INVALID;
    pattern[i] = (UChar)(unsigned char)text[i];
  }
  UErrorCode ec = U_ZERO_ERROR;
  USet *s = uset_openPatternOptions(pattern, (int32_t)n, 0, &ec);
  if (U_FAILURE(ec)) {
    if (s)
      uset_close(s);
    return ec == U_MEMORY_ALLOCATION_ERROR ? LIE_REGEX_COMPILE_RESOURCE
                                           : LIE_REGEX_COMPILE_INVALID;
  }
  return handle(ctx, s, out);
}
static status add(void *ctx, void *dst, const void *src) {
  (void)ctx;
  uset_addAll(((set_handle *)dst)->value, ((const set_handle *)src)->value);
  return LIE_REGEX_COMPILE_OK;
}
static status add_range(void *ctx, void *dst, int32_t lo, int32_t hi) {
  (void)ctx;
  uset_addRange(((set_handle *)dst)->value, lo, hi);
  return LIE_REGEX_COMPILE_OK;
}
static status remove_range(void *ctx, void *dst, int32_t lo, int32_t hi) {
  (void)ctx;
  uset_removeRange(((set_handle *)dst)->value, lo, hi);
  return LIE_REGEX_COMPILE_OK;
}
static status complement(void *ctx, void *dst) {
  (void)ctx;
  uset_complement(((set_handle *)dst)->value);
  return LIE_REGEX_COMPILE_OK;
}
static status info(void *ctx, const void *src, uint64_t *size, int32_t *first) {
  (void)ctx;
  USet *s = ((const set_handle *)src)->value;
  *size = (uint64_t)uset_size(s);
  *first = uset_charAt(s, 0);
  return LIE_REGEX_COMPILE_OK;
}
static status publish(void *ctx, const void *src, uint32_t *out) {
  lie_grammar_unicode *c = ctx;
  USet *copy = uset_cloneAsThawed(((const set_handle *)src)->value);
  if (!copy)
    return LIE_REGEX_COMPILE_RESOURCE;
  uset_removeRange(copy, 0xd800, 0xdfff);
  lie_regex_bases b;
  status rc = lie_regex_compiler_bases(c->compiler, &b);
  if (rc == LIE_REGEX_COMPILE_OK && uset_isEmpty(copy)) {
    uset_close(copy);
    *out = b.empty;
    return LIE_REGEX_COMPILE_OK;
  }
  size_t id = 0;
  for (; rc == LIE_REGEX_COMPILE_OK && id < c->count; ++id)
    if (uset_equals(copy, c->classes[id]))
      break;
  if (rc == LIE_REGEX_COMPILE_OK && id == c->count) {
    rc = grow(c, c->count + 1);
    int32_t count = uset_getRangeCount(copy);
    lie_unicode_range *ranges = NULL;
    if (rc == LIE_REGEX_COMPILE_OK && count) {
      ranges = alloc(c, (size_t)count * sizeof(*ranges));
      if (!ranges)
        rc = LIE_REGEX_COMPILE_RESOURCE;
    }
    for (int32_t i = 0; rc == LIE_REGEX_COMPILE_OK && i < count; ++i) {
      UChar32 first, last;
      UErrorCode ec = U_ZERO_ERROR;
      int32_t chars = uset_getItem(copy, i, &first, &last, NULL, 0, &ec);
      if (U_FAILURE(ec) || chars != 0 || first < 0 || last < first)
        rc = LIE_REGEX_COMPILE_INVALID;
      else
        ranges[i] = (lie_unicode_range){(uint32_t)first, (uint32_t)last};
    }
    uint32_t inserted;
    if (rc == LIE_REGEX_COMPILE_OK)
      rc = lie_regex_class_add(c->compiler, ranges, (size_t)count, &inserted);
    drop(c, ranges);
    if (rc == LIE_REGEX_COMPILE_OK && inserted != id)
      rc = LIE_REGEX_COMPILE_INVALID;
    if (rc == LIE_REGEX_COMPILE_OK) {
      c->classes[c->count++] = copy;
      copy = NULL;
    }
  }
  if (copy)
    uset_close(copy);
  return rc == LIE_REGEX_COMPILE_OK
             ? lie_regex_chars(c->compiler, (uint32_t)id, out)
             : rc;
}
static status boundary(void *ctx, bool positive, uint32_t *out) {
  lie_grammar_unicode *c = ctx;
  void *raw = NULL;
  status rc = range(ctx, 'a', 'z', &raw);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc;
  add_range(ctx, raw, 'A', 'Z');
  add_range(ctx, raw, '0', '9');
  add_range(ctx, raw, '_', '_');
  uint32_t ignored;
  rc = publish(ctx, raw, &ignored);
  set_handle *s = raw;
  set_handle **at = &c->temporary;
  while (*at != s)
    at = &(*at)->next;
  *at = s->next;
  uset_close(s->value);
  drop(c, s);
  return rc == LIE_REGEX_COMPILE_OK
             ? lie_regex_boundary(c->compiler, positive, out)
             : rc;
}
static void release_set(void *ctx, void *raw) {
  lie_grammar_unicode *c = ctx;
  set_handle *s = raw;
  set_handle **at = &c->temporary;
  while (*at && *at != s)
    at = &(*at)->next;
  if (*at) {
    *at = s->next;
    uset_close(s->value);
    drop(c, s);
  }
}
status lie_grammar_unicode_sets(lie_grammar_unicode *c,
                                lie_regex_unicode_sets *out) {
  if (!c || !out)
    return LIE_REGEX_COMPILE_INVALID;
  *out = (lie_regex_unicode_sets){c,         range,        property,   add,
                                  add_range, remove_range, complement, info,
                                  publish,   boundary,     release_set};
  return LIE_REGEX_COMPILE_OK;
}
static bool overlap(const void *a, size_t an, const void *b, size_t bn) {
  if (!an || !bn)
    return false;
  uintptr_t av = (uintptr_t)a, bv = (uintptr_t)b;
  return av > UINTPTR_MAX - an || bv > UINTPTR_MAX - bn ||
         (av < bv + bn && bv < av + an);
}
status lie_grammar_utf8_to_utf16(const char *src, size_t n, uint16_t *dst,
                                 size_t capacity, size_t *out) {
  if (!out || (n && !src) || n > BYTES || capacity > BYTES + 1 ||
      (capacity && !dst) || overlap(src, n, dst, capacity * sizeof(*dst)) ||
      overlap(src, n, out, sizeof(*out)) ||
      overlap(dst, capacity * sizeof(*dst), out, sizeof(*out)))
    return LIE_REGEX_COMPILE_INVALID;
  UErrorCode ec = U_ZERO_ERROR;
  int32_t needed = 0;
  u_strFromUTF8WithSub(NULL, 0, &needed, src ? src : "", (int32_t)n, 0xfffd,
                       NULL, &ec);
  if (ec != U_BUFFER_OVERFLOW_ERROR && U_FAILURE(ec))
    return LIE_REGEX_COMPILE_INVALID;
  if ((size_t)needed > capacity)
    return LIE_REGEX_COMPILE_RESOURCE;
  if (needed) {
    ec = U_ZERO_ERROR;
    int32_t length = 0;
    u_strFromUTF8WithSub((UChar *)dst, (int32_t)capacity, &length, src,
                         (int32_t)n, 0xfffd, NULL, &ec);
    if (U_FAILURE(ec) || length != needed)
      return LIE_REGEX_COMPILE_INVALID;
  }
  *out = (size_t)needed;
  return LIE_REGEX_COMPILE_OK;
}
lie_regex_parse_status
lie_grammar_unicode_parse(lie_grammar_unicode *c, const char *src, size_t n,
                          const lie_regex_parser_description *d, uint32_t *out,
                          lie_regex_parse_error *error) {
  lie_regex_parse_status rc = LIE_REGEX_PARSE_INVALID;
  if (!c || !d || !out || (n && !src))
    goto fail;
  if (n > BYTES) {
    rc = LIE_REGEX_PARSE_BYTES;
    goto fail;
  }
  uint16_t *units = n ? alloc(c, (n + 1) * sizeof(*units)) : NULL;
  if (n && !units) {
    rc = LIE_REGEX_PARSE_RESOURCE;
    goto fail;
  }
  size_t length = 0;
  status decode =
      lie_grammar_utf8_to_utf16(src, n, units, n ? n + 1 : 0, &length);
  lie_regex_unicode_sets sets;
  lie_grammar_unicode_sets(c, &sets);
  if (decode == LIE_REGEX_COMPILE_OK)
    rc = lie_regex_parse_utf16(c->compiler, units, length, n, &sets, d, out,
                               error);
  else {
    rc = decode == LIE_REGEX_COMPILE_RESOURCE ? LIE_REGEX_PARSE_RESOURCE
                                              : LIE_REGEX_PARSE_INVALID;
    if (error)
      *error = (lie_regex_parse_error){rc, decode};
  }
  drop(c, units);
  return rc;
fail:
  if (error)
    *error = (lie_regex_parse_error){rc, LIE_REGEX_COMPILE_INVALID};
  return rc;
}
status lie_grammar_unicode_versions(char *icu, size_t in, char *unicode,
                                    size_t un) {
  if (!icu || !unicode || in < U_MAX_VERSION_STRING_LENGTH ||
      un < U_MAX_VERSION_STRING_LENGTH || overlap(icu, in, unicode, un))
    return LIE_REGEX_COMPILE_INVALID;
  UVersionInfo v;
  char a[U_MAX_VERSION_STRING_LENGTH], b[U_MAX_VERSION_STRING_LENGTH];
  u_getVersion(v);
  u_versionToString(v, a);
  u_getUnicodeVersion(v);
  u_versionToString(v, b);
  strcpy(icu, a);
  strcpy(unicode, b);
  return LIE_REGEX_COMPILE_OK;
}
