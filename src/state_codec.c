/* SPDX-License-Identifier: MIT */
#include "state_codec.h"
#include "state_internal.h"
#include "state_kvc.h"
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
    if(s->layout.format!=LIE_STATE_ALIGNED)return lie_state_kvc_bytes(s,NULL);
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
static uint64_t payload_end(const unsigned char *h){
    return LIE_STATE_DISK_HEADER+(uint64_t)u32(h+20)*LIE_STATE_DISK_SECTION+
        (u32(h+36)?u64(h+152):u64(h+40));
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
    if(u32(h+8)==3){
        uint64_t stored=u32(h+36)?u64(h+152):u64(h+40);
        return stored<=*size-prefix&&*size-prefix-stored>=64&&
            ((!u32(h+36)&&!u64(h+152))||
             ((u32(h+36)==1||u32(h+36)==2)&&lie_state_compression_enabled()&&stored<u64(h+40)));
    }
    return u32(h+8)==2&&(u32(h+36)==1||u32(h+36)==2)&&lie_state_compression_enabled()&&
           u64(h+152)==*size-prefix&&u64(h+152)<u64(h+40);
}
/* Usage counters are advisory and deliberately excluded from the digest so
 * a hit never rehashes multi-GiB tensors. Text, extensions and reason ARE hashed. */
static bool metadata_header(int fd,const unsigned char *h,unsigned char b[64],uint64_t *offset){
    *offset=payload_end(h);
    if(u32(h+8)!=3||!transfer(fd,b,64,*offset,false,NULL,NULL)||memcmp(b,"LIECACH1",8))return false;
    uint64_t tail=64ull+u32(b+40)+u32(b+44);
    if(tail!=u64(h+48)-*offset||u32(b+12)||u32(b+32)>LIE_CACHE_AGENT_SESSION||
       (u32(b+36)&~15u)||u32(b+40)>LIE_CACHE_TEXT_MAX||u32(b+44)>LIE_CACHE_TRAILER_MAX)return false;
    for(unsigned i=48;i<64;++i)if(b[i])return false;
    return true;
}
bool lie_state_file_metadata(int fd,const lie_state_identity *id,uint64_t budget,lie_cache_metadata *m){
    if(lie_state_kvc_detect(fd))return lie_state_kvc_metadata(fd,id,budget,m);
    unsigned char h[LIE_STATE_DISK_HEADER],b[64];uint64_t size,offset;
    memset(m,0,sizeof(*m));
    if(!read_header(fd,id,h,&size))return false;
    if(u32(h+8)!=3)return true;
    if(!metadata_header(fd,h,b,&offset))return false;
    m->hits=u32(b+8);m->last_used=u64(b+16);m->created_at=u64(b+24);
    m->reason=u32(b+32);m->flags=u32(b+36);m->text_bytes=u32(b+40);m->trailer_bytes=u32(b+44);
    if(m->text_bytes+m->trailer_bytes+1>budget){memset(m,0,sizeof(*m));return false;}
    char *text=m->text_bytes?malloc(m->text_bytes+1):NULL;
    void *trailer=m->trailer_bytes?malloc(m->trailer_bytes):NULL;
    m->text=text;m->trailer=trailer;
    bool ok=(!m->text_bytes||(text&&transfer(fd,text,m->text_bytes,offset+64,false,NULL,NULL)))&&
        (!m->trailer_bytes||(trailer&&transfer(fd,trailer,m->trailer_bytes,offset+64+m->text_bytes,false,NULL,NULL)));
    if(ok&&text)text[m->text_bytes]=0;
    if(!ok)lie_cache_metadata_clear(m);
    return ok;
}
bool lie_state_file_touch(int fd,const lie_state_identity *id,uint32_t hits,uint64_t last){
    if(lie_state_kvc_detect(fd))return lie_state_kvc_touch(fd,id,hits,last);
    unsigned char h[LIE_STATE_DISK_HEADER],b[64],usage[16]={0};uint64_t size,offset;
    if(!read_header(fd,id,h,&size))return false;
    if(u32(h+8)!=3)return true; /* Legacy checkpoints have no usage record. */
    if(!metadata_header(fd,h,b,&offset))return false;
    put32(usage,hits);put64(usage+8,last);
    return transfer(fd,usage,sizeof(usage),offset+8,true,NULL,NULL);
}
uint64_t lie_state_file_bytes_ex(const lie_state *s,const lie_cache_metadata *m){
    if(s&&s->layout.format!=LIE_STATE_ALIGNED)return lie_state_kvc_bytes(s,m);
    uint64_t n=lie_state_file_bytes(s);
    if(!m)return n;
    uint64_t extra=64ull+m->text_bytes+m->trailer_bytes;
    return !lie_cache_metadata_valid(m)||n>UINT64_MAX-extra?UINT64_MAX:n+extra;
}
static bool metadata_write(int fd,const lie_cache_metadata *m,uint64_t at,const atomic_bool *cancel,EVP_MD_CTX *hash){
    unsigned char b[64]={0};memcpy(b,"LIECACH1",8);
    put64(b+24,m->created_at);put32(b+32,m->reason);put32(b+36,m->flags);
    put32(b+40,(uint32_t)m->text_bytes);put32(b+44,(uint32_t)m->trailer_bytes);
    if(EVP_DigestUpdate(hash,b,sizeof(b))!=1)return false;
    put32(b+8,m->hits);put64(b+16,m->last_used);
    return transfer(fd,b,sizeof(b),at,true,cancel,NULL)&&
        transfer(fd,(void *)m->text,m->text_bytes,at+64,true,cancel,hash)&&
        transfer(fd,(void *)m->trailer,m->trailer_bytes,at+64+m->text_bytes,true,cancel,hash);
}
static bool metadata_hash(int fd,const unsigned char *h,const atomic_bool *cancel,EVP_MD_CTX *hash){
    unsigned char b[64],buf[4096];uint64_t at;
    if(!metadata_header(fd,h,b,&at))return false;
    memset(b+8,0,16);
    if(EVP_DigestUpdate(hash,b,sizeof(b))!=1)return false;
    at+=64;
    while(at<u64(h+48)){uint64_t n=u64(h+48)-at;if(n>sizeof(buf))n=sizeof(buf);
        if(!transfer(fd,buf,(size_t)n,at,false,cancel,hash))return false;
        at+=n;}
    return true;
}
bool lie_state_file_probe(int fd,const lie_state_identity *id,uint64_t *bytes,unsigned *tokens,unsigned *context){
    if(lie_state_kvc_detect(fd))return lie_state_kvc_probe(fd,id,bytes,tokens,context);
    unsigned char h[LIE_STATE_DISK_HEADER];
    if(!id||!bytes||!tokens||!read_header(fd,id,h,bytes))return false;
    *tokens=u32(h+24);if(context)*context=u32(h+28);return true;
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
bool lie_state_file_write_ex(int fd,const lie_state_identity *id,const lie_state *s,const lie_cache_metadata *m,const atomic_bool *cancel){
    if(s&&s->layout.format!=LIE_STATE_ALIGNED)return platform()&&lie_state_kvc_write(fd,id,s,m,cancel);
    uint64_t bytes=0,payload=0;
    if(!platform()||!id||!s||!regular(fd,&bytes)||bytes||!lie_state_validate(&s->layout,&payload)||
       payload!=s->payload_bytes||lie_state_file_bytes_ex(s,m)>INT64_MAX||s->codec>2||
       (!s->codec&&s->storage_bytes!=payload)||
       (s->codec&&(s->storage_bytes>=payload||s->layout.sections[0].role!=LIE_STATE_TOKENS)))return false;
    EVP_MD_CTX *hash=EVP_MD_CTX_new();if(!hash)return false;
    unsigned char h[LIE_STATE_DISK_HEADER],section[LIE_STATE_DISK_SECTION],digest[32];unsigned count=0;
    header(h,id,s);
    if(m){put32(h+8,3);put64(h+48,lie_state_file_bytes_ex(s,m));}
    bool ok=EVP_DigestInit_ex(hash,EVP_sha256(),NULL)==1&&transfer(fd,h,sizeof(h),0,true,cancel,hash);
    uint64_t offset=sizeof(h);
    for(unsigned i=0;ok&&i<s->layout.section_count;++i){encode_section(section,&s->layout.sections[i]);
        ok=transfer(fd,section,sizeof(section),offset,true,cancel,hash);offset+=sizeof(section);}
    ok=ok&&transfer(fd,(void *)s->payload,(size_t)s->storage_bytes,offset,true,cancel,hash)&&
       (!m||metadata_write(fd,m,offset+s->storage_bytes,cancel,hash))&&
       EVP_DigestFinal_ex(hash,digest,&count)==1&&count==32&&transfer(fd,digest,32,88,true,cancel,NULL);
    EVP_MD_CTX_free(hash);return ok;
}
bool lie_state_file_write(int fd,const lie_state_identity *id,const lie_state *s,const atomic_bool *cancel){
    return lie_state_file_write_ex(fd,id,s,NULL,cancel);
}
lie_state *lie_state_file_read(int fd,const lie_state_identity *id,uint64_t domain,uint64_t budget,const atomic_bool *cancel){
    if(lie_state_kvc_detect(fd))return platform()?lie_state_kvc_read(fd,id,domain,budget,cancel):NULL;
    unsigned char h[LIE_STATE_DISK_HEADER],section[LIE_STATE_DISK_SECTION],expected[32],actual[32];uint64_t bytes=0;
    if(!domain||!id||stopped(cancel)||!read_header(fd,id,h,&bytes)||u64(h+40)>budget||
       sizeof(lie_state)>budget-u64(h+40))return NULL;
    uint64_t scratch=u32(h+36)?LIE_STATE_BLOCK_BYTES+lie_state_decode_workspace(u32(h+36)):0;
    if(scratch>budget-u64(h+40)-sizeof(lie_state))return NULL;
    uint64_t data_end=payload_end(h);
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
        ok=block&&l.sections[0].role==LIE_STATE_TOKENS&&at<=data_end-offset&&
           transfer(fd,s->payload,(size_t)at,offset,false,cancel,hash);offset+=at;
        while(ok&&at<payload){
            unsigned char frame[8];
            ok=data_end-offset>=sizeof(frame)&&transfer(fd,frame,sizeof(frame),offset,false,cancel,hash);offset+=sizeof(frame);
            if(!ok)break;
            uint32_t raw=u32(frame),coded=u32(frame+4);uint64_t want=payload-at;
            if(want>LIE_STATE_BLOCK_BYTES)want=LIE_STATE_BLOCK_BYTES;
            uint32_t stored=coded?coded:raw;
            ok=raw==want&&coded<raw&&stored<=data_end-offset;
            if(ok&&coded)ok=transfer(fd,block,stored,offset,false,cancel,hash)&&
                            lie_state_decode_block(u32(h+36),block,stored,s->payload+at,raw);
            else if(ok)ok=transfer(fd,s->payload+at,raw,offset,false,cancel,hash);
            offset+=stored;at+=raw;
        }
        free(block);ok=ok&&offset==data_end;
    }else ok=s&&transfer(fd,s->payload,(size_t)payload,offset,false,cancel,hash);
    ok=ok&&(u32(h+8)!=3||metadata_hash(fd,h,cancel,hash));
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
