/* SPDX-License-Identifier: MIT */
/* Independent exact numeric output contracts; HOST fixtures, NOT-INFERENCE. */
#include "../src/output_json.h"
#include "lie/schema_integer.h"
#include <assert.h>
#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static size_t checks;
static void accepts(const char *schema, const char *value, bool expected) {
  oj_node *s = oj_parse(schema, strlen(schema));
  oj_node *v = oj_parse(value, strlen(value));
  assert(s && v);
  bool actual = oj_schema_accepts(s, v);
  if (actual != expected)
    fprintf(stderr, "Exact output mismatch: schema=%s value=%s expected=%d actual=%d\n",
            schema, value, (int)expected, (int)actual);
  assert(actual == expected);
  oj_free(v);
  oj_free(s);
  ++checks;
}
static void compare(const char *text, size_t bytes, double boundary, int expected) {
  int actual = 99;
  assert(lie_schema_integer_compare(text, bytes, boundary, &actual) == LIE_SCHEMA_OK);
  assert(actual == expected);
  ++checks;
}
static int sign(int value) { return (value > 0) - (value < 0); }
static void comparison_oracles(void) {
  char text[96];
  for (int value = -257; value <= 257; ++value) {
    for (int twice_boundary = -5; twice_boundary <= 5; ++twice_boundary) {
      int n = snprintf(text, sizeof(text), "%d.00e+0", value);
      compare(text, (size_t)n, twice_boundary / 2.0, sign(2 * value - twice_boundary));
    }
    for (int negative = 0; negative < 2; ++negative) {
      int64_t exact = INT64_C(1000000000000000000) + value;
      if (negative) exact = -exact;
      int n = snprintf(text, sizeof(text), "%" PRId64, exact);
      compare(text, (size_t)n, negative ? -1e18 : 1e18,
              negative ? -sign(value) : sign(value));
      n = snprintf(text, sizeof(text), "%" PRId64 "0e-1", exact);
      compare(text, (size_t)n, negative ? -1e18 : 1e18,
              negative ? -sign(value) : sign(value));
    }
  }
  const char *invalid[] = {"", "-", "+1", "01", "-00", "1.", ".1", "1e",
    "1e+", "1e-", "1e1x", " 1", "1 ", "1\n", "1.1", "1e-400",
    "1000000000000000000.5", "-1000000000000000000.5",
    "1e-99999999999999999999999999999999999999"};
  for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) {
    int untouched = 99;
    assert(lie_schema_integer_compare(invalid[i], strlen(invalid[i]), 0,
                                      &untouched) == LIE_SCHEMA_INVALID);
    assert(untouched == 99);
    ++checks;
  }
  const double bad[] = {NAN, INFINITY, -INFINITY};
  for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
    int untouched = 99;
    assert(lie_schema_integer_compare("0", 1, bad[i], &untouched) == LIE_SCHEMA_INVALID);
    assert(untouched == 99);
    ++checks;
  }
  int untouched = 99;
  assert(lie_schema_integer_compare(NULL, 1, 0, &untouched) == LIE_SCHEMA_INVALID);
  assert(untouched == 99);
  assert(lie_schema_integer_compare("1", 1, 0, NULL) == LIE_SCHEMA_INVALID);
  const char span[] = {'1', '0', 'X'};
  compare(span, 2, 10, 0);
  const char nul[] = {'1', '\0', '0'};
  assert(lie_schema_integer_compare(nul, sizeof(nul), 0, &untouched) == LIE_SCHEMA_INVALID);
  assert(untouched == 99);
  union { int out; char text[16]; } alias;
  memset(&alias, '0', sizeof(alias));
  alias.text[0] = '1';
  unsigned char before[sizeof(alias)];
  memcpy(before, &alias, sizeof(alias));
  assert(lie_schema_integer_compare(alias.text, 2, 0, &alias.out) == LIE_SCHEMA_INVALID);
  assert(!memcmp(before, &alias, sizeof(alias)));
  checks += 4;
  compare("0e99999999999999999999999999999999", 34, 0, 0);
  compare("-0e-99999999999999999999999999999999", 36, -0.5, 1);
  const char *huge = "1e99999999999999999999999999999999999999";
  compare(huge, strlen(huge), DBL_MAX, 1);
  char long_span[8192];
  long_span[0] = '1'; memset(long_span + 1, '0', 8000);
  memcpy(long_span + 8001, "e-8000", 6);
  compare(long_span, 8007, 1, 0);
  compare(long_span, 8007, -0.5, 1);
  long_span[4000] = '1';
  assert(lie_schema_integer_compare(long_span, 8007, 1, &untouched) == LIE_SCHEMA_INVALID);
  assert(untouched == 99); ++checks;
}
static void large_bound_oracles(void) {
  const char *keys[] = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"};
  for (unsigned negative = 0; negative < 2; ++negative)
    for (unsigned key = 0; key < 4; ++key) {
      char schema[128];
      snprintf(schema, sizeof(schema), "{\"type\":\"integer\",\"%s\":%s1e18}",
               keys[key], negative ? "-" : "");
      for (int delta = -129; delta <= 129; ++delta) {
        int64_t exact = INT64_C(1000000000000000000) + delta;
        if (negative) exact = -exact;
        char text[64]; snprintf(text, sizeof(text), "%" PRId64, exact);
        int order = negative ? -sign(delta) : sign(delta);
        bool expected = key == 0 ? order >= 0 : key == 1 ? order <= 0
                          : key == 2 ? order > 0 : order < 0;
        accepts(schema, text, expected);
      }
    }
  const char *largest =
    "179769313486231570814527423731704356798070567525844996598917476803157260"
    "780028538760589558632766878171540458953514382464234321326889464182768467"
    "546703537516986049910576551282076245490090389328944075868508455133942304"
    "583236903222948165808559332123348274797826204144723168738177180919299881"
    "250404026184124858368";
  size_t n = strlen(largest); assert(n == 309);
  compare(largest, n, DBL_MAX, 0);
  char next[512]; memcpy(next, largest, n + 1);
  next[n - 1] = '9';
  compare(next, n, DBL_MAX, 1);
  accepts("{\"type\":\"integer\",\"maximum\":1.7976931348623157e308}", next, false);
  next[n - 1] = '7';
  compare(next, n, DBL_MAX, -1);
  accepts("{\"type\":\"integer\",\"minimum\":1.7976931348623157e308}", next, false);
  accepts("{\"type\":\"integer\",\"minimum\":1.7976931348623157e308,"
          "\"maximum\":1.7976931348623157e308}", largest, true);
}
int main(void) {
  const char *positive = "{\"type\":\"integer\",\"exclusiveMinimum\":1e18,"
                         "\"maximum\":1.0000000000000001e18}";
  accepts(positive, "1000000000000000001", true);
  accepts(positive, "1000000000000000000", false);
  accepts(positive, "1000000000000000128", true);
  accepts(positive, "1000000000000000129", false);
  const char *negative = "{\"type\":\"integer\",\"minimum\":-1.0000000000000001e18,"
                         "\"exclusiveMaximum\":-1e18}";
  accepts(negative, "-1000000000000000001", true);
  accepts(negative, "-1000000000000000000", false);
  accepts(negative, "-1000000000000000128", true);
  accepts(negative, "-1000000000000000129", false);
  accepts("{\"type\":\"integer\"}", "1000000000000000000.5", false);
  accepts("{\"type\":\"integer\"}", "1e-400", false);
  accepts("{\"type\":\"integer\"}", "1.0", true);
  accepts("{\"type\":\"integer\"}", "10e-1", true);
  accepts("{\"type\":\"integer\"}", "-0e-99999", true);
  accepts("{\"type\":\"integer\",\"exclusiveMinimum\":0.5,\"exclusiveMaximum\":1.5}", "1", true);
  accepts("{\"type\":\"integer\",\"exclusiveMinimum\":-1.5,\"exclusiveMaximum\":-0.5}", "-1", true);
  accepts("{\"type\":[\"integer\",\"null\"]}", "1e-400", false);
  accepts("{\"type\":[\"integer\",\"null\"]}", "null", true);
  accepts("{\"anyOf\":[{\"type\":\"integer\"},{\"type\":\"string\"}]}", "1e-400", false);
  accepts("{\"type\":\"object\",\"properties\":{\"value\":{\"type\":\"integer\","
          "\"exclusiveMinimum\":1e18,\"maximum\":1.0000000000000001e18}},"
          "\"required\":[\"value\"],\"additionalProperties\":false}",
          "{\"value\":1000000000000000001}", true);
  comparison_oracles(); large_bound_oracles();
  printf("Exact output-schema: %zu numeric checks; HOST NOT-INFERENCE\n", checks);
  return 0;
}
