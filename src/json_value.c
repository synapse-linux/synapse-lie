/* SPDX-License-Identifier: MIT */
#include "lie/json_value.h"
#include "lie/binary64.h"
#include <limits.h>
#include <math.h>
#include <stdalign.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  lie_json_value_description d;
  lie_json_value_info info;
} domain;
typedef union { max_align_t alignment; size_t bytes; } allocation;
typedef struct { lie_json_value **data; size_t count, capacity; } table;
struct lie_json_value {
  domain *owner;
  lie_json_value *parent;
  char *text, *key;
  size_t text_bytes, key_bytes;
  table array, object;
  double number;
  uint64_t revision;
  lie_json_value_kind kind;
  bool boolean, view_ready;
};
static const char empty[]="";
static size_t node_bytes(void) {
  const size_t a=alignof(max_align_t);
  return (sizeof(lie_json_value)+a-1)/a*a;
}
static void *view(const lie_json_value *n) {
  return n && n->owner->d.view_bytes ? (char *)(void *)n+node_bytes() : NULL;
}
void lie_json_value_description_init(lie_json_value_description *d) {
  if (!d) return;
  memset(d,0,sizeof(*d));d->abi_version=LIE_JSON_VALUE_ABI;d->struct_bytes=sizeof(*d);
  d->max_owned_bytes=64u*1024u*1024u;d->max_nodes=262144u;
  d->max_work=256u*1024u*1024u;d->max_depth=LIE_JSON_VALUE_MAX_DEPTH;
}
static bool description(lie_json_value_description *d,
                        const lie_json_value_description *in) {
  if (in) *d=*in;else lie_json_value_description_init(d);
  return d->abi_version==LIE_JSON_VALUE_ABI && d->struct_bytes==sizeof(*d) &&
    d->max_owned_bytes>=sizeof(domain) && d->max_nodes && d->max_work &&
    d->max_depth && d->max_depth<=LIE_JSON_VALUE_MAX_DEPTH &&
    (!!d->allocator.allocate==!!d->allocator.release) &&
    (!!d->view_initialize==!!d->view_release) &&
    ((!d->view_bytes && !d->view_initialize) || (d->view_bytes && d->view_initialize)) &&
    d->view_bytes<=SIZE_MAX-node_bytes();
}
static void *allocate(domain *c,size_t bytes,lie_json_value_status *rc) {
  if (bytes>SIZE_MAX-sizeof(allocation) ||
      bytes+sizeof(allocation)>c->d.max_owned_bytes-c->info.live_owned_bytes) {
    *rc=LIE_JSON_VALUE_LIMIT;return NULL;
  }
  const size_t total=bytes+sizeof(allocation);
  allocation *a=c->d.allocator.allocate ? c->d.allocator.allocate(c->d.allocator.context,total) : malloc(total);
  if (!a) { *rc=LIE_JSON_VALUE_RESOURCE;return NULL; }
  a->bytes=total;c->info.live_owned_bytes+=total;++c->info.allocations;
  if (c->info.peak_owned_bytes<c->info.live_owned_bytes)
    c->info.peak_owned_bytes=c->info.live_owned_bytes;
  return a+1;
}
static void retire(domain *c,void *p) {
  if (!p) return;
  allocation *a=(allocation *)p-1;c->info.live_owned_bytes-=a->bytes;
  if (c->d.allocator.release) c->d.allocator.release(c->d.allocator.context,a);else free(a);
}
static lie_json_value *node(domain *c,lie_json_value *parent,lie_json_value_status *rc) {
  if (c->info.live_nodes>=c->d.max_nodes) { *rc=LIE_JSON_VALUE_LIMIT;return NULL; }
  lie_json_value *n=allocate(c,node_bytes()+c->d.view_bytes,rc);
  if (!n) return NULL;
  memset(n,0,sizeof(*n));n->owner=c;n->parent=parent;n->revision=1;++c->info.live_nodes;
  if (c->d.view_initialize) {
    if (!c->d.view_initialize(c->d.view_context,n,view(n))) {
      --c->info.live_nodes;retire(c,n);*rc=LIE_JSON_VALUE_CALLBACK;return NULL;
    }
    n->view_ready=true;
  }
  return n;
}
/* Destruction is iterative even for retained inactive tables. */
static void destroy(lie_json_value *root) {
  if (!root) return;
  domain *c=root->owner;lie_json_value *n=root;
  for (;;) {
    if (n->array.count) { n=n->array.data[--n->array.count];continue; }
    if (n->object.count) { n=n->object.data[--n->object.count];continue; }
    lie_json_value *parent=n==root ? NULL : n->parent;
    if (n->view_ready) c->d.view_release(c->d.view_context,view(n));
    retire(c,n->text);retire(c,n->key);retire(c,n->array.data);retire(c,n->object.data);
    --c->info.live_nodes;retire(c,n);
    if (!parent) break;
    n=parent;
  }
}
static void clear_table(lie_json_value *n,table *t) {
  for (size_t i=0;i<t->count;++i) destroy(t->data[i]);
  retire(n->owner,t->data);memset(t,0,sizeof(*t));
}
static char *bytes_copy(domain *c,const char *s,size_t bytes,lie_json_value_status *rc) {
  if (!bytes) return NULL;
  if (bytes==SIZE_MAX) { *rc=LIE_JSON_VALUE_LIMIT;return NULL; }
  char *out=allocate(c,bytes+1,rc);if (!out) return NULL;
  memcpy(out,s,bytes);out[bytes]='\0';return out;
}
static bool spend(domain *c,size_t *work,size_t n,lie_json_value_status *rc) {
  if (n>c->d.max_work-*work) { *rc=LIE_JSON_VALUE_LIMIT;return false; }
  *work+=n;return true;
}
static unsigned depth(const lie_json_value *n) {
  unsigned d=1;while (n->parent) { ++d;n=n->parent; }return d;
}
static lie_json_value *copy_node(domain *c,const lie_json_value *src,
  lie_json_value *parent,unsigned level,size_t *work,lie_json_value_status *rc) {
  if (level>c->d.max_depth || !spend(c,work,1,rc)) { *rc=LIE_JSON_VALUE_LIMIT;return NULL; }
  lie_json_value *n=node(c,parent,rc);if (!n || !src) return n;
  n->kind=src->kind;n->boolean=src->boolean;n->number=src->number;
  if (!spend(c,work,src->text_bytes,rc)) goto fail;
  n->text=bytes_copy(c,src->text,src->text_bytes,rc);
  if (src->text_bytes && !n->text) goto fail;
  n->text_bytes=src->text_bytes;
  for (unsigned which=0;which<2;++which) {
    const table *from=which ? &src->object : &src->array;
    table *to=which ? &n->object : &n->array;
    if (!from->count) continue;
    if (from->count>SIZE_MAX/sizeof(*to->data)) { *rc=LIE_JSON_VALUE_LIMIT;goto fail; }
    to->data=allocate(c,from->count*sizeof(*to->data),rc);if (!to->data) goto fail;
    to->capacity=from->count;
    for (size_t i=0;i<from->count;++i) {
      lie_json_value *child=copy_node(c,from->data[i],n,level+1,work,rc);
      if (!child) goto fail;
      to->data[to->count++]=child;
      if (which) {
        if (!spend(c,work,from->data[i]->key_bytes,rc)) goto fail;
        child->key=bytes_copy(c,from->data[i]->key,from->data[i]->key_bytes,rc);
        if (from->data[i]->key_bytes && !child->key) goto fail;
        child->key_bytes=from->data[i]->key_bytes;
      }
    }
  }
  return n;
fail:destroy(n);return NULL;
}
lie_json_value_status lie_json_value_clone(const lie_json_value *src,
  const lie_json_value_description *in,lie_json_value **out) {
  lie_json_value_description d;if (!out || !description(&d,in)) return LIE_JSON_VALUE_INVALID;
  domain *c=d.allocator.allocate ? d.allocator.allocate(d.allocator.context,sizeof(*c)) : malloc(sizeof(*c));
  if (!c) return LIE_JSON_VALUE_RESOURCE;
  memset(c,0,sizeof(*c));c->d=d;c->info.live_owned_bytes=sizeof(*c);
  c->info.peak_owned_bytes=sizeof(*c);c->info.allocations=1;
  size_t work=0;lie_json_value_status rc=LIE_JSON_VALUE_OK;
  lie_json_value *n=copy_node(c,src,NULL,1,&work,&rc);
  if (!n) {
    if (d.allocator.release) d.allocator.release(d.allocator.context,c);else free(c);
    return rc;
  }
  *out=n;return LIE_JSON_VALUE_OK;
}
lie_json_value_status lie_json_value_create(const lie_json_value_description *d,lie_json_value **out) {
  return lie_json_value_clone(NULL,d,out);
}
void lie_json_value_release(lie_json_value *n) {
  if (!n || n->parent) return;
  domain *c=n->owner;lie_grammar_allocator a=c->d.allocator;destroy(n);
  if (a.release) a.release(a.context,c);else free(c);
}
bool lie_json_value_is_root(const lie_json_value *n) { return n && !n->parent; }
static void update_parents(lie_json_value *n) {
  for (size_t i=0;i<n->array.count;++i) n->array.data[i]->parent=n;
  for (size_t i=0;i<n->object.count;++i) n->object.data[i]->parent=n;
}
lie_json_value_status lie_json_value_assign(lie_json_value *to,const lie_json_value *from) {
  if (!to) return LIE_JSON_VALUE_INVALID;
  if (to==from) return LIE_JSON_VALUE_OK;
  domain *c=to->owner;size_t work=0;lie_json_value_status rc=LIE_JSON_VALUE_OK;
  lie_json_value *copy=copy_node(c,from,NULL,depth(to),&work,&rc);if (!copy) return rc;
  /* Identity, key and facade stay with the destination. */
  table arr=to->array,obj=to->object;char *text=to->text;size_t text_bytes=to->text_bytes;
  to->kind=copy->kind;to->boolean=copy->boolean;to->number=copy->number;
  to->array=copy->array;to->object=copy->object;to->text=copy->text;to->text_bytes=copy->text_bytes;
  copy->array=arr;copy->object=obj;copy->text=text;copy->text_bytes=text_bytes;
  update_parents(to);update_parents(copy);++to->revision;destroy(copy);
  return LIE_JSON_VALUE_OK;
}
static void moved_payload(lie_json_value *n) {
  clear_table(n,&n->array);clear_table(n,&n->object);retire(n->owner,n->text);
  n->text=NULL;n->text_bytes=0;++n->revision;
}
lie_json_value_status lie_json_value_move_clone(lie_json_value *from,
  const lie_json_value_description *d,lie_json_value **out) {
  lie_json_value_status rc=lie_json_value_clone(from,d,out);
  if (rc==LIE_JSON_VALUE_OK && from) moved_payload(from);
  return rc;
}
lie_json_value_status lie_json_value_move_assign(lie_json_value *to,lie_json_value *from) {
  if (!to || !from) return LIE_JSON_VALUE_INVALID;
  if (to==from) return LIE_JSON_VALUE_OK;
  for (const lie_json_value *n=from;n;n=n->parent) if (n==to) return LIE_JSON_VALUE_INVALID;
  for (const lie_json_value *n=to;n;n=n->parent) if (n==from) return LIE_JSON_VALUE_INVALID;
  lie_json_value_status rc=lie_json_value_assign(to,from);
  if (rc==LIE_JSON_VALUE_OK) moved_payload(from);
  return rc;
}
lie_json_value_status lie_json_value_set(lie_json_value *n,lie_json_value_kind kind,
  bool boolean,double number,const char *text,size_t count) {
  if (!n || kind<LIE_JSON_VALUE_NULL || kind>LIE_JSON_VALUE_OBJECT || (!text && count)) return LIE_JSON_VALUE_INVALID;
  lie_json_value_status rc=LIE_JSON_VALUE_OK;char *copy=NULL;
  if (kind==LIE_JSON_VALUE_STRING) {
    if (count>n->owner->d.max_work) return LIE_JSON_VALUE_LIMIT;
    copy=bytes_copy(n->owner,text,count,&rc);if (count && !copy) return rc;
  }
  if (kind==LIE_JSON_VALUE_ARRAY && n->kind!=kind) clear_table(n,&n->array);
  if (kind==LIE_JSON_VALUE_OBJECT && n->kind!=kind) clear_table(n,&n->object);
  if (kind==LIE_JSON_VALUE_STRING) {
    retire(n->owner,n->text);n->text=copy;n->text_bytes=count;
  }
  n->kind=kind;n->boolean=boolean;n->number=number;++n->revision;return LIE_JSON_VALUE_OK;
}
static lie_json_value_status append(lie_json_value *n,bool object,const char *key,
  size_t key_bytes,const lie_json_value *src,lie_json_value **out) {
  if (!n || (!key && key_bytes)) return LIE_JSON_VALUE_INVALID;
  domain *c=n->owner;lie_json_value_status rc=LIE_JSON_VALUE_OK;size_t work=0;
  lie_json_value *child=copy_node(c,src,n,depth(n)+1,&work,&rc);if (!child) return rc;
  if (!spend(c,&work,key_bytes,&rc)) goto fail;
  child->key=bytes_copy(c,key,key_bytes,&rc);if (key_bytes && !child->key) goto fail;
  child->key_bytes=key_bytes;
  table *t=object ? &n->object : &n->array;
  const lie_json_value_kind kind=object ? LIE_JSON_VALUE_OBJECT : LIE_JSON_VALUE_ARRAY;
  const size_t count=n->kind==kind ? t->count : 0;
  lie_json_value **data=t->data;size_t capacity=t->capacity;
  if (n->kind!=kind || count==capacity) {
    if (count>=SIZE_MAX/2) { rc=LIE_JSON_VALUE_LIMIT;goto fail; }
    capacity=count ? count*2 : 4;
    if (capacity>SIZE_MAX/sizeof(*data)) { rc=LIE_JSON_VALUE_LIMIT;goto fail; }
    data=allocate(c,capacity*sizeof(*data),&rc);if (!data) goto fail;
    if (count) memcpy(data,t->data,count*sizeof(*data));
  }
  if (n->kind!=kind) clear_table(n,t);
  else if (data!=t->data) retire(c,t->data);
  t->data=data;t->capacity=capacity;t->count=count+1;t->data[count]=child;
  n->kind=kind;++n->revision;if (out) *out=child;return LIE_JSON_VALUE_OK;
fail:destroy(child);return rc;
}
lie_json_value_status lie_json_value_append(lie_json_value *n,const lie_json_value *src,lie_json_value **out) {
  return append(n,false,NULL,0,src,out);
}
lie_json_value_status lie_json_value_append_member(lie_json_value *n,const char *key,
  size_t count,const lie_json_value *src,lie_json_value **out) {
  return append(n,true,key,count,src,out);
}
lie_json_value_status lie_json_value_member(lie_json_value *n,const char *key,size_t bytes,lie_json_value **out) {
  if (!n || !out || (!key && bytes)) return LIE_JSON_VALUE_INVALID;
  const lie_json_value *found=lie_json_value_find(n,key,bytes);
  if (found) { *out=(lie_json_value *)(void *)found;return LIE_JSON_VALUE_OK; }
  return append(n,true,key,bytes,NULL,out);
}
lie_json_value_kind lie_json_value_type(const lie_json_value *n) { return n ? n->kind : LIE_JSON_VALUE_NULL; }
bool lie_json_value_boolean(const lie_json_value *n,bool def) { return n && n->kind==LIE_JSON_VALUE_BOOL ? n->boolean : def; }
double lie_json_value_number(const lie_json_value *n,double def) { return n && n->kind==LIE_JSON_VALUE_NUMBER ? n->number : def; }
size_t lie_json_value_size_number(const lie_json_value *n,size_t def) {
  if (!n || n->kind!=LIE_JSON_VALUE_NUMBER || !isfinite(n->number) || n->number<0.0 ||
      floor(n->number)!=n->number || n->number>=ldexp(1.0,sizeof(size_t)*CHAR_BIT)) return def;
  return (size_t)n->number;
}
const char *lie_json_value_string(const lie_json_value *n,size_t *bytes) {
  const bool valid=n && n->kind==LIE_JSON_VALUE_STRING;
  if (bytes) *bytes=valid ? n->text_bytes : 0;
  return valid && n->text ? n->text : empty;
}
const char *lie_json_value_key(const lie_json_value *n,size_t *bytes) {
  if (bytes) *bytes=n ? n->key_bytes : 0;
  return n && n->key ? n->key : empty;
}
size_t lie_json_value_array_size(const lie_json_value *n) { return n ? n->array.count : 0; }
size_t lie_json_value_object_size(const lie_json_value *n) { return n ? n->object.count : 0; }
size_t lie_json_value_size(const lie_json_value *n) {
  return n && n->kind==LIE_JSON_VALUE_ARRAY ? n->array.count : n && n->kind==LIE_JSON_VALUE_OBJECT ? n->object.count : 0;
}
const lie_json_value *lie_json_value_at(const lie_json_value *n,bool object,size_t i) {
  if (!n) return NULL;
  const table *t=object ? &n->object : &n->array;return i<t->count ? t->data[i] : NULL;
}
const lie_json_value *lie_json_value_find(const lie_json_value *n,const char *key,size_t count) {
  if (!n || n->kind!=LIE_JSON_VALUE_OBJECT || (!key && count)) return NULL;
  for (size_t i=0;i<n->object.count;++i) {
    const lie_json_value *child=n->object.data[i];
    if (child->key_bytes==count && (!count || !memcmp(child->key,key,count))) return child;
  }
  return NULL;
}
void *lie_json_value_view(const lie_json_value *n) { return n && n->view_ready ? view(n) : NULL; }
uint64_t lie_json_value_revision(const lie_json_value *n) { return n ? n->revision : 0; }
void lie_json_value_describe(const lie_json_value *n,lie_json_value_info *out) {
  if (out) { if (n) *out=n->owner->info;else memset(out,0,sizeof(*out)); }
}

typedef struct { lie_json_value *container;char *key;size_t key_bytes; } parse_frame;
typedef struct {
  lie_json_value *root;
  parse_frame frames[LIE_JSON_PARSE_MAX_DEPTH];
  size_t count;
  bool root_seen;
  lie_json_value_status status;
} tree_builder;
static bool build_event(void *context,const lie_json_event *e) {
  tree_builder *b=context;domain *c=b->root->owner;
  if (e->kind==LIE_JSON_KEY) {
    if (!b->count) { b->status=LIE_JSON_VALUE_INVALID;return false; }
    parse_frame *f=&b->frames[b->count-1];
    char *copy=bytes_copy(c,e->text,e->text_bytes,&b->status);
    if (e->text_bytes && !copy) return false;
    retire(c,f->key);f->key=copy;f->key_bytes=e->text_bytes;return true;
  }
  if (e->kind==LIE_JSON_END_ARRAY || e->kind==LIE_JSON_END_OBJECT) {
    if (!b->count) { b->status=LIE_JSON_VALUE_INVALID;return false; }
    parse_frame *f=&b->frames[--b->count];retire(c,f->key);memset(f,0,sizeof(*f));return true;
  }
  lie_json_value *n=b->root;
  if (b->count) {
    parse_frame *f=&b->frames[b->count-1];
    if (f->container->kind==LIE_JSON_VALUE_OBJECT)
      b->status=lie_json_value_append_member(f->container,f->key,f->key_bytes,NULL,&n);
    else b->status=lie_json_value_append(f->container,NULL,&n);
    if (b->status!=LIE_JSON_VALUE_OK) return false;
    retire(c,f->key);f->key=NULL;f->key_bytes=0;
  } else if (b->root_seen) { b->status=LIE_JSON_VALUE_INVALID;return false; }
  else b->root_seen=true;
  lie_json_value_kind kind=LIE_JSON_VALUE_NULL;
  switch (e->kind) {
  case LIE_JSON_BEGIN_OBJECT: kind=LIE_JSON_VALUE_OBJECT;break;
  case LIE_JSON_BEGIN_ARRAY: kind=LIE_JSON_VALUE_ARRAY;break;
  case LIE_JSON_STRING: kind=LIE_JSON_VALUE_STRING;break;
  case LIE_JSON_NUMBER: kind=LIE_JSON_VALUE_NUMBER;break;
  case LIE_JSON_BOOL: kind=LIE_JSON_VALUE_BOOL;break;
  case LIE_JSON_NULL:break;
  default:b->status=LIE_JSON_VALUE_INVALID;return false;
  }
  b->status=lie_json_value_set(n,kind,e->boolean,e->number,e->text,e->text_bytes);
  if (b->status!=LIE_JSON_VALUE_OK) return false;
  if (kind==LIE_JSON_VALUE_OBJECT || kind==LIE_JSON_VALUE_ARRAY) {
    if (b->count>=LIE_JSON_PARSE_MAX_DEPTH) { b->status=LIE_JSON_VALUE_LIMIT;return false; }
    b->frames[b->count++]=(parse_frame){n,NULL,0};
  }
  return true;
}
lie_json_value_status lie_json_value_parse(const char *text,size_t bytes,
  const lie_json_value_description *d,const lie_json_parse_description *p,
  lie_json_value **out,lie_json_parse_error *error,lie_json_parse_info *info) {
  if (!out) return LIE_JSON_VALUE_INVALID;
  lie_json_value *root=NULL;lie_json_value_status rc=lie_json_value_create(d,&root);
  if (rc!=LIE_JSON_VALUE_OK) return rc;
  tree_builder b={0};b.root=root;b.status=LIE_JSON_VALUE_OK;
  lie_json_sink sink={&b,build_event};
  lie_json_parse_status status=lie_json_parse_events(text,bytes,p,&sink,error,info);
  if (status==LIE_JSON_PARSE_OK && b.status==LIE_JSON_VALUE_OK) {
    *out=root;return LIE_JSON_VALUE_OK;
  }
  for (size_t i=0;i<b.count;++i) retire(root->owner,b.frames[i].key);
  lie_json_value_release(root);
  if (b.status!=LIE_JSON_VALUE_OK) return b.status;
  switch (status) {
  case LIE_JSON_PARSE_RESOURCE:return LIE_JSON_VALUE_RESOURCE;
  case LIE_JSON_PARSE_LIMIT:return LIE_JSON_VALUE_LIMIT;
  case LIE_JSON_PARSE_SYNTAX:return LIE_JSON_VALUE_SYNTAX;
  case LIE_JSON_PARSE_CALLBACK:return LIE_JSON_VALUE_CALLBACK;
  default:return LIE_JSON_VALUE_INVALID;
  }
}
typedef struct {
  const lie_json_value_sink *sink;
  size_t written, limit;
  lie_json_value_status status;
} writer;
static bool write_bytes(writer *w,const char *text,size_t count) {
  if (count>w->limit-w->written) { w->status=LIE_JSON_VALUE_LIMIT;return false; }
  if (count && !w->sink->write(w->sink->context,text,count)) {
    w->status=LIE_JSON_VALUE_CALLBACK;return false;
  }
  w->written+=count;return true;
}
static bool quote(writer *w,const char *text,size_t count) {
  if (!write_bytes(w,"\"",1)) return false;
  size_t begin=0;
  static const char hex[]="0123456789abcdef";
  for (size_t i=0;i<count;++i) {
    const unsigned char c=(unsigned char)text[i];
    if (c>=0x20 && c!='"' && c!='\\') continue;
    if (!write_bytes(w,text+begin,i-begin)) return false;
    const char *escape=NULL;
    switch (c) {
    case '"':escape="\\\"";break;case '\\':escape="\\\\";break;
    case '\b':escape="\\b";break;case '\f':escape="\\f";break;
    case '\n':escape="\\n";break;case '\r':escape="\\r";break;case '\t':escape="\\t";break;
    default:break;
    }
    if (escape) { if (!write_bytes(w,escape,2)) return false; }
    else {
      char code[6]={'\\','u','0','0',hex[c>>4],hex[c&15]};
      if (!write_bytes(w,code,sizeof(code))) return false;
    }
    begin=i+1;
  }
  return write_bytes(w,text+begin,count-begin) && write_bytes(w,"\"",1);
}
typedef struct { const lie_json_value *node;size_t index; } dump_frame;
lie_json_value_status lie_json_value_dump(const lie_json_value *root,const lie_json_value_sink *sink) {
  if (!sink || !sink->write) return LIE_JSON_VALUE_INVALID;
  const size_t limit=root ? root->owner->d.max_work : 256u*1024u*1024u;
  writer w={sink,0,limit,LIE_JSON_VALUE_OK};
  dump_frame frames[LIE_JSON_VALUE_MAX_DEPTH];size_t count=0;
  const lie_json_value *n=root;
  for (;;) {
    const lie_json_value_kind kind=lie_json_value_type(n);
    if (kind==LIE_JSON_VALUE_OBJECT || kind==LIE_JSON_VALUE_ARRAY) {
      if (count>=LIE_JSON_VALUE_MAX_DEPTH) return LIE_JSON_VALUE_LIMIT;
      if (!write_bytes(&w,kind==LIE_JSON_VALUE_OBJECT ? "{" : "[",1)) return w.status;
      frames[count++]=(dump_frame){n,0};
    } else {
      bool ok=true;
      switch (kind) {
      case LIE_JSON_VALUE_NULL:ok=write_bytes(&w,"null",4);break;
      case LIE_JSON_VALUE_BOOL:ok=write_bytes(&w,n->boolean ? "true" : "false",n->boolean ? 4 : 5);break;
      case LIE_JSON_VALUE_NUMBER: {
        if (!isfinite(n->number)) return LIE_JSON_VALUE_NONFINITE;
        char text[LIE_BINARY64_TEXT_CAPACITY];size_t bytes=0;
        if (lie_binary64_format(n->number,text,sizeof(text),&bytes)!=LIE_BINARY64_OK)
          return LIE_JSON_VALUE_INVALID;
        ok=write_bytes(&w,text,bytes);break;
      }
      case LIE_JSON_VALUE_STRING:ok=quote(&w,n->text ? n->text : empty,n->text_bytes);break;
      default:return LIE_JSON_VALUE_INVALID;
      }
      if (!ok) return w.status;
    }
    bool next=false;
    while (count) {
      dump_frame *f=&frames[count-1];const bool object=f->node->kind==LIE_JSON_VALUE_OBJECT;
      const table *t=object ? &f->node->object : &f->node->array;
      if (f->index==t->count) {
        if (!write_bytes(&w,object ? "}" : "]",1)) return w.status;
        --count;continue;
      }
      if (f->index && !write_bytes(&w,",",1)) return w.status;
      n=t->data[f->index++];
      if (object && (!quote(&w,n->key ? n->key : empty,n->key_bytes) || !write_bytes(&w,":",1))) return w.status;
      next=true;break;
    }
    if (!next) return LIE_JSON_VALUE_OK;
  }
}
