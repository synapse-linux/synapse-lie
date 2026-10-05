// SPDX-License-Identifier: MIT
// Opaque identity/ID and exception translation only; memo policy/storage is
// C17.
#ifndef LIE_GUFO_SCHEMA_MEMO_HPP
#define LIE_GUFO_SCHEMA_MEMO_HPP
#include "lie/schema_memo.h"
#include <new>
#include <optional>
#include <stdexcept>
namespace lie_gufo {
class SchemaMemo {
  lie_schema_memo *memo_ = nullptr;
  static void check(lie_schema_status rc) {
    if (rc == LIE_SCHEMA_OK)
      return;
    if (rc == LIE_SCHEMA_RESOURCE)
      throw std::bad_alloc();
    if (rc == LIE_SCHEMA_WORK_LIMIT)
      throw std::invalid_argument(
          "JSON Schema: compiled grammar exceeds the rule limit");
    throw std::runtime_error("JSON Schema: invalid C17 reference memo");
  }

public:
  SchemaMemo() {
    lie_schema_memo_description d;
    lie_schema_memo_description_init(&d);
    check(lie_schema_memo_create(&d, &memo_));
  }
  ~SchemaMemo() { lie_schema_memo_release(memo_); }
  SchemaMemo(const SchemaMemo &) = delete;
  SchemaMemo &operator=(const SchemaMemo &) = delete;
  std::optional<uint32_t> get(const void *key) const {
    uint32_t value = 0;
    bool hit = false;
    check(lie_schema_memo_get(memo_, key, &value, &hit));
    return hit ? std::optional<uint32_t>(value) : std::nullopt;
  }
  void assign(const void *key, uint32_t value) {
    check(lie_schema_memo_assign(memo_, key, value));
  }
};
} // namespace lie_gufo
#endif
