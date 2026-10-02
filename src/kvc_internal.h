/* SPDX-License-Identifier: MIT */
#ifndef LIE_KVC_INTERNAL_H
#define LIE_KVC_INTERNAL_H
#include "lie/kvc.h"
#include <stdio.h>
static inline uint32_t kvc_u32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static inline uint64_t kvc_u64(const unsigned char *p) {
    return (uint64_t)kvc_u32(p) | (uint64_t)kvc_u32(p+4)<<32;
}
static inline void kvc_put32(unsigned char *p,uint32_t v) {
    for(unsigned i=0;i<4;++i)p[i]=(unsigned char)(v>>(8*i));
}
static inline void kvc_put64(unsigned char *p,uint64_t v) {
    for(unsigned i=0;i<8;++i)p[i]=(unsigned char)(v>>(8*i));
}
static inline lie_status kvc_fail(lie_error *e,lie_status rc,const char *message) {
    if(e)snprintf(e->message,sizeof(e->message),"%s",message);
    return rc;
}
static inline int kvc_cancelled(const lie_kvc_limits *l) {
    return l && l->cancelled && l->cancelled(l->userdata);
}
#endif
