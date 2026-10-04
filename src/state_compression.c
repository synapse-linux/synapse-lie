/* SPDX-License-Identifier: MIT */
#include "state_internal.h"
#include <stdlib.h>
#include <string.h>
#if LIE_CHECKPOINT_COMPRESSION
#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>
#endif
static uint32_t get32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
#if LIE_CHECKPOINT_COMPRESSION
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;++i)p[i]=(unsigned char)(n>>(i*8));}
#endif
bool lie_state_compression_enabled(void){return LIE_CHECKPOINT_COMPRESSION!=0;}
const char *lie_state_compression_codec(void){return LIE_CHECKPOINT_COMPRESSION?"byte-plane4-zstd1-v1":"none";}
uint64_t lie_state_decode_workspace(uint32_t codec){
#if LIE_CHECKPOINT_COMPRESSION
    return codec==2?LIE_STATE_BLOCK_BYTES+(uint64_t)ZSTD_estimateDCtxSize():0;
#else
    (void)codec;return 0;
#endif
}
#if LIE_CHECKPOINT_COMPRESSION
/* A reversible byte permutation, without inspecting/converting float values.
 * Group equal byte positions of four-byte words; copy a final 1..3-byte tail. */
static void planes(unsigned char *restrict to,const unsigned char *restrict from,size_t n,bool undo){
    size_t words=n/4;
    for(size_t lane=0;lane<4;++lane)for(size_t i=0;i<words;++i){
        if(undo)to[4*i+lane]=from[lane*words+i];else to[lane*words+i]=from[4*i+lane];
    }
    memcpy(to+words*4,from+words*4,n-words*4);
}
/* Bounded admission heuristic, not a ratio guarantee. False negatives only
 * forgo optional packing. The complete result must still halve retained bytes.
 * Probe at most 48 KiB before allocating/scanning a multi-GiB candidate. */
static bool worth_packing(const lie_state *p,ZSTD_CCtx *ctx,unsigned char *block,
                          size_t cap,unsigned char *shuffled,const atomic_bool *cancel){
    uint64_t prefix=p->layout.sections[0].bytes,bytes=p->payload_bytes-prefix;
    size_t n=bytes<16384?(size_t)bytes:16384;
    if(!n)return false;
    uint64_t offsets[]={0,(bytes-n)/2,bytes-n};size_t stored=0;
    for(unsigned i=0;i<3;++i){
        if(cancel&&atomic_load(cancel))return false;
        planes(shuffled,p->payload+prefix+offsets[i],n,false);
        size_t z=ZSTD_compressCCtx(ctx,block,cap,shuffled,n,1);
        if(ZSTD_isError(z))return false;
        stored+=z;
    }
    /* Allow a small estimation margin; final admission is strictly 50%. */
    return stored*100<=3*n*55;
}
#endif
bool lie_state_decode_block(uint32_t codec,const void *encoded,size_t size,void *out,size_t bytes){
#if LIE_CHECKPOINT_COMPRESSION
    if(!encoded||!out||!size||size>=bytes||bytes>LIE_STATE_BLOCK_BYTES)return false;
    if(codec!=2)return false;
    /* Static Zstd contexts prevent hidden codec allocations outside admission. */
    size_t context=ZSTD_estimateDCtxSize();unsigned char *work=malloc(LIE_STATE_BLOCK_BYTES+context);
    if(!work)return false;
    ZSTD_DCtx *ctx=ZSTD_initStaticDCtx(work+LIE_STATE_BLOCK_BYTES,context);
    size_t decoded=ctx?ZSTD_decompressDCtx(ctx,work,bytes,encoded,size):SIZE_MAX;
    bool ok=!ZSTD_isError(decoded)&&decoded==bytes;
    if(ok)planes(out,work,bytes,true);
    free(work);return ok;
#else
    (void)codec;(void)encoded;(void)size;(void)out;(void)bytes;return false;
#endif
}
bool lie_state_unpack_payload(const lie_state *p,void *out,size_t bytes){
    if(!p||!out||bytes!=p->payload_bytes)return false;
    if(!p->codec){if(p->storage_bytes!=bytes)return false;memcpy(out,p->payload,bytes);return true;}
    if(p->codec!=2||!lie_state_compression_enabled()||p->layout.sections[0].role!=LIE_STATE_TOKENS)return false;
    uint64_t prefix=p->layout.sections[0].bytes;
    if(prefix>bytes||prefix>p->storage_bytes)return false;
    memcpy(out,p->payload,(size_t)prefix);uint64_t in=prefix,at=prefix;
    while(at<bytes){
        if(p->storage_bytes-in<8)return false;
        uint32_t raw=get32(p->payload+in),coded=get32(p->payload+in+4);in+=8;
        uint64_t want=bytes-at;if(want>LIE_STATE_BLOCK_BYTES)want=LIE_STATE_BLOCK_BYTES;
        if(raw!=want||coded>=raw)return false;
        uint32_t n=coded?coded:raw;if(n>p->storage_bytes-in)return false;
        if(coded){if(!lie_state_decode_block(p->codec,p->payload+in,n,(unsigned char *)out+at,raw))return false;}
        else memcpy((unsigned char *)out+at,p->payload+in,raw);
        in+=n;at+=raw;
    }
    return in==p->storage_bytes;
}
bool lie_state_compress_cancel(lie_state **handle,uint64_t budget,const atomic_bool *cancel){
    if(handle&&*handle)for(unsigned i=0;i<(*handle)->layout.section_count;++i)
        if((*handle)->layout.sections[i].role==LIE_STATE_CACHE_SCOPE)return false;
    if(handle&&*handle&&(*handle)->layout.format!=LIE_STATE_ALIGNED)return false;
#if LIE_CHECKPOINT_COMPRESSION
    if(!handle||!*handle||(cancel&&atomic_load(cancel)))return false;
    lie_state *p=*handle;uint64_t raw=0;
    if(p->codec||atomic_load(&p->refs)!=1||!lie_state_validate(&p->layout,&raw)||raw!=p->payload_bytes||
       p->storage_bytes!=raw||raw<65536||p->layout.sections[0].role!=LIE_STATE_TOKENS)return false;
    uint64_t occupied=lie_state_bytes(p);
    /* Only reserve a result capable of halving the complete retained state.
     * A small probe rejects low-benefit data before candidate allocation.
     * Codec workspace
     * includes a static context, byte-plane input and encoded output block. */
    size_t encoded_cap=ZSTD_compressBound(LIE_STATE_BLOCK_BYTES),context=ZSTD_estimateCCtxSize(1);
    if(ZSTD_isError(context)||ZSTD_isError(encoded_cap))return false;
    uint64_t scratch=(uint64_t)encoded_cap+context+LIE_STATE_BLOCK_BYTES;
    if(budget<occupied||budget-occupied<sizeof(lie_state)+scratch)return false;
    if(occupied/2<=sizeof(lie_state))return false;
    uint64_t cap=occupied/2-sizeof(lie_state),available=budget-occupied-sizeof(lie_state)-scratch;
    if(cap>available)cap=available;
    uint64_t prefix=p->layout.sections[0].bytes;
    if(prefix>=cap)return false;
    unsigned char *block=malloc(encoded_cap),*shuffled=malloc(LIE_STATE_BLOCK_BYTES);void *work=malloc(context);
    if(!block||!shuffled||!work){free(block);free(shuffled);free(work);return false;}
    ZSTD_CCtx *ctx=ZSTD_initStaticCCtx(work,context);
    if(!ctx||!worth_packing(p,ctx,block,encoded_cap,shuffled,cancel)){
        free(block);free(shuffled);free(work);return false;
    }
    lie_state *packed=malloc(sizeof(*packed)+(size_t)cap);
    if(!packed){free(block);free(shuffled);free(work);return false;}
    memcpy(packed->payload,p->payload,(size_t)prefix);uint64_t in=prefix,out=prefix;
    bool ok=true;
    while(in<raw){
        if(cancel&&atomic_load(cancel)){ok=false;break;}
        uint32_t n=(uint32_t)((raw-in)>LIE_STATE_BLOCK_BYTES?LIE_STATE_BLOCK_BYTES:raw-in);
        planes(shuffled,p->payload+in,n,false);
        size_t compressed=ZSTD_compressCCtx(ctx,block,encoded_cap,shuffled,n,1);
        if(ZSTD_isError(compressed)){ok=false;break;}
        uint32_t coded=compressed<n?(uint32_t)compressed:0,bytes=coded?coded:n;
        if(cap-out<8||bytes>cap-out-8){ok=false;break;}
        put32(packed->payload+out,n);put32(packed->payload+out+4,coded);out+=8;
        memcpy(packed->payload+out,coded?(const void *)block:(const void *)(p->payload+in),bytes);
        in+=n;out+=bytes;
    }
    free(block);free(shuffled);free(work);
    if(!ok||(cancel&&atomic_load(cancel))){free(packed);return false;}
    lie_state *trim=realloc(packed,sizeof(*packed)+(size_t)out);
    if(!trim){free(packed);return false;}packed=trim;
    packed->layout=p->layout;packed->payload_bytes=raw;packed->storage_bytes=out;packed->codec=2;atomic_init(&packed->refs,1);
    lie_state_destroy(handle);*handle=packed;return true;
#else
    (void)handle;(void)budget;(void)cancel;return false;
#endif
}
bool lie_state_compress(lie_state **handle,uint64_t budget){return lie_state_compress_cancel(handle,budget,NULL);}
