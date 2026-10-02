/* SPDX-License-Identifier: MIT */
#include "state_internal.h"
#include <stdlib.h>
#include <string.h>
#if LIE_CHECKPOINT_COMPRESSION
#include <lz4.h>
#endif
static uint32_t get32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
#if LIE_CHECKPOINT_COMPRESSION
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;++i)p[i]=(unsigned char)(n>>(i*8));}
#endif
bool lie_state_compression_enabled(void){return LIE_CHECKPOINT_COMPRESSION!=0;}
bool lie_state_decode_block(const void *encoded,size_t size,void *out,size_t bytes){
#if LIE_CHECKPOINT_COMPRESSION
    if(!encoded||!out||!size||size>=bytes||bytes>LIE_STATE_BLOCK_BYTES)return false;
    return LZ4_decompress_safe(encoded,out,(int)size,(int)bytes)==(int)bytes;
#else
    (void)encoded;(void)size;(void)out;(void)bytes;return false;
#endif
}
bool lie_state_unpack_payload(const lie_state *p,void *out,size_t bytes){
    if(!p||!out||bytes!=p->payload_bytes)return false;
    if(!p->codec){if(p->storage_bytes!=bytes)return false;memcpy(out,p->payload,bytes);return true;}
    if(p->codec!=1||!lie_state_compression_enabled()||p->layout.sections[0].role!=LIE_STATE_TOKENS)return false;
    uint64_t prefix=p->layout.sections[0].bytes;
    if(prefix>bytes||prefix>p->storage_bytes)return false;
    memcpy(out,p->payload,(size_t)prefix);uint64_t in=prefix,at=prefix;
    while(at<bytes){
        if(p->storage_bytes-in<8)return false;
        uint32_t raw=get32(p->payload+in),coded=get32(p->payload+in+4);in+=8;
        uint64_t want=bytes-at;if(want>LIE_STATE_BLOCK_BYTES)want=LIE_STATE_BLOCK_BYTES;
        if(raw!=want||coded>=raw)return false;
        uint32_t n=coded?coded:raw;if(n>p->storage_bytes-in)return false;
        if(coded){if(!lie_state_decode_block(p->payload+in,n,(unsigned char *)out+at,raw))return false;}
        else memcpy((unsigned char *)out+at,p->payload+in,raw);
        in+=n;at+=raw;
    }
    return in==p->storage_bytes;
}
bool lie_state_compress_cancel(lie_state **handle,uint64_t budget,const atomic_bool *cancel){
#if LIE_CHECKPOINT_COMPRESSION
    if(!handle||!*handle||(cancel&&atomic_load(cancel)))return false;
    lie_state *p=*handle;uint64_t raw=0;
    if(p->codec||atomic_load(&p->refs)!=1||!lie_state_validate(&p->layout,&raw)||raw!=p->payload_bytes||
       p->storage_bytes!=raw||raw<65536||p->layout.sections[0].role!=LIE_STATE_TOKENS)return false;
    uint64_t occupied=lie_state_bytes(p);
    /* Only reserve a result capable of saving at least 12.5%. Codec workspace
     * includes its input-independent LZ4 state and output block. */
    uint64_t scratch=LZ4_COMPRESSBOUND(LIE_STATE_BLOCK_BYTES)+(uint64_t)LZ4_sizeofState();
    if(budget<occupied||budget-occupied<sizeof(lie_state)+scratch)return false;
    uint64_t cap=raw-raw/8,available=budget-occupied-sizeof(lie_state)-scratch;
    if(cap>available)cap=available;
    uint64_t prefix=p->layout.sections[0].bytes;
    if(prefix>=cap)return false;
    lie_state *packed=malloc(sizeof(*packed)+(size_t)cap);
    char *block=malloc(LZ4_COMPRESSBOUND(LIE_STATE_BLOCK_BYTES));void *work=malloc((size_t)LZ4_sizeofState());
    if(!packed||!block||!work){free(packed);free(block);free(work);return false;}
    memcpy(packed->payload,p->payload,(size_t)prefix);uint64_t in=prefix,out=prefix;
    bool ok=true;
    while(in<raw){
        if(cancel&&atomic_load(cancel)){ok=false;break;}
        uint32_t n=(uint32_t)((raw-in)>LIE_STATE_BLOCK_BYTES?LIE_STATE_BLOCK_BYTES:raw-in);
        int compressed=LZ4_compress_fast_extState(work,(const char *)p->payload+in,block,(int)n,LZ4_COMPRESSBOUND(LIE_STATE_BLOCK_BYTES),1);
        uint32_t coded=compressed>0&&(uint32_t)compressed<n?(uint32_t)compressed:0,bytes=coded?coded:n;
        if(cap-out<8||bytes>cap-out-8){ok=false;break;}
        put32(packed->payload+out,n);put32(packed->payload+out+4,coded);out+=8;
        memcpy(packed->payload+out,coded?(const void *)block:(const void *)(p->payload+in),bytes);
        in+=n;out+=bytes;
    }
    free(block);free(work);
    if(!ok||(cancel&&atomic_load(cancel))){free(packed);return false;}
    lie_state *trim=realloc(packed,sizeof(*packed)+(size_t)out);
    if(!trim){free(packed);return false;}packed=trim;
    packed->layout=p->layout;packed->payload_bytes=raw;packed->storage_bytes=out;packed->codec=1;atomic_init(&packed->refs,1);
    lie_state_destroy(handle);*handle=packed;return true;
#else
    (void)handle;(void)budget;(void)cancel;return false;
#endif
}
bool lie_state_compress(lie_state **handle,uint64_t budget){return lie_state_compress_cancel(handle,budget,NULL);}
