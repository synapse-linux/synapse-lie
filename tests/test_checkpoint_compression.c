/* SPDX-License-Identifier: MIT */
/* Lossless host state/codec fixtures only. No model forward or GPU. */
#include "../src/state_internal.h"
#include "../src/state_codec.h"
#include "../src/retention.h"
#include <assert.h>
#include <fcntl.h>
#include <math.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#if LIE_CHECKPOINT_COMPRESSION
#include <lz4.h>
#endif
static uint32_t random32(uint32_t *s){*s^=*s<<13;*s^=*s>>17;*s^=*s<<5;return *s;}
static void checksum(int fd,uint64_t size){
    unsigned char *bytes=malloc((size_t)size),digest[32];unsigned count=0;assert(bytes);
    assert(pread(fd,bytes,(size_t)size,0)==(ssize_t)size);memset(bytes+88,0,32);
    assert(EVP_Digest(bytes,(size_t)size,digest,&count,EVP_sha256(),NULL)==1&&count==32);
    assert(pwrite(fd,digest,32,88)==32);free(bytes);
}
static lie_state *fixture(unsigned pattern){
    lie_state_layout l={.abi_version=LIE_STATE_ABI,.representation_version=1,.domain=7,
        .token_count=4,.context_tokens=128,.prefill_chunk=4};
    uint64_t tokens[]={4},logits[]={3},blob[]={3u*LIE_STATE_BLOCK_BYTES+127};
    assert(lie_state_add(&l,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,tokens));
    assert(lie_state_add(&l,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,logits));
    assert(lie_state_add(&l,LIE_STATE_MODEL_COMPONENT,0,LIE_STATE_U8,1,blob));
    lie_state *p=lie_state_allocate(&l,UINT64_MAX);assert(p);memset(p->payload,0,(size_t)p->payload_bytes);
    int32_t ids[]={1,2,3,4};memcpy(p->payload,ids,sizeof(ids));
    /* Include exact NaN payload, signed zero and a subnormal: byte equality is
     * stronger than floating equality and excludes any precision conversion. */
    uint32_t bits[]={0x7fc01234,0x80000000,0x00000001};memcpy(p->payload+l.sections[1].offset,bits,sizeof(bits));
    uint32_t seed=123;unsigned char *data=p->payload+l.sections[2].offset;
    for(size_t i=0;i<blob[0];++i){
        unsigned char r=(unsigned char)random32(&seed);
        data[i]=pattern==3?(i%4==3?0x3f:r):(pattern==1||pattern==4)?r:pattern==2&&i>=LIE_STATE_BLOCK_BYTES&&i<2u*LIE_STATE_BLOCK_BYTES?r:0;
    }
    if(pattern==4){
        /* A misleadingly compressible beginning/middle/end must not bypass
         * the complete retained-size gate. Most of this state is random. */
        uint64_t start=l.sections[0].bytes,span=p->payload_bytes-start;
        memset(p->payload+start,0,65536);
        memset(p->payload+start+span/2-32768,0,65536);
        memset(p->payload+p->payload_bytes-65536,0,65536);
    }
    return p;
}
int main(void){
    assert(lie_state_compression_enabled()==(LIE_CHECKPOINT_COMPRESSION!=0));
    for(unsigned pattern=0;pattern<5;++pattern){
        lie_state *p=fixture(pattern);uint64_t raw=lie_state_bytes(p),payload=p->payload_bytes;
        unsigned char *expected=malloc((size_t)payload),*expanded=malloc((size_t)payload);assert(expected&&expanded);
        memcpy(expected,p->payload,(size_t)payload);
        assert(!lie_state_compress(&p,raw));assert(!lie_state_is_compressed(p)); /* No unaccounted workspace. */
        lie_state_retain(p);lie_state *pin=p;assert(!lie_state_compress(&p,raw*3));lie_state_destroy(&pin);
        bool packed=lie_state_compress(&p,raw*3);
        assert(packed==(LIE_CHECKPOINT_COMPRESSION&&(pattern==0||pattern==2)));
        assert(lie_state_expanded_bytes(p)==raw&&lie_state_unpack_payload(p,expanded,(size_t)payload));
        assert(!memcmp(expanded,expected,(size_t)payload));
        assert(!memcmp(lie_state_tokens(p),expected,4*sizeof(int32_t)));
        if(packed){
            assert(lie_state_bytes(p)<=raw/2&&lie_state_restore_workspace(p)==payload+lie_state_decode_workspace(p->codec));
            uint64_t prefix=p->layout.sections[0].bytes;unsigned char save=p->payload[prefix];
            p->payload[prefix]^=1;assert(!lie_state_unpack_payload(p,expanded,(size_t)payload));p->payload[prefix]=save;
            p->storage_bytes++;assert(!lie_state_unpack_payload(p,expanded,(size_t)payload));p->storage_bytes--;
        }
        char name[]="checkpoint-codec-XXXXXX";int fd=mkstemp(name);assert(fd>=0);
        lie_state_identity id={{4}};assert(lie_state_file_write(fd,&id,p,NULL));uint64_t file=0;unsigned n=0;
        assert(lie_state_file_probe(fd,&id,&file,&n)&&n==4&&file==lie_state_file_bytes(p));
        assert(!lie_state_file_read(fd,&id,7,raw-1,NULL));
        lie_state *loaded=lie_state_file_read(fd,&id,7,raw*3,NULL);assert(loaded);
        assert(loaded->codec==0&&!memcmp(loaded->payload,expected,(size_t)payload));lie_state_destroy(&loaded);
        if(packed){
            /* Valid checksums must not bypass frame bounds/expanded-size checks. */
            uint64_t first=LIE_STATE_DISK_HEADER+(uint64_t)p->layout.section_count*LIE_STATE_DISK_SECTION+p->layout.sections[0].bytes;
            uint64_t offsets[]={8,36,40,152,first,first+4};
            for(unsigned i=0;i<sizeof(offsets)/sizeof(*offsets);++i){
                unsigned char old;assert(pread(fd,&old,1,(off_t)offsets[i])==1);
                unsigned char invalid=old^0x80;assert(pwrite(fd,&invalid,1,(off_t)offsets[i])==1);checksum(fd,file);
                assert(!lie_state_file_read(fd,&id,7,raw*3,NULL));
                assert(pwrite(fd,&old,1,(off_t)offsets[i])==1);checksum(fd,file);
            }
            atomic_bool cancel=true;assert(!lie_state_file_read(fd,&id,7,raw*3,&cancel));
            loaded=lie_state_file_read(fd,&id,7,raw*3,NULL);assert(loaded);lie_state_destroy(&loaded);
        }
        assert(!ftruncate(fd,(off_t)file-1));assert(!lie_state_file_read(fd,&id,7,raw*3,NULL));
        close(fd);assert(!unlink(name));lie_state_destroy(&p);free(expected);free(expanded);
    }
#if LIE_CHECKPOINT_COMPRESSION
    /* Reader compatibility with the first released LZ4 envelope, codec 1. */
    lie_state *raw=fixture(0),*old=lie_state_allocate(&raw->layout,UINT64_MAX);assert(old);
    uint64_t in=raw->layout.sections[0].bytes,at=in;memcpy(old->payload,raw->payload,(size_t)in);
    while(in<raw->payload_bytes){
        uint32_t n=(uint32_t)((raw->payload_bytes-in)>LIE_STATE_BLOCK_BYTES?LIE_STATE_BLOCK_BYTES:raw->payload_bytes-in);
        int count=LZ4_compress_default((const char *)raw->payload+in,(char *)old->payload+at+8,(int)n,(int)n);assert(count>0);
        for(unsigned k=0;k<4;++k){old->payload[at+k]=(unsigned char)(n>>(8*k));old->payload[at+4+k]=(unsigned char)((uint32_t)count>>(8*k));}
        in+=n;at+=8+(uint32_t)count;
    }
    old->codec=1;old->storage_bytes=at;
    char legacy[]="checkpoint-legacy-XXXXXX";int fd=mkstemp(legacy);assert(fd>=0);lie_state_identity id={{4}};
    assert(lie_state_file_write(fd,&id,old,NULL));
    lie_state *loaded=lie_state_file_read(fd,&id,7,lie_state_bytes(raw)+LIE_STATE_BLOCK_BYTES,NULL);assert(loaded);
    assert(!memcmp(raw->payload,loaded->payload,(size_t)raw->payload_bytes));
    lie_state_destroy(&loaded);lie_state_destroy(&old);lie_state_destroy(&raw);close(fd);assert(!unlink(legacy));
#endif
    if(LIE_CACHE_UTILITY){
        lie_retention a,b;lie_retention_init(&a,0,false);lie_retention_init(&b,0,false);
        for(unsigned i=1;i<=8;++i)lie_retention_hit(&a,i);
        double hot=lie_retention_score(&a,8,8192,1048576,false);
        assert(hot>lie_retention_score(&b,8,8192,1048576,false));
        lie_retention_hit(&b,4096);
        assert(lie_retention_score(&a,4096,8192,1048576,false)<lie_retention_score(&b,4096,8192,1048576,false));
        assert(lie_retention_score(&b,4096,8192,524288,false)>lie_retention_score(&b,4096,8192,1048576,false));
        b.continuation=true;
        assert(lie_retention_score(&b,4096,8192,1048576,true)<lie_retention_score(&b,4096,8192,1048576,false));
        assert(isfinite(lie_retention_score(&b,UINT64_MAX,UINT64_MAX,1,false)));
    }
    puts("Lossless checkpoint blocks, exact special bits, bounds, pinning, disk restart and utility aging: PASS (NOT-INFERENCE)");
    return 0;
}
