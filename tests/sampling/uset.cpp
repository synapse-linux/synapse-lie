// SPDX-License-Identifier: MIT
// Complete host decoder and full-set identity witnesses. No model forward.
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <memory>
#include <string>
#include <unicode/uniset.h>
#include <unicode/unistr.h>
#include <vector>
#if LIE_C17_SAMPLING
#include "lie/grammar_unicode.h"
#endif
static size_t decoded = 0, operations = 0;
static void decode(const char *p, size_t n) {
  std::vector<uint16_t> units;
#if LIE_C17_SAMPLING
  units.resize(n + 1);
  size_t length = 0;
  assert(lie_grammar_utf8_to_utf16(p, n, units.data(), units.size(), &length) ==
         LIE_REGEX_COMPILE_OK);
  units.resize(length);
#else
  auto text = icu::UnicodeString::fromUTF8(
      icu::StringPiece(p, static_cast<int32_t>(n)));
  for (int32_t i = 0; i < text.length(); ++i)
    units.push_back(static_cast<uint16_t>(text.charAt(i)));
#endif
  std::printf("decode=");
  for (size_t i = 0; i < n; ++i)
    std::printf("%02x", unsigned(static_cast<uint8_t>(p[i])));
  std::printf(" units=");
  for (auto unit : units)
    std::printf("%04x,", unsigned(unit));
  std::printf("\n");
  ++decoded;
}
static std::string utf8(uint32_t cp) {
  std::string s;
  if (cp < 0x80)
    s += static_cast<char>(cp);
  else if (cp < 0x800) {
    s += static_cast<char>(0xc0 | (cp >> 6));
    s += static_cast<char>(0x80 | (cp & 63));
  } else if (cp < 0x10000) {
    s += static_cast<char>(0xe0 | (cp >> 12));
    s += static_cast<char>(0x80 | ((cp >> 6) & 63));
    s += static_cast<char>(0x80 | (cp & 63));
  } else {
    s += static_cast<char>(0xf0 | (cp >> 18));
    s += static_cast<char>(0x80 | ((cp >> 12) & 63));
    s += static_cast<char>(0x80 | ((cp >> 6) & 63));
    s += static_cast<char>(0x80 | (cp & 63));
  }
  return s;
}
class Sets {
public:
#if LIE_C17_SAMPLING
  using Handle = void *;
  Sets() {
    lie_grammar_unicode_description d;
    lie_grammar_unicode_description_init(&d);
    lie_grammar_unicode *raw = nullptr;
    assert(lie_grammar_unicode_create(&d, &raw) == LIE_REGEX_COMPILE_OK);
    owner.reset(raw);
    assert(lie_grammar_unicode_sets(raw, &h) == LIE_REGEX_COMPILE_OK);
    lie_regex_bases b;
    assert(lie_regex_compiler_bases(lie_grammar_unicode_compiler(raw), &b) ==
           LIE_REGEX_COMPILE_OK);
    expressions.push_back(b.any);
    empty = b.empty;
  }
  Handle Range(int32_t a, int32_t b) {
    Handle p;
    assert(h.range(h.context, a, b, &p) == LIE_REGEX_COMPILE_OK);
    return p;
  }
  Handle Property(const std::string &p) {
    Handle s;
    assert(h.property(h.context, p.data(), p.size(), &s) ==
           LIE_REGEX_COMPILE_OK);
    return s;
  }
  void Add(Handle a, Handle b) {
    assert(h.add(h.context, a, b) == LIE_REGEX_COMPILE_OK);
  }
  void AddRange(Handle a, int32_t lo, int32_t hi) {
    assert(h.add_range(h.context, a, lo, hi) == LIE_REGEX_COMPILE_OK);
  }
  void Remove(Handle a, int32_t lo, int32_t hi) {
    assert(h.remove_range(h.context, a, lo, hi) == LIE_REGEX_COMPILE_OK);
  }
  void Complement(Handle a) {
    assert(h.complement(h.context, a) == LIE_REGEX_COMPILE_OK);
  }
  void Dump(Handle a) {
    uint64_t size;
    int32_t first;
    assert(h.info(h.context, a, &size, &first) == LIE_REGEX_COMPILE_OK);
    uint32_t root;
    assert(h.publish(h.context, a, &root) == LIE_REGEX_COMPILE_OK);
    auto at = std::find(expressions.begin(), expressions.end(), root);
    int id = root == empty ? -1 : static_cast<int>(at - expressions.begin());
    if (root != empty && at == expressions.end())
      expressions.push_back(root);
    std::printf("set=%zu size=%llu first=%d class=%d", operations,
                static_cast<unsigned long long>(size), first, id);
    lie_regex_program *raw = nullptr;
    assert(lie_regex_seal(lie_grammar_unicode_compiler(owner.get()), root,
                          &raw) == LIE_REGEX_COMPILE_OK);
    std::unique_ptr<lie_regex_program, decltype(&lie_regex_release)> p(
        raw, lie_regex_release);
    for (uint32_t cp : Points()) {
      uint32_t state;
      bool contains;
      assert(lie_regex_advance(raw, 0, cp, &state) == LIE_REGEX_OK);
      assert(lie_regex_accepting(raw, state, &contains) == LIE_REGEX_OK);
      std::printf(" %x:%d", cp, contains);
    }
    std::printf("\n");
    ++operations;
  }
  void Drop(Handle p) { h.release(h.context, p); }

private:
  std::unique_ptr<lie_grammar_unicode, decltype(&lie_grammar_unicode_release)>
      owner{nullptr, lie_grammar_unicode_release};
  lie_regex_unicode_sets h{};
  std::vector<uint32_t> expressions;
  uint32_t empty{};
#else
  using Handle = icu::UnicodeSet *;
  Sets() {
    icu::UnicodeSet s(0, 0x10ffff);
    s.remove(0xd800, 0xdfff);
    classes.push_back(std::move(s));
  }
  Handle Range(int32_t a, int32_t b) { return new icu::UnicodeSet(a, b); }
  Handle Property(const std::string &p) {
    UErrorCode error = U_ZERO_ERROR;
    auto s =
        new icu::UnicodeSet(icu::UnicodeString::fromUTF8(p), 0, nullptr, error);
    assert(U_SUCCESS(error));
    return s;
  }
  void Add(Handle a, Handle b) { a->addAll(*b); }
  void AddRange(Handle a, int32_t lo, int32_t hi) { a->add(lo, hi); }
  void Remove(Handle a, int32_t lo, int32_t hi) { a->remove(lo, hi); }
  void Complement(Handle a) { a->complement(); }
  void Dump(Handle a) {
    auto s = *a;
    s.remove(0xd800, 0xdfff);
    auto at = std::find(classes.begin(), classes.end(), s);
    int id = s.isEmpty() ? -1 : static_cast<int>(at - classes.begin());
    if (!s.isEmpty() && at == classes.end())
      classes.push_back(s);
    std::printf("set=%zu size=%llu first=%d class=%d", operations,
                static_cast<unsigned long long>(a->size()), a->charAt(0), id);
    for (uint32_t cp : Points())
      std::printf(" %x:%d", cp, s.contains(static_cast<UChar32>(cp)));
    std::printf("\n");
    ++operations;
  }
  void Drop(Handle p) { delete p; }

private:
  std::vector<icu::UnicodeSet> classes;
#endif
  static const std::vector<uint32_t> &Points() {
    static const std::vector<uint32_t> p = {
        0,      9,       10,      13,      32,      48,     65,     90,
        95,     97,      98,      122,     0xe9,    0x391,  0x5d0,  0x627,
        0x660,  0x900,   0x2028,  0x2029,  0xd7ff,  0xd800, 0xdfff, 0xe000,
        0xffff, 0x10000, 0x1f1e6, 0x1f600, 0x10ffff};
    return p;
  }
};
int main() {
  decode("", 0);
  for (unsigned i = 0; i < 256; ++i) {
    char s = static_cast<char>(i);
    decode(&s, 1);
  }
  for (unsigned i = 0; i < 65536; ++i) {
    char s[] = {static_cast<char>(i >> 8), static_cast<char>(i)};
    decode(s, 2);
  }
  for (uint32_t cp = 0; cp <= 0x10ffff; ++cp) {
    if (cp >= 0xd800 && cp <= 0xdfff)
      continue;
    auto s = utf8(cp);
    decode(s.data(), s.size());
  }
  uint32_t random = 0x139781;
  for (size_t i = 0; i < 4096; ++i) {
    std::string s;
    for (size_t j = 0; j < i % 32; ++j) {
      random ^= random << 13;
      random ^= random >> 17;
      random ^= random << 5;
      s += static_cast<char>(random);
    }
    decode(s.data(), s.size());
  }
  Sets sets;
  auto a = sets.Range('a', 'a'), b = sets.Range('b', 'z');
  sets.Dump(a);
  sets.Dump(b);
  sets.Add(a, b);
  sets.Dump(a);
  sets.Remove(a, 'b', 'z');
  sets.Dump(a);
  sets.Complement(a);
  sets.Dump(a);
  sets.Complement(a);
  sets.Dump(a);
  sets.AddRange(a, 0xd800, 0xdfff);
  sets.Dump(a);
  sets.Remove(a, 0xd800, 0xdfff);
  sets.Dump(a);
  for (const char *pattern :
       {"[]", "[a]", "[a{bc}]", "[a{bd}]", "[{bc}]", "[{bd}]", "[{bc}{bd}]",
        "[\\uD800-\\uDFFF]", "[:L:]", "[:N:]", "[:White_Space:]",
        "[:RGI_Emoji:]", "[:ASCII:]", "[:Greek:]", "[^[:L:]]"}) {
    auto s = sets.Property(pattern);
    sets.Dump(s);
    sets.Add(a, s);
    sets.Dump(a);
    sets.Drop(s);
  }
  sets.Drop(a);
  sets.Drop(b);
  std::printf(
      "DECODES=%zu SET_OPERATIONS=%zu COMPLETE_ICU_C_API_HOST_NOT_INFERENCE\n",
      decoded, operations);
}
