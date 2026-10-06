/* SPDX-License-Identifier: MIT */
/* Syntax/diagnostic semantics: independently pinned Gufo core/json.hpp.
 * LIE owns this iterative C17 implementation and bounded key/decoder storage. */
#include "lie/json_parse.h"
#include "lie/binary64.h"
#include <stdlib.h>
#include <string.h>

typedef struct {
  const char *text;
  size_t bytes;
  uint64_t hash;
  bool present, owned;
} key;
enum phase { ARRAY_FIRST, ARRAY_VALUE, ARRAY_AFTER, OBJECT_FIRST, OBJECT_KEY, OBJECT_AFTER };
typedef struct { enum phase phase; key *keys; size_t capacity, count; } frame;
typedef struct {
  const char *text;
  size_t bytes, at, live;
  unsigned depth;
  lie_json_parse_description d;
  lie_json_sink sink;
  lie_json_parse_status status;
  lie_json_parse_error error;
  lie_json_parse_info info;
  char *decoded;
  size_t decoded_capacity, decoded_bytes;
  frame frames[LIE_JSON_PARSE_MAX_DEPTH];
} parser;

void lie_json_parse_description_init(lie_json_parse_description *d) {
  if (!d) return;
  *d = (lie_json_parse_description){.abi_version=LIE_JSON_PARSE_ABI,
    .struct_bytes=sizeof(*d), .max_input_bytes=64u*1024u*1024u,
    .max_owned_bytes=64u*1024u*1024u, .max_work=256u*1024u*1024u,
    .max_depth=LIE_JSON_PARSE_MAX_DEPTH};
}
static bool fail(parser *p, lie_json_parse_status status, const char *message) {
  if (p->status == LIE_JSON_PARSE_OK) {
    p->status=status; p->error=(lie_json_parse_error){message,p->at};
  }
  return false;
}
static bool syntax(parser *p, const char *message) { return fail(p,LIE_JSON_PARSE_SYNTAX,message); }
static bool work(parser *p, size_t count) {
  if (count > p->d.max_work-p->info.work)
    return fail(p,LIE_JSON_PARSE_LIMIT,"JSON parse work budget exceeded");
  p->info.work+=count; return true;
}
static void *allocate(parser *p, size_t bytes) {
  if (bytes > p->d.max_owned_bytes-p->live) {
    fail(p,LIE_JSON_PARSE_LIMIT,"JSON parse storage budget exceeded");return NULL;
  }
  void *out=p->d.allocator.allocate ? p->d.allocator.allocate(p->d.allocator.context,bytes) : malloc(bytes);
  ++p->info.allocations;
  if (!out) { fail(p,LIE_JSON_PARSE_RESOURCE,"cannot allocate JSON parse workspace");return NULL; }
  p->live+=bytes;
  if (p->live>p->info.peak_owned_bytes) p->info.peak_owned_bytes=p->live;
  return out;
}
static void release(parser *p, void *data, size_t bytes) {
  if (!data) return;
  if (p->d.allocator.release) p->d.allocator.release(p->d.allocator.context,data);
  else free(data);
  p->live-=bytes;
}
static bool advance(parser *p, size_t bytes) {
  if (!work(p,bytes)) return false;
  p->at+=bytes;return true;
}
static bool whitespace(parser *p) {
  while (p->at<p->bytes) {
    char c=p->text[p->at];
    if (c!=' ' && c!='\t' && c!='\r' && c!='\n') break;
    if (!advance(p,1)) return false;
  }
  return true;
}
static bool emit(parser *p, lie_json_event event) {
  if (!work(p,1)) return false;
  ++p->info.events;
  return p->sink.emit(p->sink.context,&event) || fail(p,LIE_JSON_PARSE_CALLBACK,"JSON event sink refused");
}
static bool buffer(parser *p, const char *data, size_t bytes) {
  if (bytes>SIZE_MAX-p->decoded_bytes)
    return fail(p,LIE_JSON_PARSE_LIMIT,"JSON parse storage budget exceeded");
  size_t need=p->decoded_bytes+bytes;
  if (need>p->decoded_capacity) {
    size_t capacity=p->decoded_capacity ? p->decoded_capacity : 64;
    while (capacity<need) {
      if (capacity>SIZE_MAX/2) { capacity=need;break; }
      capacity*=2;
    }
    char *next=allocate(p,capacity);if (!next) return false;
    if (p->decoded_bytes) memcpy(next,p->decoded,p->decoded_bytes);
    release(p,p->decoded,p->decoded_capacity);
    p->decoded=next;p->decoded_capacity=capacity;
  }
  if (bytes) memcpy(p->decoded+p->decoded_bytes,data,bytes);
  p->decoded_bytes=need;return true;
}
static bool hex_quad(parser *p, unsigned *out) {
  if (p->bytes-p->at<4) return syntax(p,"bad \\u");
  unsigned code=0;
  for (unsigned i=0;i<4;++i) {
    unsigned char c=(unsigned char)p->text[p->at];
    if (!advance(p,1)) return false;
    code<<=4;
    if (c>='0' && c<='9') code|=c-'0';
    else if (c>='a' && c<='f') code|=c-'a'+10;
    else if (c>='A' && c<='F') code|=c-'A'+10;
    else return syntax(p,"bad hex");
  }
  *out=code;return true;
}
static bool codepoint(parser *p, unsigned code) {
  char text[4];size_t bytes;
  if (code<0x80) { text[0]=(char)code;bytes=1; }
  else if (code<0x800) { text[0]=(char)(0xc0|(code>>6));text[1]=(char)(0x80|(code&63));bytes=2; }
  else if (code<0x10000) { text[0]=(char)(0xe0|(code>>12));text[1]=(char)(0x80|((code>>6)&63));text[2]=(char)(0x80|(code&63));bytes=3; }
  else { text[0]=(char)(0xf0|(code>>18));text[1]=(char)(0x80|((code>>12)&63));text[2]=(char)(0x80|((code>>6)&63));text[3]=(char)(0x80|(code&63));bytes=4; }
  return buffer(p,text,bytes);
}
static bool string(parser *p, const char **text, size_t *bytes, bool *escaped) {
  if (!advance(p,1)) return false;
  size_t start=p->at;p->decoded_bytes=0;*escaped=false;
  while (p->at<p->bytes) {
    unsigned char c=(unsigned char)p->text[p->at];
    if (!advance(p,1)) return false;
    if (c=='"') {
      *text=*escaped ? p->decoded : p->text+start;
      *bytes=*escaped ? p->decoded_bytes : p->at-start-1;return true;
    }
    if (c=='\\') {
      if (!*escaped && !buffer(p,p->text+start,p->at-start-1)) return false;
      *escaped=true;
      if (p->at>=p->bytes) return syntax(p,"bad escape");
      c=(unsigned char)p->text[p->at];if (!advance(p,1)) return false;
      char decoded=0;
      switch (c) {
      case '"':case '\\':case '/':decoded=(char)c;break;
      case 'b':decoded='\b';break;
      case 'f':decoded='\f';break;
      case 'n':decoded='\n';break;
      case 'r':decoded='\r';break;
      case 't':decoded='\t';break;
      case 'u': {
        unsigned code=0;if (!hex_quad(p,&code)) return false;
        if (code>=0xd800 && code<=0xdbff) {
          if (p->bytes-p->at<2 || p->text[p->at]!='\\' || p->text[p->at+1]!='u')
            return syntax(p,"unpaired high surrogate");
          if (!advance(p,2)) return false;
          unsigned low=0;if (!hex_quad(p,&low)) return false;
          if (low<0xdc00 || low>0xdfff) return syntax(p,"invalid low surrogate");
          code=0x10000+((code-0xd800)<<10)+(low-0xdc00);
        } else if (code>=0xdc00 && code<=0xdfff) return syntax(p,"unpaired low surrogate");
        if (!codepoint(p,code)) return false;
        continue;
      }
      default:return syntax(p,"bad escape");
      }
      if (!buffer(p,&decoded,1)) return false;
    } else {
      if (c<0x20) return syntax(p,"unescaped control character");
      size_t length=c<0x80 ? 1 : c>=0xc2 && c<=0xdf ? 2 : c>=0xe0 && c<=0xef ? 3 : c>=0xf0 && c<=0xf4 ? 4 : 0;
      if (!length || length-1>p->bytes-p->at) return syntax(p,"invalid UTF-8");
      for (size_t j=1;j<length;++j) {
        unsigned char b=(unsigned char)p->text[p->at+j-1];
        if (b<0x80 || b>0xbf || (j==1 && ((c==0xe0 && b<0xa0) || (c==0xed && b>0x9f) ||
            (c==0xf0 && b<0x90) || (c==0xf4 && b>0x8f)))) return syntax(p,"invalid UTF-8");
      }
      if (*escaped && !buffer(p,p->text+p->at-1,length)) return false;
      if (!advance(p,length-1)) return false;
    }
  }
  return syntax(p,"unterminated string");
}
static void clear_keys(parser *p, frame *f) {
  for (size_t i=0;i<f->capacity;++i)
    if (f->keys[i].present && f->keys[i].owned)
      release(p,(void *)f->keys[i].text,f->keys[i].bytes ? f->keys[i].bytes : 1);
  release(p,f->keys,f->capacity*sizeof(key));f->keys=NULL;f->capacity=f->count=0;
}
static bool insert_key(parser *p, frame *f, const char *text, size_t bytes, bool escaped) {
  if (!work(p,bytes)) return false;
  uint64_t hash=UINT64_C(14695981039346656037);
  for (size_t i=0;i<bytes;++i) { hash^=(unsigned char)text[i];hash*=UINT64_C(1099511628211); }
  if (f->capacity) {
    size_t at=(size_t)hash&(f->capacity-1);
    while (f->keys[at].present) {
      const key *k=&f->keys[at];if (!work(p,1)) return false;
      if (k->hash==hash && k->bytes==bytes) {
        if (!work(p,bytes)) return false;
        if (!bytes || !memcmp(k->text,text,bytes)) return syntax(p,"duplicate object key");
      }
      at=(at+1)&(f->capacity-1);
    }
  }
  if (f->count>=f->capacity/2) {
    if (f->capacity>SIZE_MAX/2/sizeof(key))
      return fail(p,LIE_JSON_PARSE_LIMIT,"JSON parse storage budget exceeded");
    size_t capacity=f->capacity ? f->capacity*2 : 16;
    key *next=allocate(p,capacity*sizeof(key));if (!next) return false;
    memset(next,0,capacity*sizeof(key));
    for (size_t i=0;i<f->capacity;++i) if (f->keys[i].present) {
      size_t at=(size_t)f->keys[i].hash&(capacity-1);
      while (next[at].present) {
        if (!work(p,1)) { release(p,next,capacity*sizeof(key));return false; }
        at=(at+1)&(capacity-1);
      }
      next[at]=f->keys[i];
    }
    release(p,f->keys,f->capacity*sizeof(key));f->keys=next;f->capacity=capacity;
  }
  if (escaped) {
    char *copy=allocate(p,bytes ? bytes : 1);if (!copy) return false;
    if (bytes) memcpy(copy,text,bytes);
    text=copy;
  }
  size_t at=(size_t)hash&(f->capacity-1);
  while (f->keys[at].present) at=(at+1)&(f->capacity-1);
  f->keys[at]=(key){text,bytes,hash,true,escaped};++f->count;return true;
}
static bool digit(char c) { return c>='0' && c<='9'; }
static bool number(parser *p) {
  size_t start=p->at;
  if (p->at<p->bytes && p->text[p->at]=='-' && !advance(p,1)) return false;
  if (p->at>=p->bytes) return syntax(p,"bad number");
  if (p->text[p->at]=='0') {
    if (!advance(p,1)) return false;
    if (p->at<p->bytes && digit(p->text[p->at])) return syntax(p,"bad number");
  } else if (p->text[p->at]>='1' && p->text[p->at]<='9') {
    do { if (!advance(p,1)) return false; } while (p->at<p->bytes && digit(p->text[p->at]));
  } else return syntax(p,"bad number");
  if (p->at<p->bytes && p->text[p->at]=='.') {
    if (!advance(p,1)) return false;
    if (p->at>=p->bytes || !digit(p->text[p->at])) return syntax(p,"bad number");
    do { if (!advance(p,1)) return false; } while (p->at<p->bytes && digit(p->text[p->at]));
  }
  if (p->at<p->bytes && (p->text[p->at]=='e' || p->text[p->at]=='E')) {
    if (!advance(p,1)) return false;
    if (p->at<p->bytes && (p->text[p->at]=='-' || p->text[p->at]=='+') && !advance(p,1)) return false;
    if (p->at>=p->bytes || !digit(p->text[p->at])) return syntax(p,"bad number");
    do { if (!advance(p,1)) return false; } while (p->at<p->bytes && digit(p->text[p->at]));
  }
  double value=0;
  if (lie_binary64_parse(p->text+start,p->at-start,NULL,&value)!=LIE_BINARY64_OK) return syntax(p,"bad number");
  return emit(p,(lie_json_event){.kind=LIE_JSON_NUMBER,.text=p->text+start,.text_bytes=p->at-start,.number=value});
}
static bool value(parser *p) {
  if (!whitespace(p)) return false;
  if (p->at>=p->bytes) return syntax(p,"unexpected end of input");
  char c=p->text[p->at];
  if (c=='{' || c=='[') {
    if (p->depth>=p->d.max_depth) return syntax(p,"maximum nesting depth exceeded");
    if (!advance(p,1)) return false;
    p->frames[p->depth++]=(frame){.phase=c=='{' ? OBJECT_FIRST : ARRAY_FIRST};
    return emit(p,(lie_json_event){.kind=c=='{' ? LIE_JSON_BEGIN_OBJECT : LIE_JSON_BEGIN_ARRAY});
  }
  if (c=='"') {
    const char *text=NULL;size_t bytes=0;bool escaped=false;
    return string(p,&text,&bytes,&escaped) && emit(p,(lie_json_event){.kind=LIE_JSON_STRING,.text=text,.text_bytes=bytes});
  }
  if (c=='t' || c=='f' || c=='n') {
    const char *literal=c=='t' ? "true" : c=='f' ? "false" : "null";
    size_t bytes=c=='f' ? 5 : 4;
    if (bytes>p->bytes-p->at || memcmp(p->text+p->at,literal,bytes)) return syntax(p,"bad literal");
    return advance(p,bytes) && emit(p,(lie_json_event){.kind=c=='n' ? LIE_JSON_NULL : LIE_JSON_BOOL,.boolean=c=='t'});
  }
  return number(p);
}
static bool container(parser *p) {
  frame *f=&p->frames[p->depth-1];
  if (!whitespace(p)) return false;
  if (f->phase==OBJECT_FIRST && p->at<p->bytes && p->text[p->at]=='}') {
    if (!advance(p,1) || !emit(p,(lie_json_event){.kind=LIE_JSON_END_OBJECT})) return false;
    clear_keys(p,f);--p->depth;return true;
  }
  if (f->phase==ARRAY_FIRST && p->at<p->bytes && p->text[p->at]==']') {
    if (!advance(p,1) || !emit(p,(lie_json_event){.kind=LIE_JSON_END_ARRAY})) return false;
    --p->depth;return true;
  }
  if (f->phase==ARRAY_FIRST || f->phase==ARRAY_VALUE) { f->phase=ARRAY_AFTER;return value(p); }
  if (f->phase==OBJECT_FIRST || f->phase==OBJECT_KEY) {
    if (p->at>=p->bytes || p->text[p->at]!='"') return syntax(p,"expected object key string");
    const char *text=NULL;size_t bytes=0;bool escaped=false;
    if (!string(p,&text,&bytes,&escaped) || !whitespace(p)) return false;
    if (p->at>=p->bytes || p->text[p->at]!=':') return syntax(p,"expected ':' after key");
    if (!advance(p,1) || !insert_key(p,f,text,bytes,escaped) ||
        !emit(p,(lie_json_event){.kind=LIE_JSON_KEY,.text=text,.text_bytes=bytes})) return false;
    f->phase=OBJECT_AFTER;return value(p);
  }
  bool object=f->phase==OBJECT_AFTER;
  if (p->at>=p->bytes) return syntax(p,object ? "unterminated object" : "unterminated array");
  char c=p->text[p->at];
  if (c==',') { f->phase=object ? OBJECT_KEY : ARRAY_VALUE;return advance(p,1); }
  if (c==(object ? '}' : ']')) {
    if (!advance(p,1) || !emit(p,(lie_json_event){.kind=object ? LIE_JSON_END_OBJECT : LIE_JSON_END_ARRAY})) return false;
    clear_keys(p,f);--p->depth;return true;
  }
  return syntax(p,object ? "expected ',' or '}' in object" : "expected ',' or ']' in array");
}
lie_json_parse_status lie_json_parse_events(const char *text, size_t bytes,
  const lie_json_parse_description *description, const lie_json_sink *sink,
  lie_json_parse_error *error, lie_json_parse_info *info) {
  parser p={.text=text,.bytes=bytes};
  lie_json_parse_description_init(&p.d);if (description) p.d=*description;
  if ((bytes && !text) || !sink || !sink->emit || p.d.abi_version!=LIE_JSON_PARSE_ABI ||
      p.d.struct_bytes!=sizeof(p.d) || !p.d.max_input_bytes || !p.d.max_owned_bytes || !p.d.max_work ||
      !p.d.max_depth || p.d.max_depth>LIE_JSON_PARSE_MAX_DEPTH ||
      (!!p.d.allocator.allocate != !!p.d.allocator.release)) {
    fail(&p,LIE_JSON_PARSE_INVALID,"invalid JSON parser description or sink");goto done;
  }
  p.sink=*sink;
  if (bytes>p.d.max_input_bytes) { fail(&p,LIE_JSON_PARSE_LIMIT,"JSON input budget exceeded");goto done; }
  if (!value(&p)) goto done;
  while (p.depth) if (!container(&p)) goto done;
  if (!whitespace(&p)) goto done;
  if (p.at!=bytes) syntax(&p,"trailing input");
done:
  for (unsigned i=0;i<p.depth;++i) clear_keys(&p,&p.frames[i]);
  release(&p,p.decoded,p.decoded_capacity);
  p.info.input_consumed=p.at;
  if (error) *error=p.error;
  if (info) *info=p.info;
  return p.status;
}
