// SPDX-License-Identifier: MIT
// Opposite-option header consumer; synthetic host, NOT GPU build/link qualification.
#undef LIE_C17_SAMPLING
#define LIE_C17_SAMPLING LIE_TEST_HEADER_VIEW
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <cstdio>
using namespace gufo::sampling;
int main() {
  auto vocabulary=std::make_shared<ConstraintVocabulary>(2,[](uint32_t token){
    return ConstraintVocabulary::Piece{token?"{}":"",!token};
  });
  assert(vocabulary->size()==2);
  TokenConstraint c;c.vocabulary=vocabulary;c.grammar=JsonConstraint::Object();
  auto state=c.grammar->Start();auto mask=c.Allowed(state);
  assert(mask->size()==2 && (*mask)[0]==0 && (*mask)[1]==1);
  auto end=vocabulary->Accept(*c.grammar,state,1);assert(c.grammar->Complete(end));
  auto final=c.Allowed(end);assert((*final)[0]==1 && (*final)[1]==0);
  std::printf("Opposite-option vocabulary header view=%d PASS; HOST_NOT_INFERENCE\n",LIE_TEST_HEADER_VIEW);
}
