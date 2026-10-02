/* SPDX-License-Identifier: MIT */
#include "state_codec.h"
#include "state_internal.h"
#include <errno.h>
#include <float.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static uint32_t u32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t u64(const unsigned char *p){return u32(p)|(uint64_t)u32(p+4)<<32;}
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;++i)p[i]=(unsigned char)(n>>(8*i));}
static void put64(unsigned char *p,uint64_t n){for(unsigned i=0;i<8;++i)p[i]=(unsigned char)(n>>(8*i));}
static bool platform(void){const uint32_t one=1;return *(const unsigned char *)&one==1&&sizeof(float)==4&&FLT_RADIX==2&&FLT_MANT_DIG==24;}
static bool stopped(const atomic_bool *cancel){return cancel&&atomic_load(cancel);}
static bool transfer(int fd,void *p,size_t n,uint64_t offset,bool write,const atomic_bool *cancel,EVP_MD_CTX *hash){
    unsigned char *at=p;
    while(n){
        if(stopped(cancel)||offset>INT64_MAX)return false;
        size_t chunk=n>1048576?1048576:n;
        ssize_t done=write?pwrite(fd,at,chunk,(off_t)offset):pread(fd,at,chunk,(off_t)offset);
        if(done<0&&errno==EINTR)continue;
        if(done<=0)return false;
        if(hash&&EVP_DigestUpdate(hash,at,(size_t)done)!=1)return false;
        at+=done;n-=(size_t)done;offset+=(uint64_t)done;
    }
    return !stopped(cancel);
}
static bool regular(int fd,uint64_t *bytes){
    struct stat st;
    if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1||st.st_uid!=geteuid()||
       (st.st_mode&0777)!=0600||st.st_size<0)return false;
    *bytes=(uint64_t)st.st_size;return true;
}
uint64_t lie_state_file_bytes(const lie_state *s){
    if(!s)return 0;
    uint64_t framing=LIE_STATE_DISK_HEADER+(uint64_t)s->layout.section_count*LIE_STATE_DISK_SECTION;
    return s->storage_bytes>UINT64_MAX-framing?UINT64_MAX:framing+s->storage_bytes;
}
static void header(unsigned char *h,const lie_state_identity *id,const lie_state *s){
    memset(h,0,LIE_STATE_DISK_HEADER);memcpy(h,"LIEPFX1",8);
    put32(h+8,s->codec?2:1);put32(h+12,LIE_STATE_DISK_HEADER);put32(h+36,s->codec);
    put32(h+16,s->layout.representation_version);put32(h+20,s->layout.section_count);
    put32(h+24,s->layout.token_count);put32(h+28,s->layout.context_tokens);put32(h+32,s->layout.prefill_chunk);
    put64(h+40,s->payload_bytes);put64(h+48,lie_state_file_bytes(s));memcpy(h+56,id->bytes,32);
    for(unsigned i=0;i<8;++i)put32(h+120+i*4,s->layout.model_data[i]);
    if(s->codec)put64(h+152,s->storage_bytes);
}
static bool read_header(int fd,const lie_state_identity *id,unsigned char *h,uint64_t *size){
    if(!platform()||!regular(fd,size)||*size<LIE_STATE_DISK_HEADER||
       !transfer(fd,h,LIE_STATE_DISK_HEADER,0,false,NULL,NULL)||memcmp(h,"LIEPFX1",8)||
       u32(h+12)!=LIE_STATE_DISK_HEADER||
       memcmp(h+56,id->bytes,32)||!u32(h+16)||!u32(h+20)||u32(h+20)>LIE_STATE_MAX_SECTIONS||
       !u32(h+24)||u32(h+24)>u32(h+28)||!u32(h+32)||u64(h+48)!=*size)return false;
    uint64_t prefix=LIE_STATE_DISK_HEADER+(uint64_t)u32(h+20)*LIE_STATE_DISK_SECTION;
    if(*size<prefix)return false;
    if(u32(h+8)==1)return !u32(h+36)&&!u64(h+152)&&u64(h+40)==*size-prefix;
    return u32(h+8)==2&&u32(h+36)==1&&lie_state_compression_enabled()&&
           u64(h+152)==*size-prefix&&u64(h+152)<u64(h+40);
}
bool lie_state_file_probe(int fd,const lie_state_identity *id,uint64_t *bytes,unsigned *tokens){
    unsigned char h[LIE_STATE_DISK_HEADER];
    if(!id||!bytes||!tokens||!read_header(fd,id,h,bytes))return false;
    *tokens=u32(h+24);return true;
}
static void encode_section(unsigned char *b,const lie_state_section *s){
    put32(b,s->role);put32(b+4,s->layer);put32(b+8,s->dtype);put32(b+12,s->rank);
    for(unsigned k=0;k<4;++k)put64(b+16+8*k,s->shape[k]);
    put64(b+48,s->bytes);put64(b+56,s->offset);
}
static void decode_section(lie_state_section *s,const unsigned char *b){
    s->role=u32(b);s->layer=u32(b+4);s->dtype=u32(b+8);s->rank=u32(b+12);
    for(unsigned k=0;k<4;++k)s->shape[k]=u64(b+16+8*k);
    s->bytes=u64(b+48);s->offset=u64(b+56);
}
bool lie_state_file_write(int fd,const lie_state_identity *id,const lie_state *s,const atomic_bool *cancel){
    uint64_t bytes=0,payload=0;
    if(!platform()||!id||!s||!regular(fd,&bytes)||bytes||!lie_state_validate(&s->layout,&payload)||
       payload!=s->payload_bytes||lie_state_file_bytes(s)>INT64_MAX||s->codec>1||
       (!s->codec&&s->storage_bytes!=payload)||
       (s->codec&&(s->storage_bytes>=payload||s->layout.sections[0].role!=LIE_STATE_TOKENS)))return false;
    EVP_MD_CTX *hash=EVP_MD_CTX_new();if(!hash)return false;
    unsigned char h[LIE_STATE_DISK_HEADER],section[LIE_STATE_DISK_SECTION],digest[32];unsigned count=0;
    header(h,id,s);
    bool ok=EVP_DigestInit_ex(hash,EVP_sha256(),NULL)==1&&transfer(fd,h,sizeof(h),0,true,cancel,hash);
    uint64_t offset=sizeof(h);
    for(unsigned i=0;ok&&i<s->layout.section_count;++i){encode_section(section,&s->layout.sections[i]);
        ok=transfer(fd,section,sizeof(section),offset,true,cancel,hash);offset+=sizeof(section);}
    ok=ok&&transfer(fd,(void *)s->payload,(size_t)s->storage_bytes,offset,true,cancel,hash)&&
       EVP_DigestFinal_ex(hash,digest,&count)==1&&count==32&&transfer(fd,digest,32,88,true,cancel,NULL);
    EVP_MD_CTX_free(hash);return ok;
}
lie_state *lie_state_file_read(int fd,const lie_state_identity *id,uint64_t domain,uint64_t budget,const atomic_bool *cancel){
    unsigned char h[LIE_STATE_DISK_HEADER],section[LIE_STATE_DISK_SECTION],expected[32],actual[32];uint64_t bytes=0;
    if(!domain||!id||stopped(cancel)||!read_header(fd,id,h,&bytes)||u64(h+40)>budget||
       sizeof(lie_state)>budget-u64(h+40))return NULL;
    uint64_t scratch=u32(h+36)?LIE_STATE_BLOCK_BYTES:0;
    if(scratch>budget-u64(h+40)-sizeof(lie_state))return NULL;
    memcpy(expected,h+88,32);memset(h+88,0,32);
    EVP_MD_CTX *hash=EVP_MD_CTX_new();if(!hash)return NULL;
    bool ok=EVP_DigestInit_ex(hash,EVP_sha256(),NULL)==1&&EVP_DigestUpdate(hash,h,sizeof(h))==1;
    lie_state_layout l={.abi_version=LIE_STATE_ABI,.domain=domain,.representation_version=u32(h+16),
        .section_count=u32(h+20),.token_count=u32(h+24),.context_tokens=u32(h+28),.prefill_chunk=u32(h+32)};
    for(unsigned i=0;i<8;++i)l.model_data[i]=u32(h+120+4*i);
    uint64_t offset=sizeof(h),payload=0;
    for(unsigned i=0;ok&&i<l.section_count;++i){ok=transfer(fd,section,sizeof(section),offset,false,cancel,hash);
        if(ok)decode_section(&l.sections[i],section);
        offset+=sizeof(section);}
    ok=ok&&lie_state_validate(&l,&payload)&&payload==u64(h+40);
    lie_state *s=ok?lie_state_allocate(&l,budget):NULL;unsigned count=0;
    if(s&&u32(h+36)){
        unsigned char *block=malloc(LIE_STATE_BLOCK_BYTES);uint64_t at=l.sections[0].bytes;
        ok=block&&l.sections[0].role==LIE_STATE_TOKENS&&at<=bytes-offset&&
           transfer(fd,s->payload,(size_t)at,offset,false,cancel,hash);offset+=at;
        while(ok&&at<payload){
            unsigned char frame[8];
            ok=bytes-offset>=sizeof(frame)&&transfer(fd,frame,sizeof(frame),offset,false,cancel,hash);offset+=sizeof(frame);
            if(!ok)break;
            uint32_t raw=u32(frame),coded=u32(frame+4);uint64_t want=payload-at;
            if(want>LIE_STATE_BLOCK_BYTES)want=LIE_STATE_BLOCK_BYTES;
            uint32_t stored=coded?coded:raw;
            ok=raw==want&&coded<raw&&stored<=bytes-offset;
            if(ok&&coded)ok=transfer(fd,block,stored,offset,false,cancel,hash)&&
                            lie_state_decode_block(block,stored,s->payload+at,raw);
            else if(ok)ok=transfer(fd,s->payload+at,raw,offset,false,cancel,hash);
            offset+=stored;at+=raw;
        }
        free(block);ok=ok&&offset==bytes;
    }else ok=s&&transfer(fd,s->payload,(size_t)payload,offset,false,cancel,hash);
    ok=ok&&EVP_DigestFinal_ex(hash,actual,&count)==1&&count==32&&!memcmp(expected,actual,32);
    EVP_MD_CTX_free(hash);
    /* Padding is canonical, and all physical token IDs are nonnegative. */
    if(ok){uint64_t end=0;for(unsigned i=0;i<l.section_count&&ok;++i){
        const lie_state_section *p=&l.sections[i];
        for(uint64_t k=end;k<p->offset;++k)if(s->payload[k])ok=false;
        end=p->offset+p->bytes;
    }
        const int32_t *tokens=lie_state_tokens(s);
        for(unsigned i=0;ok&&i<l.token_count;++i)if(tokens[i]<0)ok=false;
    }
    if(!ok||stopped(cancel))lie_state_destroy(&s);
    return s;
}
bool lie_state_prefix_key(const lie_state_identity *id,const int32_t *tokens,size_t n,char hex[65]){
    if(!id||!tokens||!n||n>UINT32_MAX||!hex)return false;
    EVP_MD_CTX *ctx=EVP_MD_CTX_new();if(!ctx)return false;
    unsigned char b[4096],digest[32];unsigned count=0;put64(b,n);
    bool ok=EVP_DigestInit_ex(ctx,EVP_sha256(),NULL)==1&&EVP_DigestUpdate(ctx,"LIE-prefix-key-v1",17)==1&&
        EVP_DigestUpdate(ctx,id->bytes,32)==1&&EVP_DigestUpdate(ctx,b,8)==1;
    for(size_t i=0;ok&&i<n;){size_t batch=n-i;if(batch>sizeof(b)/4)batch=sizeof(b)/4;
        for(size_t k=0;k<batch;++k)put32(b+4*k,(uint32_t)tokens[i+k]);
        ok=EVP_DigestUpdate(ctx,b,batch*4)==1;i+=batch;}
    ok=ok&&EVP_DigestFinal_ex(ctx,digest,&count)==1&&count==32;
    EVP_MD_CTX_free(ctx);if(ok)for(unsigned i=0;i<32;++i)snprintf(hex+2*i,3,"%02x",digest[i]);
    return ok;
}
