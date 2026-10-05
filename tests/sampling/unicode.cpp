// SPDX-License-Identifier: MIT
// Complete string state/mask-key and Unicode-DFA witnesses; HOST NOT-INFERENCE.
#include "src/core/json_schema_lexeme.hpp"
#include "src/core/json_schema_regex.hpp"
#include <cstdio>
#include <string>
#include <vector>
using gufo::sampling::JsonSchemaLexeme;
using gufo::sampling::JsonSchemaRegex;
static void state(const std::string &s) {
  std::printf("state=");for (unsigned char b:s) std::printf("%02x",unsigned(b));std::printf("\n");
}
int main() {
  const char *schemas[]={"{}",R"({"minLength":3})",R"({"maxLength":1})",R"({"minLength":2,"maxLength":4})",
    R"({"minLength":0,"maxLength":0})",R"({"minLength":4,"maxLength":2})",
    R"({"pattern":"^(a|é|😀){1,3}$"})",R"({"pattern":"^😀$"})",R"({"pattern":"^[\\u0000-\\u007f]{1,2}$"})",
    R"({"pattern":"^(ab)*$","minLength":1000000,"maxLength":1000001})",
    R"({"pattern":"^a$","minLength":2})",R"({"pattern":"\\bcat\\b"})",R"({"pattern":"(?=ab)a.*"})",
    R"({"format":"date"})",R"({"format":"ipv4"})",R"({"format":"email"})",R"({"format":"hostname","minLength":254})",
    R"({"pattern":"["})",R"({"minLength":-1})",R"({"maxLength":1.5})"};
  std::vector<std::string> texts={"", "\"", "\"\"", "\"a\"", "\"ab\"", "\"aaé\"", "\"😀\"", "\"é😀\"",
    R"("\u00e9")",R"("\uD83D\uDE00")",R"("\uDBFF\uDFFF")",R"("\uD800\uDC00")",R"("\uDE00")",R"("\uD800")",
    R"("\uD800\uDBFF")",R"("\u0000")",R"("\n\t\/\\\"")",R"("\x")", "\"\xc0\x80\"", "\"\xed\xa0\x80\"",
    "\"\xf0\x80\x80\x80\"", "\"\xf4\x90\x80\x80\"", "\"cat!\"", "\"cats\"", "\"2026-10-05\"", "\"127.0.0.1\"",
    "\"a@b\"", "\""+std::string(40,'a')+"\""};
  size_t policies=0,transitions=0,canonicals=0,branches=0,queries=0;
  for (size_t si=0;si<std::size(schemas);++si) {
    std::printf("schema=%zu\n",si);std::shared_ptr<const JsonSchemaLexeme> lexeme;
    try {lexeme=JsonSchemaLexeme::String(gufo::json::parse(schemas[si]));}
    catch(const std::exception &e) {std::printf("refusal=%s\n",e.what());continue;}
    ++policies;
    for (size_t ti=0;ti<texts.size();++ti) {
      std::string s;bool prefix=true;std::printf("text=%zu\n",ti);
      for (size_t i=0;i<texts[ti].size()&&prefix;++i) {
        unsigned char b=texts[ti][i];auto m=lexeme->Advance(s,b);
        std::printf("byte=%u match=%d,%d\n",unsigned(b),m.prefix,m.complete);state(s);++transitions;prefix=m.prefix;
        for (size_t window:{0u,1u,4u,32u,1000000u}) {
          auto key=s;lexeme->CanonicalMaskState(key,window);std::printf("window=%zu ",window);state(key);++canonicals;
        }
        if (m.prefix) for (unsigned next=0;next<256;++next) {
          auto branch=s;auto bm=lexeme->Advance(branch,static_cast<unsigned char>(next));
          std::printf("next=%u match=%d,%d ",next,bm.prefix,bm.complete);state(branch);++branches;
        }
      }
      auto check=lexeme->Check(texts[ti]);std::printf("check=%d,%d\n",check.prefix,check.complete);
    }
  }
  const char *patterns[]={"", "^(ab)*$", "^a{2,4}$", "^(a|é|😀){1,3}$", "(?=ab)a.*", "\\bcat\\b"};
  for (auto pattern:patterns) {
    std::vector<std::string> expressions;if (*pattern) expressions.push_back(pattern);
    auto r=JsonSchemaRegex::Compile(expressions,128);std::printf("regex=%s suffix=%u\n",pattern,r->MaximumSuffix());
    uint32_t s=r->Start();
    for (uint32_t cp:{uint32_t('a'),uint32_t('b'),0xe9u,0x1f600u,uint32_t('c'),uint32_t('a'),uint32_t('t')}) {
      std::printf("dfa=%u accepting=%d\n",s,r->Accepting(s));
      for (uint32_t min:{0u,1u,2u,3u,17u,1000000u}) for (uint32_t extra:{0u,1u,5u}) {
        std::printf("finish=%u,%u,%d advance=%d\n",min,min+extra,r->CanFinish(s,min,min+extra),r->CanAdvance(s,0,0x10ffff,min,min+extra));++queries;
      }
      s=r->Advance(s,cp);
    }
  }
  std::printf("POLICIES=%zu TRANSITIONS=%zu CANONICALS=%zu BYTE_BRANCHES=%zu DFA_QUERIES=%zu COMPLETE_UNICODE_HOST_NOT_INFERENCE\n",policies,transitions,canonicals,branches,queries);
}
