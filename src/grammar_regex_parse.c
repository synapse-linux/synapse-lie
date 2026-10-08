/* SPDX-License-Identifier: MIT */
/* Copyright (c) 2026 gufo contributors. */
/* Attributed syntax/assertion expansion port from official Gufo f783fedb. */
#include "lie/grammar_regex_parse.h"
#include <stdlib.h>
#include <string.h>
#define INF UINT32_MAX
#define UNITS 16384u
#define NODES 65536u
#define WORK 32000000u
typedef struct {
  uint32_t *p;
  size_t n, cap;
} ids;
typedef enum {
  ATOM,
  SEQUENCE,
  ALTERNATIVE,
  REPEAT,
  POSITIVE,
  NEGATIVE,
  END
} kind;
typedef struct {
  kind kind;
  uint32_t atom, low, high;
  bool assertion;
  ids children;
} syntax;
typedef struct {
  lie_regex_compiler *compiler;
  lie_regex_bases base;
  const uint16_t *text;
  size_t length, position, work;
  lie_regex_unicode_sets sets;
  lie_regex_parser_description d;
  syntax *nodes;
  size_t count, capacity;
  lie_regex_parse_error error;
} parser;
typedef lie_regex_parse_status status;
static void *default_allocate(void *ctx, size_t n) {
  (void)ctx;
  return malloc(n);
}
static void default_release(void *ctx, void *p) {
  (void)ctx;
  free(p);
}
void lie_regex_parser_description_init(lie_regex_parser_description *d) {
  if (d)
    *d = (lie_regex_parser_description){
        LIE_REGEX_PARSER_ABI, sizeof(*d), NODES, WORK, {0}};
}
const char *lie_regex_parse_reason(status s) {
  switch (s) {
  case LIE_REGEX_PARSE_OK:
    return "";
  case LIE_REGEX_PARSE_INVALID:
    return "invalid C17 regex parser input";
  case LIE_REGEX_PARSE_RESOURCE:
    return "regex parser allocation failed";
  case LIE_REGEX_PARSE_WORK_LIMIT:
    return "regex parser work limit exceeded";
  case LIE_REGEX_PARSE_NODE_LIMIT:
    return "regex syntax node budget exceeded";
  case LIE_REGEX_PARSE_COMPILER:
    return "regex expression compiler refused";
  case LIE_REGEX_PARSE_BYTES:
    return "regex exceeds 16384 bytes";
  case LIE_REGEX_PARSE_PARENTHESES:
    return "unbalanced regex parentheses";
  case LIE_REGEX_PARSE_TRUNCATED:
    return "truncated regex";
  case LIE_REGEX_PARSE_REPETITION:
    return "invalid regex repetition";
  case LIE_REGEX_PARSE_REPETITION_LARGE:
    return "regex repetition is too large";
  case LIE_REGEX_PARSE_HEX:
    return "invalid regex Unicode escape";
  case LIE_REGEX_PARSE_BOUNDARY_ESCAPE:
    return "word-boundary regex assertions are unsupported";
  case LIE_REGEX_PARSE_OCTAL:
    return "legacy octal regex escapes are unsupported";
  case LIE_REGEX_PARSE_CONTROL:
    return "regex control escape requires an ASCII letter";
  case LIE_REGEX_PARSE_CODEPOINT:
    return "invalid regex Unicode code point";
  case LIE_REGEX_PARSE_EMPTY_CODEPOINT:
    return "empty regex Unicode code point";
  case LIE_REGEX_PARSE_SURROGATE:
    return "unpaired surrogate in regex";
  case LIE_REGEX_PARSE_ESCAPE:
    return "unsupported regex escape or backreference";
  case LIE_REGEX_PARSE_PROPERTY_BRACES:
    return "Unicode property escape requires braces";
  case LIE_REGEX_PARSE_PROPERTY_NAME:
    return "invalid Unicode property name";
  case LIE_REGEX_PARSE_PROPERTY:
    return "invalid regex Unicode property";
  case LIE_REGEX_PARSE_RANGE:
    return "invalid regex character range";
  case LIE_REGEX_PARSE_NESTING:
    return "regex nesting exceeds 32 levels";
  case LIE_REGEX_PARSE_GROUP:
    return "unsupported regex group, lookbehind or inline flag";
  case LIE_REGEX_PARSE_NO_ATOM:
    return "regex repetition has no preceding atom";
  case LIE_REGEX_PARSE_ASSERTION_REPEAT:
    return "regex assertions in unbounded or large repetitions are unsupported";
  }
  return "invalid C17 regex parser status";
}
static status fail(parser *p, status s) {
  p->error.status = s;
  return s;
}
static status compiled(parser *p, lie_regex_compile_status s) {
  if (s == LIE_REGEX_COMPILE_OK)
    return LIE_REGEX_PARSE_OK;
  p->error.compiler_status = s;
  return fail(p, s == LIE_REGEX_COMPILE_RESOURCE ? LIE_REGEX_PARSE_RESOURCE
                                                 : LIE_REGEX_PARSE_COMPILER);
}
static status charge(parser *p, size_t n) {
  if (n > p->d.max_work - p->work)
    return fail(p, LIE_REGEX_PARSE_WORK_LIMIT);
  p->work += n;
  return LIE_REGEX_PARSE_OK;
}
static void drop(parser *p, void *v) {
  if (v)
    p->d.allocator.release(p->d.allocator.context, v);
}
static status grow(parser *p, void **v, size_t *cap, size_t used, size_t need,
                   size_t width) {
  if (need > p->d.max_nodes || need > SIZE_MAX / width)
    return fail(p, LIE_REGEX_PARSE_NODE_LIMIT);
  if (need <= *cap)
    return LIE_REGEX_PARSE_OK;
  size_t n = *cap ? *cap : 8;
  if (n > p->d.max_nodes)
    n = p->d.max_nodes;
  while (n < need)
    n = n > p->d.max_nodes / 2 ? p->d.max_nodes : n * 2;
  void *raw = p->d.allocator.allocate(p->d.allocator.context, n * width);
  if (!raw)
    return fail(p, LIE_REGEX_PARSE_RESOURCE);
  if (used)
    memcpy(raw, *v, used * width);
  drop(p, *v);
  *v = raw;
  *cap = n;
  return LIE_REGEX_PARSE_OK;
}
static status append(parser *p, ids *v, uint32_t id) {
  status s = charge(p, 1);
  if (s == LIE_REGEX_PARSE_OK)
    s = grow(p, (void **)&v->p, &v->cap, v->n, v->n + 1, sizeof(*v->p));
  if (s == LIE_REGEX_PARSE_OK)
    v->p[v->n++] = id;
  return s;
}
static status node(parser *p, kind k, uint32_t *out) {
  status s = charge(p, 1);
  if (s == LIE_REGEX_PARSE_OK)
    s = grow(p, (void **)&p->nodes, &p->capacity, p->count, p->count + 1,
             sizeof(*p->nodes));
  if (s == LIE_REGEX_PARSE_OK) {
    *out = (uint32_t)p->count;
    p->nodes[p->count++] = (syntax){.kind = k};
  }
  return s;
}
static int32_t peek(const parser *p) {
  if (p->position >= p->length)
    return 0xffff;
  uint32_t cp = p->text[p->position];
  if (cp >= 0xd800 && cp <= 0xdbff && p->position + 1 < p->length) {
    uint32_t lo = p->text[p->position + 1];
    if (lo >= 0xdc00 && lo <= 0xdfff)
      cp = 0x10000 + ((cp - 0xd800) << 10) + lo - 0xdc00;
  }
  return (int32_t)cp;
}
static status take(parser *p, int32_t *out) {
  if (p->position >= p->length)
    return fail(p, LIE_REGEX_PARSE_TRUNCATED);
  status s = charge(p, 1);
  if (s != LIE_REGEX_PARSE_OK)
    return s;
  *out = peek(p);
  p->position += *out >= 0x10000 ? 2 : 1;
  return LIE_REGEX_PARSE_OK;
}
static status count(parser *p, uint32_t *out) {
  if (peek(p) < '0' || peek(p) > '9')
    return fail(p, LIE_REGEX_PARSE_REPETITION);
  uint64_t v = 0;
  while (peek(p) >= '0' && peek(p) <= '9') {
    int32_t cp;
    status s = take(p, &cp);
    if (s != LIE_REGEX_PARSE_OK)
      return s;
    v = v * 10 + (uint32_t)(cp - '0');
    if (v >= INF)
      return fail(p, LIE_REGEX_PARSE_REPETITION_LARGE);
  }
  *out = (uint32_t)v;
  return LIE_REGEX_PARSE_OK;
}
static status hex(parser *p, unsigned n, uint32_t *out) {
  uint32_t v = 0;
  for (unsigned i = 0; i < n; ++i) {
    int32_t cp;
    status s = take(p, &cp);
    if (s != LIE_REGEX_PARSE_OK)
      return s;
    int32_t digit = cp >= '0' && cp <= '9'   ? cp - '0'
                    : cp >= 'a' && cp <= 'f' ? cp - 'a' + 10
                    : cp >= 'A' && cp <= 'F' ? cp - 'A' + 10
                                             : -1;
    if (digit < 0)
      return fail(p, LIE_REGEX_PARSE_HEX);
    v = (v << 4) | (uint32_t)digit;
  }
  *out = v;
  return LIE_REGEX_PARSE_OK;
}
static status range(parser *p, int32_t lo, int32_t hi, void **out) {
  return compiled(p, p->sets.range(p->sets.context, lo, hi, out));
}
static void set_drop(parser *p, void *v) {
  if (v)
    p->sets.release(p->sets.context, v);
}
static status escape(parser *p, bool in_class, void **out) {
  int32_t cp;
  status s = take(p, &cp);
  if (s != LIE_REGEX_PARSE_OK)
    return s;
  char property[136] = {0};
  size_t property_n = 0;
  bool invert = false;
  switch (cp) {
  case 'd':
  case 'D':
    strcpy(property, "[0-9]");
    invert = cp == 'D';
    break;
  case 's':
  case 'S':
    strcpy(property, "[\\p{Zs}\\u0009-\\u000d\\u2028\\u2029\\ufeff]");
    invert = cp == 'S';
    break;
  case 'w':
  case 'W':
    strcpy(property, "[a-zA-Z0-9_]");
    invert = cp == 'W';
    break;
  case 'p':
  case 'P': {
    int32_t c;
    s = take(p, &c);
    if (s != LIE_REGEX_PARSE_OK)
      return s;
    if (c != '{')
      return fail(p, LIE_REGEX_PARSE_PROPERTY_BRACES);
    property[0] = '[';
    property[1] = '\\';
    property[2] = (char)cp;
    property[3] = '{';
    size_t n = 0;
    while (peek(p) != '}') {
      s = take(p, &c);
      if (s != LIE_REGEX_PARSE_OK)
        return s;
      if (c > 127 || n >= 128)
        return fail(p, LIE_REGEX_PARSE_PROPERTY_NAME);
      property[4 + n++] = (char)c;
    }
    ++p->position;
    property[4 + n] = '}';
    property[5 + n] = ']';
    property[6 + n] = 0;
    property_n = 6 + n;
    break;
  }
  case 'n':
    cp = '\n';
    break;
  case 'r':
    cp = '\r';
    break;
  case 't':
    cp = '\t';
    break;
  case 'f':
    cp = '\f';
    break;
  case 'v':
    cp = '\v';
    break;
  case 'b':
    if (!in_class)
      return fail(p, LIE_REGEX_PARSE_BOUNDARY_ESCAPE);
    cp = '\b';
    break;
  case '0':
    if (peek(p) >= '0' && peek(p) <= '9')
      return fail(p, LIE_REGEX_PARSE_OCTAL);
    cp = 0;
    break;
  case 'c':
    s = take(p, &cp);
    if (s != LIE_REGEX_PARSE_OK)
      return s;
    if (!((cp >= 'a' && cp <= 'z') || (cp >= 'A' && cp <= 'Z')))
      return fail(p, LIE_REGEX_PARSE_CONTROL);
    cp %= 32;
    break;
  case 'u': {
    uint32_t value;
    if (peek(p) == '{') {
      ++p->position;
      value = 0;
      unsigned digits = 0;
      while (peek(p) != '}') {
        uint32_t digit;
        s = hex(p, 1, &digit);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        ++digits;
        value = (value << 4) | digit;
        if (value > 0x10ffff)
          return fail(p, LIE_REGEX_PARSE_CODEPOINT);
      }
      ++p->position;
      if (!digits)
        return fail(p, LIE_REGEX_PARSE_EMPTY_CODEPOINT);
    } else {
      s = hex(p, 4, &value);
      if (s != LIE_REGEX_PARSE_OK)
        return s;
      if (value >= 0xd800 && value <= 0xdbff) {
        int32_t c;
        s = take(p, &c);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        if (c != '\\')
          return fail(p, LIE_REGEX_PARSE_SURROGATE);
        s = take(p, &c);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        if (c != 'u')
          return fail(p, LIE_REGEX_PARSE_SURROGATE);
        uint32_t low;
        s = hex(p, 4, &low);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        if (low < 0xdc00 || low > 0xdfff)
          return fail(p, LIE_REGEX_PARSE_SURROGATE);
        value = 0x10000 + ((value - 0xd800) << 10) + low - 0xdc00;
      }
    }
    cp = (int32_t)value;
    break;
  }
  case 'x': {
    uint32_t value;
    s = hex(p, 2, &value);
    if (s != LIE_REGEX_PARSE_OK)
      return s;
    cp = (int32_t)value;
    break;
  }
  default:
    if (cp > 127 ||
        ((!cp || !strchr("^$\\.*+?()[]{}|/", cp)) && !(in_class && cp == '-')))
      return fail(p, LIE_REGEX_PARSE_ESCAPE);
  }
  if (!property[0])
    return range(p, cp, cp, out);
  if (!property_n)
    property_n = strlen(property);
  void *set = NULL;
  lie_regex_compile_status rc =
      p->sets.property(p->sets.context, property, property_n, &set);
  if (rc != LIE_REGEX_COMPILE_OK)
    return rc == LIE_REGEX_COMPILE_INVALID ? fail(p, LIE_REGEX_PARSE_PROPERTY)
                                           : compiled(p, rc);
  if (invert)
    s = compiled(p, p->sets.complement(p->sets.context, set));
  if (s != LIE_REGEX_PARSE_OK) {
    set_drop(p, set);
    return s;
  }
  *out = set;
  return LIE_REGEX_PARSE_OK;
}
static status character_class(parser *p, void **out) {
  void *result = NULL;
  status s = range(p, 1, 0, &result);
  if (s != LIE_REGEX_PARSE_OK)
    return s;
  bool negate = peek(p) == '^';
  if (negate)
    ++p->position;
  while (peek(p) != ']' && s == LIE_REGEX_PARSE_OK) {
    int32_t cp;
    void *a = NULL, *b = NULL;
    s = take(p, &cp);
    if (s == LIE_REGEX_PARSE_OK)
      s = cp == '\\' ? escape(p, true, &a) : range(p, cp, cp, &a);
    if (s == LIE_REGEX_PARSE_OK && peek(p) == '-' &&
        (p->position + 1 >= p->length || p->text[p->position + 1] != ']')) {
      ++p->position;
      s = take(p, &cp);
      if (s == LIE_REGEX_PARSE_OK)
        s = cp == '\\' ? escape(p, true, &b) : range(p, cp, cp, &b);
      uint64_t an = 0, bn = 0;
      int32_t af = 0, bf = 0;
      if (s == LIE_REGEX_PARSE_OK)
        s = compiled(p, p->sets.info(p->sets.context, a, &an, &af));
      if (s == LIE_REGEX_PARSE_OK)
        s = compiled(p, p->sets.info(p->sets.context, b, &bn, &bf));
      if (s == LIE_REGEX_PARSE_OK && (an != 1 || bn != 1 || af > bf))
        s = fail(p, LIE_REGEX_PARSE_RANGE);
      if (s == LIE_REGEX_PARSE_OK)
        s = compiled(p, p->sets.add_range(p->sets.context, a, af, bf));
    }
    if (s == LIE_REGEX_PARSE_OK)
      s = compiled(p, p->sets.add(p->sets.context, result, a));
    set_drop(p, b);
    set_drop(p, a);
  }
  if (s == LIE_REGEX_PARSE_OK) {
    ++p->position;
    if (negate)
      s = compiled(p, p->sets.complement(p->sets.context, result));
  }
  if (s != LIE_REGEX_PARSE_OK) {
    set_drop(p, result);
    return s;
  }
  *out = result;
  return LIE_REGEX_PARSE_OK;
}
static status alternatives(parser *p, unsigned depth, uint32_t *out) {
  if (depth > 32)
    return fail(p, LIE_REGEX_PARSE_NESTING);
  uint32_t alt;
  status s = node(p, ALTERNATIVE, &alt);
  if (s != LIE_REGEX_PARSE_OK)
    return s;
  do {
    uint32_t seq;
    s = node(p, SEQUENCE, &seq);
    if (s != LIE_REGEX_PARSE_OK)
      return s;
    while (p->position < p->length && peek(p) != ')' && peek(p) != '|') {
      int32_t cp;
      s = take(p, &cp);
      if (s != LIE_REGEX_PARSE_OK)
        return s;
      uint32_t atom;
      if (cp == '(') {
        bool positive = false, negative = false;
        if (peek(p) == '?') {
          ++p->position;
          int32_t modifier;
          s = take(p, &modifier);
          if (s != LIE_REGEX_PARSE_OK)
            return s;
          positive = modifier == '=';
          negative = modifier == '!';
          if (!positive && !negative && modifier != ':')
            return fail(p, LIE_REGEX_PARSE_GROUP);
        }
        s = alternatives(p, depth + 1, &atom);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        s = take(p, &cp);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        if (cp != ')')
          return fail(p, LIE_REGEX_PARSE_PARENTHESES);
        if (positive || negative) {
          uint32_t assertion;
          s = node(p, positive ? POSITIVE : NEGATIVE, &assertion);
          if (s == LIE_REGEX_PARSE_OK)
            s = append(p, &p->nodes[assertion].children, atom);
          if (s != LIE_REGEX_PARSE_OK)
            return s;
          p->nodes[assertion].assertion = true;
          atom = assertion;
        }
      } else {
        s = node(p, cp == '$' ? END : ATOM, &atom);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        void *set = NULL;
        if (cp == '[')
          s = character_class(p, &set);
        else if (cp == '^') {
          p->nodes[atom].atom = p->base.start;
          p->nodes[atom].assertion = true;
        } else if (cp == '$') {
          p->nodes[atom].atom = p->base.epsilon;
          p->nodes[atom].assertion = true;
        } else if (cp == '\\') {
          if (peek(p) == 'b' || peek(p) == 'B') {
            s = take(p, &cp);
            if (s == LIE_REGEX_PARSE_OK)
              s = compiled(p, p->sets.boundary(p->sets.context, cp == 'b',
                                               &p->nodes[atom].atom));
            p->nodes[atom].assertion = true;
          } else
            s = escape(p, false, &set);
        } else if (cp == '.') {
          s = range(p, 0, 0x10ffff, &set);
          const int32_t removed[] = {0xd800, 0xdfff, '\n',   '\n',
                                     '\r',   '\r',   0x2028, 0x2029};
          for (size_t i = 0; i < sizeof(removed) / sizeof(*removed) &&
                             s == LIE_REGEX_PARSE_OK;
               i += 2)
            s = compiled(p, p->sets.remove_range(p->sets.context, set,
                                                 removed[i], removed[i + 1]));
        } else {
          if (cp > 0 && cp < 128 && strchr("*+?{}", cp))
            return fail(p, LIE_REGEX_PARSE_NO_ATOM);
          s = range(p, cp, cp, &set);
        }
        if (s == LIE_REGEX_PARSE_OK && set)
          s = compiled(
              p, p->sets.publish(p->sets.context, set, &p->nodes[atom].atom));
        set_drop(p, set);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
      }
      int32_t quantifier = peek(p);
      if (quantifier == '*' || quantifier == '+' || quantifier == '?' ||
          quantifier == '{') {
        ++p->position;
        uint32_t low = quantifier == '+' ? 1 : 0,
                 high = quantifier == '?' ? 1 : INF;
        if (quantifier == '{') {
          s = count(p, &low);
          if (s != LIE_REGEX_PARSE_OK)
            return s;
          high = low;
          if (peek(p) == ',') {
            ++p->position;
            if (peek(p) == '}')
              high = INF;
            else {
              s = count(p, &high);
              if (s != LIE_REGEX_PARSE_OK)
                return s;
            }
          }
          s = take(p, &cp);
          if (s != LIE_REGEX_PARSE_OK)
            return s;
          if (cp != '}' || high < low)
            return fail(p, LIE_REGEX_PARSE_REPETITION);
        }
        if (p->nodes[atom].assertion && (high == INF || high > 32))
          return fail(p, LIE_REGEX_PARSE_ASSERTION_REPEAT);
        uint32_t repeated;
        s = node(p, REPEAT, &repeated);
        if (s == LIE_REGEX_PARSE_OK)
          s = append(p, &p->nodes[repeated].children, atom);
        if (s != LIE_REGEX_PARSE_OK)
          return s;
        p->nodes[repeated].low = low;
        p->nodes[repeated].high = high;
        p->nodes[repeated].assertion = p->nodes[atom].assertion;
        atom = repeated;
        if (peek(p) == '?')
          ++p->position;
      }
      p->nodes[seq].assertion |= p->nodes[atom].assertion;
      s = append(p, &p->nodes[seq].children, atom);
      if (s != LIE_REGEX_PARSE_OK)
        return s;
    }
    p->nodes[alt].assertion |= p->nodes[seq].assertion;
    s = append(p, &p->nodes[alt].children, seq);
    if (s != LIE_REGEX_PARSE_OK)
      return s;
    if (peek(p) != '|')
      break;
    ++p->position;
  } while (true);
  *out = alt;
  return LIE_REGEX_PARSE_OK;
}
typedef struct {
  uint32_t id, tail;
  size_t index;
  ids choices;
} frame;
static status combine2(parser *p, lie_regex_operation op, uint32_t a,
                       uint32_t b, uint32_t *out) {
  uint32_t args[] = {a, b};
  return compiled(p, lie_regex_combine(p->compiler, op, args, 2, out));
}
static status expand(parser *p, uint32_t root, uint32_t tail, uint32_t *out) {
  frame *frames = NULL;
  size_t depth = 0, capacity = 0;
  status s = grow(p, (void **)&frames, &capacity, 0, 1, sizeof(*frames));
  if (s != LIE_REGEX_PARSE_OK)
    return s;
  frames[depth++] = (frame){.id = root, .tail = tail};
  uint32_t result = 0;
  bool returned = false;
  while (depth && s == LIE_REGEX_PARSE_OK) {
    s = charge(p, 1);
    if (s != LIE_REGEX_PARSE_OK)
      break;
    frame *f = frames + depth - 1;
    const syntax *n = p->nodes + f->id;
    if (returned) {
      returned = false;
      if (n->kind == SEQUENCE || (n->kind == REPEAT && n->assertion)) {
        f->tail = result;
        ++f->index;
      } else if (n->kind == ALTERNATIVE) {
        s = append(p, &f->choices, result);
        ++f->index;
      } else if (n->kind == REPEAT) {
        uint32_t repeated;
        s = compiled(p, lie_regex_repeat(p->compiler, result, n->low, n->high,
                                         &repeated));
        if (s == LIE_REGEX_PARSE_OK)
          s = combine2(p, LIE_REGEX_CONCATENATION, repeated, f->tail, &result);
        f->index = 1;
      } else {
        if (n->kind == NEGATIVE)
          s = compiled(p, lie_regex_not(p->compiler, result, &result));
        if (s == LIE_REGEX_PARSE_OK)
          s = combine2(p, LIE_REGEX_INTERSECTION, result, f->tail, &result);
        f->index = 1;
      }
      if (s != LIE_REGEX_PARSE_OK)
        break;
    }
    uint32_t child = 0, child_tail = 0;
    bool descend = false, done = false;
    switch (n->kind) {
    case ATOM:
      s = combine2(p, LIE_REGEX_CONCATENATION, n->atom, f->tail, &result);
      done = true;
      break;
    case END:
      s = combine2(p, LIE_REGEX_INTERSECTION, n->atom, f->tail, &result);
      done = true;
      break;
    case SEQUENCE:
      if (f->index < n->children.n) {
        child = n->children.p[n->children.n - 1 - f->index];
        child_tail = f->tail;
        descend = true;
      } else {
        result = f->tail;
        done = true;
      }
      break;
    case ALTERNATIVE:
      if (f->index < n->children.n) {
        child = n->children.p[f->index];
        child_tail = f->tail;
        descend = true;
      } else {
        s = compiled(p, lie_regex_combine(p->compiler, LIE_REGEX_UNION,
                                          f->choices.p, f->choices.n, &result));
        done = true;
      }
      break;
    case REPEAT:
      if (n->assertion) {
        if (f->index >= n->low)
          s = append(p, &f->choices, f->tail);
        if (s == LIE_REGEX_PARSE_OK && f->index < n->high) {
          child = n->children.p[0];
          child_tail = f->tail;
          descend = true;
        } else if (s == LIE_REGEX_PARSE_OK) {
          s = compiled(p,
                       lie_regex_combine(p->compiler, LIE_REGEX_UNION,
                                         f->choices.p, f->choices.n, &result));
          done = true;
        }
      } else if (!f->index) {
        child = n->children.p[0];
        child_tail = p->base.epsilon;
        descend = true;
      } else
        done = true;
      break;
    case POSITIVE:
    case NEGATIVE:
      if (!f->index) {
        child = n->children.p[0];
        child_tail = p->base.all;
        descend = true;
      } else
        done = true;
      break;
    }
    if (s != LIE_REGEX_PARSE_OK)
      break;
    if (descend) {
      s = grow(p, (void **)&frames, &capacity, depth, depth + 1,
               sizeof(*frames));
      if (s == LIE_REGEX_PARSE_OK)
        frames[depth++] = (frame){.id = child, .tail = child_tail};
    } else if (done) {
      drop(p, f->choices.p);
      --depth;
      returned = true;
    }
  }
  for (size_t i = 0; i < depth; ++i)
    drop(p, frames[i].choices.p);
  drop(p, frames);
  if (s == LIE_REGEX_PARSE_OK)
    *out = result;
  return s;
}
status lie_regex_parse_utf16(lie_regex_compiler *compiler, const uint16_t *text,
                             size_t length, size_t bytes,
                             const lie_regex_unicode_sets *sets,
                             const lie_regex_parser_description *d,
                             uint32_t *out, lie_regex_parse_error *error) {
  parser p = {.compiler = compiler, .text = text, .length = length};
  status s = LIE_REGEX_PARSE_INVALID;
  if (!compiler || !sets || !d || !out || (length && !text) ||
      d->abi_version != LIE_REGEX_PARSER_ABI || d->struct_bytes != sizeof(*d) ||
      !d->max_nodes || d->max_nodes > NODES || !d->max_work ||
      ((d->allocator.allocate == NULL) != (d->allocator.release == NULL)) ||
      !sets->range || !sets->property || !sets->add || !sets->add_range ||
      !sets->remove_range || !sets->complement || !sets->info ||
      !sets->publish || !sets->boundary || !sets->release)
    goto finish;
  p.sets = *sets;
  p.d = *d;
  if (!p.d.allocator.allocate) {
    p.d.allocator.allocate = default_allocate;
    p.d.allocator.release = default_release;
  }
  if (bytes > UNITS || length > UNITS) {
    s = LIE_REGEX_PARSE_BYTES;
    goto finish;
  }
  s = compiled(&p, lie_regex_compiler_bases(compiler, &p.base));
  if (s != LIE_REGEX_PARSE_OK)
    goto finish;
  uint32_t syntax_root, expanded, result;
  s = alternatives(&p, 0, &syntax_root);
  if (s == LIE_REGEX_PARSE_OK && p.position != p.length)
    s = fail(&p, LIE_REGEX_PARSE_PARENTHESES);
  if (s == LIE_REGEX_PARSE_OK)
    s = expand(&p, syntax_root, p.base.all, &expanded);
  if (s == LIE_REGEX_PARSE_OK)
    s = combine2(&p, LIE_REGEX_CONCATENATION, p.base.all, expanded, &result);
  if (s == LIE_REGEX_PARSE_OK)
    *out = result;
finish:
  if (p.d.allocator.release) {
    for (size_t i = 0; i < p.count; ++i)
      drop(&p, p.nodes[i].children.p);
    drop(&p, p.nodes);
  }
  p.error.status = s;
  if (error)
    *error = p.error;
  return s;
}
