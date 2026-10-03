/* SPDX-License-Identifier: MIT */
#include "kvc_internal.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <openssl/evp.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define KVC_IO_BYTES (1024u*1024u)
struct lie_kvc { lie_kvc_view view; size_t bytes; unsigned char wire[]; };
lie_kvc_limits lie_kvc_default_limits(uint64_t bytes) {
    return (lie_kvc_limits){.memory_bytes=bytes,.text_bytes=8u*1024u*1024u,.trailer_bytes=1024u*1024u};
}
static int quant_valid(unsigned q) { return q==2||q==4||q==5||q==6||q==8; }
static lie_status bounds(const unsigned char *p,uint64_t bytes,const lie_kvc_limits *l,
                         lie_kvc_header *h,size_t *text,size_t *payload,size_t *trailer,lie_error *e) {
    if(!l||bytes<LIE_KVC_HEADER_BYTES)return kvc_fail(e,LIE_INVALID,"truncated KVC header");
    if(kvc_cancelled(l))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
    if(memcmp(p,"KVC",3)||p[3]!=1||p[20]!=2)
        return kvc_fail(e,LIE_UNSUPPORTED,"unsupported KVC version or payload ABI");
    *h=(lie_kvc_header){.model_id=p[7],.quant_bits=p[4],.reason=p[5],.flags=p[6],
        .tokens=kvc_u32(p+8),.hits=kvc_u32(p+12),.context_tokens=kvc_u32(p+16),
        .created_at=kvc_u64(p+24),.last_used=kvc_u64(p+32)};
    if(!quant_valid(h->quant_bits)||!h->tokens||h->tokens>h->context_tokens)
        return kvc_fail(e,LIE_INVALID,"invalid KVC quantization or token count");
    uint64_t nt=kvc_u32(p+48),np=kvc_u64(p+40),remaining=bytes-LIE_KVC_HEADER_BYTES;
    if(nt>remaining||np>remaining-nt||!np)return kvc_fail(e,LIE_INVALID,"truncated KVC text or payload");
    uint64_t nx=remaining-nt-np;
    if(bytes>SIZE_MAX-sizeof(lie_kvc)||l->memory_bytes<sizeof(lie_kvc)||
       bytes>l->memory_bytes-sizeof(lie_kvc)||nt>l->text_bytes||nx>l->trailer_bytes)
        return kvc_fail(e,LIE_RESOURCE_LIMIT,"KVC memory or metadata budget exceeded");
    *text=(size_t)nt;*payload=(size_t)np;*trailer=(size_t)nx;return LIE_OK;
}
lie_status lie_kvc_parse(const void *raw,size_t bytes,const lie_kvc_limits *l,lie_kvc_view *out,lie_error *e) {
    if(!raw||!out)return kvc_fail(e,LIE_INVALID,"invalid KVC input");
    lie_kvc_view v={0};size_t nt=0,np=0,nx=0;
    lie_status rc=bounds(raw,bytes,l,&v.header,&nt,&np,&nx,e);if(rc!=LIE_OK)return rc;
    const unsigned char *p=raw;
    v.text=(lie_kvc_span){p+LIE_KVC_HEADER_BYTES,nt};
    v.payload=(lie_kvc_span){v.text.data+nt,np};v.trailer=(lie_kvc_span){v.payload.data+np,nx};
    *out=v;return LIE_OK;
}
static lie_status copy_bytes(unsigned char *dst,const unsigned char *src,size_t n,
                             const lie_kvc_limits *l,lie_error *e) {
    while(n){
        if(kvc_cancelled(l))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
        size_t chunk=n>KVC_IO_BYTES?KVC_IO_BYTES:n;
        memcpy(dst,src,chunk);dst+=chunk;src+=chunk;n-=chunk;
    }
    return LIE_OK;
}
lie_status lie_kvc_create(const lie_kvc_view *v,const lie_kvc_limits *l,lie_kvc **out,lie_error *e) {
    if(!v||!l||!out||*out||(!v->text.data&&v->text.bytes)||!v->payload.data||
       (!v->trailer.data&&v->trailer.bytes)||v->text.bytes>UINT32_MAX)
        return kvc_fail(e,LIE_INVALID,"invalid KVC components");
    size_t n=LIE_KVC_HEADER_BYTES;
    const lie_kvc_span spans[]={v->text,v->payload,v->trailer};
    for(unsigned i=0;i<3;++i){
        if(spans[i].bytes>SIZE_MAX-n)return kvc_fail(e,LIE_RESOURCE_LIMIT,"KVC length overflow");
        n+=spans[i].bytes;
    }
    unsigned char header[LIE_KVC_HEADER_BYTES]={0};
    memcpy(header,"KVC\1",4);header[4]=v->header.quant_bits;header[5]=v->header.reason;
    header[6]=v->header.flags;header[7]=v->header.model_id;header[20]=2;
    kvc_put32(header+8,v->header.tokens);kvc_put32(header+12,v->header.hits);
    kvc_put32(header+16,v->header.context_tokens);kvc_put64(header+24,v->header.created_at);
    kvc_put64(header+32,v->header.last_used);kvc_put64(header+40,v->payload.bytes);
    kvc_put32(header+48,(uint32_t)v->text.bytes);
    lie_kvc_header h;size_t nt,np,nx;
    lie_status rc=bounds(header,n,l,&h,&nt,&np,&nx,e);if(rc!=LIE_OK)return rc;
    lie_kvc *k=malloc(sizeof(*k)+n);if(!k)return kvc_fail(e,LIE_RESOURCE_LIMIT,"KVC allocation failed");
    k->bytes=n;memcpy(k->wire,header,sizeof(header));size_t pos=sizeof(header);
    for(unsigned i=0;i<3&&rc==LIE_OK;++i){rc=copy_bytes(k->wire+pos,spans[i].data,spans[i].bytes,l,e);pos+=spans[i].bytes;}
    if(rc==LIE_OK)rc=lie_kvc_parse(k->wire,n,l,&k->view,e);
    if(rc!=LIE_OK){free(k);return rc;}*out=k;return LIE_OK;
}
static lie_status transfer(int fd,unsigned char *p,size_t bytes,int writing,
                           const lie_kvc_limits *l,lie_error *e) {
    size_t pos=0;
    if((uint64_t)bytes>INT64_MAX||sizeof(off_t)<8)return kvc_fail(e,LIE_UNSUPPORTED,"KVC requires 64-bit file offsets");
    while(pos<bytes){
        if(kvc_cancelled(l))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
        size_t chunk=bytes-pos;if(chunk>KVC_IO_BYTES)chunk=KVC_IO_BYTES;
        ssize_t n=writing?pwrite(fd,p+pos,chunk,(off_t)pos):pread(fd,p+pos,chunk,(off_t)pos);
        if(n<0&&errno==EINTR)continue;
        if(n<=0||(size_t)n>chunk)return kvc_fail(e,LIE_BACKEND_FAILED,writing?"KVC write failed":"KVC read failed");
        pos+=(size_t)n;
    }
    if(kvc_cancelled(l))return kvc_fail(e,LIE_CANCELLED,"KVC operation cancelled");
    return LIE_OK;
}
static int same_file(const struct stat *a,const struct stat *b) {
    return a->st_dev==b->st_dev&&a->st_ino==b->st_ino&&a->st_size==b->st_size&&
        a->st_mtim.tv_sec==b->st_mtim.tv_sec&&a->st_mtim.tv_nsec==b->st_mtim.tv_nsec&&
        a->st_ctim.tv_sec==b->st_ctim.tv_sec&&a->st_ctim.tv_nsec==b->st_ctim.tv_nsec;
}
lie_status lie_kvc_read_fd(int fd,const lie_kvc_limits *l,lie_kvc **out,lie_error *e) {
    if(!l||!out||*out)return kvc_fail(e,LIE_INVALID,"invalid KVC read request");
    struct stat before,after;
    if(fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_size<LIE_KVC_HEADER_BYTES)
        return kvc_fail(e,LIE_INVALID,"KVC source must be a complete regular file");
    unsigned char header[LIE_KVC_HEADER_BYTES];
    lie_status rc=transfer(fd,header,sizeof(header),0,l,e);if(rc!=LIE_OK)return rc;
    lie_kvc_header h;size_t nt,np,nx;
    rc=bounds(header,(uint64_t)before.st_size,l,&h,&nt,&np,&nx,e);if(rc!=LIE_OK)return rc;
    size_t n=(size_t)before.st_size;lie_kvc *k=malloc(sizeof(*k)+n);
    if(!k)return kvc_fail(e,LIE_RESOURCE_LIMIT,"KVC allocation failed");
    k->bytes=n;rc=transfer(fd,k->wire,n,0,l,e);
    if(rc==LIE_OK&&(fstat(fd,&after)||!same_file(&before,&after)||memcmp(header,k->wire,sizeof(header))))
        rc=kvc_fail(e,LIE_INVALID,"KVC source changed during read");
    if(rc==LIE_OK)rc=lie_kvc_parse(k->wire,n,l,&k->view,e);
    if(rc!=LIE_OK){free(k);return rc;}*out=k;return LIE_OK;
}
lie_status lie_kvc_write_fd(int fd,const lie_kvc *k,const lie_kvc_limits *l,lie_error *e) {
    if(!k||!l)return kvc_fail(e,LIE_INVALID,"invalid KVC write request");
    lie_kvc_view v;lie_status rc=lie_kvc_parse(k->wire,k->bytes,l,&v,e);if(rc!=LIE_OK)return rc;
    struct stat st;int flags=fcntl(fd,F_GETFL);
    if(flags<0||(flags&O_APPEND)||fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size||
       st.st_uid!=geteuid()||st.st_nlink!=1||(st.st_mode&0777)!=0600)
        return kvc_fail(e,LIE_INVALID,"KVC destination must be an empty private regular file");
    return transfer(fd,(unsigned char *)k->wire,k->bytes,1,l,e);
}
const lie_kvc_view *lie_kvc_get_view(const lie_kvc *k){return k?&k->view:NULL;}
lie_kvc_span lie_kvc_wire(const lie_kvc *k){return k?(lie_kvc_span){k->wire,k->bytes}:(lie_kvc_span){0};}
uint64_t lie_kvc_memory_bytes(const lie_kvc *k){return k?sizeof(*k)+(uint64_t)k->bytes:0;}
void lie_kvc_destroy(lie_kvc **k){if(k){free(*k);*k=NULL;}}
lie_status lie_kvc_filename(lie_kvc_span text,char out[44],lie_error *e) {
    if(!out||(!text.data&&text.bytes))return kvc_fail(e,LIE_INVALID,"invalid KVC text key");
    unsigned char digest[EVP_MAX_MD_SIZE];unsigned n=0;
    if(!EVP_Digest(text.data,text.bytes,digest,&n,EVP_sha1(),NULL)||n!=20)
        return kvc_fail(e,LIE_BACKEND_FAILED,"KVC text digest failed");
    static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<20;++i){out[2*i]=hex[digest[i]>>4];out[2*i+1]=hex[digest[i]&15];}
    memcpy(out+40,".kv",4);return LIE_OK;
}
