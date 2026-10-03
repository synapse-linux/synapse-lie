/* SPDX-License-Identifier: MIT */
/* Private bounded JSON values for model output/schema checks. No transport or
 * JSON library dependency. Syntax, decoded UTF-8/NUL, finite numbers and depth
 * are checked before exposing a value. Not a general JSON-Schema engine. */
#include "output_json.h"
#include "lie/text.h"
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  const char *p, *end;
  size_t nodes;
} reader;
static void ws(reader *r) {
  while (r->p < r->end &&
         (*r->p == ' ' || *r->p == '\n' || *r->p == '\r' || *r->p == '\t'))
    ++r->p;
}
void oj_free(oj_node *v) {
  while (v) {
    oj_node *next = v->next;
    oj_free(v->child);
    free(v->string);
    free(v);
    v = next;
  }
}
static int hex(char c) {
  if (c >= '0' && c <= '9')
    return c - '0';
  if (c >= 'a' && c <= 'f')
    return c - 'a' + 10;
  if (c >= 'A' && c <= 'F')
    return c - 'A' + 10;
  return -1;
}
static bool unit(reader *r, uint32_t *v) {
  if (r->end - r->p < 4)
    return false;
  *v = 0;
  for (unsigned i = 0; i < 4; ++i) {
    int h = hex(*r->p++);
    if (h < 0)
      return false;
    *v = *v * 16 + (unsigned)h;
  }
  return true;
}
static char *string(reader *r) {
  if (r->p == r->end || *r->p++ != '"')
    return NULL;
  const char *start = r->p, *scan = start;
  bool escaped = false;
  while (scan < r->end) {
    char c = *scan++;
    if (!escaped && c == '"')
      break;
    if (!escaped && c == '\\')
      escaped = true;
    else
      escaped = false;
  }
  if (scan == start || scan[-1] != '"' || escaped)
    return NULL;
  char *out = malloc((size_t)(scan - start) + 1);
  if (!out)
    return NULL;
  size_t n = 0;
  bool closed = false;
  while (r->p < r->end) {
    unsigned char c = (unsigned char)*r->p++;
    if (c == '"') {
      closed = true;
      break;
    }
    if (c < 32)
      goto fail;
    if (c != '\\') {
      out[n++] = (char)c;
      continue;
    }
    if (r->p == r->end)
      goto fail;
    char e = *r->p++;
    if (e == '"' || e == '\\' || e == '/')
      out[n++] = e;
    else if (e == 'b')
      out[n++] = '\b';
    else if (e == 'f')
      out[n++] = '\f';
    else if (e == 'n')
      out[n++] = '\n';
    else if (e == 'r')
      out[n++] = '\r';
    else if (e == 't')
      out[n++] = '\t';
    else if (e == 'u') {
      uint32_t u;
      if (!unit(r, &u) || !u)
        goto fail;
      if (u >= 0xd800 && u <= 0xdbff) {
        uint32_t lo;
        if (r->end - r->p < 2 || memcmp(r->p, "\\u", 2))
          goto fail;
        r->p += 2;
        if (!unit(r, &lo) || lo < 0xdc00 || lo > 0xdfff)
          goto fail;
        u = 0x10000 + (u - 0xd800) * 1024 + lo - 0xdc00;
      } else if (u >= 0xdc00 && u <= 0xdfff)
        goto fail;
      if (u < 128)
        out[n++] = (char)u;
      else if (u < 2048) {
        out[n++] = (char)(0xc0 | (u >> 6));
        out[n++] = (char)(0x80 | (u & 63));
      } else if (u < 65536) {
        out[n++] = (char)(0xe0 | (u >> 12));
        out[n++] = (char)(0x80 | ((u >> 6) & 63));
        out[n++] = (char)(0x80 | (u & 63));
      } else {
        out[n++] = (char)(0xf0 | (u >> 18));
        out[n++] = (char)(0x80 | ((u >> 12) & 63));
        out[n++] = (char)(0x80 | ((u >> 6) & 63));
        out[n++] = (char)(0x80 | (u & 63));
      }
    } else
      goto fail;
  }
  if (!closed || !lie_utf8_valid(out, n, false))
    goto fail;
  out[n] = 0;
  return out;
fail:
  free(out);
  return NULL;
}
static bool digit(reader *r) {
  return r->p < r->end && *r->p >= '0' && *r->p <= '9';
}
static bool number(reader *r, double *out) {
  bool minus = r->p < r->end && *r->p == '-';
  if (minus)
    ++r->p;
  if (!digit(r))
    return false;
  /* Keep a bounded significant mantissa and decimal scale. Very long but
   * small finite literals never overflow an intermediate parser accumulator. */
  long double m = 0;
  int scale = 0;
  unsigned kept = 0;
  bool nonzero = false;
  const char *integer = r->p;
  while (digit(r)) {
    unsigned d = (unsigned)(*r->p++ - '0');
    nonzero |= d != 0;
    if (!nonzero)
      continue;
    if (kept < 19) {
      m = m * 10 + d;
      ++kept;
    } else if (scale < 1000000)
      ++scale;
  }
  if (r->p - integer > 1 && *integer == '0')
    return false;
  if (r->p < r->end && *r->p == '.') {
    ++r->p;
    if (!digit(r))
      return false;
    while (digit(r)) {
      unsigned d = (unsigned)(*r->p++ - '0');
      nonzero |= d != 0;
      if (!nonzero) {
        if (scale > -1000000)
          --scale;
        continue;
      }
      if (kept < 19) {
        m = m * 10 + d;
        ++kept;
        if (scale > -1000000)
          --scale;
      }
    }
  }
  if (r->p < r->end && (*r->p == 'e' || *r->p == 'E')) {
    ++r->p;
    bool neg = false;
    if (r->p < r->end && (*r->p == '+' || *r->p == '-'))
      neg = *r->p++ == '-';
    if (!digit(r))
      return false;
    int exponent = 0;
    while (digit(r)) {
      unsigned d = (unsigned)(*r->p++ - '0');
      if (exponent < 1000000)
        exponent = exponent * 10 + (int)d;
    }
    scale += neg ? -exponent : exponent;
  }
  if (!nonzero) {
    *out = minus ? -0.0 : 0.0;
    return true;
  }
  if (scale > 309)
    return false;
  long double v = scale < -400 ? 0 : m * powl(10, (long double)scale);
  *out = (double)(minus ? -v : v);
  return isfinite(*out);
}
static oj_node *value(reader *r, unsigned depth) {
  ws(r);
  if (r->p == r->end || depth >= 32 || ++r->nodes > 32768)
    return NULL;
  oj_node *v = calloc(1, sizeof(*v));
  if (!v)
    return NULL;
  v->start = r->p;
  char c = *r->p;
  if (c == '"') {
    v->type = OJ_STRING;
    v->string = string(r);
    if (!v->string)
      goto fail;
  } else if (c == '{' || c == '[') {
    v->type = c == '{' ? OJ_OBJECT : OJ_ARRAY;
    ++r->p;
    ws(r);
    char closing = c == '{' ? '}' : ']';
    oj_node **tail = &v->child;
    if (r->p < r->end && *r->p == closing)
      ++r->p;
    else
      for (;;) {
        if (c == '{') {
          oj_node *key = calloc(1, sizeof(*key));
          if (!key)
            goto fail;
          key->type = OJ_STRING;
          key->start = r->p;
          key->string = string(r);
          if (!key->string) {
            free(key);
            goto fail;
          }
          key->bytes = (size_t)(r->p - key->start);
          for (oj_node *p = v->child; p; p = p->next->next)
            if (!strcmp(p->string, key->string)) {
              oj_free(key);
              goto fail;
            }
          *tail = key;
          tail = &key->next;
          ws(r);
          if (r->p == r->end || *r->p++ != ':')
            goto fail;
        }
        oj_node *part = value(r, depth + 1);
        if (!part)
          goto fail;
        *tail = part;
        tail = &part->next;
        ws(r);
        if (r->p == r->end)
          goto fail;
        if (*r->p == closing) {
          ++r->p;
          break;
        }
        if (*r->p++ != ',')
          goto fail;
        ws(r);
      }
  } else if (c == '-' || (c >= '0' && c <= '9')) {
    v->type = OJ_NUMBER;
    if (!number(r, &v->number))
      goto fail;
  } else {
    const char *literal = c == 't'   ? "true"
                          : c == 'f' ? "false"
                          : c == 'n' ? "null"
                                     : "";
    size_t n = strlen(literal);
    if (!n || r->end - r->p < (ptrdiff_t)n || memcmp(r->p, literal, n))
      goto fail;
    r->p += n;
    v->type = c == 'n' ? OJ_NULL : OJ_BOOL;
    v->boolean = c == 't';
  }
  v->bytes = (size_t)(r->p - v->start);
  return v;
fail:
  oj_free(v);
  return NULL;
}
oj_node *oj_parse(const char *s, size_t n) {
  if (!s || !n || n > 8u * 1024u * 1024u || !lie_utf8_valid(s, n, false))
    return NULL;
  reader r = {s, s + n, 0};
  oj_node *v = value(&r, 0);
  ws(&r);
  if (r.p != r.end) {
    oj_free(v);
    return NULL;
  }
  return v;
}
const oj_node *oj_field(const oj_node *v, const char *name) {
  if (!v || v->type != OJ_OBJECT)
    return NULL;
  for (const oj_node *k = v->child; k && k->next; k = k->next->next)
    if (!strcmp(k->string, name))
      return k->next;
  return NULL;
}
bool oj_type_is(const oj_node *v, const char *name) {
  const oj_node *t = oj_field(v, "type");
  if (t && t->type == OJ_STRING && !strcmp(t->string, name))
    return true;
  if (t && t->type == OJ_ARRAY)
    for (const oj_node *p = t->child; p; p = p->next)
      if (p->type == OJ_STRING && !strcmp(p->string, name))
        return true;
  const char *keys[] = {"anyOf", "oneOf"};
  for (unsigned i = 0; i < 2; ++i) {
    const oj_node *a = oj_field(v, keys[i]);
    if (a && a->type == OJ_ARRAY)
      for (const oj_node *p = a->child; p; p = p->next)
        if (oj_type_is(p, name))
          return true;
  }
  return false;
}
char *oj_quote(const char *s, size_t n) {
  if (!s || n > (SIZE_MAX - 3) / 6)
    return NULL;
  char *p = malloc(n * 6 + 3);
  if (!p)
    return NULL;
  size_t k = 0;
  p[k++] = '"';
  const char *hexes = "0123456789abcdef";
  for (size_t i = 0; i < n; ++i) {
    unsigned char c = (unsigned char)s[i];
    if (c == '"' || c == '\\') {
      p[k++] = '\\';
      p[k++] = (char)c;
    } else if (c < 32) {
      p[k++] = '\\';
      p[k++] = 'u';
      p[k++] = '0';
      p[k++] = '0';
      p[k++] = hexes[c >> 4];
      p[k++] = hexes[c & 15];
    } else
      p[k++] = (char)c;
  }
  p[k++] = '"';
  p[k] = 0;
  return p;
}
