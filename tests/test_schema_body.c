/* SPDX-License-Identifier: MIT */
/* Independent immutable tree, complete finite language and refusal oracles. */
#include "lie/schema_body.h"
#include "lie/schema_visit.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct node node;
typedef struct {
  char *key;
  size_t bytes;
  node *value;
} edge;
struct node {
  node *next;
  lie_schema_value v;
  char *text;
  edge *edges;
};
typedef union {
  max_align_t align;
  size_t bytes;
} allocation;
typedef struct {
  size_t calls, fail, live;
} memory;
typedef struct {
  node *nodes, *root;
  size_t calls, fail, visits, kept, normalized, routes;
  size_t depths[4096];
  lie_schema_node visited[4096];
  lie_schema_body_description d;
  lie_schema_container_counts counts;
  size_t enums;
  lie_grammar_builder *builder;
  lie_schema_memo *memo;
  memory mem;
  bool invalid_keep, invalid_normalized;
} fixture;
static size_t oracles, callback_refusals, allocation_refusals;
static void *allocate(void *p, size_t bytes) {
  memory *m = p;
  if (++m->calls == m->fail)
    return NULL;
  allocation *v = malloc(sizeof(*v) + bytes);
  assert(v);
  v->bytes = bytes;
  ++m->live;
  return v + 1;
}
static void release(void *p, void *v) {
  memory *m = p;
  assert(m->live);
  --m->live;
  free((allocation *)v - 1);
}
static bool refuse(fixture *f) { return ++f->calls == f->fail; }
static char *bytes_copy(const char *p, size_t n) {
  char *s = malloc(n + 1);
  assert(s);
  if (n)
    memcpy(s, p, n);
  s[n] = 0;
  return s;
}
static node *make(fixture *f, lie_schema_kind kind, const char *s, size_t bytes,
                  double number) {
  node *n = calloc(1, sizeof(*n));
  assert(n);
  n->next = f->nodes;
  f->nodes = n;
  n->text = bytes_copy(s, bytes);
  n->v = (lie_schema_value){
      .kind = kind, .text = {n->text, bytes}, .number = number};
  return n;
}
static node *object(fixture *f) {
  return make(f, LIE_SCHEMA_OBJECT, NULL, 0, 0);
}
static node *array(fixture *f) { return make(f, LIE_SCHEMA_ARRAY, NULL, 0, 0); }
static node *text(fixture *f, const char *s) {
  return make(f, LIE_SCHEMA_STRING, s, strlen(s), 0);
}
static node *number(fixture *f, double v) {
  return make(f, LIE_SCHEMA_NUMBER, NULL, 0, v);
}
static void member(node *n, const char *key, size_t bytes, node *value) {
  edge *e = realloc(n->edges, (n->v.count + 1) * sizeof(*e));
  assert(e);
  n->edges = e;
  e[n->v.count++] = (edge){bytes_copy(key, bytes), bytes, value};
}
static void field(node *n, const char *key, node *value) {
  member(n, key, strlen(key), value);
}
static void item(node *n, node *value) { member(n, NULL, 0, value); }
static node *get(const node *n, const char *key) {
  for (size_t i = 0; i < n->v.count; ++i)
    if (n->edges[i].bytes == strlen(key) &&
        !memcmp(n->edges[i].key, key, strlen(key)))
      return n->edges[i].value;
  return NULL;
}
static node *copy(fixture *f, const node *n) {
  node *r = make(f, n->v.kind, n->v.text.data, n->v.text.size, n->v.number);
  r->v.boolean = n->v.boolean;
  for (size_t i = 0; i < n->v.count; ++i)
    member(r, n->edges[i].key, n->edges[i].bytes, copy(f, n->edges[i].value));
  return r;
}
static node *schema(fixture *f, const char *type) {
  node *s = object(f);
  field(s, "type", text(f, type));
  return s;
}
static lie_schema_status describe(void *p, lie_schema_node n,
                                  lie_schema_value *out) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  *out = ((const node *)n)->v;
  return LIE_SCHEMA_OK;
}
static lie_schema_status child(void *p, lie_schema_node n, size_t i,
                               lie_schema_bytes *key, lie_schema_node *out) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  const node *v = n;
  assert(i < v->v.count);
  *key = (lie_schema_bytes){v->edges[i].key, v->edges[i].bytes};
  *out = v->edges[i].value;
  return LIE_SCHEMA_OK;
}
static lie_schema_status clone(void *p, lie_schema_node n,
                               lie_schema_node *out) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  *out = copy(p, n);
  return LIE_SCHEMA_OK;
}
static lie_schema_status create(void *p, const lie_schema_value *v,
                                lie_schema_node *out) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  node *n = make(p, v->kind, v->text.data, v->text.size, v->number);
  n->v.boolean = v->boolean;
  *out = n;
  return LIE_SCHEMA_OK;
}
static lie_schema_status append_member(void *p, lie_schema_node n,
                                       lie_schema_bytes key,
                                       lie_schema_node value) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  member((node *)n, key.data, key.size, copy(p, value));
  return LIE_SCHEMA_OK;
}
static lie_schema_status put(void *p, lie_schema_node n, lie_schema_bytes key,
                             lie_schema_node value) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  node *v = (node *)n, *owned = copy(p, value);
  for (size_t i = 0; i < v->v.count; ++i)
    if (v->edges[i].bytes == key.size &&
        !memcmp(v->edges[i].key, key.data, key.size)) {
      v->edges[i].value = owned;
      return LIE_SCHEMA_OK;
    }
  member(v, key.data, key.size, owned);
  return LIE_SCHEMA_OK;
}
static lie_schema_status append(void *p, lie_schema_node n,
                                lie_schema_node value) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  item((node *)n, copy(p, value));
  return LIE_SCHEMA_OK;
}
static lie_schema_status format(void *p, lie_schema_bytes name,
                                lie_schema_node *out) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  node *n = object(p);
  field(n, "pattern", make(p, LIE_SCHEMA_STRING, name.data, name.size, 0));
  *out = n;
  return LIE_SCHEMA_OK;
}
static lie_schema_status multiple(void *p, lie_schema_node l, lie_schema_node r,
                                  lie_schema_node *out) {
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  unsigned a = (unsigned)((const node *)l)->v.number,
           b = (unsigned)((const node *)r)->v.number;
  assert(a && b && a < 100 && b < 100);
  unsigned n = a;
  while (n % b)
    n += a;
  *out = number(p, n);
  return LIE_SCHEMA_OK;
}
static lie_schema_status builder_status(lie_builder_status rc) {
  return rc == LIE_BUILDER_OK         ? LIE_SCHEMA_OK
         : rc == LIE_BUILDER_RESOURCE ? LIE_SCHEMA_RESOURCE
         : rc == LIE_BUILDER_EMPTY    ? LIE_SCHEMA_EMPTY
                                      : LIE_SCHEMA_INVALID;
}
static lie_schema_status literal(fixture *f, const char *s, uint32_t *out) {
  return builder_status(
      lie_builder_literal(f->builder, (const uint8_t *)s, strlen(s), out));
}
static lie_schema_status number_literal(void *p, lie_schema_node n,
                                        lie_grammar_builder *b, uint32_t *out) {
  fixture *f = p;
  assert(b == f->builder);
  if (refuse(f))
    return LIE_SCHEMA_CALLBACK;
  char s[48];
  int bytes = snprintf(s, sizeof(s), "%.0f", ((const node *)n)->v.number);
  assert(bytes > 0 && (size_t)bytes < sizeof(s));
  return literal(f, s, out);
}
static lie_schema_status accept(void *p, lie_schema_node s, lie_schema_node v,
                                bool *out) {
  (void)s;
  (void)v;
  if (refuse(p))
    return LIE_SCHEMA_CALLBACK;
  *out = true;
  return LIE_SCHEMA_OK;
}
static lie_schema_status rule(void *p, lie_schema_node n, size_t depth,
                              lie_schema_route r, lie_schema_bytes name,
                              uint32_t *out) {
  fixture *f = p;
  (void)depth;
  (void)r;
  if (refuse(f))
    return LIE_SCHEMA_CALLBACK;
  ++f->routes;
  node *low = get(n, "minimum"), *high = get(n, "maximum");
  if (low && high && low->v.number > high->v.number)
    return LIE_SCHEMA_EMPTY;
  node *min = get(n, "minItems");
  if (min && min->v.number < 0)
    return LIE_SCHEMA_INVALID;
  if (name.size == 4 && !memcmp(name.data, "null", 4))
    return literal(f, "null", out);
  if (name.size == 7 && !memcmp(name.data, "boolean", 7)) {
    uint32_t ids[2];
    lie_schema_status rc = literal(f, "true", &ids[0]);
    if (rc)
      return rc;
    rc = literal(f, "false", &ids[1]);
    if (rc)
      return rc;
    return builder_status(lie_builder_alternatives(f->builder, ids, 2, out));
  }
  if (name.size == 6 && !memcmp(name.data, "string", 6))
    return literal(f, "\"s\"", out);
  if (name.size == 6 && !memcmp(name.data, "object", 6))
    return literal(f, "{}", out);
  if (name.size == 5 && !memcmp(name.data, "array", 5))
    return literal(f, "[]", out);
  if ((name.size == 7 && !memcmp(name.data, "integer", 7)) ||
      (name.size == 6 && !memcmp(name.data, "number", 6)))
    return literal(f, "1", out);
  return LIE_SCHEMA_INVALID;
}
static lie_schema_status body(void *p, lie_schema_node n, size_t depth,
                              uint32_t *out, lie_schema_error *error) {
  fixture *f = p;
  return lie_schema_compile_body(&f->d, f->root, n, depth, f->builder, 0,
                                 &f->counts, &f->enums, out, error);
}
static lie_schema_status visit(void *p, lie_schema_node n, size_t depth,
                               uint32_t *out) {
  fixture *f = p;
  if (refuse(f))
    return LIE_SCHEMA_CALLBACK;
  assert(f->visits < 4096);
  f->visited[f->visits] = n;
  f->depths[f->visits++] = depth;
  lie_schema_body_access access;
  lie_schema_body_access_init(&access);
  access.context = f;
  access.body = body;
  return lie_schema_visit_rule(f->memo, f->builder, n, depth, access, out,
                               NULL);
}
static lie_schema_status keep(void *p, lie_schema_node n,
                              lie_schema_node *out) {
  fixture *f = p;
  if (refuse(f))
    return LIE_SCHEMA_CALLBACK;
  ++f->kept;
  *out = f->invalid_keep ? NULL : copy(f, n);
  return LIE_SCHEMA_OK;
}
static lie_schema_status normalize(void *p, lie_schema_node s,
                                   lie_schema_node n,
                                   lie_schema_normalized *out) {
  fixture *f = p;
  if (refuse(f))
    return LIE_SCHEMA_CALLBACK;
  ++f->normalized;
  if (f->invalid_normalized) {
    *out = (lie_schema_normalized){true, NULL};
    return LIE_SCHEMA_OK;
  }
  return lie_schema_normalize(&f->d.values, f->root, s, n, 0, out, NULL);
}
static bool init(fixture *f) {
  lie_schema_body_description_init(&f->d);
  f->d.transform.access = (lie_schema_access){
      f, describe, child, clone, create, put, append, format, multiple};
  f->d.transform.allocator =
      (lie_grammar_allocator){&f->mem, allocate, release};
  f->d.values.transform = f->d.transform;
  f->d.values.leaf_context = f;
  f->d.values.accept = accept;
  f->d.values.number_literal = number_literal;
  f->d.append_member = append_member;
  f->d.compile = (lie_schema_compile_access){f, visit, keep, normalize};
  f->d.rules = (lie_schema_rule_access){f, rule};
  lie_builder_description bd;
  lie_builder_description_init(&bd);
  bd.allocator = f->d.transform.allocator;
  lie_schema_memo_description md;
  lie_schema_memo_description_init(&md);
  md.allocator = f->d.transform.allocator;
  if (lie_builder_create(&bd, &f->builder))
    return false;
  return lie_schema_memo_create(&md, &f->memo) == LIE_SCHEMA_OK;
}
static void retire(fixture *f) {
  lie_schema_memo_release(f->memo);
  lie_builder_release(f->builder);
  assert(f->mem.live == 0);
  while (f->nodes) {
    node *n = f->nodes;
    f->nodes = n->next;
    for (size_t i = 0; i < n->v.count; ++i)
      free(n->edges[i].key);
    free(n->edges);
    free(n->text);
    free(n);
  }
}
static lie_schema_status compile(fixture *f, size_t depth, uint32_t *out,
                                 lie_schema_error *e) {
  return lie_schema_compile_body(&f->d, f->root, f->root, depth, f->builder, 0,
                                 &f->counts, &f->enums, out, e);
}
static bool accepts(const lie_grammar_program *p, const char *text) {
  lie_grammar_state *s = NULL;
  assert(lie_grammar_start(p, &s) == LIE_GRAMMAR_OK);
  for (size_t i = 0; i < strlen(text); ++i) {
    lie_grammar_state *next = NULL;
    assert(lie_grammar_advance(p, s, (uint8_t)text[i], &next) ==
           LIE_GRAMMAR_OK);
    lie_grammar_state_release(s);
    s = next;
  }
  bool yes = lie_grammar_complete(s);
  lie_grammar_state_release(s);
  return yes;
}
static void language(fixture *f, uint32_t id, const char *const *yes,
                     size_t count) {
  lie_grammar_description d;
  assert(lie_builder_finish(f->builder, id, 0, &d) == LIE_BUILDER_OK);
  lie_grammar_program *p = NULL;
  assert(lie_grammar_program_create(&d, &p) == LIE_GRAMMAR_OK);
  for (size_t i = 0; i < count; ++i) {
    assert(accepts(p, yes[i]));
    ++oracles;
  }
  for (const char **s = (const char *[]){"", "x", "nullx", "\"bad\"", NULL}; *s;
       ++s) {
    assert(!accepts(p, *s));
    ++oracles;
  }
  lie_grammar_program_release(p);
}
static void ordered_definitions_and_references(void) {
  fixture f = {0};
  assert(init(&f));
  f.root = object(&f);
  node *defs = object(&f), *a = schema(&f, "null"), *b = schema(&f, "boolean");
  field(defs, "\xc3\xa9", a);
  field(defs, "b", b);
  field(f.root, "$defs", defs);
  field(f.root, "$ref", text(&f, "#/$defs/b"));
  field(f.root, "title", text(&f, "discarded"));
  uint32_t out;
  assert(compile(&f, 4, &out, NULL) == LIE_SCHEMA_OK);
  assert(f.visits == 3 && f.visited[0] == a && f.visited[1] == b &&
         f.visited[2] == b && f.depths[0] == 4 && f.depths[2] == 4 &&
         f.counts.characters == 2 && f.kept == 0);
  language(&f, out, (const char *[]){"true", "false"}, 2);
  retire(&f);
  f = (fixture){0};
  assert(init(&f));
  f.root = object(&f);
  a = schema(&f, "integer");
  defs = object(&f);
  field(defs, "x", a);
  field(f.root, "$defs", defs);
  field(f.root, "$ref", text(&f, "#/$defs/x"));
  field(f.root, "type", text(&f, "integer"));
  assert(compile(&f, 3, &out, NULL) == LIE_SCHEMA_OK && f.kept == 1 &&
         f.depths[1] == 3);
  language(&f, out, (const char *[]){"1"}, 1);
  retire(&f);
}
static void finite_and_priority(void) {
  for (unsigned shape = 0; shape < 4; ++shape) {
    fixture f = {0};
    assert(init(&f));
    f.root = schema(&f, "integer");
    node *e = array(&f);
    item(e, number(&f, 1));
    item(e, number(&f, 2));
    field(f.root, "enum", e);
    if (shape == 1)
      field(f.root, "const", number(&f, 2));
    if (shape == 2)
      field(f.root, "const", number(&f, 3));
    if (shape == 3)
      e->edges[1].value = text(&f, "wrong");
    uint32_t out = UINT32_MAX;
    lie_schema_error err = {0};
    lie_schema_status rc = compile(&f, 0, &out, &err);
    if (shape == 2) {
      assert(rc == LIE_SCHEMA_EMPTY &&
             !strcmp(err.message,
                     "enum/const has no value satisfying its constraints") &&
             out == UINT32_MAX);
      ++oracles;
    } else if (shape == 3) {
      assert(rc == LIE_SCHEMA_INVALID &&
             !strcmp(err.message, "enum/const value does not match its type") &&
             out == UINT32_MAX);
      ++oracles;
    } else {
      assert(rc == LIE_SCHEMA_OK && f.kept == 1 && f.enums == 2);
      language(&f, out,
               shape ? (const char *[]){"2"} : (const char *[]){"1", "2"},
               shape ? 1 : 2);
    }
    retire(&f);
  }
  fixture f = {0};
  assert(init(&f));
  f.root = schema(&f, "array");
  field(f.root, "minItems", number(&f, -1));
  field(f.root, "enum", number(&f, 0));
  uint32_t out = UINT32_MAX;
  lie_schema_error e = {0};
  assert(compile(&f, 0, &out, &e) == LIE_SCHEMA_INVALID && f.routes == 1 &&
         e.message == NULL && out == UINT32_MAX);
  ++oracles;
  retire(&f);
  f = (fixture){0};
  assert(init(&f));
  f.root = schema(&f, "integer");
  field(f.root, "const", number(&f, 1));
  f.invalid_normalized = true;
  assert(compile(&f, 0, &out, &e) == LIE_SCHEMA_INVALID &&
         !strcmp(e.message, "invalid canonical value node"));
  ++oracles;
  retire(&f);
  f = (fixture){0};
  assert(init(&f));
  f.root = schema(&f, "integer");
  field(f.root, "const", number(&f, 1));
  f.invalid_keep = true;
  assert(compile(&f, 0, &out, &e) == LIE_SCHEMA_INVALID &&
         !strcmp(e.message, "invalid retained schema node"));
  ++oracles;
  retire(&f);
  /* Duplicate metadata survives the finite base copy, in source order. */
  f = (fixture){0};
  assert(init(&f));
  f.root = schema(&f, "null");
  field(f.root, "title", text(&f, "a"));
  field(f.root, "title", text(&f, "b"));
  field(f.root, "const", make(&f, LIE_SCHEMA_NULL, NULL, 0, 0));
  assert(compile(&f, 0, &out, NULL) == LIE_SCHEMA_OK);
  const node *base = f.visited[0];
  assert(base->v.count == 3 && !strcmp(base->edges[1].value->text, "a") &&
         !strcmp(base->edges[2].value->text, "b"));
  ++oracles;
  retire(&f);
}
static void boundaries(void) {
  for (unsigned which = 0; which < 7; ++which) {
    fixture f = {0};
    assert(init(&f));
    f.root = schema(&f, "null");
    uint32_t out = UINT32_MAX;
    lie_schema_error e = {0};
    size_t depth = 0;
    if (which == 0)
      depth = 17;
    if (which == 1)
      f.root->v.kind = LIE_SCHEMA_BOOL;
    if (which == 2)
      field(f.root, "$defs", array(&f));
    if (which == 3)
      field(f.root, "anyOf", array(&f));
    if (which == 4) {
      field(f.root, "const", make(&f, LIE_SCHEMA_NULL, NULL, 0, 0));
      f.enums = 1000;
    }
    if (which == 5) {
      node *defs = object(&f);
      field(defs, "x", schema(&f, "null"));
      field(f.root, "$defs", defs);
      f.counts.characters = 120000;
    }
    if (which == 6) {
      field(f.root, "$ref", text(&f, "https://invalid"));
    }
    assert(compile(&f, depth, &out, &e) == LIE_SCHEMA_INVALID &&
           out == UINT32_MAX && e.message);
    ++oracles;
    retire(&f);
  }
  for (unsigned which = 0; which < 3; ++which) {
    fixture f = {0};
    assert(init(&f));
    f.root = schema(&f, "string");
    node *e = array(&f);
    const size_t count = which == 2 ? 1001 : 251;
    char chars[62];
    memset(chars, 'x', sizeof(chars) - 1);
    chars[61] = 0;
    for (size_t i = 0; i < count; ++i)
      item(e, text(&f, which == 0 ? "x" : chars));
    field(f.root, "enum", e);
    uint32_t out = UINT32_MAX;
    lie_schema_error err = {0};
    lie_schema_status rc = compile(&f, 0, &out, &err);
    if (which == 0) {
      assert(rc == LIE_SCHEMA_OK && f.enums == 251 &&
             f.counts.characters == 251);
      language(&f, out, (const char *[]){"\"x\""}, 1);
    } else {
      assert(rc == LIE_SCHEMA_INVALID && out == UINT32_MAX && err.message);
      assert(!strcmp(err.message,
                     which == 1 ? "an enum with more than 250 entries is "
                                  "limited to 15000 string characters"
                                : "maximum enum/const value count is 1000"));
      ++oracles;
    }
    retire(&f);
  }
}
static void abi_work_and_empty_bodies(void) {
  fixture f = {0};
  assert(init(&f));
  f.root = schema(&f, "null");
  const lie_schema_body_description valid = f.d;
  uint32_t out = UINT32_MAX;
  for (unsigned which = 0; which < 15; ++which) {
    f.d = valid;
    switch (which) {
    case 0:
      ++f.d.abi_version;
      break;
    case 1:
      --f.d.struct_bytes;
      break;
    case 2:
      ++f.d.transform.abi_version;
      break;
    case 3:
      ++f.d.values.abi_version;
      break;
    case 4:
      --f.d.values.struct_bytes;
      break;
    case 5:
      f.d.values.max_depth = 257;
      break;
    case 6:
      f.d.append_member = NULL;
      break;
    case 7:
      f.d.compile.visit = NULL;
      break;
    case 8:
      f.d.compile.keep_schema = NULL;
      break;
    case 9:
      f.d.compile.normalize = NULL;
      break;
    case 10:
      f.d.rules.rule = NULL;
      break;
    case 11:
      f.d.transform.access.create = NULL;
      break;
    case 12:
      f.d.transform.access.clone = NULL;
      break;
    case 13:
      f.d.transform.access.put = NULL;
      break;
    default:
      f.d.transform.max_work = 0;
      break;
    }
    assert(compile(&f, 0, &out, NULL) == LIE_SCHEMA_INVALID &&
           out == UINT32_MAX);
    ++oracles;
  }
  f.d = valid;
  f.d.transform.max_work = 1;
  assert(compile(&f, 0, &out, NULL) == LIE_SCHEMA_WORK_LIMIT &&
         out == UINT32_MAX);
  ++oracles;
  f.d = valid;
  assert(compile(&f, 16, &out, NULL) == LIE_SCHEMA_OK);
  ++oracles;
  retire(&f);
  f = (fixture){0};
  assert(init(&f));
  f.root = schema(&f, "null");
  field(f.root, "const", make(&f, LIE_SCHEMA_NULL, NULL, 0, 0));
  f.enums = 999;
  f.counts.characters = 120000;
  assert(compile(&f, 0, &out, NULL) == LIE_SCHEMA_OK && f.enums == 1000 &&
         f.counts.characters == 120000);
  language(&f, out, (const char *[]){"null"}, 1);
  retire(&f);
  f = (fixture){0};
  assert(init(&f));
  f.root = object(&f);
  node *defs = object(&f), *recursive = object(&f);
  field(recursive, "$ref", text(&f, "#/$defs/r"));
  field(defs, "r", recursive);
  field(f.root, "$defs", defs);
  field(f.root, "$ref", text(&f, "#/$defs/r"));
  assert(compile(&f, 0, &out, NULL) == LIE_SCHEMA_OK && f.visits == 3 &&
         f.visited[0] == recursive && f.visited[1] == recursive &&
         f.visited[2] == recursive);
  lie_grammar_description empty;
  assert(lie_builder_finish(f.builder, out, 0, &empty) == LIE_BUILDER_CYCLE);
  ++oracles;
  retire(&f);
  f = (fixture){0};
  assert(init(&f));
  f.root = schema(&f, "string");
  node *branches = array(&f);
  item(branches, schema(&f, "null"));
  item(branches, schema(&f, "integer"));
  field(f.root, "anyOf", branches);
  assert(compile(&f, 0, &out, NULL) == LIE_SCHEMA_OK && f.visits == 0);
  assert(lie_builder_finish(f.builder, out, 0, &empty) == LIE_BUILDER_EMPTY);
  ++oracles;
  retire(&f);
}
static size_t construction(size_t fail, size_t callback, size_t *sites) {
  fixture f = {0};
  f.mem.fail = fail;
  f.fail = callback;
  bool ready = init(&f);
  size_t construction_calls = f.mem.calls;
  if (ready) {
    f.root = object(&f);
    node *defs = object(&f);
    field(defs, "a", schema(&f, "null"));
    field(f.root, "$defs", defs);
    node *branches = array(&f);
    for (size_t i = 0; i < 17; ++i) {
      node *branch = schema(&f, "integer"), *e = array(&f);
      item(e, number(&f, 1));
      item(e, number(&f, 2));
      field(branch, "enum", e);
      item(branches, branch);
    }
    field(f.root, "anyOf", branches);
    field(f.root, "type", text(&f, "integer"));
    uint32_t out = UINT32_MAX;
    lie_schema_status rc = compile(&f, 2, &out, NULL);
    *sites = f.calls;
    construction_calls = f.mem.calls;
    if (callback) {
      assert(rc == LIE_SCHEMA_CALLBACK && out == UINT32_MAX &&
             f.calls == callback);
      ++callback_refusals;
    } else if (fail) {
      assert(rc == LIE_SCHEMA_RESOURCE && out == UINT32_MAX);
      ++allocation_refusals;
    } else {
      assert(rc == LIE_SCHEMA_OK && f.kept >= 17 && f.normalized == 34 &&
             f.enums == 34 && f.depths[0] == 2);
      language(&f, out, (const char *[]){"1", "2"}, 2);
    }
  } else {
    assert(fail && f.mem.calls == fail);
    ++allocation_refusals;
  }
  retire(&f);
  return construction_calls;
}
int main(void) {
  ordered_definitions_and_references();
  finite_and_priority();
  boundaries();
  abi_work_and_empty_bodies();
  size_t callbacks = 0;
  const size_t allocations = construction(0, 0, &callbacks);
  assert(callbacks > 100 && allocations > 5);
  for (size_t n = 1; n <= callbacks; ++n) {
    size_t ignored = 0;
    construction(0, n, &ignored);
  }
  for (size_t n = 1; n <= allocations; ++n) {
    size_t ignored = 0;
    construction(n, 0, &ignored);
  }
  printf("C17 schema body: %zu independent oracles, %zu callback refusals, %zu "
         "allocation refusals, %zu construction allocation sites; "
         "HOST_NOT_INFERENCE\n",
         oracles, callback_refusals, allocation_refusals, allocations);
}
