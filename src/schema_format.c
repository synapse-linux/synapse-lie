/* SPDX-License-Identifier: MIT */
/* Pinned format patterns and IPv6 alternative ordering adapted from official
 * MIT Gufo json_schema_lexeme.cpp. LIE owns bounded C17 construction/publication.
 * Provenance and preserved limitations are recorded in gufo-NOTICE. */
#include "lie/schema_format.h"
#include "schema_internal.h"
#include <stdint.h>
#include <string.h>

#define FORMAT_LEAP "(?:[0-9]{2}(?:0[48]|[2468][048]|[13579][26])|(?:[02468][048]|[13579][26])00)"
#define FORMAT_DATE "(?:[0-9]{4}-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12][0-9]|3[01])|(?:0[469]|11)-(?:0[1-9]|[12][0-9]|30)|02-(?:0[1-9]|1[0-9]|2[0-8]))|" FORMAT_LEAP "-02-29)"
#define FORMAT_TIME "(?:[01][0-9]|2[0-3]):[0-5][0-9]:(?:[0-5][0-9]|60)(?:\\.[0-9]+)?(?:[zZ]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
#define FORMAT_IPV4 "(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
#define TRY(call) do { lie_schema_status rc_ = (call); if (rc_ != LIE_SCHEMA_OK) return rc_; } while (0)
typedef struct { char bytes[LIE_SCHEMA_FORMAT_PATTERN_CAPACITY]; size_t size; } pattern;
static lie_schema_status error(lie_schema_error *e, lie_schema_status status, const char *message) {
  if (e) *e=(lie_schema_error){message,{NULL,0},""};
  return status;
}
static bool named(lie_schema_bytes name, const char *text) {
  size_t n=strlen(text);
  return name.size==n && !memcmp(name.data,text,n);
}
static lie_schema_status append(pattern *p, const char *text) {
  size_t n=strlen(text);
  if (n>sizeof(p->bytes)-p->size) return LIE_SCHEMA_RESOURCE;
  memcpy(p->bytes+p->size,text,n); p->size+=n; return LIE_SCHEMA_OK;
}
static lie_schema_status groups(pattern *p, unsigned count) {
  for (unsigned i=0;i<count;++i) {
    if (i) TRY(append(p,":"));
    TRY(append(p,"[0-9a-fA-F]{1,4}"));
  }
  return LIE_SCHEMA_OK;
}
static lie_schema_status build(lie_schema_bytes name, pattern *p) {
  if (named(name,"date")) return append(p,"^" FORMAT_DATE "$");
  if (named(name,"time")) return append(p,"^" FORMAT_TIME "$");
  if (named(name,"date-time")) return append(p,"^" FORMAT_DATE "[tT]" FORMAT_TIME "$");
  if (named(name,"uuid")) return append(p,"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$");
  if (named(name,"ipv4")) return append(p,"^" FORMAT_IPV4 "$");
  if (named(name,"hostname")) return append(p,"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\\.?$");
  if (named(name,"email")) return append(p,"^[^@\\s]+@[^@\\s]+$");
  if (named(name,"duration")) return append(p,"^P(?:[0-9]+W|(?=[0-9]|T[0-9])(?:[0-9]+Y)?(?:[0-9]+M)?(?:[0-9]+D)?(?:T(?=[0-9])(?:[0-9]+H)?(?:[0-9]+M)?(?:[0-9]+(?:\\.[0-9]+)?S)?)?)$");
  if (!named(name,"ipv6")) return LIE_SCHEMA_INVALID;
  TRY(append(p,"^(?:")); TRY(groups(p,8));
  for (unsigned left=0;left<8;++left) for (unsigned right=0;left+right<8;++right) {
    TRY(append(p,"|")); TRY(groups(p,left)); TRY(append(p,"::")); TRY(groups(p,right));
  }
  TRY(append(p,"|")); TRY(groups(p,6)); TRY(append(p,":" FORMAT_IPV4));
  for (unsigned left=0;left<6;++left) for (unsigned right=0;left+right<6;++right) {
    TRY(append(p,"|")); TRY(groups(p,left)); TRY(append(p,"::")); TRY(groups(p,right));
    if (right) TRY(append(p,":"));
    TRY(append(p,FORMAT_IPV4));
  }
  return append(p,")$");
}
lie_schema_status lie_schema_format_pattern(lie_schema_bytes name,
    char *out, size_t capacity, size_t *bytes, lie_schema_error *e) {
  if ((name.size && !name.data) || !out || !bytes)
    return error(e,LIE_SCHEMA_INVALID,"invalid string format input");
  uintptr_t input=(uintptr_t)name.data, output=(uintptr_t)out;
  if (name.size>UINTPTR_MAX-input || capacity>UINTPTR_MAX-output ||
      (name.size && capacity && input<output+capacity && output<input+name.size))
    return error(e,LIE_SCHEMA_INVALID,"overlapping string format storage");
  pattern p={0};
  lie_schema_status rc=build(name,&p);
  if (rc==LIE_SCHEMA_INVALID) return error(e,rc,"unsupported string format");
  if (rc!=LIE_SCHEMA_OK || p.size>capacity)
    return error(e,LIE_SCHEMA_RESOURCE,"string format pattern capacity exceeded");
  memcpy(out,p.bytes,p.size); *bytes=p.size; return LIE_SCHEMA_OK;
}
lie_schema_status lie_schema_format_expand(const lie_schema_transform_description *d,
    lie_schema_bytes name, lie_schema_node *out, lie_schema_error *e) {
  if (!lie_schema_internal_valid(d) || !d->access.create || !d->access.put || !out)
    return error(e,LIE_SCHEMA_INVALID,"invalid string format writer");
  char text[LIE_SCHEMA_FORMAT_PATTERN_CAPACITY]; size_t bytes=0;
  TRY(lie_schema_format_pattern(name,text,sizeof(text),&bytes,e));
  lie_schema_context c={d,0,e};
  lie_schema_node object=NULL, value=NULL;
  TRY(lie_schema_internal_tick(&c,bytes));
  TRY(lie_schema_internal_create(&c,(lie_schema_value){.kind=LIE_SCHEMA_OBJECT},&object));
  TRY(lie_schema_internal_create(&c,(lie_schema_value){.kind=LIE_SCHEMA_STRING,.text={text,bytes}},&value));
  TRY(lie_schema_internal_put(&c,object,(lie_schema_bytes){"pattern",7},value));
  if (named(name,"hostname")) {
    TRY(lie_schema_internal_create(&c,(lie_schema_value){.kind=LIE_SCHEMA_NUMBER,.number=253},&value));
    TRY(lie_schema_internal_put(&c,object,(lie_schema_bytes){"maxLength",9},value));
  }
  *out=object; return LIE_SCHEMA_OK;
}
