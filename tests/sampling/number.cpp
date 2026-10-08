// SPDX-License-Identifier: MIT
// Complete numeric prefix/value/intersection witnesses; HOST NOT-INFERENCE.
#include "src/core/json_schema_lexeme.hpp"
#include <cstdio>
#include <string>
#include <vector>
using gufo::sampling::JsonSchemaLexeme;
int main() {
  const char *schemas[] = {
    "{}", R"({"minimum":0})", R"({"exclusiveMinimum":0})",
    R"({"maximum":0})", R"({"exclusiveMaximum":0})",
    R"({"minimum":-2,"maximum":2})", R"({"exclusiveMinimum":-2,"exclusiveMaximum":2})",
    R"({"minimum":14,"maximum":15,"multipleOf":0.3})",
    R"({"minimum":-15,"maximum":-14,"multipleOf":0.3})",
    R"({"minimum":-0.3,"maximum":0.3,"multipleOf":0.1})",
    R"({"minimum":0.01,"maximum":0.03,"multipleOf":0.02})",
    R"({"minimum":0.01,"maximum":0.03,"multipleOf":0.05})",
    R"({"minimum":1,"maximum":1})", R"({"minimum":0.1,"maximum":0.1,"multipleOf":0.1})",
    R"({"minimum":1,"exclusiveMinimum":2,"maximum":5,"exclusiveMaximum":4})",
    R"({"minimum":2,"exclusiveMinimum":1,"maximum":4,"exclusiveMaximum":5})",
    R"({"minimum":1,"exclusiveMaximum":1})", R"({"minimum":2,"maximum":1})",
    R"({"multipleOf":0.1})", R"({"multipleOf":0.15})", R"({"multipleOf":0.25})",
    R"({"multipleOf":1.2})", R"({"multipleOf":2.5})", R"({"multipleOf":1e-20})",
    R"({"multipleOf":1e20})", R"({"multipleOf":1e-300})",
    R"({"minimum":1e100,"maximum":2e100,"multipleOf":1e99})",
    R"({"minimum":1e-100,"maximum":2e-100,"multipleOf":1e-101})",
    R"({"minimum":-1e100,"maximum":-1e99,"multipleOf":1e99})",
    R"({"multipleOf":0})", R"({"multipleOf":-1})", R"({"minimum":"x"})"
  };
  std::vector<std::string> texts = {"", "-", "0", "-0", "0.", "-0.0", "0.1", "0.3", "0.30000000000000004",
    "1", "1.", "1.2", "1.50", "-1.5", "2", "-2", "3", "6", "14", "14.4", "14.5", "15", "-14.4", "-14.5",
    "01", "-01", ".1", "1..", "--1", "1e2", "+1", "1-", "1\n", "1e-300",
    std::string(100,'9'), "0."+std::string(100,'0')+"1", std::string(4096,'9'), "1"+std::string(4094,'0')+".", std::string(4097,'9')};
  // Long scalar boundaries are checked directly, not quadratically prefix-expanded.
  size_t policies = 0, prefixes = 0, values = 0, intersections = 0;
  for (bool integer : {false,true}) for (size_t si=0; si<std::size(schemas); ++si) {
    printf("schema=%zu integer=%d\n",si,integer);
    std::shared_ptr<const JsonSchemaLexeme> lexeme;
    try { lexeme = JsonSchemaLexeme::Number(gufo::json::parse(schemas[si]),integer); }
    catch (const std::exception &e) { printf("refusal=%s\n",e.what()); continue; }
    ++policies;
    for (size_t ti=0; ti<texts.size(); ++ti) {
      const auto &t=texts[ti]; size_t begin=t.size()>256?t.size():0;
      for (size_t n=begin;n<=t.size();++n) {
        auto m=lexeme->Check(std::string_view(t.data(),n));
        printf("text=%zu prefix=%zu match=%d,%d\n",ti,n,m.prefix,m.complete); ++prefixes;
      }
    }
    for (const char *s : {"0", "-0.0", "0.3", "3e-1", "1.2e1", "1e100", "1e-100", "-1e100", "1e-300", "true", "null"}) {
      printf("value=%s accepted=%d\n",s,lexeme->AcceptValue(gufo::json::parse(s))); ++values;
    }
  }
  const char *steps[] = {"0.1","0.2","0.3","0.15","0.25","1.2","2.5","1e-100","1e100","1e-300","1e300","0","-1","\"x\""};
  for (auto a:steps) for (auto b:steps) {
    printf("intersect=%s,%s\n",a,b);
    try { auto v=JsonSchemaLexeme::IntersectMultipleOf(gufo::json::parse(a),gufo::json::parse(b)); printf("lcm=%s\n",v.dump().c_str()); }
    catch (const std::exception &e) { printf("refusal=%s\n",e.what()); }
    ++intersections;
  }
  printf("POLICIES=%zu PREFIXES=%zu VALUES=%zu INTERSECTIONS=%zu COMPLETE_NUMBER_HOST_NOT_INFERENCE\n",policies,prefixes,values,intersections);
}
