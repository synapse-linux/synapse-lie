/* SPDX-License-Identifier: MIT */
#include "output_json.h"
#include "lie/binary64.h"
#include "lie/grammar_number.h"
#include "lie/schema_integer.h"
#include <string.h>
/* The transitional compiler admits binary64 schema numbers and uses their
 * shortest JSON spelling for decimal predicates/literals. Match that schema
 * domain, but retain every original output digit in the final check. Integer
 * interval bounds continue to use the exact represented binary64 boundary. */
static bool number_spelling(const oj_node *schema, char *text,
                            lie_number_text *span, double *number) {
  double value;
  size_t bytes = 0;
  if (!schema || schema->type != OJ_NUMBER ||
      lie_binary64_parse(schema->start, schema->bytes, NULL, &value) !=
          LIE_BINARY64_OK ||
      lie_binary64_format(value, text, LIE_BINARY64_TEXT_CAPACITY, &bytes) !=
          LIE_BINARY64_OK)
    return false;
  *span = (lie_number_text){text, bytes};
  if (number) *number = value;
  return true;
}
static bool equal(const oj_node *a, const oj_node *b) {
  if (!a || !b || a->type != b->type)
    return false;
  if (a->type == OJ_STRING)
    return !strcmp(a->string, b->string);
  if (a->type == OJ_NUMBER) {
    char text[LIE_BINARY64_TEXT_CAPACITY];
    lie_number_text schema;
    int order;
    return number_spelling(a, text, &schema, NULL) &&
           lie_number_compare(schema, (lie_number_text){b->start, b->bytes},
                              &order) == LIE_NUMBER_OK && order == 0;
  }
  if (a->type == OJ_BOOL)
    return a->boolean == b->boolean;
  if (a->type == OJ_OBJECT) {
    size_t count = 0, other = 0;
    for (const oj_node *k = a->child; k; k = k->next->next) {
      ++count;
      if (!equal(k->next, oj_field(b, k->string)))
        return false;
    }
    for (const oj_node *k = b->child; k; k = k->next->next)
      ++other;
    return count == other;
  }
  const oj_node *x = a->child, *y = b->child;
  while (x && y) {
    if (!equal(x, y))
      return false;
    x = x->next;
    y = y->next;
  }
  return !x && !y;
}
static bool accepts(const oj_node *root, const oj_node *s, const oj_node *v,
                    unsigned depth) {
  if (!s || !v || depth > 64)
    return false;
  if (s->type == OJ_BOOL)
    return s->boolean;
  if (s->type != OJ_OBJECT)
    return false;
  const oj_node *ref = oj_field(s, "$ref");
  if (ref) {
    if (ref->type != OJ_STRING ||
        (strcmp(ref->string, "#") && strncmp(ref->string, "#/$defs/", 8)))
      return false;
    const oj_node *target =
        !strcmp(ref->string, "#")
            ? root
            : oj_field(oj_field(root, "$defs"), ref->string + 8);
    return target && accepts(root, target, v, depth + 1);
  }
  const char *const types[] = {"null",   "boolean", "number",
                               "string", "array",   "object"};
  int integer_order = 0;
  bool integer = v->type == OJ_NUMBER &&
                 lie_schema_integer_compare(v->start, v->bytes, 0,
                                            &integer_order) == LIE_SCHEMA_OK;
  if (oj_field(s, "type") && !oj_type_is(s, types[v->type]) &&
      !(integer && oj_type_is(s, "integer")))
    return false;
  const oj_node *choices = oj_field(s, "enum");
  if (choices) {
    if (choices->type != OJ_ARRAY)
      return false;
    bool found = false;
    for (const oj_node *x = choices->child; x; x = x->next)
      found |= equal(x, v);
    if (!found)
      return false;
  }
  if (oj_field(s, "const") && !equal(oj_field(s, "const"), v))
    return false;
  const char *const unions[] = {"anyOf", "oneOf", "allOf"};
  for (unsigned k = 0; k < 3; ++k) {
    choices = oj_field(s, unions[k]);
    if (!choices)
      continue;
    if (choices->type != OJ_ARRAY)
      return false;
    unsigned yes = 0, total = 0;
    for (const oj_node *x = choices->child; x; x = x->next) {
      ++total;
      yes += accepts(root, x, v, depth + 1);
    }
    if (!yes || (k == 1 && yes != 1) || (k == 2 && yes != total))
      return false;
  }
  if (v->type == OJ_OBJECT) {
    const oj_node *req = oj_field(s, "required"),
                  *props = oj_field(s, "properties"),
                  *extra = oj_field(s, "additionalProperties");
    if (req) {
      if (req->type != OJ_ARRAY)
        return false;
      for (const oj_node *x = req->child; x; x = x->next)
        if (x->type != OJ_STRING || !oj_field(v, x->string))
          return false;
    }
    for (const oj_node *k = v->child; k; k = k->next->next) {
      const oj_node *p = oj_field(props, k->string);
      if (p) {
        if (!accepts(root, p, k->next, depth + 1))
          return false;
      } else if (extra && !accepts(root, extra, k->next, depth + 1))
        return false;
    }
  }
  if (v->type == OJ_ARRAY) {
    size_t count = 0;
    const oj_node *items = oj_field(s, "items");
    for (const oj_node *x = v->child; x; x = x->next) {
      ++count;
      if (items && !accepts(root, items, x, depth + 1))
        return false;
    }
    const oj_node *min = oj_field(s, "minItems"),
                  *max = oj_field(s, "maxItems");
    if ((min && (min->type != OJ_NUMBER || count < min->number)) ||
        (max && (max->type != OJ_NUMBER || count > max->number)))
      return false;
  }
  if (v->type == OJ_NUMBER) {
    const char *keys[] = {"minimum", "maximum", "exclusiveMinimum",
                          "exclusiveMaximum", "multipleOf"};
    for (unsigned i = 0; i < 5; ++i) {
      const oj_node *n = oj_field(s, keys[i]);
      if (!n)
        continue;
      char text[LIE_BINARY64_TEXT_CAPACITY];
      lie_number_text boundary;
      double number;
      if (!number_spelling(n, text, &boundary, &number))
        return false;
      if (i < 4) {
        int order = 0;
        bool compared = integer
            ? lie_schema_integer_compare(v->start, v->bytes, number, &order) ==
                  LIE_SCHEMA_OK
            : lie_number_compare((lie_number_text){v->start, v->bytes},
                                 boundary, &order) == LIE_NUMBER_OK;
        if (!compared ||
            (i == 0 && order < 0) || (i == 1 && order > 0) ||
            (i == 2 && order <= 0) || (i == 3 && order >= 0)) return false;
      } else {
        bool multiple = false;
        if (lie_number_multiple((lie_number_text){v->start, v->bytes},
                                boundary, &multiple) != LIE_NUMBER_OK || !multiple)
          return false;
      }
    }
  }
  return true;
}
bool oj_schema_accepts(const oj_node *s, const oj_node *v) {
  return accepts(s, s, v, 0);
}
