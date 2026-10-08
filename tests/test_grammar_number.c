/* SPDX-License-Identifier: MIT */
/* Independent integer/rational oracles; synthetic host checks, NOT-INFERENCE. */
#include "lie/grammar_number.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static lie_number_text text(const char *s) { return (lie_number_text){s, strlen(s)}; }
static lie_number_policy *create(lie_number_description *d) {
  lie_number_policy *p = NULL; assert(lie_number_create(d, &p) == LIE_NUMBER_OK); return p;
}
static void cents(char *out, int n) {
  unsigned a = (unsigned)(n < 0 ? -n : n);
  sprintf(out, "%s%u.%02u", n < 0 ? "-" : "", a / 100, a % 100);
}
static unsigned gcd(unsigned a, unsigned b) { while (b) { unsigned r = a % b; a = b; b = r; } return a; }
static unsigned scientific_cents(const char *s, size_t n) {
  size_t i = 0; unsigned value = 0;
  while (i < n && s[i] != 'e') { assert(s[i] >= '0' && s[i] <= '9'); value = value * 10 + (unsigned)(s[i++] - '0'); }
  assert(i < n && s[i++] == 'e'); bool negative = i < n && s[i] == '-'; if (negative) ++i;
  unsigned e = 0; while (i < n) { assert(s[i] >= '0' && s[i] <= '9'); e = e * 10 + (unsigned)(s[i++] - '0'); }
  int shift = 2 + (negative ? -(int)e : (int)e);
  while (shift > 0) { value *= 10; --shift; }
  while (shift < 0) { assert(value % 10 == 0); value /= 10; ++shift; }
  return value;
}
typedef struct { size_t calls, fail, alive, policy_bytes, workspace_bytes; } allocation;
static void *allocate(void *context, size_t bytes) {
  allocation *a = context; if (++a->calls == a->fail) return NULL;
  if (a->calls == 1) a->policy_bytes = bytes; else a->workspace_bytes = bytes;
  void *p = malloc(bytes); if (p) ++a->alive; return p;
}
static void release(void *context, void *p) { allocation *a = context; assert(a->alive); --a->alive; free(p); }
/* Pending final qualification: these oracles use only integer cross-products
 * and remainder, independently of the decimal/JSON/provider implementation. */
static void complete_scalar_oracles(void) {
  for (int a = -173; a <= 173; ++a) {
    char value[32]; cents(value, a);
    for (int b = -41; b <= 41; ++b) {
      char bound[32]; sprintf(bound, "%de-3", b);
      int order = 99;
      int difference = a * 10 - b;
      assert(lie_number_compare(text(value), text(bound), &order) == LIE_NUMBER_OK);
      assert(order == (difference > 0) - (difference < 0));
    }
    for (int b = 1; b <= 31; ++b) {
      char step[32]; cents(step, b);
      bool multiple = false;
      assert(lie_number_multiple(text(value), text(step), &multiple) == LIE_NUMBER_OK);
      assert(multiple == (a % b == 0));
    }
  }
  struct { const char *a, *b; int order; } pairs[] = {
    {"-0e4000", "0.0000", 0}, {"-3e-1", "-0.300", 0},
    {"0.3000000000000000001", "0.3", 1},
    {"-0.3000000000000000001", "-0.3", -1},
    {"1000000000000000001", "1e18", 1},
    {"1e-400", "0", 1}, {"-1e-400", "0", -1},
    {"1e4096", "1e-4096", 1}
  };
  for (size_t i = 0; i < sizeof(pairs) / sizeof(*pairs); ++i) {
    int order = 99;
    assert(lie_number_compare(text(pairs[i].a), text(pairs[i].b), &order) == LIE_NUMBER_OK);
    assert(order == pairs[i].order);
  }
  const char *invalid[] = {"", "01", "+1", "1.", ".1", "1e", "1e-", "1x", " 1", "1 "};
  for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i) {
    int order = 99; bool multiple = true;
    assert(lie_number_compare(text(invalid[i]), text("0"), &order) == LIE_NUMBER_INVALID);
    assert(order == 99);
    assert(lie_number_compare(text("0"), text(invalid[i]), &order) == LIE_NUMBER_INVALID);
    assert(order == 99);
    assert(lie_number_multiple(text(invalid[i]), text("0.3"), &multiple) == LIE_NUMBER_INVALID);
    assert(multiple);
    assert(lie_number_multiple(text("0"), text(invalid[i]), &multiple) == LIE_NUMBER_INVALID);
    assert(multiple);
  }
  int order = 99; bool multiple = true;
  assert(lie_number_compare(text("1e4097"), text("0"), &order) == LIE_NUMBER_RESOURCE && order == 99);
  assert(lie_number_multiple(text("1e4097"), text("0.1"), &multiple) == LIE_NUMBER_RESOURCE && multiple);
  assert(lie_number_multiple(text("1e4096"), text("1e-4096"), &multiple) == LIE_NUMBER_RESOURCE && multiple);
  char large[4097]; memset(large, '1', sizeof(large));
  assert(lie_number_compare((lie_number_text){large, sizeof(large)}, text("0"), &order) == LIE_NUMBER_RESOURCE && order == 99);
  assert(lie_number_multiple((lie_number_text){large, sizeof(large)}, text("1"), &multiple) == LIE_NUMBER_RESOURCE && multiple);
  assert(lie_number_compare((lie_number_text){NULL, 1}, text("0"), &order) == LIE_NUMBER_INVALID && order == 99);
  assert(lie_number_compare(text("0"), text("0"), NULL) == LIE_NUMBER_INVALID);
  assert(lie_number_multiple(text("0"), text("1"), NULL) == LIE_NUMBER_INVALID);
  const char *nonpositive[] = {"0", "-0", "-0.1"};
  for (size_t i = 0; i < sizeof(nonpositive) / sizeof(*nonpositive); ++i) {
    assert(lie_number_multiple(text("0"), text(nonpositive[i]), &multiple) == LIE_NUMBER_INVALID);
    assert(multiple);
  }
  union { int order; bool multiple; char text[16]; } alias;
  memset(&alias, 0, sizeof(alias)); memcpy(alias.text, "0.3", 3);
  unsigned char before[sizeof(alias)]; memcpy(before, &alias, sizeof(alias));
  assert(lie_number_compare((lie_number_text){alias.text, 3}, text("0.3"), &alias.order) == LIE_NUMBER_INVALID);
  assert(!memcmp(before, &alias, sizeof(alias)));
  assert(lie_number_multiple(text("0.9"), (lie_number_text){alias.text, 3}, &alias.multiple) == LIE_NUMBER_INVALID);
  assert(!memcmp(before, &alias, sizeof(alias)));
  const char span[] = {'3', 'e', '-', '1', 'X'};
  assert(lie_number_compare((lie_number_text){span, 4}, text("0.3"), &order) == LIE_NUMBER_OK && !order);
  const char nul[] = {'1', '\0', '0'};
  order = 99;
  assert(lie_number_compare((lie_number_text){nul, sizeof(nul)}, text("0"), &order) == LIE_NUMBER_INVALID && order == 99);
  allocation a = {.fail = 1};
  lie_grammar_allocator hooks = {&a, allocate, release};
  assert(lie_number_multiple_with_allocator(text("0.9"), text("0.3"), &hooks, 0, &multiple) == LIE_NUMBER_RESOURCE);
  assert(multiple && a.calls == 1 && !a.alive);
  a.fail = 0;
  assert(lie_number_multiple_with_allocator(text("144.4"), text("0.3"), &hooks, 1, &multiple) == LIE_NUMBER_WORK_LIMIT);
  assert(multiple && !a.alive);
  assert(lie_number_multiple_with_allocator(text("-0e4000"), text("0.3"), &hooks, 1, &multiple) == LIE_NUMBER_OK && multiple);
  assert(!a.alive);
  hooks.release = NULL;
  size_t calls = a.calls;
  assert(lie_number_multiple_with_allocator(text("0"), text("1"), &hooks, 0, &multiple) == LIE_NUMBER_INVALID);
  assert(multiple && a.calls == calls && !a.alive);
}
int main(void) {
  complete_scalar_oracles();
  size_t values = 0, intersections = 0;
  lie_number_description d; lie_number_description_init(&d);
  d.minimum = text("-12.5"); d.maximum = text("17.75"); d.multiple = text("0.15");
  lie_number_policy *p = create(&d);
  /* Fixed-point oracle uses only integer bounds/modulus, independently of
   * the C decimal implementation and JSON/Gufo parser. */
  for (int n = -2500; n <= 2500; ++n) {
    char s[32]; cents(s, n); bool ok;
    assert(lie_number_accept(p, text(s), &ok) == LIE_NUMBER_OK);
    assert(ok == (n >= -1250 && n <= 1775 && n % 15 == 0)); ++values;
  }
  lie_number_release(p);
  const char *steps[] = {"0.1", "0.15", "0.25", "1.2", "2.5", "1e-20"};
  unsigned grids[] = {1, 3, 1, 6, 5, 1};
  for (size_t i = 0; i < 6; ++i) {
    lie_number_description_init(&d); d.integer = true; d.multiple = text(steps[i]); p = create(&d);
    for (int n = -100; n <= 100; ++n) {
      char s[32]; sprintf(s, "%d", n); bool ok;
      assert(lie_number_accept(p, text(s), &ok) == LIE_NUMBER_OK); assert(ok == (n % (int)grids[i] == 0)); ++values;
      cents(s, n * 100 + 1); assert(lie_number_accept(p, text(s), &ok) == LIE_NUMBER_OK); assert(!ok); ++values;
    }
    lie_number_release(p);
  }
  for (unsigned a = 1; a <= 40; ++a) for (unsigned b = 1; b <= 40; ++b) {
    char left[32], right[32], out[128]; size_t n = 999;
    sprintf(left, "%u.%u", a / 10, a % 10); cents(right, (int)b);
    assert(lie_number_intersect(text(left), text(right), NULL, 0, out, sizeof(out), &n) == LIE_NUMBER_OK);
    assert(scientific_cents(out, n) == (a * 10 / gcd(a * 10, b)) * b); ++intersections;
  }
  lie_number_description_init(&d); d.minimum = text("14"); d.maximum = text("15"); d.multiple = text("0.3"); p = create(&d);
  struct { const char *s; bool prefix, complete; } cases[] = {
    {"", true, false}, {"-", false, false}, {"1", true, false},
    {"14.", true, false}, {"14.4", true, true}, {"14.5", false, false},
    {"15", true, true}, {"15.0", true, true}, {"15.1", false, false},
    {"1e1", false, false}, {"+14", false, false}, {".3", false, false},
    {"01", false, false}, {"--1", false, false}, {"1..", false, false}
  };
  for (size_t i = 0; i < sizeof(cases)/sizeof(*cases); ++i) {
    lie_number_match m; assert(lie_number_check(p, text(cases[i].s), &m) == LIE_NUMBER_OK);
    assert(m.prefix == cases[i].prefix && m.complete == cases[i].complete);
  }
  bool ok = false; assert(lie_number_accept(p, text("144e-1"), &ok) == LIE_NUMBER_OK && ok);
  ok = true; assert(lie_number_accept(p, text("14."), &ok) == LIE_NUMBER_INVALID && ok);
  lie_number_release(p);
  lie_number_description_init(&d); d.minimum = text("2"); d.maximum = text("1");
  p = (lie_number_policy *)(uintptr_t)1;
  assert(lie_number_create(&d, &p) == LIE_NUMBER_EMPTY_INTERVAL && p == (lie_number_policy *)(uintptr_t)1);
  d.minimum = text("1"); d.maximum = text("2"); d.multiple = text("3");
  assert(lie_number_create(&d, &p) == LIE_NUMBER_EMPTY_GRID);
  d.minimum = text("0.1"); d.maximum = text("0.1"); d.integer = true; d.multiple = text("0.1");
  assert(lie_number_create(&d, &p) == LIE_NUMBER_EMPTY_INTERVAL);
  d.integer = false; d.exclusive_minimum = text("0.1");
  assert(lie_number_create(&d, &p) == LIE_NUMBER_EMPTY_INTERVAL);
  lie_number_description_init(&d); p = create(&d);
  char large[4098]; memset(large, '9', sizeof(large)); lie_number_match m;
  assert(lie_number_check(p, (lie_number_text){large,4096}, &m) == LIE_NUMBER_OK && m.prefix && m.complete);
  assert(lie_number_check(p, (lie_number_text){large,4097}, &m) == LIE_NUMBER_OK && !m.prefix && !m.complete);
  large[4095] = '.';
  assert(lie_number_check(p, (lie_number_text){large,4096}, &m) == LIE_NUMBER_OK && !m.prefix && !m.complete);
  m = (lie_number_match){true,true}; assert(lie_number_check(p, (lie_number_text){NULL,1}, &m) == LIE_NUMBER_INVALID && m.complete);
  lie_number_release(p);
  /* Every allocator refusal is transactional and leak-free. */
  for (size_t fail = 1; fail <= 2; ++fail) {
    allocation a = {.fail=fail}; lie_number_description_init(&d); d.allocator = (lie_grammar_allocator){&a,allocate,release};
    p = (lie_number_policy *)(uintptr_t)1;
    assert(lie_number_create(&d,&p) == LIE_NUMBER_RESOURCE && p == (lie_number_policy *)(uintptr_t)1 && !a.alive);
  }
  allocation a = {0}; lie_number_description_init(&d); d.allocator = (lie_grammar_allocator){&a,allocate,release};
  char minimum[] = "-10"; d.minimum = text(minimum); p = create(&d); minimum[1] = '9';
  a.fail = a.calls + 1; m = (lie_number_match){true,true};
  assert(lie_number_check(p,text("1"),&m) == LIE_NUMBER_RESOURCE && m.prefix && m.complete && a.alive == 1);
  a.fail = a.calls + 1; ok = true;
  assert(lie_number_accept(p,text("1"),&ok) == LIE_NUMBER_RESOURCE && ok && a.alive == 1);
  a.fail = 0; assert(lie_number_accept(p,text("-11"),&ok) == LIE_NUMBER_OK && !ok);
  lie_number_release(p); assert(!a.alive);
  lie_number_description_init(&d); d.max_work = 1; p = create(&d); m = (lie_number_match){true,true};
  assert(lie_number_check(p,text("1"),&m) == LIE_NUMBER_WORK_LIMIT && m.prefix && m.complete); lie_number_release(p);
  size_t policy_bytes = a.policy_bytes, workspace_bytes = a.workspace_bytes;
  lie_number_description_init(&d); d.max_work = 1;
  d.minimum = text("0.1"); d.maximum = text("0.2"); d.multiple = text("0.15");
  p = (lie_number_policy *)(uintptr_t)1;
  assert(lie_number_create(&d,&p) == LIE_NUMBER_WORK_LIMIT && p == (lie_number_policy *)(uintptr_t)1);
  lie_number_description_init(&d); d.abi_version++;
  assert(lie_number_create(&d,&p) == LIE_NUMBER_INVALID);
  lie_number_description_init(&d); d.allocator.allocate = allocate;
  assert(lie_number_create(&d,&p) == LIE_NUMBER_INVALID);
  char out[64]; memset(out,'x',sizeof(out)); size_t length = 777;
  allocation failed = {.fail=1};
  lie_grammar_allocator hooks = {&failed,allocate,release};
  assert(lie_number_intersect(text("0.3"),text("0.2"),&hooks,0,out,sizeof(out),&length) == LIE_NUMBER_RESOURCE);
  assert(!failed.alive && length == 777 && out[0] == 'x');
  assert(lie_number_intersect(text("0.3"),text("0.2"),NULL,1,out,sizeof(out),&length) == LIE_NUMBER_WORK_LIMIT);
  assert(length == 777 && out[0] == 'x');
  assert(lie_number_intersect(text("0.3"),text("0.2"),NULL,0,out,1,&length) == LIE_NUMBER_RESOURCE && length == 777 && out[0] == 'x');
  assert(lie_number_intersect(text("0"),text("0.2"),NULL,0,out,sizeof(out),&length) == LIE_NUMBER_INVALID && length == 777);
  strcpy(out,"0.3"); assert(lie_number_intersect(text(out),text("0.2"),NULL,0,out,sizeof(out),&length) == LIE_NUMBER_INVALID && !strcmp(out,"0.3"));
  assert(lie_number_equal(text("-0e+4000"),text("0.00"),&ok) == LIE_NUMBER_OK && ok);
  assert(lie_number_equal(text("3e-1"),text("0.3000"),&ok) == LIE_NUMBER_OK && ok);
  ok = true; assert(lie_number_equal(text("1e4097"),text("0"),&ok) == LIE_NUMBER_RESOURCE && ok);
  printf("NUMBER_RATIONAL_VALUES=%zu LCM_PAIRS=%zu POLICY_BYTES=%zu WORKSPACE_BYTES=%zu HOST_NOT_INFERENCE\n", values, intersections, policy_bytes, workspace_bytes);
}
