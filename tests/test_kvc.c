/* SPDX-License-Identifier: MIT */
/* Parser/serializer and I/O faults only. NOT-INFERENCE. */
#include "lie/kvc_qwen.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
ssize_t __real_pread(int,void *,size_t,off_t);
ssize_t __real_pwrite(int,const void *,size_t,off_t);
static unsigned reads,writes;
static int short_io,read_fault,write_fault;
ssize_t __wrap_pread(int fd,void *p,size_t n,off_t off) {
    ++reads;
    if(read_fault==1){read_fault=0;errno=EINTR;return -1;}
    if(read_fault==2)return 0;
    if(read_fault==3&&reads==2){unsigned char value=99;
        assert(__real_pwrite(fd,&value,1,5)==1);read_fault=0;}
    if(short_io&&n>7)n=7;
    return __real_pread(fd,p,n,off);
}
ssize_t __wrap_pwrite(int fd,const void *p,size_t n,off_t off) {
    ++writes;
    if(write_fault==1){write_fault=0;errno=EINTR;return -1;}
    if(write_fault==2){errno=ENOSPC;return -1;}
    if(short_io&&n>11)n=11;
    return __real_pwrite(fd,p,n,off);
}
static void put32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;++i)p[i]=(unsigned char)(v>>(8*i));}
static int cancel(void *u){unsigned *n=u;return --*n==0;}
static int scratch(void){char path[]="/tmp/lie-kvc-test-XXXXXX";int fd=mkstemp(path);assert(fd>=0);assert(!unlink(path));return fd;}
int main(int argc,char **argv) {
    assert(argc==3);
    lie_error e={0};lie_kvc_limits limits=lie_kvc_default_limits(1024*1024);
    lie_kvc *k=NULL,*again=NULL;lie_kvc_view v;
    int fd=open(argv[1],O_RDONLY);assert(fd>=0);
    read_fault=1;short_io=1;
    assert(lie_kvc_read_fd(fd,&limits,&k,&e)==LIE_OK&&reads>10);short_io=0;
    assert(!lseek(fd,0,SEEK_CUR));
    const lie_kvc_view *view=lie_kvc_get_view(k);lie_kvc_span wire=lie_kvc_wire(k);
    assert(view->header.model_id==5&&view->header.tokens==5&&view->header.reason==6&&view->header.flags==15);
    assert(view->text.bytes==7&&view->header.hits==7&&view->header.created_at==123456789);
    assert(lie_kvc_parse(wire.data,wire.bytes,&limits,&v,&e)==LIE_OK);
    assert(v.payload.data==view->payload.data);
    assert(lie_kvc_create(view,&limits,&again,&e)==LIE_OK);
    assert(lie_kvc_wire(again).bytes==wire.bytes&&!memcmp(lie_kvc_wire(again).data,wire.data,wire.bytes));
    lie_kvc_destroy(&again);
    uint64_t exact=lie_kvc_memory_bytes(k);lie_kvc_limits tight=limits;tight.memory_bytes=exact-1;
    assert(lie_kvc_read_fd(fd,&tight,&again,&e)==LIE_RESOURCE_LIMIT&&!again);
    ++tight.memory_bytes;assert(lie_kvc_read_fd(fd,&tight,&again,&e)==LIE_OK);lie_kvc_destroy(&again);
    tight=limits;tight.text_bytes=6;assert(lie_kvc_create(view,&tight,&again,&e)==LIE_RESOURCE_LIMIT);
    tight=limits;tight.trailer_bytes=0;assert(lie_kvc_read_fd(fd,&tight,&again,&e)==LIE_RESOURCE_LIMIT);
    lie_kvc_view sentinel;memset(&sentinel,0x5a,sizeof(sentinel));v=sentinel;
    for(size_t n=0;n<wire.bytes-view->trailer.bytes;++n){
        assert(lie_kvc_parse(wire.data,n,&limits,&v,&e)!=LIE_OK);
        assert(!memcmp(&v,&sentinel,sizeof(v)));
    }
    unsigned char *bad=malloc(wire.bytes);assert(bad);
    memcpy(bad,wire.data,wire.bytes);memset(bad+40,0xff,8);
    assert(lie_kvc_parse(bad,wire.bytes,&limits,&v,&e)==LIE_INVALID);
    memcpy(bad,wire.data,wire.bytes);put32(bad+48,UINT32_MAX);
    assert(lie_kvc_parse(bad,wire.bytes,&limits,&v,&e)==LIE_INVALID);
    for(unsigned at=3;at<=20;at+=17){memcpy(bad,wire.data,wire.bytes);bad[at]=99;
        assert(lie_kvc_parse(bad,wire.bytes,&limits,&v,&e)==LIE_UNSUPPORTED);}
    memcpy(bad,wire.data,wire.bytes);bad[4]=3;
    assert(lie_kvc_parse(bad,wire.bytes,&limits,&v,&e)==LIE_INVALID);
    for(unsigned q=2;q<=8;++q)if(q!=3&&q!=7){bad[4]=(unsigned char)q;assert(lie_kvc_parse(bad,wire.bytes,&limits,&v,&e)==LIE_OK);}
    read_fault=2;assert(lie_kvc_read_fd(fd,&limits,&again,&e)==LIE_BACKEND_FAILED&&!again);read_fault=0;
    unsigned countdown=3;tight=limits;tight.cancelled=cancel;tight.userdata=&countdown;
    assert(lie_kvc_read_fd(fd,&tight,&again,&e)==LIE_CANCELLED&&!again);
    countdown=1;assert(lie_kvc_create(view,&tight,&again,&e)==LIE_CANCELLED&&!again);

    lie_kvc_qwen_geometry g={4,1,2,1,4,3,2,3,2,5,2,6,32};lie_kvc_qwen_layout layout;
    assert(lie_kvc_qwen_decode(view->payload,&g,&limits,&layout,&e)==LIE_OK);
    assert(layout.frontier.mtp_tokens==3&&layout.frontier.tokens==5&&layout.text_positions);
    assert(layout.bytes==view->payload.bytes&&layout.section_count==20);
    assert(lie_kvc_qwen_decode_record(view,&g,&limits,&layout,&e)==LIE_OK);
    lie_kvc_view mismatch=*view;--mismatch.header.tokens;
    assert(lie_kvc_qwen_decode_record(&mismatch,&g,&limits,&layout,&e)==LIE_INVALID);
    lie_kvc_span parts[LIE_STATE_MAX_SECTIONS];
    for(unsigned i=0;i<layout.section_count;++i)parts[i]=(lie_kvc_span){view->payload.data+layout.sections[i].offset,(size_t)layout.sections[i].bytes};
    unsigned char *encoded=malloc(view->payload.bytes);assert(encoded);size_t required=0;
    assert(lie_kvc_qwen_encode(&g,&layout.frontier,parts,layout.section_count,&limits,
                              encoded,view->payload.bytes-1,&required,&e)==LIE_BUFFER_SMALL&&required==view->payload.bytes);
    assert(lie_kvc_qwen_encode(&g,&layout.frontier,parts,layout.section_count,&limits,
                              encoded,view->payload.bytes,&required,&e)==LIE_OK);
    assert(!memcmp(encoded,view->payload.data,required));
    lie_kvc_qwen_layout parsed,unchanged;memset(&unchanged,0x5a,sizeof(unchanged));parsed=unchanged;
    for(size_t n=0;n<view->payload.bytes;++n){
        assert(lie_kvc_qwen_decode((lie_kvc_span){view->payload.data,n},&g,&limits,&parsed,&e)!=LIE_OK);
        assert(!memcmp(&parsed,&unchanged,sizeof(parsed)));
    }
    --parts[4].bytes;
    assert(lie_kvc_qwen_encode(&g,&layout.frontier,parts,layout.section_count,&limits,
                              encoded,required,&required,&e)==LIE_INVALID);++parts[4].bytes;
    assert(lie_kvc_qwen_encode(&g,&layout.frontier,parts,layout.section_count-1,&limits,
                              encoded,required,&required,&e)==LIE_INVALID);
    assert(lie_kvc_qwen_encode(&g,&layout.frontier,parts,layout.section_count,&limits,
                              (void *)view->payload.data,required,&required,&e)==LIE_INVALID);
    const size_t mutations[]={0,4,24,28,32,36,40,44,48,52,(size_t)layout.mtp_count_offset};
    for(unsigned i=0;i<sizeof(mutations)/sizeof(*mutations);++i){
        memcpy(encoded,view->payload.data,required);put32(encoded+mutations[i],UINT32_MAX);
        assert(lie_kvc_qwen_decode((lie_kvc_span){encoded,required},&g,&limits,&parsed,&e)!=LIE_OK);
    }
    memcpy(encoded,view->payload.data,required);
    for(unsigned i=0;i<layout.section_count;++i)if(layout.sections[i].role==LIE_STATE_NGRAM)
        put32(encoded+layout.sections[i].offset,32);
    assert(lie_kvc_qwen_decode((lie_kvc_span){encoded,required},&g,&limits,&parsed,&e)==LIE_INVALID);
    countdown=1;assert(lie_kvc_qwen_decode(view->payload,&g,&tight,&parsed,&e)==LIE_CANCELLED);
    countdown=2;assert(lie_kvc_qwen_decode(view->payload,&g,&tight,&parsed,&e)==LIE_CANCELLED);
    lie_kvc_qwen_geometry huge=g;huge.value_heads=huge.linear_head_dim=UINT32_MAX;
    assert(lie_kvc_qwen_plan(&huge,&layout.frontier,&parsed,&e)==LIE_RESOURCE_LIMIT);
    huge=g;huge.trunk_layers=UINT32_MAX;
    assert(lie_kvc_qwen_plan(&huge,&layout.frontier,&parsed,&e)==LIE_INVALID);

    /* Independent writer bytes are checked by Python after this process exits. */
    lie_kvc_view output=*view;output.payload=(lie_kvc_span){encoded,required};
    assert(lie_kvc_qwen_encode(&g,&layout.frontier,parts,layout.section_count,&limits,
                              encoded,required,&required,&e)==LIE_OK);
    assert(lie_kvc_create(&output,&limits,&again,&e)==LIE_OK);
    int dest=open(argv[2],O_RDWR|O_CREAT|O_EXCL,0600);assert(dest>=0);
    assert(lseek(dest,13,SEEK_SET)==13);short_io=1;write_fault=1;
    assert(lie_kvc_write_fd(dest,again,&limits,&e)==LIE_OK&&writes>10);short_io=0;
    assert(lseek(dest,0,SEEK_CUR)==13);
    assert(lie_kvc_write_fd(dest,again,&limits,&e)==LIE_INVALID);assert(!close(dest));
    /* Unlinked descriptors are refused; callers must supply an owned file. */
    dest=scratch();assert(lie_kvc_write_fd(dest,again,&limits,&e)==LIE_INVALID);assert(!close(dest));
    char scratch_path[]="/tmp/lie-kvc-output-XXXXXX";dest=mkstemp(scratch_path);assert(dest>=0);
    write_fault=2;assert(lie_kvc_write_fd(dest,again,&limits,&e)==LIE_BACKEND_FAILED);write_fault=0;
    countdown=2;assert(lie_kvc_write_fd(dest,again,&tight,&e)==LIE_CANCELLED);
    assert(!ftruncate(dest,0));assert(!fchmod(dest,0644));assert(lie_kvc_write_fd(dest,again,&limits,&e)==LIE_INVALID);
    assert(!fchmod(dest,0600));assert(!fcntl(dest,F_SETFL,O_APPEND));assert(lie_kvc_write_fd(dest,again,&limits,&e)==LIE_INVALID);
    assert(!close(dest)&&!unlink(scratch_path));
    /* A concurrent header change is refused; no partially read object escapes. */
    dest=scratch();assert(__real_pwrite(dest,wire.data,wire.bytes,0)==(ssize_t)wire.bytes);
    reads=0;read_fault=3;lie_kvc_destroy(&again);
    assert(lie_kvc_read_fd(dest,&limits,&again,&e)==LIE_INVALID&&!again);assert(!close(dest));
    lie_kvc_view overflow=*view;overflow.payload.bytes=SIZE_MAX;
    lie_kvc_destroy(&again);assert(lie_kvc_create(&overflow,&limits,&again,&e)==LIE_RESOURCE_LIMIT&&!again);
    /* A sparse oversized source is refused before a payload read/allocation. */
    dest=scratch();assert(__real_pwrite(dest,wire.data,52,0)==52);assert(!ftruncate(dest,2*1024*1024));
    reads=0;assert(lie_kvc_read_fd(dest,&limits,&again,&e)==LIE_RESOURCE_LIMIT&&reads==1);assert(!close(dest));
    char key[44];assert(lie_kvc_filename((lie_kvc_span){(const unsigned char *)"abc",3},key,&e)==LIE_OK);
    assert(!strcmp(key,"a9993e364706816aba3e25717850c26c9cd0d89d.kv"));
    /* Deterministic mutation smoke: exercise mixed length/header/token damage.
     * Success is permitted for unchecksummed opaque tensor bytes. */
    uint32_t rng=0x51573802u;
    for(unsigned trial=0;trial<4000;++trial){
        memcpy(bad,wire.data,wire.bytes);
        for(unsigned j=0;j<4;++j){rng=rng*1664525u+1013904223u;size_t at=rng%wire.bytes;
            rng=rng*1664525u+1013904223u;bad[at]^=(unsigned char)(rng>>24);}
        if(lie_kvc_parse(bad,wire.bytes,&limits,&v,&e)==LIE_OK)
            (void)lie_kvc_qwen_decode_record(&v,&g,&limits,&parsed,&e);
    }
    assert(!close(fd));free(encoded);free(bad);lie_kvc_destroy(&again);lie_kvc_destroy(&k);lie_kvc_destroy(&k);
    assert(!lie_kvc_memory_bytes(k)&&!lie_kvc_wire(k).data&&!lie_kvc_get_view(k));
    puts("KVC bounds, exact Qwen wire, cancellation and I/O faults: PASS (NOT-INFERENCE)");return 0;
}
