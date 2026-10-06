/* SPDX-License-Identifier: MIT */
/* Independent publication/capacity/ordered writer-refusal oracles. */
#include "lie/schema_format.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct node node;
struct node { lie_schema_value value; char text[LIE_SCHEMA_FORMAT_PATTERN_CAPACITY];
  const char *keys[2]; const node *children[2]; };
typedef struct { node nodes[3]; size_t count,calls,fail_at; } fixture;
static size_t oracles,refusals;
static lie_schema_status describe(void *p,lie_schema_node n,lie_schema_value *out) {
  (void)p; *out=((const node *)n)->value; return LIE_SCHEMA_OK;
}
static lie_schema_status child(void *p,lie_schema_node n,size_t at,lie_schema_bytes *key,lie_schema_node *out) {
  (void)p; const node *value=n; assert(at<value->value.count);
  *key=(lie_schema_bytes){value->keys[at],strlen(value->keys[at])}; *out=value->children[at]; return LIE_SCHEMA_OK;
}
static lie_schema_status create(void *p,const lie_schema_value *value,lie_schema_node *out) {
  fixture *f=p; if (++f->calls==f->fail_at) return LIE_SCHEMA_CALLBACK;
  assert(f->count<3); node *n=&f->nodes[f->count++]; n->value=*value;
  if (value->kind==LIE_SCHEMA_STRING) {
    assert(value->text.size<=sizeof(n->text)); memcpy(n->text,value->text.data,value->text.size);
    n->value.text.data=n->text;
  }
  *out=n; return LIE_SCHEMA_OK;
}
static lie_schema_status put(void *p,lie_schema_node target,lie_schema_bytes key,lie_schema_node value) {
  fixture *f=p; if (++f->calls==f->fail_at) return LIE_SCHEMA_CALLBACK;
  node *n=(node *)target; assert(n->value.count<2);
  const char *stored=key.size==7 && !memcmp(key.data,"pattern",7) ? "pattern" :
    key.size==9 && !memcmp(key.data,"maxLength",9) ? "maxLength" : NULL;
  assert(stored); size_t at=n->value.count++; n->keys[at]=stored; n->children[at]=value;
  return LIE_SCHEMA_OK;
}
static lie_schema_transform_description description(fixture *f) {
  lie_schema_transform_description d; lie_schema_transform_description_init(&d);
  d.access.context=f; d.access.describe=describe; d.access.child=child;
  d.access.create=create; d.access.put=put; return d;
}
int main(void) {
  const char *names[]={"date","time","date-time","uuid","ipv4","ipv6","hostname","email","duration"};
  for (size_t i=0;i<9;++i) {
    lie_schema_bytes name={names[i],strlen(names[i])};
    char text[LIE_SCHEMA_FORMAT_PATTERN_CAPACITY], saved[sizeof(text)];
    memset(text,0x5a,sizeof(text)); size_t bytes=999; lie_schema_error e={0};
    assert(lie_schema_format_pattern(name,text,sizeof(text),&bytes,&e)==LIE_SCHEMA_OK);
    assert(bytes>2 && text[0]=='^' && text[bytes-1]=='$' && bytes<sizeof(text));
    assert(text[bytes]==0x5a); oracles+=2;
    if (!strcmp(names[i],"uuid")) {
      const char *expected="^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$";
      assert(bytes==strlen(expected) && !memcmp(text,expected,bytes)); ++oracles;
    }
    const size_t required=bytes;
    for (unsigned small=0;small<2;++small) {
      memset(text,0x5a,sizeof(text)); memcpy(saved,text,sizeof(text)); bytes=999;
      assert(lie_schema_format_pattern(name,text,small ? required-1 : 0,&bytes,&e)==LIE_SCHEMA_RESOURCE);
      assert(bytes==999 && !memcmp(text,saved,sizeof(text))); ++oracles;
    }
    assert(lie_schema_format_pattern(name,text,required,&bytes,&e)==LIE_SCHEMA_OK && bytes==required); ++oracles;
    fixture f={0};
    lie_schema_transform_description d=description(&f); lie_schema_node out=NULL;
    assert(lie_schema_format_expand(&d,name,&out,&e)==LIE_SCHEMA_OK && out);
    const node *object=out; assert(object->value.kind==LIE_SCHEMA_OBJECT);
    const bool hostname=!strcmp(names[i],"hostname");
    assert(object->value.count==(hostname ? 2u : 1u) && !strcmp(object->keys[0],"pattern"));
    assert(object->children[0]->value.text.size==bytes && !memcmp(object->children[0]->text,text,bytes));
    if (hostname) assert(!strcmp(object->keys[1],"maxLength") &&
      object->children[1]->value.kind==LIE_SCHEMA_NUMBER && object->children[1]->value.number==253);
    oracles+=3;
    const size_t calls=f.calls;
    for (size_t at=1;at<=calls;++at) {
      memset(&f,0,sizeof(f)); f.fail_at=at; d=description(&f); out=&d;
      assert(lie_schema_format_expand(&d,name,&out,&e)==LIE_SCHEMA_CALLBACK && out==&d); ++refusals;
    }
    memset(&f,0,sizeof(f));d=description(&f);d.max_work=1;out=&d;
    assert(lie_schema_format_expand(&d,name,&out,&e)==LIE_SCHEMA_WORK_LIMIT && out==&d && !f.calls); ++oracles;
  }
  for (const char **name=(const char *[]) {"", "DATE", "uri", "ipv6x", "email\0x", NULL};*name;++name) {
    char text[32], saved[32];memset(text,0x5a,sizeof(text));memcpy(saved,text,sizeof(text));
    size_t bytes=999;lie_schema_error e={0};size_t n=strlen(*name)==5 && !memcmp(*name,"email",5) ? 7 : strlen(*name);
    assert(lie_schema_format_pattern((lie_schema_bytes){*name,n},text,sizeof(text),&bytes,&e)==LIE_SCHEMA_INVALID);
    assert(!strcmp(e.message,"unsupported string format") && bytes==999 && !memcmp(text,saved,sizeof(text))); ++oracles;
  }
  char storage[32]="email";size_t bytes=999;lie_schema_error e={0};
  assert(lie_schema_format_pattern((lie_schema_bytes){storage,5},storage,sizeof(storage),&bytes,&e)==LIE_SCHEMA_INVALID && bytes==999); ++oracles;
  fixture f={0};lie_schema_transform_description d=description(&f);lie_schema_node out=&d;
  d.access.create=NULL;
  assert(lie_schema_format_expand(&d,(lie_schema_bytes){"email",5},&out,&e)==LIE_SCHEMA_INVALID && out==&d); ++oracles;
  printf("C17 schema format: %zu independent oracles, %zu callback refusals; HOST_NOT_INFERENCE\n",oracles,refusals);
}
