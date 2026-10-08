/* SPDX-License-Identifier: MIT */
/* String/Unicode primitive runtime port from independently pinned official MIT
 * Gufo f783fedb9bea2ec7de941f6da4e02f4a4596b29e, json_schema_lexeme.cpp. */
#include "lie/grammar_string.h"
#include <string.h>
enum { BODY, ESCAPE, HEX, LOW_SLASH, LOW_U, LOW_HEX, UTF8 };
enum { DFA, COUNT, VALUE, EXTRA, MODE, FIELDS };
typedef struct { uint32_t field[FIELDS]; } state;
_Static_assert(sizeof(state) == LIE_STRING_STATE_BYTES, "string state layout");
static lie_string_status regex_status(lie_regex_status s) {
  switch (s) {
  case LIE_REGEX_OK: return LIE_STRING_OK;
  case LIE_REGEX_RESOURCE: return LIE_STRING_RESOURCE;
  case LIE_REGEX_WORK_LIMIT: return LIE_STRING_WORK_LIMIT;
  default: return LIE_STRING_STATE;
  }
}
#define TRY(x) do { lie_string_status rc_ = (x); if (rc_ != LIE_STRING_OK) return rc_; } while (0)
static uint32_t min32(uint32_t a, uint32_t b) { return a < b ? a : b; }
static uint32_t max32(uint32_t a, uint32_t b) { return a > b ? a : b; }
void lie_string_policy_init(lie_string_policy *p) {
  if (!p) return;
  memset(p,0,sizeof(*p)); p->abi_version = LIE_STRING_ABI; p->struct_bytes = sizeof(*p); p->maximum = UINT32_MAX;
}
static bool policy_valid(const lie_string_policy *p) {
  return p && p->abi_version == LIE_STRING_ABI && p->struct_bytes == sizeof(*p) &&
    p->regex && lie_regex_state_count(p->regex) && p->minimum <= p->maximum;
}
lie_string_status lie_string_policy_validate(const lie_string_policy *p) {
  if (!p || p->abi_version != LIE_STRING_ABI || p->struct_bytes != sizeof(*p) || !p->regex) return LIE_STRING_INVALID;
  if (p->minimum > p->maximum) return LIE_STRING_EMPTY_LENGTH;
  bool possible;
  TRY(regex_status(lie_regex_can_finish(p->regex,0,p->minimum,p->maximum,&possible)));
  return possible ? LIE_STRING_OK : LIE_STRING_EMPTY_PATTERN;
}
static lie_string_status state_valid(const lie_string_policy *p, const state *s) {
  const uint32_t *f = s->field;
  if (f[MODE] > UTF8) return LIE_STRING_PHASE;
  if (f[DFA] >= lie_regex_state_count(p->regex) || f[COUNT] > p->maximum) return LIE_STRING_STATE;
  unsigned rem = f[EXTRA] & 255;
  switch (f[MODE]) {
  case BODY: case ESCAPE:
    if (f[VALUE] || f[EXTRA]) return LIE_STRING_STATE;
    break;
  case LOW_SLASH: case LOW_U:
    if (f[VALUE] < 0xd800 || f[VALUE] > 0xdbff || f[EXTRA]) return LIE_STRING_STATE;
    break;
  case HEX: case LOW_HEX:
    if (!rem || rem > 4) return LIE_STRING_STATE;
    if (f[MODE] == LOW_HEX) {
      if ((f[EXTRA] >> 8) < 0xd800 || (f[EXTRA] >> 8) > 0xdbff) return LIE_STRING_STATE;
    } else if (f[EXTRA] != rem) return LIE_STRING_STATE;
    if (p->scalar_only) { if (f[VALUE] > 2) return LIE_STRING_STATE; }
    else if (f[VALUE] >= (1u << (4 * (4 - rem)))) return LIE_STRING_STATE;
    break;
  case UTF8:
    if (!rem || rem > 3) return LIE_STRING_STATE;
    if (p->scalar_only) {
      if (f[EXTRA] != rem || (f[VALUE] >> 8) < 0x80 || (f[VALUE] >> 8) > 0xbf ||
          (f[VALUE] & 255) < (f[VALUE] >> 8) || (f[VALUE] & 255) > 0xbf) return LIE_STRING_STATE;
    } else {
      unsigned width = f[EXTRA] >> 8;
      if (width < 2 || width > 4 || rem >= width || f[VALUE] > (0x10ffffu >> (6 * rem))) return LIE_STRING_STATE;
    }
    break;
  }
  return LIE_STRING_OK;
}
static uint32_t remaining_minimum(const lie_string_policy *p, uint32_t count) {
  return count >= p->minimum ? 0 : p->minimum - count;
}
static lie_string_status character(const lie_string_policy *p, state *s, uint32_t cp, bool *ok) {
  *ok = false; uint32_t *f = s->field;
  if (f[COUNT] == p->maximum || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff)) return LIE_STRING_OK;
  uint32_t count = f[COUNT] + 1;
  if (!p->scalar_only) {
    uint32_t next; TRY(regex_status(lie_regex_advance(p->regex,f[DFA],cp,&next)));
    bool possible; TRY(regex_status(lie_regex_can_finish(p->regex,next,remaining_minimum(p,count),p->maximum-count,&possible)));
    if (!possible) return LIE_STRING_OK;
    f[DFA] = next;
  }
  f[COUNT] = p->maximum == UINT32_MAX ? min32(count,p->minimum) : count;
  f[VALUE] = f[EXTRA] = 0; f[MODE] = BODY; *ok = true; return LIE_STRING_OK;
}
static lie_string_status range(const lie_string_policy *p, const state *s, uint32_t first, uint32_t last, bool *ok) {
  *ok = false; const uint32_t *f = s->field;
  if (first > last || f[COUNT] == p->maximum) return LIE_STRING_OK;
  uint32_t count = f[COUNT] + 1;
  return regex_status(lie_regex_can_advance(p->regex,f[DFA],first,last,remaining_minimum(p,count),p->maximum-count,ok));
}
static lie_string_status pending(const lie_string_policy *p, const state *s, bool *ok) {
  const uint32_t *f = s->field;
  if (p->scalar_only) { *ok = f[COUNT] < p->maximum; return LIE_STRING_OK; }
  if (f[MODE] == ESCAPE) return range(p,s,0,0x10ffff,ok);
  if (f[MODE] == UTF8) {
    unsigned shift = 6 * (f[EXTRA] & 255), width = f[EXTRA] >> 8;
    uint32_t minimum = width == 2 ? 0x80 : width == 3 ? 0x800 : 0x10000;
    return range(p,s,max32(minimum,f[VALUE] << shift),min32(0x10ffff,((f[VALUE]+1) << shift)-1),ok);
  }
  if (f[MODE] == LOW_SLASH || f[MODE] == LOW_U) {
    uint32_t first = 0x10000 + (f[VALUE]-0xd800)*1024;
    return range(p,s,first,first+1023,ok);
  }
  unsigned shift = 4 * (f[EXTRA] & 255);
  uint32_t first = f[VALUE] << shift, last = ((f[VALUE]+1) << shift)-1;
  if (f[MODE] == LOW_HEX) {
    uint32_t low = max32(first,0xdc00), high = min32(last,0xdfff);
    if (low > high) { *ok = false; return LIE_STRING_OK; }
    uint32_t base = 0x10000 + ((f[EXTRA] >> 8)-0xd800)*1024;
    return range(p,s,base+low-0xdc00,base+high-0xdc00,ok);
  }
  *ok = false;
  if (first <= 0xd7ff) { TRY(range(p,s,first,min32(last,0xd7ff),ok)); if (*ok) return LIE_STRING_OK; }
  if (last >= 0xe000) { TRY(range(p,s,max32(first,0xe000),last,ok)); if (*ok) return LIE_STRING_OK; }
  if (first <= 0xdbff && last >= 0xd800)
    return range(p,s,0x10000+(max32(first,0xd800)-0xd800)*1024,0x10000+(min32(last,0xdbff)-0xd800+1)*1024-1,ok);
  return LIE_STRING_OK;
}
static lie_string_status advance(const lie_string_policy *p, state *s, bool started, uint8_t byte,
  lie_string_match *match, bool *changed) {
  *match = (lie_string_match){false,false}; *changed = false;
  uint32_t *f = s->field; bool ok;
  if (!started) { if (byte != '"') return LIE_STRING_OK; f[DFA] = 0; }
  else switch (f[MODE]) {
  case BODY:
    if (byte == '"') {
      TRY(regex_status(lie_regex_accepting(p->regex,f[DFA],&ok)));
      match->complete = f[COUNT] >= p->minimum && ok; return LIE_STRING_OK;
    }
    if (byte == '\\') f[MODE] = ESCAPE;
    else if (byte < 0x20) return LIE_STRING_OK;
    else if (byte < 0x80) { TRY(character(p,s,byte,&ok)); if (!ok) return LIE_STRING_OK; }
    else {
      unsigned width = byte >= 0xc2 && byte <= 0xdf ? 2 : byte >= 0xe0 && byte <= 0xef ? 3 : byte >= 0xf0 && byte <= 0xf4 ? 4 : 0;
      if (!width) return LIE_STRING_OK;
      f[MODE] = UTF8;
      if (p->scalar_only) {
        unsigned low = byte == 0xe0 ? 0xa0 : byte == 0xf0 ? 0x90 : 0x80;
        unsigned high = byte == 0xed ? 0x9f : byte == 0xf4 ? 0x8f : 0xbf;
        f[VALUE] = (low << 8) | high; f[EXTRA] = width-1;
      } else { f[VALUE] = byte & ((1u << (7-width))-1); f[EXTRA] = (width << 8) | (width-1); }
    }
    break;
  case ESCAPE:
    if (byte == 'u') { f[MODE] = HEX; f[EXTRA] = 4; }
    else {
      static const uint8_t keys[] = {'"','\\','/','b','f','n','r','t'};
      static const uint8_t values[] = {'"','\\','/','\b','\f','\n','\r','\t'};
      size_t i = 0; while (i < sizeof(keys) && keys[i] != byte) ++i;
      if (i == sizeof(keys)) return LIE_STRING_OK;
      TRY(character(p,s,values[i],&ok)); if (!ok) return LIE_STRING_OK;
    }
    break;
  case LOW_SLASH:
    if (byte != '\\') return LIE_STRING_OK;
    f[MODE] = LOW_U; break;
  case LOW_U:
    if (byte != 'u') return LIE_STRING_OK;
    f[MODE] = LOW_HEX; f[EXTRA] = (f[VALUE] << 8) | 4; f[VALUE] = 0; break;
  case HEX: case LOW_HEX: {
    int digit = byte >= '0' && byte <= '9' ? byte-'0' : byte >= 'a' && byte <= 'f' ? byte-'a'+10 : byte >= 'A' && byte <= 'F' ? byte-'A'+10 : -1;
    if (digit < 0) return LIE_STRING_OK;
    if (p->scalar_only) {
      unsigned remaining = f[EXTRA] & 255;
      if (f[MODE] == LOW_HEX) {
        if ((remaining == 4 && digit != 13) || (remaining == 3 && digit < 12)) return LIE_STRING_OK;
      } else if (remaining == 4) f[VALUE] = digit == 13 ? 1 : 0;
      else if (remaining == 3 && f[VALUE] == 1) {
        if (digit >= 12) return LIE_STRING_OK;
        f[VALUE] = digit >= 8 ? 2 : 0;
      }
      --f[EXTRA];
      if (!(f[EXTRA] & 255)) {
        if (f[MODE] == HEX && f[VALUE] == 2) { f[VALUE] = 0xd800; f[MODE] = LOW_SLASH; }
        else { TRY(character(p,s,0,&ok)); if (!ok) return LIE_STRING_OK; }
      }
    } else {
      f[VALUE] = (f[VALUE] << 4) | (uint32_t)digit; --f[EXTRA];
      if (!(f[EXTRA] & 255)) {
        uint32_t cp = f[VALUE];
        if (f[MODE] == LOW_HEX) {
          if (cp < 0xdc00 || cp > 0xdfff) return LIE_STRING_OK;
          cp = 0x10000 + ((f[EXTRA] >> 8)-0xd800)*1024 + cp-0xdc00;
        } else if (cp >= 0xd800 && cp <= 0xdbff) { f[MODE] = LOW_SLASH; f[EXTRA] = 0; break; }
        TRY(character(p,s,cp,&ok)); if (!ok) return LIE_STRING_OK;
      }
    }
    break;
  }
  case UTF8:
    if (p->scalar_only) {
      if (byte < (f[VALUE] >> 8) || byte > (f[VALUE] & 255)) return LIE_STRING_OK;
      if (!--f[EXTRA]) { TRY(character(p,s,0,&ok)); if (!ok) return LIE_STRING_OK; }
      else f[VALUE] = (0x80 << 8) | 0xbf;
    } else {
      if (byte < 0x80 || byte > 0xbf) return LIE_STRING_OK;
      f[VALUE] = (f[VALUE] << 6) | (byte & 0x3f); --f[EXTRA];
      if (!(f[EXTRA] & 255)) {
        unsigned width = f[EXTRA] >> 8; uint32_t minimum = width == 2 ? 0x80 : width == 3 ? 0x800 : 0x10000;
        if (f[VALUE] < minimum) return LIE_STRING_OK;
        TRY(character(p,s,f[VALUE],&ok)); if (!ok) return LIE_STRING_OK;
      }
    }
    break;
  }
  if (f[MODE] != BODY) { TRY(pending(p,s,&ok)); if (!ok) return LIE_STRING_OK; }
  match->prefix = true; *changed = true; return LIE_STRING_OK;
}
lie_string_status lie_string_advance(const lie_string_policy *p, uint8_t *encoded, size_t *length,
  size_t capacity, uint8_t byte, lie_string_match *out) {
  if (!policy_valid(p) || !encoded || !length || !out) return LIE_STRING_INVALID;
  if (*length && *length != LIE_STRING_STATE_BYTES) return LIE_STRING_STATE;
  if (capacity < *length) return LIE_STRING_RESOURCE;
  state s = {{0}};
  if (*length) { memcpy(&s,encoded,sizeof(s)); TRY(state_valid(p,&s)); }
  lie_string_match result; bool changed;
  TRY(advance(p,&s,*length != 0,byte,&result,&changed));
  if (changed) {
    if (capacity < sizeof(s)) return LIE_STRING_RESOURCE;
    memcpy(encoded,&s,sizeof(s)); *length = sizeof(s);
  }
  *out = result; return LIE_STRING_OK;
}
lie_string_status lie_string_check(const lie_string_policy *p, const uint8_t *bytes, size_t length, lie_string_match *out) {
  if (!policy_valid(p) || !out || (length && !bytes)) return LIE_STRING_INVALID;
  state s = {{0}}; lie_string_match result = {true,false}; bool started = false;
  for (size_t i = 0; i < length; ++i) {
    if (!result.prefix) { result = (lie_string_match){false,false}; break; }
    bool changed; TRY(advance(p,&s,started,bytes[i],&result,&changed));
    if (changed) started = true;
  }
  *out = result; return LIE_STRING_OK;
}
lie_string_status lie_string_canonical(const lie_string_policy *p, uint8_t *encoded, size_t length, size_t token_bytes) {
  if (!policy_valid(p) || (length && !encoded)) return LIE_STRING_INVALID;
  if (!length) return LIE_STRING_OK;
  if (length != LIE_STRING_STATE_BYTES) return LIE_STRING_STATE;
  state s; memcpy(&s,encoded,sizeof(s)); TRY(state_valid(p,&s));
  size_t suffix = lie_regex_maximum_suffix(p->regex);
  if (token_bytes > SIZE_MAX - suffix) return LIE_STRING_INVALID;
  size_t window = token_bytes + suffix;
  if (p->scalar_only && s.field[COUNT] < p->minimum && p->minimum-s.field[COUNT] > token_bytes) s.field[COUNT] = 0;
  else if (s.field[COUNT] >= p->minimum && p->maximum-s.field[COUNT] >= window) s.field[COUNT] = p->minimum;
  memcpy(encoded,&s,sizeof(s)); return LIE_STRING_OK;
}
lie_string_match lie_string_whitespace(uint8_t *count, uint8_t byte) {
  if (!count || *count >= 32 || (byte != ' ' && byte != '\t' && byte != '\r' && byte != '\n')) return (lie_string_match){false,false};
  ++*count; return (lie_string_match){*count < 32,true};
}
