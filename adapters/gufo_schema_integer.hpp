// SPDX-License-Identifier: MIT
// Borrowed native JSON view and typed diagnostic translation only.
#ifndef LIE_GUFO_SCHEMA_INTEGER_HPP
#define LIE_GUFO_SCHEMA_INTEGER_HPP
#include "lie/schema_integer.h"
#include "gufo_schema_transform.hpp"
namespace lie_gufo {
inline uint32_t schema_integer(const SchemaValue &schema,
    lie_grammar_builder *builder, uint32_t unrestricted) {
  const auto reader = schema_reader();
  uint32_t result = 0;
  lie_schema_error error{};
  schema_check(lie_schema_integer_compile(&reader, &schema, builder,
                                        unrestricted, &result, &error), error);
  return result;
}
} // namespace lie_gufo
#endif
