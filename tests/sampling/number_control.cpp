// SPDX-License-Identifier: MIT
// Complete three-arm numeric leaf decisions and typed refusal witnesses.
#include "src/core/json.hpp"
#include "src/core/json_schema_lexeme.hpp"
#include "src/core/json_constraint.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
#if LIE_C17_SAMPLING
#include "gufo_schema_number.hpp"
#endif
using gufo::json::Value;
using gufo::sampling::JsonSchemaLexeme;
static size_t cases;
template<class F> static void witness(F f) {
  std::cout << "case=" << cases++ << ' ';
  try { f(); }
  catch (const gufo::sampling::JsonSchemaEmpty &e) { std::cout << "EMPTY " << e.what(); }
  catch (const std::invalid_argument &e) { std::cout << "INVALID " << e.what(); }
  catch (const std::runtime_error &e) { std::cout << "RUNTIME " << e.what(); }
  std::cout << '\n';
}
int main() {
  const double inf=std::numeric_limits<double>::infinity();
  const double nan=std::numeric_limits<double>::quiet_NaN();
  std::vector<Value> values={Value(),Value(true),Value("0.3"),Value::array(),Value::object()};
  for (double v : {0., -0., 0.1, -0.1, 0.15, 0.2, 0.3, 0.6, 1., -1.,
      1.2, 2., 3., 9007199254740991., 9007199254740992., 1000000000000000128.,
      1e-100, 1e100, std::numeric_limits<double>::denorm_min(),
      std::numeric_limits<double>::min(), std::numeric_limits<double>::max(),
      std::nextafter(0.3,0.), std::nextafter(0.3,1.), inf, -inf, nan})
    values.emplace_back(v);
  for (bool integer : {false,true}) {
    for (const char *key : {"minimum","maximum","exclusiveMinimum","exclusiveMaximum","multipleOf"})
      for (const auto &value : values) {
        auto schema=Value::object(); schema[key]=value;
        witness([&] {
          const auto policy=JsonSchemaLexeme::Number(schema,integer);
          std::cout << "POLICY ";
          for (const auto &probe : values) {
            try { std::cout << policy->AcceptValue(probe) << ','; }
            catch (const std::invalid_argument &e) { std::cout << "INVALID(" << e.what() << "),"; }
          }
        });
      }
    // Ordered failures are independent of input object member order.
    auto schema=Value::object(); schema["multipleOf"]=0.; schema["maximum"]="bad";
    schema["minimum"]=inf;
    witness([&] { (void)JsonSchemaLexeme::Number(schema,integer); std::cout << "OK"; });
    schema["minimum"]=0.;
    witness([&] { (void)JsonSchemaLexeme::Number(schema,integer); std::cout << "OK"; });
  }
  std::vector<Value> steps={Value(),Value(true),Value("x"),Value(0.),Value(-0.),
    Value(-1.),Value(inf),Value(-inf),Value(nan),Value(0.1),Value(0.15),Value(0.2),
    Value(0.3),Value(1.2),Value(9007199254740991.),Value(9007199254740992.)};
  for (const auto &a : steps) for (const auto &b : steps)
    witness([&] { std::cout << JsonSchemaLexeme::IntersectMultipleOf(a,b).dump(); });
  // Literal numeric construction must keep the original grammar and state IDs.
  for (double v : {-0.,0.1,0.3,1.2,9007199254740992.,1000000000000000128.,1e-100,1e100}) {
    auto root=Value::object(); root["type"]="object"; root["properties"]=Value::object();
    auto leaf=Value::object(); leaf["type"]="number"; leaf["const"]=v;
    root["properties"]["v"]=leaf; root["required"]=Value::array();
    root["required"].push_back("v"); root["additionalProperties"]=false;
    const auto before=root.dump();
    witness([&] {
      const auto grammar=gufo::sampling::JsonConstraint::Compile(root,false);
      const std::string text=std::string("{\"v\":")+Value(v).dump()+"}";
      auto state=grammar->Start();
      for (unsigned char byte : text) {
        state=grammar->Advance(state,byte);
        for (const auto &frame : state) {
          std::cout << '[';
          for (auto symbol : frame.symbols) std::cout << symbol << ',';
          std::cout << "]";
          for (unsigned char c : frame.lexeme) std::cout << unsigned(c) << ',';
        }
        std::cout << ';';
      }
      assert(grammar->Complete(state)); std::cout << "COMPLETE";
    });
    assert(root.dump()==before);
  }
#if LIE_C17_SAMPLING
  // The private ABI retains exceptions from its codec without crossing C.
  for (unsigned kind=0;kind<4;++kind) {
    lie_gufo::SchemaNumber number; auto d=number.description();
    assert(!d.serialize && !d.parse && !d.conversion_context);
    struct Hook { lie_gufo::SchemaNumber *number; unsigned kind; } hook{&number,kind};
    d.conversion_context=&hook;
    d.serialize=[](void *p,double,char *,size_t,size_t *) noexcept {
      auto &h=*static_cast<Hook *>(p);
      return h.number->invoke([&](auto &) {
        if (h.kind==0) throw std::bad_alloc();
        if (h.kind==1) throw gufo::sampling::JsonSchemaEmpty("numeric sentinel");
        if (h.kind==2) throw std::runtime_error("numeric sentinel");
        throw std::invalid_argument("numeric sentinel");
      });
    };
    Value schema=Value::object(); schema["minimum"]=0.;
    lie_number_policy *out=nullptr; lie_schema_error error{};
    const auto rc=lie_schema_number_create(&d,&schema,false,&out,&error);
    assert(rc==(kind==1 ? LIE_SCHEMA_EMPTY : LIE_SCHEMA_CALLBACK) && !out);
    unsigned caught=999;
    try { number.check(rc,error); }
    catch (const std::bad_alloc &) { caught=0; }
    catch (const gufo::sampling::JsonSchemaEmpty &e) { caught=1; assert(std::string(e.what())=="numeric sentinel"); }
    catch (const std::invalid_argument &e) { caught=3; assert(std::string(e.what())=="numeric sentinel"); }
    catch (const std::runtime_error &e) { caught=2; assert(std::string(e.what())=="numeric sentinel"); }
    assert(caught==kind);
  }
  {
    lie_gufo::SchemaNumber number;
    bool caught=false;
    try { (void)number.intersect(Value(1e308),Value(0.3)); }
    catch (const std::runtime_error &e) {
      assert(std::string(e.what())=="JSON parse error: bad number"); caught=true;
    }
    assert(caught);
  }
#endif
  std::cout << "NUMERIC_CONTROL_CASES=" << cases << " HOST_NOT_INFERENCE\n";
}
