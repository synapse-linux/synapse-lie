/* SPDX-License-Identifier: MIT */
/* Model-neutral KVC persistence. The exact DS4 payload is retained in RAM.
 * A trailing LIE binding extension (after untouched client extensions) binds
 * identity, component descriptors and SHA-256. It is not model payload data. */
#include "state_kvc.h"
#include "state_internal.h"
#include "kvc_internal.h"
#include <errno.h>
#include <openssl/evp.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define FOOTER 192u
#define SECTION 64u
typedef struct {unsigned char h[52],f[FOOTER];uint64_t size,payload,aux,text,client,table;} frame;
static bool stopped(const atomic_bool *c){return c&&atomic_load(c);}
static bool io(int fd,void *p,size_t n,uint64_t offset,bool write,const atomic_bool *c,EVP_MD_CTX *hash){
    unsigned char *at=p;
    while(n){
        if(stopped(c)||offset>INT64_MAX)return false;
        size_t chunk=n>1048576?1048576:n;
        ssize_t got=write?pwrite(fd,at,chunk,(off_t)offset):pread(fd,at,chunk,(off_t)offset);
        if(got<0&&errno==EINTR)continue;
        if(got<=0)return false;
        if(hash&&EVP_DigestUpdate(hash,at,(size_t)got)!=1)return false;
        at+=got;offset+=(uint64_t)got;n-=(size_t)got;
    }
    return !stopped(c);
}
static bool regular(int fd,uint64_t *n){struct stat s;
    if(fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_uid!=geteuid()||s.st_nlink!=1||(s.st_mode&0777)!=0600||s.st_size<0)return false;
    *n=(uint64_t)s.st_size;return true;
}
bool lie_state_kvc_detect(int fd){unsigned char h[4];return io(fd,h,4,0,false,NULL,NULL)&&!memcmp(h,"KVC\1",4);}
static bool inspect(int fd,const lie_state_identity *id,frame *r){
    if(!id||!regular(fd,&r->size)||r->size<52+FOOTER||
       !io(fd,r->h,52,0,false,NULL,NULL)||!io(fd,r->f,FOOTER,r->size-FOOTER,false,NULL,NULL))return false;
    const unsigned char *h=r->h,*f=r->f;unsigned q=h[4];
    if(memcmp(h,"KVC\1",4)||h[20]!=2||(q!=2&&q!=4&&q!=5&&q!=6&&q!=8)||
       !kvc_u32(h+8)||kvc_u32(h+8)>kvc_u32(h+16)||h[5]>LIE_CACHE_AGENT_SESSION||(h[6]&~15u)||
       memcmp(f,"LIEKVC1",8)||(kvc_u32(f+8)!=1&&kvc_u32(f+8)!=2)||kvc_u32(f+12)!=FOOTER||
       memcmp(f+32,id->bytes,32)||!kvc_u32(f+16)||!kvc_u32(f+20)||
       !kvc_u32(f+24)||kvc_u32(f+24)>LIE_STATE_MAX_SECTIONS||kvc_u32(f+28)!=LIE_STATE_ABI)return false;
    for(unsigned i=21;i<24;++i)if(h[i])return false;
    r->aux=0;
    if(kvc_u32(f+8)==1){for(unsigned i=176;i<FOOTER;++i)if(f[i])return false;}
    else{
        r->aux=kvc_u64(f+176);
        if(!r->aux||r->aux>SIZE_MAX||kvc_u32(f+184)!=LIE_STATE_KVC_AUX||kvc_u32(f+188))return false;
    }
    r->text=kvc_u32(h+48);r->payload=kvc_u64(h+40);r->client=kvc_u64(f+128);
    uint64_t table=(uint64_t)kvc_u32(f+24)*SECTION;
    if(r->text>LIE_CACHE_TEXT_MAX||!r->payload||r->payload>SIZE_MAX||r->client>LIE_CACHE_TRAILER_MAX||
       r->payload>SIZE_MAX-r->aux||r->payload!=kvc_u64(f+136)||r->size<52+FOOTER+table+r->text+r->client||
       r->size-52-FOOTER-table-r->text-r->client!=r->payload+r->aux)return false;
    r->table=52+r->text+r->payload+r->client+r->aux;return true;
}
uint64_t lie_state_kvc_bytes(const lie_state *s,const lie_cache_metadata *m){
    uint64_t model,aux;
    if(!s||!lie_state_kvc_parts(&s->layout,&model,&aux)||model+aux!=s->payload_bytes||s->codec||s->storage_bytes!=s->payload_bytes||
       (m&&!lie_cache_metadata_valid(m)))return UINT64_MAX;
    uint64_t overhead=52+FOOTER+(uint64_t)s->layout.section_count*SECTION+(m?m->text_bytes+m->trailer_bytes:0);
    return s->payload_bytes>UINT64_MAX-overhead?UINT64_MAX:s->payload_bytes+overhead;
}
static void encode(unsigned char b[SECTION],const lie_state_section *s){
    kvc_put32(b,s->role);kvc_put32(b+4,s->layer);kvc_put32(b+8,s->dtype);kvc_put32(b+12,s->rank);
    for(unsigned i=0;i<4;++i)kvc_put64(b+16+8*i,s->shape[i]);
    kvc_put64(b+48,s->bytes);kvc_put64(b+56,s->offset);
}
static void decode(lie_state_section *s,const unsigned char b[SECTION]){
    s->role=kvc_u32(b);s->layer=kvc_u32(b+4);s->dtype=kvc_u32(b+8);s->rank=kvc_u32(b+12);
    for(unsigned i=0;i<4;++i)s->shape[i]=kvc_u64(b+16+8*i);
    s->bytes=kvc_u64(b+48);s->offset=kvc_u64(b+56);
}
static bool hash_header(EVP_MD_CTX *hash,const unsigned char h[52]){
    unsigned char b[52];memcpy(b,h,52);memset(b+12,0,4);memset(b+32,0,8);
    return EVP_DigestUpdate(hash,b,52)==1;
}
bool lie_state_kvc_write(int fd,const lie_state_identity *id,const lie_state *s,const lie_cache_metadata *meta,const atomic_bool *c){
    lie_cache_metadata empty={0};const lie_cache_metadata *m=meta?meta:&empty;
    uint64_t size=0,payload=0,aux=0;
    if(!id||!s||!regular(fd,&size)||size||!lie_state_kvc_parts(&s->layout,&payload,&aux)||payload+aux!=s->payload_bytes||
       lie_state_kvc_bytes(s,m)>INT64_MAX)return false;
    unsigned char h[52]={0},f[FOOTER]={0},b[SECTION];
    memcpy(h,"KVC\1",4);h[4]=(uint8_t)s->layout.quant_bits;h[5]=(uint8_t)m->reason;
    h[6]=(uint8_t)m->flags;h[7]=(uint8_t)s->layout.model_id;h[20]=2;
    kvc_put32(h+8,s->layout.token_count);kvc_put32(h+12,m->hits);kvc_put32(h+16,s->layout.context_tokens);
    kvc_put64(h+24,m->created_at);kvc_put64(h+32,m->last_used);kvc_put64(h+40,payload);kvc_put32(h+48,(uint32_t)m->text_bytes);
    memcpy(f,"LIEKVC1",8);kvc_put32(f+8,aux?2:1);kvc_put32(f+12,FOOTER);kvc_put32(f+16,s->layout.representation_version);
    kvc_put32(f+20,s->layout.prefill_chunk);kvc_put32(f+24,s->layout.section_count);kvc_put32(f+28,LIE_STATE_ABI);
    memcpy(f+32,id->bytes,32);for(unsigned i=0;i<8;++i)kvc_put32(f+96+4*i,s->layout.model_data[i]);
    kvc_put64(f+128,m->trailer_bytes);kvc_put64(f+136,payload);
    if(aux){kvc_put64(f+176,aux);kvc_put32(f+184,LIE_STATE_KVC_AUX);}
    char key[65];if(!lie_state_prefix_key(id,lie_state_tokens(s),s->layout.token_count,key))return false;
    for(unsigned i=0;i<32;++i){unsigned hi=(unsigned)(key[2*i]<='9'?key[2*i]-'0':key[2*i]-'a'+10);
        unsigned lo=(unsigned)(key[2*i+1]<='9'?key[2*i+1]-'0':key[2*i+1]-'a'+10);f[144+i]=(unsigned char)(hi*16+lo);}
    EVP_MD_CTX *hash=EVP_MD_CTX_new();if(!hash)return false;
    bool ok=EVP_DigestInit_ex(hash,EVP_sha256(),NULL)==1&&hash_header(hash,h)&&io(fd,h,52,0,true,c,NULL);
    uint64_t at=52;
    ok=ok&&io(fd,(void *)m->text,m->text_bytes,at,true,c,hash);at+=m->text_bytes;
    ok=ok&&io(fd,(void *)s->payload,(size_t)payload,at,true,c,hash);at+=payload;
    ok=ok&&io(fd,(void *)m->trailer,m->trailer_bytes,at,true,c,hash);at+=m->trailer_bytes;
    ok=ok&&io(fd,(void *)(s->payload+payload),(size_t)aux,at,true,c,hash);at+=aux;
    for(unsigned i=0;ok&&i<s->layout.section_count;++i){encode(b,&s->layout.sections[i]);ok=io(fd,b,SECTION,at,true,c,hash);at+=SECTION;}
    unsigned n=0;
    ok=ok&&EVP_DigestUpdate(hash,f,FOOTER)==1&&EVP_DigestFinal_ex(hash,f+64,&n)==1&&n==32&&io(fd,f,FOOTER,at,true,c,NULL);
    EVP_MD_CTX_free(hash);return ok;
}
static bool hash_range(int fd,uint64_t at,uint64_t bytes,const atomic_bool *c,EVP_MD_CTX *hash){
    unsigned char b[4096];while(bytes){size_t n=bytes>sizeof(b)?sizeof(b):(size_t)bytes;
        if(!io(fd,b,n,at,false,c,hash))return false;
        bytes-=n;at+=n;}return true;
}
lie_state *lie_state_kvc_read(int fd,const lie_state_identity *id,uint64_t domain,uint64_t budget,const atomic_bool *c){
    frame r;if(!domain||stopped(c)||!inspect(fd,id,&r)||r.payload+r.aux>budget||sizeof(lie_state)>budget-r.payload-r.aux)return NULL;
    lie_state_layout l={.abi_version=LIE_STATE_ABI,.domain=domain,.format=r.aux?LIE_STATE_KVC_AUX:LIE_STATE_KVC,
        .model_id=r.h[7],.quant_bits=r.h[4],.representation_version=kvc_u32(r.f+16),.prefill_chunk=kvc_u32(r.f+20),
        .section_count=kvc_u32(r.f+24),.token_count=kvc_u32(r.h+8),.context_tokens=kvc_u32(r.h+16)};
    for(unsigned i=0;i<8;++i)l.model_data[i]=kvc_u32(r.f+96+4*i);
    unsigned char table[LIE_STATE_MAX_SECTIONS*SECTION];size_t table_bytes=l.section_count*SECTION;
    if(!io(fd,table,table_bytes,r.table,false,c,NULL))return NULL;
    for(unsigned i=0;i<l.section_count;++i)decode(&l.sections[i],table+i*SECTION);
    uint64_t model,aux;if(!lie_state_kvc_parts(&l,&model,&aux)||model!=r.payload||aux!=r.aux)return NULL;
    lie_state *s=lie_state_allocate(&l,budget);if(!s)return NULL;
    EVP_MD_CTX *hash=EVP_MD_CTX_new();unsigned char want[32],actual[32];unsigned n=0;
    memcpy(want,r.f+64,32);memset(r.f+64,0,32);
    bool ok=hash&&EVP_DigestInit_ex(hash,EVP_sha256(),NULL)==1&&hash_header(hash,r.h)&&
        hash_range(fd,52,r.text,c,hash)&&io(fd,s->payload,(size_t)r.payload,52+r.text,false,c,hash)&&
        hash_range(fd,52+r.text+r.payload,r.client,c,hash)&&
        io(fd,s->payload+r.payload,(size_t)r.aux,52+r.text+r.payload+r.client,false,c,hash)&&EVP_DigestUpdate(hash,table,table_bytes)==1&&
        EVP_DigestUpdate(hash,r.f,FOOTER)==1&&EVP_DigestFinal_ex(hash,actual,&n)==1&&n==32&&!memcmp(want,actual,32);
    EVP_MD_CTX_free(hash);
    const int32_t *tokens=lie_state_tokens(s);
    for(uint32_t i=0;ok&&i<l.token_count;++i){if(!(i%16384)&&stopped(c))ok=false;if(tokens[i]<0)ok=false;}
    if(!ok||stopped(c))lie_state_destroy(&s);
    return s;
}
bool lie_state_kvc_probe(int fd,const lie_state_identity *id,uint64_t *bytes,unsigned *tokens,unsigned *context){
    frame r;if(!bytes||!tokens||!inspect(fd,id,&r))return false;
    *bytes=r.size;*tokens=kvc_u32(r.h+8);if(context)*context=kvc_u32(r.h+16);return true;
}
bool lie_state_kvc_metadata(int fd,const lie_state_identity *id,uint64_t budget,lie_cache_metadata *out){
    if(!out)return false;
    memset(out,0,sizeof(*out));frame r;
    if(!inspect(fd,id,&r)||r.text+r.client+(r.text?1:0)>budget)return false;
    char *text=r.text?malloc((size_t)r.text+1):NULL;void *trailer=r.client?malloc((size_t)r.client):NULL;
    if((r.text&&!text)||(r.client&&!trailer)||!io(fd,text,(size_t)r.text,52,false,NULL,NULL)||
       !io(fd,trailer,(size_t)r.client,52+r.text+r.payload,false,NULL,NULL)){free(text);free(trailer);return false;}
    if(text)text[r.text]=0;
    *out=(lie_cache_metadata){.text=text,.text_bytes=(size_t)r.text,.trailer=trailer,.trailer_bytes=(size_t)r.client,
        .reason=r.h[5],.flags=r.h[6],.hits=kvc_u32(r.h+12),.created_at=kvc_u64(r.h+24),.last_used=kvc_u64(r.h+32)};
    return true;
}
bool lie_state_kvc_touch(int fd,const lie_state_identity *id,uint32_t hits,uint64_t last){
    frame r;unsigned char b[8];if(!inspect(fd,id,&r))return false;
    kvc_put32(b,hits);if(!io(fd,b,4,12,true,NULL,NULL))return false;
    kvc_put64(b,last);return io(fd,b,8,32,true,NULL,NULL);
}
bool lie_state_kvc_token_key(int fd,const lie_state_identity *id,char hex[65]){
    frame r;if(!hex||!inspect(fd,id,&r))return false;
    static const char digits[]="0123456789abcdef";
    for(unsigned i=0;i<32;++i){hex[2*i]=digits[r.f[144+i]>>4];hex[2*i+1]=digits[r.f[144+i]&15];}
    hex[64]=0;return true;
}
