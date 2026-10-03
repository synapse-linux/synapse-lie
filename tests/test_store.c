/* SPDX-License-Identifier: MIT */
/* Disk/parser/ownership fixtures only; NOT-INFERENCE. */
#include "lie/store.h"
#include "../src/state_codec.h"
#include "fake_executor.h"
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <openssl/evp.h>
#include <poll.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static atomic_int fail_write,fail_flush,fail_rename;
ssize_t __real_pwrite(int,const void *,size_t,off_t);
ssize_t __wrap_pwrite(int fd,const void *p,size_t n,off_t at){
    if(atomic_exchange(&fail_write,0)){errno=EIO;return -1;}return __real_pwrite(fd,p,n,at);
}
int __real_fsync(int);
int __wrap_fsync(int fd){if(atomic_exchange(&fail_flush,0)){errno=EIO;return -1;}return __real_fsync(fd);}
int __real_renameat(int,const char *,int,const char *);
int __wrap_renameat(int a,const char *x,int b,const char *y){
    if(atomic_exchange(&fail_rename,0)){errno=EIO;return -1;}return __real_renameat(a,x,b,y);
}
static lie_store_result complete(lie_store *s){
    lie_store_result r={0};
    for(unsigned i=0;i<3000;++i){if(lie_store_take(s,&r)){if(!r.state)lie_store_result_release(s,&r);return r;}
        struct pollfd fd={lie_store_fd(s),POLLIN,0};assert(poll(&fd,1,1)>=0);}
    assert(!"store completion deadline");return r;
}
static lie_state *capture(lie_model *m,int value){
    lie_error e={0};lie_sequence *s=NULL;lie_state *state=NULL;lie_state_layout l;uint64_t bytes;
    int32_t tokens[]={0,value,value,value};
    assert(lie_sequence_create(m,&s,&e)==LIE_OK&&lie_sequence_prefill(s,tokens,4,&e)==LIE_OK);
    assert(lie_state_plan(s,&l,&bytes,&e)==LIE_OK&&lie_state_capture(s,&l,bytes,&state,&e)==LIE_OK);
    assert(lie_sequence_close(&s,&e)==LIE_OK);return state;
}
static unsigned entries(const char *path){
    DIR *d=opendir(path);assert(d);unsigned n=0;struct dirent *e;
    while((e=readdir(d)))if(e->d_name[0]!='.')++n;
    closedir(d);return n;
}
static void checksum(int fd,uint64_t size){
    assert(size<4096);unsigned char bytes[4096],digest[32];unsigned count=0;
    assert(pread(fd,bytes,(size_t)size,0)==(ssize_t)size);memset(bytes+88,0,32);
    assert(EVP_Digest(bytes,(size_t)size,digest,&count,EVP_sha256(),NULL)==1&&count==32);
    assert(pwrite(fd,digest,32,88)==32);
}
static void clean(const char *path){
    DIR *d=opendir(path);assert(d);int fd=dirfd(d);struct dirent *e;
    while((e=readdir(d)))if(strcmp(e->d_name,".")&&strcmp(e->d_name,".."))assert(!unlinkat(fd,e->d_name,0));
    closedir(d);assert(!rmdir(path));
}
int main(void){
    char cwd[2048],base[2200],path[2300],file[2300];assert(getcwd(cwd,sizeof(cwd)));
    snprintf(base,sizeof(base),"%s/ssd-store-XXXXXX",cwd);assert(mkdtemp(base));
    snprintf(path,sizeof(path),"%s/store",base);snprintf(file,sizeof(file),"%s/codec",base);
    lie_model_options mo={LIE_EXECUTOR_ABI,sizeof(mo),128,4};lie_model *m=NULL;lie_error e={0};
    assert(lie_backend_open(":fixture:",&mo,&m,&e)==LIE_OK);lie_state *state=capture(m,10);
    lie_state_identity id={{7}},foreign={{8}};uint64_t domain=lie_state_description(state)->domain;
    int fd=open(file,O_RDWR|O_CREAT|O_EXCL|O_CLOEXEC,0600);assert(fd>=0);
    assert(lie_state_file_write(fd,&id,state,NULL));uint64_t size=lie_state_file_bytes(state);
    lie_state *loaded=lie_state_file_read(fd,&id,domain,UINT64_MAX,NULL);assert(loaded);
    assert(lie_state_layout_equal(lie_state_description(state),lie_state_description(loaded)));
    lie_state_destroy(&loaded);
    loaded=lie_state_file_read(fd,&id,domain+1,UINT64_MAX,NULL);assert(loaded&&lie_state_description(loaded)->domain==domain+1);lie_state_destroy(&loaded);
    assert(!lie_state_file_read(fd,&foreign,domain,UINT64_MAX,NULL));
    assert(!lie_state_file_read(fd,&id,domain,lie_state_bytes(state)-1,NULL));
    unsigned offsets[]={0,8,12,16,20,24,28,32,36,40,48,56,88,120,152,160,168,208,216,(unsigned)size-1};
    for(unsigned i=0;i<sizeof(offsets)/sizeof(*offsets);++i){unsigned char old;
        assert(pread(fd,&old,1,offsets[i])==1);unsigned char changed=old^0x80;
        assert(pwrite(fd,&changed,1,offsets[i])==1);
        assert(!lie_state_file_read(fd,&id,domain,UINT64_MAX,NULL));
        assert(pwrite(fd,&old,1,offsets[i])==1);
    }
    /* Correct checksums cannot rescue malformed section geometry. This reaches
     * the structural parser, rather than merely exercising digest rejection. */
    unsigned malformed[]={160+12,160+48,224,224+56};
    unsigned char replacement[]={0,0,1,0};
    for(unsigned i=0;i<sizeof(malformed)/sizeof(*malformed);++i){unsigned char old;
        assert(pread(fd,&old,1,malformed[i])==1&&old!=replacement[i]);
        assert(pwrite(fd,&replacement[i],1,malformed[i])==1);checksum(fd,size);
        assert(!lie_state_file_read(fd,&id,domain,UINT64_MAX,NULL));
        assert(pwrite(fd,&old,1,malformed[i])==1);checksum(fd,size);
    }
    unsigned char dimension[8],overflow[8];memset(overflow,255,sizeof(overflow));
    assert(pread(fd,dimension,8,176)==8&&pwrite(fd,overflow,8,176)==8);checksum(fd,size);
    assert(!lie_state_file_read(fd,&id,domain,UINT64_MAX,NULL));
    assert(pwrite(fd,dimension,8,176)==8);checksum(fd,size);
    atomic_bool cancelled=true;assert(!lie_state_file_read(fd,&id,domain,UINT64_MAX,&cancelled));
    assert(!ftruncate(fd,(off_t)size-1));assert(!lie_state_file_read(fd,&id,domain,UINT64_MAX,NULL));
    assert(!ftruncate(fd,0));assert(lie_state_file_write(fd,&id,state,NULL));
    assert(!fchmod(fd,0644));assert(!lie_state_file_read(fd,&id,domain,UINT64_MAX,NULL));assert(!fchmod(fd,0600));
    char alias[2300];snprintf(alias,sizeof(alias),"%s/alias",base);assert(!link(file,alias));
    assert(!lie_state_file_read(fd,&id,domain,UINT64_MAX,NULL));assert(!unlink(alias));
    /* Identity changes with content or execution policy; same inputs repeat. */
    lie_state_identity first,again,changed;
    assert(lie_state_identity_files(&fd,1,"fixture-policy",&first,&e)==LIE_OK);
    assert(lie_state_identity_files(&fd,1,"fixture-policy",&again,&e)==LIE_OK&&!memcmp(&first,&again,sizeof(first)));
    assert(lie_state_identity_files(&fd,1,"different-policy",&changed,&e)==LIE_OK&&memcmp(&first,&changed,sizeof(first)));
    assert(!ftruncate(fd,1));assert(lie_state_identity_files(&fd,1,"fixture-policy",&changed,&e)==LIE_OK&&memcmp(&first,&changed,sizeof(first)));
    close(fd);assert(!unlink(file));

    lie_store *s=NULL,*other=NULL;lie_store_options off={0};
    assert(lie_store_open(&off,NULL,0,&s,&e)==LIE_OK&&!s&&access(path,F_OK));
    lie_store_options options={path,4096,32768};
    assert(lie_store_open(&options,&id,domain,&s,&e)==LIE_OK&&s);
    assert(lie_store_open(&options,&id,domain,&other,&e)!=LIE_OK&&!other); /* Exclusive process lock. */
    for(unsigned fault=0;fault<3;++fault){
        if(fault==0)atomic_store(&fail_write,1);
        if(fault==1)atomic_store(&fail_flush,1);
        if(fault==2)atomic_store(&fail_rename,1);
        assert(lie_store_write(s,state));lie_store_result r=complete(s);assert(!r.read&&!r.state&&!entries(path));
    }
    assert(lie_store_write(s,state));lie_state_destroy(&state); /* Writer holds the immutable payload. */
    lie_store_result r=complete(s);assert(!r.read&&!r.state&&entries(path)==1);
    lie_store_info info;lie_store_snapshot(s,&info);assert(info.writes==1&&info.errors==3&&info.disk_bytes==size+64&&info.allocated_bytes<=4096&&!info.staging_bytes);
    lie_store_close(&s);assert(!s&&entries(path)==1); /* Close/disable never delete committed entries. */
    assert(lie_store_open(&off,NULL,0,&s,&e)==LIE_OK&&!s&&entries(path)==1);
    assert(lie_store_open(&options,&id,domain,&s,&e)==LIE_OK);
    int32_t prompt[]={0,10,10,10,20,20,20,20};uint64_t ticket=lie_store_read(s,prompt,8,4);assert(ticket);
    assert(!lie_store_read(s,prompt,8,4)); /* In-flight or completed results still occupy the slot. */
    r=complete(s);assert(r.read&&r.ticket==ticket&&r.state&&lie_state_description(r.state)->domain==domain);
    assert(!memcmp(lie_state_tokens(r.state),prompt,4*sizeof(*prompt)));
    lie_store_snapshot(s,&info);assert(info.pending==1&&info.staging_bytes==options.staging_bytes);
    assert(!lie_store_read(s,prompt,8,4));lie_store_result_release(s,&r);
    prompt[1]=99;assert(lie_store_read(s,prompt,8,4));r=complete(s);assert(r.read&&!r.state);
    state=capture(m,20);assert(lie_store_write(s,state));r=complete(s);assert(!r.state);lie_state_destroy(&state);
    lie_store_snapshot(s,&info);assert(info.entries==1&&info.evictions==1&&info.hits==1&&info.misses==1&&info.peak_staging_bytes<=options.staging_bytes);
    lie_store_close(&s);
    /* Foreign identities never expose bytes as a usable state. */
    assert(lie_store_open(&options,&foreign,domain,&s,&e)==LIE_OK);prompt[1]=prompt[2]=prompt[3]=20;
    assert(lie_store_read(s,prompt,4,4));r=complete(s);assert(!r.state);lie_store_close(&s);
    clean(path);
    /* Utility works in the asynchronous SSD store too; OFF returns to LRU. */
    options.quota_bytes=8192;assert(lie_store_open(&options,&id,domain,&s,&e)==LIE_OK);
    state=capture(m,10);assert(lie_store_write(s,state));lie_state_destroy(&state);complete(s);
    prompt[1]=prompt[2]=prompt[3]=10;
    for(unsigned hit=0;hit<8;++hit){assert(lie_store_read(s,prompt,4,4));r=complete(s);assert(r.state);lie_store_result_release(s,&r);}
    for(int value=20;value<=30;value+=10){state=capture(m,value);assert(lie_store_write(s,state));lie_state_destroy(&state);complete(s);}
    assert(lie_store_read(s,prompt,4,4));r=complete(s);assert((r.state!=NULL)==(LIE_CACHE_UTILITY!=0));
    if(r.state)lie_store_result_release(s,&r);
    lie_store_close(&s);clean(path);

    /* Rewriting extensions is atomic: failed writes/fsync/rename leave the
     * previous committed payload and extension bytes usable. */
    assert(lie_store_open(&options,&id,domain,&s,&e)==LIE_OK);
    state=capture(m,10);lie_cache_metadata original={.reason=LIE_CACHE_COLD,.trailer="old",.trailer_bytes=3};
    assert(lie_store_write_ex(s,state,&original));complete(s);
    lie_cache_metadata changed_meta=original;changed_meta.trailer="new";
    prompt[1]=prompt[2]=prompt[3]=10;
    for(unsigned fault=0;fault<3;++fault){
        if(fault==0)atomic_store(&fail_write,1);
        if(fault==1)atomic_store(&fail_flush,1);
        if(fault==2)atomic_store(&fail_rename,1);
        assert(lie_store_write_ex(s,state,&changed_meta));complete(s);
        assert(lie_store_read(s,prompt,4,4));r=complete(s);
        assert(r.state&&r.metadata.trailer_bytes==3&&!memcmp(r.metadata.trailer,"old",3));lie_store_result_release(s,&r);
    }
    assert(lie_store_write_ex(s,state,&changed_meta));complete(s);
    assert(lie_store_read(s,prompt,4,4));r=complete(s);
    assert(r.state&&r.metadata.hits==4&&!memcmp(r.metadata.trailer,"new",3));lie_store_result_release(s,&r);
    lie_store_snapshot(s,&info);assert(info.entries==1&&info.errors==3&&info.writes==2);
    lie_state_destroy(&state);lie_store_close(&s);clean(path);

    /* Compressed envelope survives store close/reopen and bounded I/O import. */
    fake_state_padding(2u*1024u*1024u);state=capture(m,10);options.quota_bytes=options.staging_bytes=16u*1024u*1024u;
    assert(lie_state_compress(&state,options.staging_bytes)==(LIE_CHECKPOINT_COMPRESSION!=0));
    assert(lie_store_open(&options,&id,domain,&s,&e)==LIE_OK&&lie_store_write(s,state));
    lie_state_destroy(&state);complete(s);lie_store_close(&s);
    assert(lie_store_open(&options,&id,domain,&s,&e)==LIE_OK&&lie_store_read(s,prompt,4,4));r=complete(s);assert(r.state);
    assert(lie_state_is_compressed(r.state)==(LIE_CHECKPOINT_COMPRESSION!=0));
    lie_sequence *restored=NULL;assert(lie_sequence_create(m,&restored,&e)==LIE_OK);
    assert(lie_state_restore(restored,r.state,&e)==LIE_OK&&lie_sequence_close(&restored,&e)==LIE_OK);
    lie_store_result_release(s,&r);lie_store_close(&s);fake_state_padding(0);clean(path);
    /* Unsafe directories, symlinks and unrelated contents are refused. */
    assert(!mkdir(path,0755));assert(lie_store_open(&options,&id,domain,&s,&e)!=LIE_OK&&!s);assert(!rmdir(path));
    assert(!symlink(base,path));assert(lie_store_open(&options,&id,domain,&s,&e)!=LIE_OK&&!s);assert(!unlink(path));
    assert(!mkdir(path,0700));snprintf(file,sizeof(file),"%s/store/unrelated",base);
    fd=open(file,O_CREAT|O_EXCL|O_WRONLY,0600);assert(fd>=0);close(fd);
    assert(lie_store_open(&options,&id,domain,&s,&e)!=LIE_OK&&!s&&!access(file,F_OK));clean(path);
    assert(!rmdir(base));assert(lie_model_close(&m,&e)==LIE_OK);
    puts("SSD codec, full identity, restart, bounds, quota and atomic failure fixtures: PASS (NOT-INFERENCE)");return 0;
}
