// SPDX-License-Identifier: MIT
// Only vocabulary size/layout is option-independent; private request types
// must use the library's selected option. No request-state API is called here.
#undef LIE_C17_SAMPLING
#define LIE_C17_SAMPLING LIE_TEST_HEADER_VIEW
#include "src/core/json_constraint.hpp"
extern "C" size_t LieVocabularyOtherHeaderSize(
    const gufo::sampling::ConstraintVocabulary *vocabulary) {
  return vocabulary->size();
}
