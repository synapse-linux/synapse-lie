/* SPDX-License-Identifier: MIT */
/* Independent exact bit vectors, capacity/refusal and decimal midpoint oracles. */
#include "lie/binary64.h"
#include <assert.h>
#include <fenv.h>
#include <stdio.h>
#include <string.h>
static uint64_t bits(double d) { uint64_t u; memcpy(&u,&d,8);return u; }
static double value(uint64_t u) { double d;memcpy(&d,&u,8);return d; }
static size_t checks,refusals;
static void parse(const char *text,uint64_t expected) {
 double out=123;
 assert(lie_binary64_parse(text,strlen(text),NULL,&out)==LIE_BINARY64_OK);
 assert(bits(out)==expected);++checks;
}
static void bad(const char *text,lie_binary64_status expected) {
 double out=123;
 assert(lie_binary64_parse(text,strlen(text),NULL,&out)==expected && out==123);++refusals;
}
static void halfway(void) {
 const char *mid="1.00000000000000011102230246251565404236316680908203125";
 parse(mid,UINT64_C(0x3ff0000000000000));
 char longtext[20000];size_t n=strlen(mid);memcpy(longtext,mid,n);
 memset(longtext+n,'0',17000);longtext[n+17000]=0;
 parse(longtext,UINT64_C(0x3ff0000000000000));
 longtext[n+16999]='1';parse(longtext,UINT64_C(0x3ff0000000000001));
 /* Base10 school multiplication is independent of the parser's base2 limbs.
  * Half the least subnormal is exactly5^1075 *10^-1075. */
 unsigned char digits[1100]={1};size_t count=1;
 for(unsigned k=0;k<1075;++k){unsigned carry=0;for(size_t i=0;i<count;++i){unsigned x=digits[i]*5+carry;digits[i]=(unsigned char)(x%10);carry=x/10;}while(carry){digits[count++]=(unsigned char)(carry%10);carry/=10;}}
 char sub[4096];size_t at=0;sub[at++]='0';sub[at++]='.';
 for(size_t i=count;i<1075;++i)sub[at++]='0';
 for(size_t i=count;i--;)sub[at++]=(char)('0'+digits[i]);
 sub[at]=0;
 bad(sub,LIE_BINARY64_RANGE);
 memset(sub+at,'0',1800);sub[at+1800]=0;bad(sub,LIE_BINARY64_RANGE);
 sub[at+1799]='1';parse(sub,1);
 parse("1.00000000000000033306690738754696212708950042724609375",UINT64_C(0x3ff0000000000002));
}
int main(void) {
 const struct { const char *text;uint64_t u; } vectors[]={
  {"0",0},{"-0",UINT64_C(0x8000000000000000)}, {"1",UINT64_C(0x3ff0000000000000)},
  {"-1",UINT64_C(0xbff0000000000000)},{"0.1",UINT64_C(0x3fb999999999999a)},
  {"0.3",UINT64_C(0x3fd3333333333333)}, {"5e-324",1},
  {"2.2250738585072014e-308",UINT64_C(0x0010000000000000)},
  {"1.7976931348623157e+308",UINT64_C(0x7fefffffffffffff)},
  {"9007199254740992",UINT64_C(0x4340000000000000)},
  {"1000000000000000128",UINT64_C(0x43abc16d674ec801)}};
 for(size_t i=0;i<sizeof(vectors)/sizeof(*vectors);++i){
  parse(vectors[i].text,vectors[i].u);
  char text[64];memset(text,0xa5,64);size_t length=999;
  assert(lie_binary64_format(value(vectors[i].u),text,sizeof(text),&length)==LIE_BINARY64_OK);
  assert(length==strlen(vectors[i].text)&&!memcmp(text,vectors[i].text,length));++checks;
  for(size_t capacity=0;capacity<length;++capacity){char storage[64],before[64];memset(storage,0xa5,64);memcpy(before,storage,64);size_t bytes=777;
   assert(lie_binary64_format(value(vectors[i].u),storage,capacity,&bytes)==LIE_BINARY64_CAPACITY);
   assert(bytes==777&&!memcmp(storage,before,64));++refusals;
  }
 }
 parse(" \n\t-0.000e9999999999999999999999999999999\r ",UINT64_C(0x8000000000000000));
 parse("1.0000000000000000000000000000000000000000000000000000000000000000000000000000000000",UINT64_C(0x3ff0000000000000));
 for(size_t i=0;i<10;++i){const char *s[]={"+1","01","1.",".1","--1","1e","1e+","1e-","NaN","1 2"};bad(s[i],LIE_BINARY64_INVALID);}
 bad("1e9999999999999999999999999999999",LIE_BINARY64_RANGE);
 bad("1e-9999999999999999999999999999999",LIE_BINARY64_RANGE);
 bad("1e-400",LIE_BINARY64_RANGE);bad("1.7976931348623159e308",LIE_BINARY64_RANGE);
 halfway();
 int original=fegetround();
 for(size_t i=0;i<4;++i){int modes[]={FE_TONEAREST,FE_UPWARD,FE_DOWNWARD,FE_TOWARDZERO};assert(fesetround(modes[i])==0);
  for(size_t j=0;j<sizeof(vectors)/sizeof(*vectors);++j)parse(vectors[j].text,vectors[j].u);
  char text[64];size_t length=0;assert(lie_binary64_format(0.1,text,64,&length)==LIE_BINARY64_OK&&!memcmp(text,"0.1",3)&&length==3);++checks;
  assert(fegetround()==modes[i]);
 }
 assert(fesetround(original)==0);
 lie_binary64_limits limits;lie_binary64_limits_init(&limits);double out=123;
 limits.max_text_bytes=1;assert(lie_binary64_parse("0.3",3,&limits,&out)==LIE_BINARY64_TEXT_LIMIT&&out==123);++refusals;
 lie_binary64_limits_init(&limits);limits.max_work=1;assert(lie_binary64_parse("0.3",3,&limits,&out)==LIE_BINARY64_WORK_LIMIT&&out==123);++refusals;
 lie_binary64_limits_init(&limits);limits.max_work=60;
 const char *complex="1.00000000000000011102230246251565404236316680908203125";
 assert(lie_binary64_parse(complex,strlen(complex),&limits,&out)==LIE_BINARY64_WORK_LIMIT&&out==123);++refusals;
 union {double number;char text[64];size_t length;} alias;strcpy(alias.text,"0.3");unsigned char copy[sizeof(alias)];memcpy(copy,&alias,sizeof(alias));
 assert(lie_binary64_parse(alias.text,3,NULL,&alias.number)==LIE_BINARY64_INVALID&&!memcmp(copy,&alias,sizeof(alias)));++refusals;
 assert(lie_binary64_format(0.3,alias.text,64,&alias.length)==LIE_BINARY64_INVALID&&!memcmp(copy,&alias,sizeof(alias)));++refusals;
 char text[64];memset(text,0xa5,64);size_t bytes=333;
 assert(lie_binary64_format(value(UINT64_C(0x7ff0000000000000)),text,64,&bytes)==LIE_BINARY64_INVALID&&bytes==333);++refusals;
 assert(lie_binary64_format(value(UINT64_C(0x7ff8000000000001)),text,64,&bytes)==LIE_BINARY64_INVALID&&bytes==333);++refusals;
 printf("C17 binary64: %zu independent bit/rounding oracles, %zu refusals; HOST_NOT_INFERENCE\n",checks,refusals);
}
