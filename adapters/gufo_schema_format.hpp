// SPDX-License-Identifier: MIT
// Private byte/string/JSON staging and typed error translation only.
#ifndef LIE_GUFO_SCHEMA_FORMAT_HPP
#define LIE_GUFO_SCHEMA_FORMAT_HPP
#include "lie/schema_format.h"
#include "gufo_schema_transform.hpp"
#include <array>
namespace lie_gufo {
inline std::string format_pattern(std::string_view format) {
  std::array<char,LIE_SCHEMA_FORMAT_PATTERN_CAPACITY> text;
  size_t size=0; lie_schema_error e{};
  schema_check(lie_schema_format_pattern({format.data(),format.size()},
    text.data(),text.size(),&size,&e),e);
  return std::string(text.data(),size);
}
inline SchemaValue format_schema(std::string_view format) {
  SchemaArena arena; const auto d=arena.description();
  lie_schema_node out=nullptr; lie_schema_error e{};
  arena.check(lie_schema_format_expand(&d,{format.data(),format.size()},&out,&e),e);
  return arena.take(out);
}
} // namespace lie_gufo
#endif
