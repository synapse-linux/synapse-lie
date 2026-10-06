/* SPDX-License-Identifier: MIT */
/* Independent event/UTF8/ordering oracles and exhaustive owned failure points. */
#include "lie/json_parse.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
  size_t calls, fail_at, live, peak, events, refuse_event;
  struct { void *data;size_t bytes; } allocations[1024];
  lie_json_event recorded[1024];
  char text[32768];size_t text_bytes;
} fixture;
static size_t checks, allocation_refusals, callback_refusals;
static void *allocate(void *context,size_t bytes) {
  fixture *f=context;if (++f->calls==f->fail_at) return NULL;
  void *out=malloc(bytes);assert(out);
  for(size_t i=0;i<1024;++i) if(!f->allocations[i].data) {
    f->allocations[i].data=out;f->allocations[i].bytes=bytes;f->live+=bytes;
    if(f->live>f->peak)f->peak=f->live;
    return out;
  }
  abort();
}
static void release(void *context,void *data) {
  fixture *f=context;
  for(size_t i=0;i<1024;++i)if(f->allocations[i].data==data) {
    f->live-=f->allocations[i].bytes;f->allocations[i].data=NULL;free(data);return;
  }
  abort();
}
static bool emit(void *context,const lie_json_event *event) {
  fixture *f=context;assert(f->events<1024);
  if(++f->events==f->refuse_event)return false;
  lie_json_event *copy=&f->recorded[f->events-1];*copy=*event;
  if(event->text_bytes) {
    assert(event->text_bytes<=sizeof(f->text)-f->text_bytes);
    memcpy(f->text+f->text_bytes,event->text,event->text_bytes);
    copy->text=f->text+f->text_bytes;f->text_bytes+=event->text_bytes;
  }
  return true;
}
static lie_json_parse_status parse(fixture *f,const char *text,size_t bytes,
                                 lie_json_parse_description *d,lie_json_parse_error *error,
                                 lie_json_parse_info *info) {
  d->allocator=(lie_grammar_allocator){f,allocate,release};
  lie_json_sink sink={f,emit};
  lie_json_parse_status rc=lie_json_parse_events(text,bytes,d,&sink,error,info);
  assert(f->live==0 && info->allocations==f->calls && info->peak_owned_bytes==f->peak);
  ++checks;return rc;
}
static void bad(const char *text,const char *reason) {
  fixture f={0};lie_json_parse_description d;lie_json_parse_description_init(&d);
  lie_json_parse_error e={0};lie_json_parse_info info={0};
  assert(parse(&f,text,strlen(text),&d,&e,&info)==LIE_JSON_PARSE_SYNTAX);
  assert(!strcmp(e.message,reason) && e.offset<=strlen(text));
}
static void events(void) {
  const char *text="{\"a\":[true,null,-0,\"z\"],\"\\u0062\":{\"\":1}}";
  const lie_json_event_kind kinds[]={LIE_JSON_BEGIN_OBJECT,LIE_JSON_KEY,LIE_JSON_BEGIN_ARRAY,
    LIE_JSON_BOOL,LIE_JSON_NULL,LIE_JSON_NUMBER,LIE_JSON_STRING,LIE_JSON_END_ARRAY,
    LIE_JSON_KEY,LIE_JSON_BEGIN_OBJECT,LIE_JSON_KEY,LIE_JSON_NUMBER,
    LIE_JSON_END_OBJECT,LIE_JSON_END_OBJECT};
  fixture f={0};lie_json_parse_description d;lie_json_parse_description_init(&d);
  lie_json_parse_error e={0};lie_json_parse_info info={0};
  assert(parse(&f,text,strlen(text),&d,&e,&info)==LIE_JSON_PARSE_OK);
  assert(f.events==sizeof(kinds)/sizeof(*kinds) && info.input_consumed==strlen(text));
  for(size_t i=0;i<f.events;++i)assert(f.recorded[i].kind==kinds[i]);
  assert(f.recorded[1].text_bytes==1 && f.recorded[1].text[0]=='a');
  assert(f.recorded[8].text_bytes==1 && f.recorded[8].text[0]=='b');
  assert(f.recorded[10].text_bytes==0 && f.recorded[3].boolean);
  uint64_t bits;memcpy(&bits,&f.recorded[5].number,8);assert(bits==UINT64_C(0x8000000000000000));
  assert(f.recorded[11].number==1);
}
static void utf8(void) {
  const struct { const char *input,*output;size_t bytes; } cases[]={
    {"\"\\u0000\"","\0",1},{"\"\\u007f\"","\x7f",1},
    {"\"\\u0080\"","\xc2\x80",2},{"\"\\u07ff\"","\xdf\xbf",2},
    {"\"\\u0800\"","\xe0\xa0\x80",3},{"\"\\ud7ff\"","\xed\x9f\xbf",3},
    {"\"\\ue000\"","\xee\x80\x80",3},{"\"\\uffff\"","\xef\xbf\xbf",3},
    {"\"\\ud800\\udc00\"","\xf0\x90\x80\x80",4},
    {"\"\\udbff\\udfff\"","\xf4\x8f\xbf\xbf",4},
    {"\"\\b\\f\\n\\r\\t\\/\\\\\\\"\"","\b\f\n\r\t/\\\"",8}};
  for(size_t i=0;i<sizeof(cases)/sizeof(*cases);++i) {
    fixture f={0};lie_json_parse_description d;lie_json_parse_description_init(&d);
    lie_json_parse_error e={0};lie_json_parse_info info={0};
    assert(parse(&f,cases[i].input,strlen(cases[i].input),&d,&e,&info)==LIE_JSON_PARSE_OK);
    assert(f.events==1 && f.recorded[0].kind==LIE_JSON_STRING);
    assert(f.recorded[0].text_bytes==cases[i].bytes && !memcmp(f.recorded[0].text,cases[i].output,cases[i].bytes));
    char raw[16]={'"'};memcpy(raw+1,cases[i].output,cases[i].bytes);raw[cases[i].bytes+1]='"';
    if(i<10 && i!=0) {
      memset(&f,0,sizeof(f));assert(parse(&f,raw,cases[i].bytes+2,&d,&e,&info)==LIE_JSON_PARSE_OK);
      assert(info.allocations==0 && !memcmp(f.recorded[0].text,cases[i].output,cases[i].bytes));
    }
  }
  for(unsigned byte=0;byte<256;++byte) {
    char raw[3]={'"',(char)byte,'"'};
    fixture f={0};lie_json_parse_description d;lie_json_parse_description_init(&d);
    lie_json_parse_error e={0};lie_json_parse_info info={0};
    bool valid=byte>=32 && byte<128 && byte!='"' && byte!='\\';
    assert(parse(&f,raw,3,&d,&e,&info)==(valid ? LIE_JSON_PARSE_OK : LIE_JSON_PARSE_SYNTAX));
  }
  bad("\"\xc0\x80\"","invalid UTF-8");bad("\"\xe0\x80\x80\"","invalid UTF-8");
  bad("\"\xed\xa0\x80\"","invalid UTF-8");bad("\"\xf0\x80\x80\x80\"","invalid UTF-8");
  bad("\"\xf4\x90\x80\x80\"","invalid UTF-8");
}
static void syntax_oracles(void) {
  const struct { const char *input,*reason; } cases[]={
    {"","unexpected end of input"},{" ","unexpected end of input"},{"[","unexpected end of input"},
    {"{","expected object key string"},{"{0:1}","expected object key string"},
    {"{\"a\" 1}","expected ':' after key"},{"{\"a\":1","unterminated object"},
    {"[1","unterminated array"},{"[1 2]","expected ',' or ']' in array"},
    {"{\"a\":1 \"b\":2}","expected ',' or '}' in object"},{"[1,]","bad number"},
    {"{\"a\":1,}","expected object key string"},{"true false","trailing input"},
    {"truex","trailing input"},{"False","bad number"},{"tru","bad literal"},
    {"falze","bad literal"},{"nill","bad literal"},{"+1","bad number"},
    {"01","bad number"},{"-","bad number"},{"1.","bad number"},{"1e+","bad number"},
    {"1e400","bad number"},{"1e-400","bad number"},{"\"","unterminated string"},
    {"\"\\","bad escape"},{"\"\\v\"","bad escape"},{"\"\\u0\"","bad \\u"},
    {"\"\\u00xz\"","bad hex"},{"\"\\ud800\"","unpaired high surrogate"},
    {"\"\\ud800\\u0000\"","invalid low surrogate"},{"\"\\udfff\"","unpaired low surrogate"},
    {"{\"a\":1,\"\\u0061\":BAD}","duplicate object key"},
    {"{\"\\u0000\":1,\"\\u0000\":0}","duplicate object key"}};
  for(size_t i=0;i<sizeof(cases)/sizeof(*cases);++i)bad(cases[i].input,cases[i].reason);
  fixture f={0};lie_json_parse_description d;lie_json_parse_description_init(&d);
  lie_json_parse_error e={0};lie_json_parse_info info={0};
  const char *scopes="{\"a\":{\"a\":0},\"b\":{\"a\":1}}";
  assert(parse(&f,scopes,strlen(scopes),&d,&e,&info)==LIE_JSON_PARSE_OK);
  char depth[258];memset(depth,'[',128);memset(depth+128,']',128);
  memset(&f,0,sizeof(f));assert(parse(&f,depth,256,&d,&e,&info)==LIE_JSON_PARSE_OK && info.allocations==0);
  memset(depth,'[',129);memset(depth+129,']',129);
  memset(&f,0,sizeof(f));assert(parse(&f,depth,258,&d,&e,&info)==LIE_JSON_PARSE_SYNTAX && !strcmp(e.message,"maximum nesting depth exceeded"));
}
static void failures(void) {
  char input[40000];size_t at=0;input[at++]='{';
  for(unsigned i=0;i<120;++i) {
    int n=snprintf(input+at,sizeof(input)-at,"%s\"key\\u0061%u\":{\"\\u0000\":\"%0100u\\n%0100u\"}",i ? "," : "",i,i,i);
    assert(n>0 && (size_t)n<sizeof(input)-at);at+=(size_t)n;
  }
  input[at++]='}';
  fixture baseline={0};lie_json_parse_description d;lie_json_parse_description_init(&d);
  lie_json_parse_error e={0};lie_json_parse_info info={0};
  assert(parse(&baseline,input,at,&d,&e,&info)==LIE_JSON_PARSE_OK);
  for(size_t i=1;i<=baseline.calls;++i) {
    fixture f={.fail_at=i};
    assert(parse(&f,input,at,&d,&e,&info)==LIE_JSON_PARSE_RESOURCE);++allocation_refusals;
  }
  for(size_t i=1;i<=baseline.events;++i) {
    fixture f={.refuse_event=i};
    assert(parse(&f,input,at,&d,&e,&info)==LIE_JSON_PARSE_CALLBACK);++callback_refusals;
  }
  fixture f={0};lie_json_parse_description_init(&d);d.max_input_bytes=1;
  assert(parse(&f,input,at,&d,&e,&info)==LIE_JSON_PARSE_LIMIT && f.events==0);
  memset(&f,0,sizeof(f));lie_json_parse_description_init(&d);d.max_work=1;
  assert(parse(&f,input,at,&d,&e,&info)==LIE_JSON_PARSE_LIMIT);
  memset(&f,0,sizeof(f));lie_json_parse_description_init(&d);d.max_owned_bytes=baseline.peak-1;
  assert(parse(&f,input,at,&d,&e,&info)==LIE_JSON_PARSE_LIMIT);
  memset(&f,0,sizeof(f));lie_json_parse_description_init(&d);d.max_owned_bytes=baseline.peak;
  assert(parse(&f,input,at,&d,&e,&info)==LIE_JSON_PARSE_OK);
  memset(&f,0,sizeof(f));lie_json_parse_description_init(&d);d.max_depth=1;
  assert(parse(&f,"[[]]",4,&d,&e,&info)==LIE_JSON_PARSE_SYNTAX);
}
int main(void) {
  events();utf8();syntax_oracles();failures();
  fixture f={0};lie_json_sink sink={&f,emit};lie_json_parse_description d;
  lie_json_parse_description_init(&d);d.abi_version=0;
  assert(lie_json_parse_events("null",4,&d,&sink,NULL,NULL)==LIE_JSON_PARSE_INVALID);++checks;
  lie_json_parse_description_init(&d);d.max_depth=129;
  assert(lie_json_parse_events("null",4,&d,&sink,NULL,NULL)==LIE_JSON_PARSE_INVALID);++checks;
  lie_json_parse_description_init(&d);d.allocator.allocate=allocate;
  assert(lie_json_parse_events("null",4,&d,&sink,NULL,NULL)==LIE_JSON_PARSE_INVALID);++checks;
  assert(lie_json_parse_events(NULL,1,NULL,&sink,NULL,NULL)==LIE_JSON_PARSE_INVALID);++checks;
  assert(lie_json_parse_events("null",4,NULL,NULL,NULL,NULL)==LIE_JSON_PARSE_INVALID);++checks;
  assert(!f.events && !f.calls);
  printf("C17 JSON parser: %zu independent checks, %zu allocator refusals, %zu callback refusals; HOST_NOT_INFERENCE\n",checks,allocation_refusals,callback_refusals);
}
