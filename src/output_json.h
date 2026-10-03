/* SPDX-License-Identifier: MIT */
#ifndef LIE_OUTPUT_JSON_H
#define LIE_OUTPUT_JSON_H
#include <stdbool.h>
#include <stddef.h>
typedef enum {
  OJ_NULL,
  OJ_BOOL,
  OJ_NUMBER,
  OJ_STRING,
  OJ_ARRAY,
  OJ_OBJECT
} oj_type;
typedef struct oj_node {
  oj_type type;
  char *string;
  double number;
  bool boolean;
  struct oj_node *child, *next;
  const char *start;
  size_t bytes;
} oj_node;
oj_node *oj_parse(const char *, size_t);
void oj_free(oj_node *);
const oj_node *oj_field(const oj_node *, const char *);
bool oj_type_is(const oj_node *, const char *);
char *oj_quote(const char *, size_t);
bool oj_schema_accepts(const oj_node *schema, const oj_node *value);
#endif
