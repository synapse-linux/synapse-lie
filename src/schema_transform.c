/* SPDX-License-Identifier: MIT */
/* Schema algorithms adapted independently from the pinned Gufo compiler;
 * provenance and retained leaf policies are recorded in third_party/gufo-NOTICE. */
#include "lie/schema_transform.h"
#include "schema_internal.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef lie_schema_context context;
typedef struct { lie_schema_node a, b; } pair;
#define TRY(call) do { lie_schema_status rc_ = (call); if (rc_ != LIE_SCHEMA_OK) return rc_; } while (0)
static lie_schema_status fail(context *c, lie_schema_status rc, const char *msg) {
  if (c->error) *c->error = (lie_schema_error){msg,{NULL,0},""};
  return rc;
}
static lie_schema_status detail(context *c, const char *msg, lie_schema_bytes key, const char *suffix) {
  if (c->error) *c->error = (lie_schema_error){msg,key,suffix};
  return LIE_SCHEMA_INVALID;
}
static lie_schema_status tick(context *c, size_t n) {
  if (n > c->d->max_work - c->work)
    return fail(c,LIE_SCHEMA_WORK_LIMIT,"schema transformation work limit exceeded");
  c->work += n; return LIE_SCHEMA_OK;
}
static void *allocate(context *c, size_t n) {
  if (c->d->allocator.allocate)
    return c->d->allocator.allocate(c->d->allocator.context,n);
  return malloc(n);
}
static void release(context *c, void *p) {
  if (!p) return;
  if (c->d->allocator.release) c->d->allocator.release(c->d->allocator.context,p);
  else free(p);
}
static bool bytes_equal(lie_schema_bytes a, lie_schema_bytes b) {
  return a.size == b.size && (!a.size || !memcmp(a.data,b.data,a.size));
}
static bool key_is(lie_schema_bytes a, const char *b) {
  return bytes_equal(a,(lie_schema_bytes){b,strlen(b)});
}
static lie_schema_status describe(context *c, lie_schema_node n, lie_schema_value *v) {
  TRY(tick(c,1));
  if (!n) return fail(c,LIE_SCHEMA_INVALID,"invalid schema node");
  memset(v,0,sizeof(*v));
  TRY(c->d->access.describe(c->d->access.context,n,v));
  if ((unsigned)v->kind > LIE_SCHEMA_OBJECT || (v->text.size && !v->text.data))
    return fail(c,LIE_SCHEMA_INVALID,"invalid schema node view");
  return LIE_SCHEMA_OK;
}
static lie_schema_status child(context *c, lie_schema_node n, size_t i, lie_schema_bytes *key, lie_schema_node *out) {
  TRY(tick(c,1)); *key=(lie_schema_bytes){NULL,0}; *out=NULL;
  TRY(c->d->access.child(c->d->access.context,n,i,key,out));
  if (!*out || (key->size && !key->data)) return fail(c,LIE_SCHEMA_INVALID,"invalid schema child view");
  return LIE_SCHEMA_OK;
}
static lie_schema_status find(context *c, lie_schema_node n, lie_schema_bytes key, lie_schema_node *out) {
  lie_schema_value v; TRY(describe(c,n,&v)); *out=NULL;
  if (v.kind != LIE_SCHEMA_OBJECT) return LIE_SCHEMA_OK;
  for (size_t i=0;i<v.count;++i) {
    lie_schema_bytes k; lie_schema_node item; TRY(child(c,n,i,&k,&item));
    TRY(tick(c,k.size)); if (bytes_equal(k,key)) { *out=item; break; }
  }
  return LIE_SCHEMA_OK;
}
static lie_schema_status field(context *c, lie_schema_node n, const char *key, lie_schema_node *out) {
  return find(c,n,(lie_schema_bytes){key,strlen(key)},out);
}
static lie_schema_status equal(context *c, lie_schema_node a, lie_schema_node b, bool *out) {
  pair local[16]={{a,b}}, *stack=local; size_t count=1,capacity=16; bool result=true;
  lie_schema_status rc=LIE_SCHEMA_OK;
  while (count && result) {
    const pair p=stack[--count]; lie_schema_value av,bv;
    rc=describe(c,p.a,&av); if (rc) break;
    rc=describe(c,p.b,&bv); if (rc) break;
    if (av.kind != bv.kind) { result=false; break; }
    if (av.kind == LIE_SCHEMA_NUMBER) result=av.number==bv.number;
    else if (av.kind == LIE_SCHEMA_BOOL) result=av.boolean==bv.boolean;
    else if (av.kind == LIE_SCHEMA_STRING) {
      rc=tick(c,av.text.size); if (rc) break;
      result=bytes_equal(av.text,bv.text);
    } else if (av.kind == LIE_SCHEMA_ARRAY || av.kind == LIE_SCHEMA_OBJECT) {
      if (av.count != bv.count) { result=false; break; }
      if (av.count > c->d->max_pairs-count) { rc=fail(c,LIE_SCHEMA_WORK_LIMIT,"schema equality pair limit exceeded"); break; }
      const size_t needed=count+av.count;
      if (needed > capacity) {
        size_t cap=capacity;
        while (cap<needed) cap=cap>c->d->max_pairs/2 ? c->d->max_pairs : cap*2;
        if (cap>SIZE_MAX/sizeof(pair)) { rc=fail(c,LIE_SCHEMA_RESOURCE,"schema equality storage overflow"); break; }
        pair *next=allocate(c,cap*sizeof(*next));
        if (!next) { rc=fail(c,LIE_SCHEMA_RESOURCE,"schema equality allocation failed"); break; }
        if (count) memcpy(next,stack,count*sizeof(*next));
        if (stack!=local) release(c,stack);
        stack=next; capacity=cap;
      }
      for (size_t i=0;i<av.count;++i) {
        lie_schema_bytes ak,bk; lie_schema_node an,bn;
        rc=child(c,p.a,i,&ak,&an); if (rc) break;
        if (av.kind==LIE_SCHEMA_OBJECT) rc=find(c,p.b,ak,&bn);
        else rc=child(c,p.b,i,&bk,&bn);
        if (rc) break;
        if (!bn) { result=false; break; }
        stack[count++]=(pair){an,bn};
      }
      if (rc) break;
    }
  }
  if (stack!=local) release(c,stack);
  if (!rc) *out=result;
  return rc;
}
static lie_schema_status reference(context *c, lie_schema_node root, lie_schema_node ref, lie_schema_node *out) {
  lie_schema_value v; TRY(describe(c,ref,&v));
  if (v.kind!=LIE_SCHEMA_STRING || !v.text.size || v.text.data[0]!='#' ||
      (v.text.size>1 && v.text.data[1]!='/'))
    return fail(c,LIE_SCHEMA_INVALID,"only local JSON pointer references are supported");
  if (v.text.size==1) { *out=root; return LIE_SCHEMA_OK; }
  TRY(tick(c,v.text.size));
  char *decoded=allocate(c,v.text.size);
  if (!decoded) return fail(c,LIE_SCHEMA_RESOURCE,"JSON pointer allocation failed");
  lie_schema_status rc=LIE_SCHEMA_OK; lie_schema_node target=root;
  size_t offset=2;
  for (;;) {
    size_t end=offset; while (end<v.text.size && v.text.data[end]!='/') ++end;
    size_t n=0;
    for (size_t i=offset;i<end;++i) {
      char ch=v.text.data[i];
      if (ch=='~') {
        if (++i==end || (v.text.data[i]!='0' && v.text.data[i]!='1')) {
          rc=fail(c,LIE_SCHEMA_INVALID,"invalid JSON pointer escape"); break;
        }
        ch=v.text.data[i]=='0' ? '~' : '/';
      }
      decoded[n++]=ch;
    }
    if (rc) break;
    lie_schema_value tv; rc=describe(c,target,&tv); if (rc) break;
    if (tv.kind==LIE_SCHEMA_ARRAY) {
      size_t index=0; bool valid=n!=0;
      for (size_t i=0;i<n && valid;++i) {
        const unsigned digit=(unsigned char)decoded[i]-'0';
        if (digit>9 || index>(SIZE_MAX-digit)/10) valid=false;
        else index=index*10+digit;
      }
      if (valid && index<tv.count) {
        lie_schema_bytes ignored; rc=child(c,target,index,&ignored,&target);
      } else target=NULL;
    } else rc=find(c,target,(lie_schema_bytes){decoded,n},&target);
    if (rc) break;
    if (!target) { rc=fail(c,LIE_SCHEMA_INVALID,"local reference does not exist"); break; }
    if (end==v.text.size) break;
    offset=end+1;
  }
  release(c,decoded); if (!rc) *out=target; return rc;
}
static lie_schema_status keys(context *c, lie_schema_node n) {
  static const char *const allowed[]={"type","properties","required","additionalProperties","items","minItems","maxItems","enum","const","anyOf","$defs","$ref","title","description","minimum","maximum","exclusiveMinimum","exclusiveMaximum","multipleOf","pattern","format","minLength","maxLength"};
  lie_schema_value v; TRY(describe(c,n,&v));
  if (v.kind!=LIE_SCHEMA_OBJECT) return fail(c,LIE_SCHEMA_INVALID,"each schema must be an object");
  for (size_t i=0;i<v.count;++i) {
    lie_schema_bytes k; lie_schema_node item; TRY(child(c,n,i,&k,&item));
    bool known=false; TRY(tick(c,k.size));
    for (size_t j=0;j<sizeof(allowed)/sizeof(*allowed);++j) if (key_is(k,allowed[j])) { known=true; break; }
    if (!known) return detail(c,"unsupported keyword: ",k,"");
    if (key_is(k,"title") || key_is(k,"description") || key_is(k,"anyOf")) {
      lie_schema_value iv; TRY(describe(c,item,&iv));
      if (key_is(k,"anyOf")) {
        if (iv.kind!=LIE_SCHEMA_ARRAY || !iv.count) return fail(c,LIE_SCHEMA_INVALID,"anyOf needs at least one branch");
      } else if (iv.kind!=LIE_SCHEMA_STRING) return detail(c,"",k," must be a string");
    }
  }
  return LIE_SCHEMA_OK;
}
static lie_schema_status clone(context *c, lie_schema_node n, lie_schema_node *out) {
  TRY(tick(c,1)); *out=NULL; TRY(c->d->access.clone(c->d->access.context,n,out));
  return *out ? LIE_SCHEMA_OK : fail(c,LIE_SCHEMA_INVALID,"invalid schema writer node");
}
static lie_schema_status create(context *c, lie_schema_value v, lie_schema_node *out) {
  TRY(tick(c,1)); *out=NULL; TRY(c->d->access.create(c->d->access.context,&v,out));
  return *out ? LIE_SCHEMA_OK : fail(c,LIE_SCHEMA_INVALID,"invalid schema writer node");
}
static lie_schema_status put(context *c, lie_schema_node n, lie_schema_bytes k, lie_schema_node v) {
  TRY(tick(c,1)); return c->d->access.put(c->d->access.context,n,k,v);
}
static lie_schema_status append(context *c, lie_schema_node n, lie_schema_node v) {
  TRY(tick(c,1)); return c->d->access.append(c->d->access.context,n,v);
}
static lie_schema_status without(context *c, lie_schema_node n, const char *a, const char *b, lie_schema_node *out) {
  lie_schema_node result; TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_OBJECT},&result));
  lie_schema_value v; TRY(describe(c,n,&v));
  for (size_t i=0;i<v.count;++i) {
    lie_schema_bytes k; lie_schema_node item; TRY(child(c,n,i,&k,&item));
    if (!key_is(k,a) && (!b || !key_is(k,b))) TRY(put(c,result,k,item));
  }
  *out=result; return LIE_SCHEMA_OK;
}
static lie_schema_status permits(context *c, lie_schema_node n, lie_schema_bytes key, bool *out) {
  lie_schema_node closed,fields,item=NULL; TRY(field(c,n,"additionalProperties",&closed));
  lie_schema_value v={0}; if (closed) TRY(describe(c,closed,&v));
  if (!closed || (v.kind==LIE_SCHEMA_BOOL && v.boolean)) { *out=true; return LIE_SCHEMA_OK; }
  TRY(field(c,n,"properties",&fields)); if (fields) TRY(find(c,fields,key,&item));
  *out=item!=NULL; return LIE_SCHEMA_OK;
}
static lie_schema_status closed(context *c, lie_schema_node n, bool *out) {
  lie_schema_node item; TRY(field(c,n,"additionalProperties",&item));
  lie_schema_value v={0}; if (item) TRY(describe(c,item,&v));
  *out=item && !(v.kind==LIE_SCHEMA_BOOL && v.boolean); return LIE_SCHEMA_OK;
}
static lie_schema_status conjoin(context *c, lie_schema_node root, lie_schema_node left, lie_schema_node right, unsigned depth, lie_schema_node *out) {
  if (depth>64) return fail(c,LIE_SCHEMA_INVALID,"schema intersection exceeds its reference budget");
  TRY(keys(c,left)); TRY(keys(c,right));
  lie_schema_node ref;
  TRY(field(c,left,"$ref",&ref));
  if (ref) {
    lie_schema_node target,siblings,merged; TRY(reference(c,root,ref,&target));
    TRY(without(c,left,"$ref","$defs",&siblings));
    TRY(conjoin(c,root,target,siblings,depth+1,&merged));
    return conjoin(c,root,merged,right,depth+1,out);
  }
  TRY(field(c,right,"$ref",&ref));
  if (ref) {
    lie_schema_node target,siblings,merged; TRY(reference(c,root,ref,&target));
    TRY(without(c,right,"$ref","$defs",&siblings));
    TRY(conjoin(c,root,target,siblings,depth+1,&merged));
    return conjoin(c,root,left,merged,depth+1,out);
  }
  lie_schema_node any; TRY(field(c,left,"anyOf",&any));
  if (any) {
    lie_schema_node result,branches,siblings,base;
    TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_OBJECT},&result));
    TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_ARRAY},&branches));
    TRY(without(c,left,"anyOf",NULL,&base));
    TRY(conjoin(c,root,base,right,depth+1,&siblings));
    lie_schema_value av; TRY(describe(c,any,&av)); size_t count=0;
    for (size_t i=0;i<av.count;++i) {
      lie_schema_bytes ignored; lie_schema_node branch,merged; TRY(child(c,any,i,&ignored,&branch));
      lie_schema_status rc=conjoin(c,root,branch,siblings,depth+1,&merged);
      if (rc==LIE_SCHEMA_EMPTY) continue;
      if (rc) return rc;
      TRY(append(c,branches,merged)); ++count;
    }
    if (!count) return fail(c,LIE_SCHEMA_EMPTY,"schema intersection is empty");
    TRY(put(c,result,(lie_schema_bytes){"anyOf",5},branches)); *out=result; return LIE_SCHEMA_OK;
  }
  TRY(field(c,right,"anyOf",&any)); if (any) return conjoin(c,root,right,left,depth+1,out);
  lie_schema_node rf,lf; TRY(field(c,right,"format",&rf)); TRY(field(c,left,"format",&lf));
  if (rf && lf) {
    bool same; TRY(equal(c,lf,rf,&same));
    if (!same) {
      lie_schema_value fv; TRY(describe(c,rf,&fv));
      if (fv.kind!=LIE_SCHEMA_STRING) return fail(c,LIE_SCHEMA_INVALID,"format must be a string");
      lie_schema_node base,format=NULL,merged; TRY(without(c,right,"format",NULL,&base));
      lie_schema_status frc=c->d->access.format(c->d->access.context,fv.text,&format);
      if (frc) {
        if (frc==LIE_SCHEMA_EMPTY && c->error) *c->error=(lie_schema_error){0};
        return frc;
      }
      if (!format) return fail(c,LIE_SCHEMA_INVALID,"invalid schema writer node");
      TRY(conjoin(c,root,base,format,depth+1,&merged));
      return conjoin(c,root,left,merged,depth+1,out);
    }
  }
  lie_schema_node result; TRY(clone(c,left,&result));
  lie_schema_value rv; TRY(describe(c,right,&rv));
  for (size_t i=0;i<rv.count;++i) {
    lie_schema_bytes k; lie_schema_node value,previous; TRY(child(c,right,i,&k,&value));
    TRY(find(c,left,k,&previous));
    if (key_is(k,"title") || key_is(k,"description") || !previous) { TRY(put(c,result,k,value)); continue; }
    bool same; TRY(equal(c,previous,value,&same)); if (same) continue;
    lie_schema_value pv,vv; TRY(describe(c,previous,&pv)); TRY(describe(c,value,&vv));
    if (key_is(k,"minimum") || key_is(k,"exclusiveMinimum") || key_is(k,"minLength") || key_is(k,"minItems") || key_is(k,"maximum") || key_is(k,"exclusiveMaximum") || key_is(k,"maxLength") || key_is(k,"maxItems")) {
      if (pv.kind!=LIE_SCHEMA_NUMBER || vv.kind!=LIE_SCHEMA_NUMBER) return fail(c,LIE_SCHEMA_INVALID,"bounds must be numbers");
      const bool lower=(k.size>=3 && !memcmp(k.data,"min",3)) || key_is(k,"exclusiveMinimum");
      const double number=lower ? (pv.number<vv.number ? vv.number : pv.number) : (vv.number<pv.number ? vv.number : pv.number);
      lie_schema_node n; TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_NUMBER,.number=number},&n)); TRY(put(c,result,k,n));
    } else if (key_is(k,"multipleOf")) {
      lie_schema_node n=NULL;
      lie_schema_status mrc=c->d->access.multiple(c->d->access.context,previous,value,&n);
      if (mrc) {
        if (mrc==LIE_SCHEMA_EMPTY && c->error) *c->error=(lie_schema_error){0};
        return mrc;
      }
      if (!n) return fail(c,LIE_SCHEMA_INVALID,"invalid schema writer node");
      TRY(put(c,result,k,n));
    } else if (key_is(k,"pattern")) {
      if (pv.kind!=LIE_SCHEMA_STRING || vv.kind!=LIE_SCHEMA_STRING) return fail(c,LIE_SCHEMA_INVALID,"pattern must be a string");
      const char *prefix="(?=[\\s\\S]*(?:", *middle="))(?=[\\s\\S]*(?:", *suffix="))";
      const size_t overhead=strlen(prefix)+strlen(middle)+strlen(suffix);
      if (pv.text.size>SIZE_MAX-overhead || vv.text.size>SIZE_MAX-overhead-pv.text.size) return fail(c,LIE_SCHEMA_RESOURCE,"pattern intersection storage overflow");
      const size_t n=overhead+pv.text.size+vv.text.size; TRY(tick(c,n)); char *p=allocate(c,n);
      if (!p) return fail(c,LIE_SCHEMA_RESOURCE,"pattern intersection allocation failed");
      size_t at=0;
      memcpy(p+at,prefix,strlen(prefix)); at+=strlen(prefix);
      if (pv.text.size) memcpy(p+at,pv.text.data,pv.text.size);
      at+=pv.text.size;
      memcpy(p+at,middle,strlen(middle)); at+=strlen(middle);
      if (vv.text.size) memcpy(p+at,vv.text.data,vv.text.size);
      at+=vv.text.size;
      memcpy(p+at,suffix,strlen(suffix)); lie_schema_node node=NULL;
      lie_schema_status rc=create(c,(lie_schema_value){.kind=LIE_SCHEMA_STRING,.text={p,n}},&node);
      release(c,p); if (rc) return rc; TRY(put(c,result,k,node));
    } else if (key_is(k,"required") || key_is(k,"enum")) {
      const bool enumeration=key_is(k,"enum");
      if (pv.kind!=LIE_SCHEMA_ARRAY || vv.kind!=LIE_SCHEMA_ARRAY) return fail(c,LIE_SCHEMA_INVALID,enumeration ? "enum must be an array" : "required must be an array");
      lie_schema_node list; if (enumeration) TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_ARRAY},&list));
      else { TRY(field(c,result,"required",&list)); }
      const lie_schema_node source=enumeration ? previous : value, other=enumeration ? value : previous;
      const size_t sn=enumeration ? pv.count : vv.count, on=enumeration ? vv.count : pv.count; size_t kept=0;
      for (size_t j=0;j<sn;++j) {
        lie_schema_bytes ignored; lie_schema_node item; TRY(child(c,source,j,&ignored,&item)); bool matched=false;
        for (size_t t=0;t<on;++t) { lie_schema_node old; TRY(child(c,other,t,&ignored,&old)); TRY(equal(c,item,old,&matched)); if (matched) break; }
        if (matched==enumeration) { TRY(append(c,list,item)); ++kept; }
      }
      if (enumeration && !kept) return fail(c,LIE_SCHEMA_EMPTY,"enum intersection is empty");
      TRY(put(c,result,k,list));
    } else if (key_is(k,"type")) {
      lie_schema_node common; TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_ARRAY},&common)); size_t count=0; lie_schema_node last=NULL;
      const size_t pn=pv.kind==LIE_SCHEMA_ARRAY ? pv.count : 1, vn=vv.kind==LIE_SCHEMA_ARRAY ? vv.count : 1;
      for (size_t j=0;j<pn;++j) for (size_t t=0;t<vn;++t) {
        lie_schema_node a=previous,b=value; lie_schema_bytes ignored;
        if (pv.kind==LIE_SCHEMA_ARRAY) TRY(child(c,previous,j,&ignored,&a));
        if (vv.kind==LIE_SCHEMA_ARRAY) TRY(child(c,value,t,&ignored,&b));
        TRY(equal(c,a,b,&same));
        if (same) last=a;
        else {
          lie_schema_value av,bv; TRY(describe(c,a,&av)); TRY(describe(c,b,&bv));
          if (!((key_is(av.text,"number") && key_is(bv.text,"integer")) || (key_is(av.text,"integer") && key_is(bv.text,"number")))) continue;
          TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_STRING,.text={"integer",7}},&last));
        }
        TRY(append(c,common,last)); ++count;
      }
      if (!count) return fail(c,LIE_SCHEMA_EMPTY,"schema constraints have no common type");
      TRY(put(c,result,k,count==1 ? last : common));
    } else if (key_is(k,"items")) {
      lie_schema_node n; TRY(conjoin(c,root,previous,value,depth+1,&n)); TRY(put(c,result,k,n));
    } else if (key_is(k,"properties")) {
      if (pv.kind!=LIE_SCHEMA_OBJECT || vv.kind!=LIE_SCHEMA_OBJECT) return fail(c,LIE_SCHEMA_INVALID,"properties must be an object");
      bool lc,rc; TRY(closed(c,left,&lc)); TRY(closed(c,right,&rc));
      lie_schema_node properties; TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_OBJECT},&properties));
      for (size_t j=0;j<pv.count;++j) {
        lie_schema_bytes name; lie_schema_node n,other; TRY(child(c,previous,j,&name,&n)); TRY(find(c,value,name,&other));
        if (other) { lie_schema_node merged; TRY(conjoin(c,root,n,other,depth+1,&merged)); TRY(put(c,properties,name,merged)); }
        else if (!rc) TRY(put(c,properties,name,n));
      }
      if (!lc) for (size_t j=0;j<vv.count;++j) {
        lie_schema_bytes name; lie_schema_node n,other; TRY(child(c,value,j,&name,&n)); TRY(find(c,previous,name,&other)); if (!other) TRY(put(c,properties,name,n));
      }
      TRY(put(c,result,k,properties));
    } else {
      if (key_is(k,"const")) return fail(c,LIE_SCHEMA_EMPTY,"const intersection is empty");
      return detail(c,"incompatible schema constraints for ",k,"");
    }
  }
  lie_schema_node properties; TRY(field(c,result,"properties",&properties));
  if (properties) {
    lie_schema_node allowed; TRY(create(c,(lie_schema_value){.kind=LIE_SCHEMA_OBJECT},&allowed));
    lie_schema_value v; TRY(describe(c,properties,&v));
    for (size_t i=0;v.kind==LIE_SCHEMA_OBJECT && i<v.count;++i) {
      lie_schema_bytes name; lie_schema_node item; TRY(child(c,properties,i,&name,&item));
      bool lp,rp; TRY(permits(c,left,name,&lp)); TRY(permits(c,right,name,&rp)); if (lp && rp) TRY(put(c,allowed,name,item));
    }
    TRY(put(c,result,(lie_schema_bytes){"properties",10},allowed));
  }
  *out=result; return LIE_SCHEMA_OK;
}
void lie_schema_transform_description_init(lie_schema_transform_description *d) {
  if (!d) return;
  memset(d,0,sizeof(*d)); d->abi_version=LIE_SCHEMA_TRANSFORM_ABI;
  d->struct_bytes=sizeof(*d); d->max_work=64000000; d->max_pairs=262144;
}
static bool valid(const lie_schema_transform_description *d) {
  return d && d->abi_version==LIE_SCHEMA_TRANSFORM_ABI && d->struct_bytes==sizeof(*d) &&
    d->max_work && d->max_pairs && d->max_pairs<=SIZE_MAX/sizeof(pair) &&
    (!!d->allocator.allocate==!!d->allocator.release) && d->access.describe && d->access.child;
}
lie_schema_status lie_schema_equal(const lie_schema_transform_description *d, lie_schema_node a, lie_schema_node b, bool *out, lie_schema_error *e) {
  if (!valid(d) || !a || !b || !out) return LIE_SCHEMA_INVALID;
  context c={d,0,e}; return equal(&c,a,b,out);
}
lie_schema_status lie_schema_reference(const lie_schema_transform_description *d, lie_schema_node root, lie_schema_node ref, lie_schema_node *out, lie_schema_error *e) {
  if (!valid(d) || !root || !ref || !out) return LIE_SCHEMA_INVALID;
  context c={d,0,e}; return reference(&c,root,ref,out);
}
lie_schema_status lie_schema_keys(const lie_schema_transform_description *d, lie_schema_node n, lie_schema_error *e) {
  if (!valid(d) || !n) return LIE_SCHEMA_INVALID;
  context c={d,0,e}; return keys(&c,n);
}
lie_schema_status lie_schema_conjoin(const lie_schema_transform_description *d, lie_schema_node root, lie_schema_node left, lie_schema_node right, unsigned depth, lie_schema_node *out, lie_schema_error *e) {
  if (!valid(d) || !root || !left || !right || !out || !d->access.clone || !d->access.create || !d->access.put || !d->access.append || !d->access.format || !d->access.multiple) return LIE_SCHEMA_INVALID;
  context c={d,0,e}; return conjoin(&c,root,left,right,depth,out);
}
bool lie_schema_internal_valid(const lie_schema_transform_description *d) { return valid(d); }
lie_schema_status lie_schema_internal_tick(context *c,size_t n) { return tick(c,n); }
lie_schema_status lie_schema_internal_fail(context *c,lie_schema_status r,const char *s) { return fail(c,r,s); }
void *lie_schema_internal_allocate(context *c,size_t n) { return allocate(c,n); }
void lie_schema_internal_release(context *c,void *p) { release(c,p); }
lie_schema_status lie_schema_internal_describe(context *c,lie_schema_node n,lie_schema_value *v) { return describe(c,n,v); }
lie_schema_status lie_schema_internal_child(context *c,lie_schema_node n,size_t i,lie_schema_bytes *k,lie_schema_node *v) { return child(c,n,i,k,v); }
lie_schema_status lie_schema_internal_find(context *c,lie_schema_node n,lie_schema_bytes k,lie_schema_node *v) { return find(c,n,k,v); }
lie_schema_status lie_schema_internal_field(context *c,lie_schema_node n,const char *k,lie_schema_node *v) { return field(c,n,k,v); }
lie_schema_status lie_schema_internal_equal(context *c,lie_schema_node a,lie_schema_node b,bool *v) { return equal(c,a,b,v); }
lie_schema_status lie_schema_internal_reference(context *c,lie_schema_node n,lie_schema_node r,lie_schema_node *v) { return reference(c,n,r,v); }
lie_schema_status lie_schema_internal_clone(context *c,lie_schema_node n,lie_schema_node *v) { return clone(c,n,v); }
lie_schema_status lie_schema_internal_create(context *c,lie_schema_value n,lie_schema_node *v) { return create(c,n,v); }
lie_schema_status lie_schema_internal_put(context *c,lie_schema_node n,lie_schema_bytes k,lie_schema_node v) { return put(c,n,k,v); }
lie_schema_status lie_schema_internal_append(context *c,lie_schema_node n,lie_schema_node v) { return append(c,n,v); }
