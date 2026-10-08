// SPDX-License-Identifier: MIT
// Independent MPFR nearest-bit oracle; QA only, never linked into products.
#include "lie/binary64.h"
#include <mpfr.h>
#include <bit>
#include <cassert>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
static size_t checks;
static bool codec_active;
static size_t codec_heap_calls;
extern "C" void *__real_malloc(size_t);
extern "C" void *__real_calloc(size_t,size_t);
extern "C" void *__real_realloc(void *,size_t);
extern "C" void __real_free(void *);
extern "C" void *__wrap_malloc(size_t n){if(codec_active)++codec_heap_calls;return __real_malloc(n);}
extern "C" void *__wrap_calloc(size_t n,size_t w){if(codec_active)++codec_heap_calls;return __real_calloc(n,w);}
extern "C" void *__wrap_realloc(void *p,size_t n){if(codec_active)++codec_heap_calls;return __real_realloc(p,n);}
extern "C" void __wrap_free(void *p){if(codec_active)++codec_heap_calls;__real_free(p);}
static uint64_t seed=0xd9b4fa78a9630351ULL;
static uint64_t next_random(){seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;return seed;}
static void oracle(const std::string &s){
 mpfr_t exact;mpfr_init2(exact,mpfr_prec_t(s.size()*4+4096));
 assert(mpfr_set_str(exact,s.c_str(),10,MPFR_RNDN)==0);
 double reference=mpfr_get_d(exact,MPFR_RNDN),actual=123;
 bool range=!std::isfinite(reference)||(reference==0&&!mpfr_zero_p(exact));
 codec_active=true;auto rc=lie_binary64_parse(s.data(),s.size(),nullptr,&actual);codec_active=false;
 if(range){if(rc!=LIE_BINARY64_RANGE||actual!=123){std::printf("RANGE mismatch len=%zu status=%d\n",s.size(),int(rc));assert(false);}}
 else if(rc!=LIE_BINARY64_OK||std::bit_cast<uint64_t>(reference)!=std::bit_cast<uint64_t>(actual)){std::printf("BIT mismatch len=%zu ref=%016llx actual=%016llx rc=%d text=%.100s\n",s.size(),(unsigned long long)std::bit_cast<uint64_t>(reference),(unsigned long long)std::bit_cast<uint64_t>(actual),int(rc),s.c_str());assert(false);}
 mpfr_clear(exact);++checks;
}
int main(){
 for(unsigned i=0;i<12000;++i){size_t count=i%4==0?1+next_random()%1100:1+next_random()%40;std::string s=next_random()%2?"-":"";s+=char('1'+next_random()%9);if(count>1){s+='.';for(size_t k=1;k<count;++k)s+=char('0'+next_random()%10);}s+='e';s+=std::to_string(int(next_random()%660)-340);oracle(s);}
 for(unsigned i=0;i<600;++i){uint64_t u=next_random()&0x7fefffffffffffffULL;if(!u)u=1;double a=std::bit_cast<double>(u),b=std::nextafter(a,INFINITY);if(!std::isfinite(b))continue;
  mpfr_t left,right,mid;mpfr_inits2(4096,left,right,mid,(mpfr_ptr)nullptr);mpfr_set_d(left,a,MPFR_RNDN);mpfr_set_d(right,b,MPFR_RNDN);mpfr_add(mid,left,right,MPFR_RNDN);mpfr_div_2ui(mid,mid,1,MPFR_RNDN);
  char *text=nullptr;assert(mpfr_asprintf(&text,"%.1200Rf",mid)>0);std::string s=text;mpfr_free_str(text);oracle(s);oracle(s+std::string(1200,'0')+"1");oracle("-"+s+std::string(1200,'0')+"1");
  mpfr_clears(left,right,mid,(mpfr_ptr)nullptr);
 }
 for(unsigned i=0;i<1000000;++i){uint64_t u=next_random();double d=std::bit_cast<double>(u);if(!std::isfinite(d))continue;
  char expected[64],actual[64];auto ref=std::to_chars(expected,expected+64,d);size_t bytes=0;
  codec_active=true;auto formatted=lie_binary64_format(d,actual,64,&bytes);codec_active=false;
  assert(formatted==LIE_BINARY64_OK&&bytes==size_t(ref.ptr-expected)&&std::string(actual,bytes)==std::string(expected,ref.ptr));
  double parsed=0;codec_active=true;auto parsed_status=lie_binary64_parse(actual,bytes,nullptr,&parsed);codec_active=false;
  assert(parsed_status==LIE_BINARY64_OK&&std::bit_cast<uint64_t>(parsed)==u);++checks;
 }
 mpfr_free_cache();assert(codec_heap_calls==0);
 std::printf("BINARY64_ORACLE CHECKS=%zu MPFR=%s CODEC_HEAP_CALLS=%zu HOST_NOT_INFERENCE\n",checks,mpfr_get_version(),codec_heap_calls);
}
