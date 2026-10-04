/* SPDX-License-Identifier: MIT */
/* Conservative Linux identity: full files, loaded build, device policy and
 * numerical environment. No hash cache/stat-only acceptance. SSD opt-in only. */
#define _GNU_SOURCE
#include "lie/store.h"
#include <errno.h>
#include <fcntl.h>
#include <link.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>
extern char **environ;
typedef struct {EVP_MD_CTX *hash;unsigned files;bool ok;} identity_context;
static bool add(EVP_MD_CTX *hash,const void *p,size_t n){
    unsigned char length[8];for(unsigned i=0;i<8;++i)length[i]=(unsigned char)((uint64_t)n>>(8*i));
    return EVP_DigestUpdate(hash,length,8)==1&&EVP_DigestUpdate(hash,p,n)==1;
}
static bool file(EVP_MD_CTX *hash,int fd){
    struct stat a,b;unsigned char bytes[1048576];
    if(fstat(fd,&a)||!S_ISREG(a.st_mode)||a.st_size<0)return false;
    uint64_t size=(uint64_t)a.st_size;unsigned char length[8];
    for(unsigned i=0;i<8;++i)length[i]=(unsigned char)(size>>(8*i));
    if(EVP_DigestUpdate(hash,length,8)!=1)return false;
    for(off_t offset=0;offset<a.st_size;){
        size_t count=(uint64_t)(a.st_size-offset)>sizeof(bytes)?sizeof(bytes):(size_t)(a.st_size-offset);
        ssize_t n=pread(fd,bytes,count,offset);if(n<0&&errno==EINTR)continue;
        if(n<=0||EVP_DigestUpdate(hash,bytes,(size_t)n)!=1)return false;
        offset+=n;
    }
    return !fstat(fd,&b)&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino&&a.st_size==b.st_size&&
        a.st_mtim.tv_sec==b.st_mtim.tv_sec&&a.st_mtim.tv_nsec==b.st_mtim.tv_nsec&&
        a.st_ctim.tv_sec==b.st_ctim.tv_sec&&a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
}
static int library(struct dl_phdr_info *info,size_t size,void *opaque){
    (void)size;identity_context *c=opaque;const char *path=info->dlpi_name;
    if(!strcmp(path,"linux-vdso.so.1"))return 0;
    if(!*path)path="/proc/self/exe";
    if(++c->files>256){c->ok=false;return 1;}
    int fd=open(path,O_RDONLY|O_CLOEXEC);c->ok=fd>=0&&add(c->hash,path,strlen(path))&&file(c->hash,fd);
    if(fd>=0)close(fd);
    return c->ok?0:1;
}
static int compare(const void *a,const void *b){return strcmp(*(const char *const *)a,*(const char *const *)b);}
lie_status lie_state_identity_files(const int *fds,size_t count,const char *policy,lie_state_identity *out,lie_error *e){
    if(!fds||!count||count>65535||!policy||strlen(policy)>16384||!out)return LIE_INVALID;
    EVP_MD_CTX *hash=EVP_MD_CTX_new();if(!hash)return LIE_RESOURCE_LIMIT;
    struct utsname host;bool ok=!uname(&host)&&EVP_DigestInit_ex(hash,EVP_sha256(),NULL)==1&&
        add(hash,"LIE-SSD-identity-v1",19)&&add(hash,policy,strlen(policy))&&
        add(hash,host.release,strlen(host.release))&&add(hash,host.version,strlen(host.version))&&add(hash,host.machine,strlen(host.machine));
    unsigned char file_count[8];for(unsigned i=0;i<8;++i)file_count[i]=(unsigned char)((uint64_t)count>>(8*i));
    ok=ok&&add(hash,"weights",7)&&add(hash,file_count,sizeof(file_count));
    for(size_t i=0;ok&&i<count;++i)ok=file(hash,fds[i]);
    ok=ok&&add(hash,"loaded-build",12);
    identity_context c={hash,0,ok};if(ok)(void)dl_iterate_phdr(library,&c);ok=c.ok;
    const char *env[256];size_t used=0;
    for(char **p=environ;ok&&p&&*p;++p){
        if(strncmp(*p,"GUFO_",5)&&strncmp(*p,"HIP",3)&&strncmp(*p,"HSA_",4)&&strncmp(*p,"ROCR_",5)&&
           strncmp(*p,"ROCBLAS",7)&&strncmp(*p,"AMD",3)&&strncmp(*p,"GPU_",4)&&strncmp(*p,"CUDA_",5)&&
           strncmp(*p,"CUBLAS_",7)&&strncmp(*p,"NVIDIA_",7)&&strncmp(*p,"OMP_",4)&&strncmp(*p,"OPENBLAS_",9))continue;
        if(used==256||strlen(*p)>16384){ok=false;break;}env[used++]=*p;
    }
    qsort(env,used,sizeof(*env),compare);
    for(size_t i=0;ok&&i<used;++i)ok=add(hash,env[i],strlen(env[i]));
    unsigned n=0;ok=ok&&EVP_DigestFinal_ex(hash,out->bytes,&n)==1&&n==32;EVP_MD_CTX_free(hash);
    if(!ok&&e)snprintf(e->message,sizeof(e->message),"cannot establish complete immutable SSD model/build identity");
    return ok?LIE_OK:LIE_INVALID;
}
