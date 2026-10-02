/* SPDX-License-Identifier: MIT */
#include "lie/store.h"
#include "state_codec.h"
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/eventfd.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <time.h>
#include <unistd.h>

#define STORE_ENTRIES 64u
typedef struct { char name[69];uint64_t bytes,allocated,age;unsigned tokens; } entry;
struct lie_store {
    pthread_t thread;
    pthread_mutex_t gate;
    pthread_cond_t ready;
    int directory,lock,notice;
    bool stop,busy,done,read,taken;
    atomic_bool cancel;
    uint64_t domain,ticket,clock,block_bytes;
    lie_state_identity identity;
    lie_store_info info;
    entry entries[STORE_ENTRIES];
    int32_t *tokens;
    size_t count;
    uint32_t chunk;
    lie_state *state;
    uint64_t elapsed;
};
static uint64_t now(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;}
static lie_status fail(lie_error *e,const char *message){if(e)snprintf(e->message,sizeof(e->message),"%s",message);return LIE_INVALID;}
static bool hex_name(const char *s){
    if(strlen(s)!=68||strcmp(s+64,".lie"))return false;
    for(unsigned i=0;i<64;++i)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return false;
    return true;
}
static bool owned_file(int fd,struct stat *s){return !fstat(fd,s)&&S_ISREG(s->st_mode)&&s->st_uid==geteuid()&&s->st_nlink==1&&(s->st_mode&0777)==0600&&s->st_size>=0&&s->st_blocks>=0;}
static int open_file(lie_store *s,const char *name){
    int fd=openat(s->directory,name,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);struct stat st;
    if(fd>=0&&!owned_file(fd,&st)){close(fd);fd=-1;}return fd;
}
static bool same_file(lie_store *s,const char *name,int fd){
    struct stat a,b;return owned_file(fd,&a)&&!fstatat(s->directory,name,&b,AT_SYMLINK_NOFOLLOW)&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino;
}
/* Walk directory FDs without following symlinks. Only the explicitly named
 * final directory is created. Ancestors must already exist. */
static int private_directory(const char *path){
    if(!path||*path!='/'||strlen(path)>4095)return -1;
    char *copy=strdup(path);if(!copy)return -1;
    int fd=open("/",O_RDONLY|O_DIRECTORY|O_CLOEXEC);char *save=NULL;
    for(char *part=strtok_r(copy,"/",&save);part&&fd>=0;){
        char *next=strtok_r(NULL,"/",&save);
        if(!strcmp(part,".")||!strcmp(part,"..")){close(fd);fd=-1;break;}
        if(!next&&mkdirat(fd,part,0700)&&errno!=EEXIST){close(fd);fd=-1;break;}
        int child=openat(fd,part,O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW);close(fd);fd=child;part=next;
    }
    free(copy);struct stat st;
    if(fd>=0&&(fstat(fd,&st)||st.st_uid!=geteuid()||(st.st_mode&0777)!=0700)){close(fd);fd=-1;}
    return fd;
}
static void account(lie_store *s){
    uint64_t bytes=0,allocated=0;unsigned count=0;
    for(unsigned i=0;i<STORE_ENTRIES;++i)if(s->entries[i].name[0]){bytes+=s->entries[i].bytes;allocated+=s->entries[i].allocated;++count;}
    pthread_mutex_lock(&s->gate);s->info.disk_bytes=bytes;s->info.allocated_bytes=allocated;s->info.entries=count;pthread_mutex_unlock(&s->gate);
}
static bool remove_entry(lie_store *s,unsigned i){
    entry *e=&s->entries[i];int fd=open_file(s,e->name);
    bool ok=fd>=0&&same_file(s,e->name,fd)&&!unlinkat(s->directory,e->name,0);
    if(fd>=0)close(fd);
    if(ok){memset(e,0,sizeof(*e));pthread_mutex_lock(&s->gate);++s->info.evictions;pthread_mutex_unlock(&s->gate);account(s);}
    return ok;
}
static bool scan(lie_store *s){
    int duplicate=openat(s->directory,".",O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(duplicate<0)return false;
    DIR *dir=fdopendir(duplicate);if(!dir){close(duplicate);return false;}
    bool ok=true;unsigned count=0;struct dirent *d;
    for(;;){
        errno=0;d=readdir(dir);if(!d){if(errno)ok=false;break;}
        const char *name=d->d_name;
        if(!strcmp(name,".")||!strcmp(name,"..")||!strcmp(name,".lie-prefix.lock"))continue;
        bool partial=!strncmp(name,".pending-",9)&&hex_name(name+9);
        if(!partial&&!hex_name(name)){ok=false;break;}
        int fd=open_file(s,name);struct stat st;
        if(fd<0||!owned_file(fd,&st)){if(fd>=0)close(fd);ok=false;break;}
        if(partial){ok=same_file(s,name,fd)&&!unlinkat(s->directory,name,0);close(fd);if(!ok)break;continue;}
        if(count==STORE_ENTRIES){close(fd);ok=false;break;}
        entry *e=&s->entries[count++];memcpy(e->name,name,69);e->bytes=(uint64_t)st.st_size;
        e->allocated=(uint64_t)st.st_blocks*512;e->age=++s->clock;uint64_t bytes=0;
        if(!lie_state_file_probe(fd,&s->identity,&bytes,&e->tokens))e->tokens=0;
        close(fd);
        /* Bound accounting even for foreign/corrupt files; never overflow. */
        uint64_t a=0,b=0;
        for(unsigned i=0;i<count;++i){
            if(s->entries[i].bytes>UINT64_MAX-a||s->entries[i].allocated>UINT64_MAX-b){ok=false;break;}
            a+=s->entries[i].bytes;b+=s->entries[i].allocated;
        }
        if(!ok)break;
    }
    closedir(dir);if(ok)ok=fsync(s->directory)==0;
    if(ok)account(s);
    return ok;
}
static bool reserve_disk(lie_store *s,uint64_t bytes,unsigned *slot){
    if(bytes>UINT64_MAX-(s->block_bytes-1))return false;
    uint64_t allocated=((bytes+s->block_bytes-1)/s->block_bytes)*s->block_bytes;
    if(bytes>s->info.quota_bytes||allocated>s->info.quota_bytes)return false;
    for(;;){uint64_t used=0,blocks=0;unsigned free_slot=STORE_ENTRIES,oldest=STORE_ENTRIES;
        for(unsigned i=0;i<STORE_ENTRIES;++i){entry *e=&s->entries[i];if(!e->name[0]){free_slot=i;continue;}
            used+=e->bytes;blocks+=e->allocated;if(oldest==STORE_ENTRIES||e->age<s->entries[oldest].age)oldest=i;}
        if(free_slot<STORE_ENTRIES&&used<=s->info.quota_bytes-bytes&&blocks<=s->info.quota_bytes-allocated){*slot=free_slot;return true;}
        if(oldest==STORE_ENTRIES||!remove_entry(s,oldest))return false;
    }
}
static bool write_state(lie_store *s){
    char name[69]={0},temporary[78];const lie_state_layout *l=lie_state_description(s->state);
    if(!lie_state_prefix_key(&s->identity,lie_state_tokens(s->state),l->token_count,name))return false;
    memcpy(name+64,".lie",5);
    for(unsigned i=0;i<STORE_ENTRIES;++i)if(!strcmp(s->entries[i].name,name)){s->entries[i].age=++s->clock;return true;}
    unsigned slot=0;uint64_t bytes=lie_state_file_bytes(s->state);
    if(!reserve_disk(s,bytes,&slot))return false;
    snprintf(temporary,sizeof(temporary),".pending-%s",name);
    int fd=openat(s->directory,temporary,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);if(fd<0)return false;
    bool renamed=false;struct stat st;
    bool ok=lie_state_file_write(fd,&s->identity,s->state,&s->cancel)&&!fsync(fd)&&owned_file(fd,&st)&&same_file(s,temporary,fd);
    if(ok){
        uint64_t allocated=(uint64_t)st.st_blocks*512,used=0;
        for(unsigned i=0;i<STORE_ENTRIES;++i)used+=s->entries[i].allocated;
        ok=(uint64_t)st.st_size==bytes&&allocated<=s->info.quota_bytes&&used<=s->info.quota_bytes-allocated;
    }
    if(ok){ok=renameat(s->directory,temporary,s->directory,name)==0;renamed=ok;}
    if(renamed){entry *e=&s->entries[slot];memcpy(e->name,name,sizeof(name));
        e->bytes=(uint64_t)st.st_size;e->allocated=(uint64_t)st.st_blocks*512;e->age=++s->clock;e->tokens=l->token_count;
        account(s);ok=fsync(s->directory)==0;
    }else if(same_file(s,temporary,fd)){(void)unlinkat(s->directory,temporary,0);(void)fsync(s->directory);}
    close(fd);
    if(ok){pthread_mutex_lock(&s->gate);++s->info.writes;s->info.written_bytes+=bytes;pthread_mutex_unlock(&s->gate);}
    return ok;
}
static lie_state *read_state(lie_store *s){
    /* Try longest eligible exact frontier first; failed candidates do not
     * prevent trying an earlier compatible checkpoint. No recurrent trimming. */
    unsigned ceiling=UINT32_MAX;
    for(unsigned attempt=0;attempt<STORE_ENTRIES&&!atomic_load(&s->cancel);++attempt){
        unsigned best=STORE_ENTRIES;
        for(unsigned i=0;i<STORE_ENTRIES;++i){entry *e=&s->entries[i];
            if(e->tokens&&e->tokens<=s->count&&e->tokens<ceiling&&(e->tokens==s->count||e->tokens%s->chunk==0)&&
               (best==STORE_ENTRIES||e->tokens>s->entries[best].tokens))best=i;
        }
        if(best==STORE_ENTRIES)break;
        ceiling=s->entries[best].tokens;char name[69]={0};
        if(!lie_state_prefix_key(&s->identity,s->tokens,ceiling,name))break;
        memcpy(name+64,".lie",5);
        /* Several entries may have the same frontier length. */
        best=STORE_ENTRIES;
        for(unsigned i=0;i<STORE_ENTRIES;++i)if(!strcmp(s->entries[i].name,name)){best=i;break;}
        if(best==STORE_ENTRIES)continue;
        uint64_t input=s->count*sizeof(*s->tokens);int fd=open_file(s,name);
        lie_state *state=fd<0?NULL:lie_state_file_read(fd,&s->identity,s->domain,s->info.staging_budget_bytes-input,&s->cancel);
        if(fd>=0)close(fd);
        if(state){const lie_state_layout *l=lie_state_description(state);
            if(l->token_count!=ceiling||l->prefill_chunk!=s->chunk||memcmp(lie_state_tokens(state),s->tokens,ceiling*sizeof(*s->tokens)))lie_state_destroy(&state);
        }
        if(state){s->entries[best].age=++s->clock;
            pthread_mutex_lock(&s->gate);s->info.read_bytes+=s->entries[best].bytes;pthread_mutex_unlock(&s->gate);return state;}
        if(atomic_load(&s->cancel))break;
        pthread_mutex_lock(&s->gate);++s->info.errors;pthread_mutex_unlock(&s->gate);
        /* Budget refusal is a miss, not grounds to remove a large valid file. */
    }
    return NULL;
}
static void *io_worker(void *p){
    lie_store *s=p;pthread_mutex_lock(&s->gate);
    for(;;){
        while((!s->busy||s->done)&&!s->stop)pthread_cond_wait(&s->ready,&s->gate);
        if(s->stop&&(!s->busy||s->done))break;
        bool read=s->read;pthread_mutex_unlock(&s->gate);uint64_t start=now();
        lie_state *result=read?read_state(s):NULL;bool ok=read||write_state(s);uint64_t end=now();
        pthread_mutex_lock(&s->gate);s->elapsed=end>=start?end-start:0;
        if(read){s->state=result;s->info.read_ns+=s->elapsed;
            if(atomic_load(&s->cancel)){lie_state_destroy(&s->state);++s->info.cancelled;}
            else if(s->state)++s->info.hits;else ++s->info.misses;
        }else{s->info.write_ns+=s->elapsed;if(!ok)++s->info.errors;lie_state_destroy(&s->state);}
        free(s->tokens);s->tokens=NULL;s->done=true;
        uint64_t one=1;ssize_t n;do{n=write(s->notice,&one,sizeof(one));}while(n<0&&errno==EINTR);
        if(n!=(ssize_t)sizeof(one))abort();
    }
    pthread_mutex_unlock(&s->gate);return NULL;
}
lie_status lie_store_open(const lie_store_options *o,const lie_state_identity *id,uint64_t domain,lie_store **out,lie_error *e){
    if(!o||!out||*out)return fail(e,"invalid SSD store output/options");
    if(!o->directory){if(o->quota_bytes||o->staging_bytes)return fail(e,"SSD limits require an explicit directory");return LIE_OK;}
    if(!id||!domain||o->quota_bytes<4096||o->quota_bytes>INT64_MAX||o->staging_bytes<32768||o->staging_bytes>SIZE_MAX)
        return fail(e,"invalid SSD quota/staging/identity");
    lie_store *s=calloc(1,sizeof(*s));if(!s)return LIE_RESOURCE_LIMIT;
    s->directory=s->lock=s->notice=-1;s->identity=*id;s->domain=domain;atomic_init(&s->cancel,false);
    s->info=(lie_store_info){.enabled=true,.quota_bytes=o->quota_bytes,.staging_budget_bytes=o->staging_bytes};
    if(pthread_mutex_init(&s->gate,NULL)){free(s);return LIE_RESOURCE_LIMIT;}
    if(pthread_cond_init(&s->ready,NULL)){pthread_mutex_destroy(&s->gate);free(s);return LIE_RESOURCE_LIMIT;}
    s->directory=private_directory(o->directory);if(s->directory<0)goto bad;
    s->lock=openat(s->directory,".lie-prefix.lock",O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK,0600);
    struct stat st;struct statvfs fs;
    if(s->lock<0||!owned_file(s->lock,&st)||!same_file(s,".lie-prefix.lock",s->lock)||flock(s->lock,LOCK_EX|LOCK_NB)||
       fstatvfs(s->directory,&fs)||!fs.f_frsize||fs.f_frsize>1048576)goto bad;
    s->block_bytes=fs.f_frsize;
    if(!scan(s))goto bad;
    /* Refuse an existing store above the requested cap before READY. The
     * operator can reopen with its prior quota; no startup deletion surprise. */
    if(s->info.disk_bytes>o->quota_bytes||s->info.allocated_bytes>o->quota_bytes)goto bad;
    s->notice=eventfd(0,EFD_CLOEXEC|EFD_NONBLOCK);
    if(s->notice<0||pthread_create(&s->thread,NULL,io_worker,s))goto bad;
    *out=s;return LIE_OK;
bad:
    if(s->notice>=0)close(s->notice);
    if(s->lock>=0)close(s->lock);
    if(s->directory>=0)close(s->directory);
    pthread_cond_destroy(&s->ready);pthread_mutex_destroy(&s->gate);free(s);
    return fail(e,"SSD store requires a private directory, safe entries and exclusive ownership");
}
int lie_store_fd(const lie_store *s){return s?s->notice:-1;}
static void admitted(lie_store *s,uint64_t bytes,bool read){
    s->read=read;s->busy=true;s->done=false;s->elapsed=0;++s->ticket;
    if(!s->ticket)++s->ticket;
    atomic_store(&s->cancel,false);s->info.pending=1;s->info.staging_bytes=bytes;
    if(bytes>s->info.peak_staging_bytes)s->info.peak_staging_bytes=bytes;
    pthread_cond_signal(&s->ready);
}
uint64_t lie_store_read(lie_store *s,const int32_t *tokens,size_t n,uint32_t chunk){
    if(!s||!tokens||!n||n>UINT32_MAX||!chunk||n>SIZE_MAX/sizeof(*tokens))return 0;
    pthread_mutex_lock(&s->gate);uint64_t ticket=0;
    if(!s->stop&&!s->busy&&n*sizeof(*tokens)<s->info.staging_budget_bytes){
        s->tokens=malloc(n*sizeof(*tokens));
        if(s->tokens){memcpy(s->tokens,tokens,n*sizeof(*tokens));s->count=n;s->chunk=chunk;
            /* Reserve the entire staging cap before asynchronous allocation. */
            admitted(s,s->info.staging_budget_bytes,true);++s->info.lookups;ticket=s->ticket;}
    }
    pthread_mutex_unlock(&s->gate);return ticket;
}
bool lie_store_can_write(lie_store *s,uint64_t bytes){
    if(!s)return false;
    pthread_mutex_lock(&s->gate);bool ok=!s->stop&&!s->busy&&bytes<=s->info.staging_budget_bytes&&bytes<=s->info.quota_bytes;
    pthread_mutex_unlock(&s->gate);return ok;
}
bool lie_store_write(lie_store *s,lie_state *state){
    if(!s||!state)return false;
    uint64_t bytes=lie_state_bytes(state);pthread_mutex_lock(&s->gate);
    bool ok=!s->stop&&!s->busy&&lie_state_description(state)->domain==s->domain&&
        bytes<=s->info.staging_budget_bytes&&lie_state_file_bytes(state)<=s->info.quota_bytes;
    if(ok){lie_state_retain(state);s->state=state;admitted(s,bytes,false);}else ++s->info.skipped;
    pthread_mutex_unlock(&s->gate);return ok;
}
void lie_store_cancel(lie_store *s,uint64_t ticket){
    if(!s)return;
    pthread_mutex_lock(&s->gate);if(s->busy&&s->read&&s->ticket==ticket)atomic_store(&s->cancel,true);pthread_mutex_unlock(&s->gate);
}
bool lie_store_take(lie_store *s,lie_store_result *r){
    if(!s||!r)return false;
    pthread_mutex_lock(&s->gate);bool ok=s->busy&&s->done&&!s->taken;
    if(ok){*r=(lie_store_result){s->ticket,s->elapsed,s->read,s->state};s->state=NULL;s->taken=true;
        uint64_t value;ssize_t n;
        do{n=read(s->notice,&value,sizeof(value));}while(n<0&&errno==EINTR);
        if(n<0&&errno!=EAGAIN)abort();}
    pthread_mutex_unlock(&s->gate);return ok;
}
void lie_store_result_release(lie_store *s,lie_store_result *r){
    assert(s&&r);lie_state_destroy(&r->state);
    pthread_mutex_lock(&s->gate);assert(s->taken&&s->ticket==r->ticket);
    s->taken=s->busy=s->done=false;s->info.pending=0;s->info.staging_bytes=0;
    pthread_mutex_unlock(&s->gate);
}
void lie_store_snapshot(lie_store *s,lie_store_info *out){
    if(!out)return;
    if(!s){memset(out,0,sizeof(*out));return;}
    pthread_mutex_lock(&s->gate);*out=s->info;pthread_mutex_unlock(&s->gate);
}
void lie_store_close(lie_store **store){
    if(!store||!*store)return;
    lie_store *s=*store;pthread_mutex_lock(&s->gate);s->stop=true;
    assert(!s->taken);
    if(s->read)atomic_store(&s->cancel,true);
    pthread_cond_signal(&s->ready);pthread_mutex_unlock(&s->gate);pthread_join(s->thread,NULL);
    lie_state_destroy(&s->state);free(s->tokens);close(s->notice);close(s->lock);close(s->directory);
    pthread_cond_destroy(&s->ready);pthread_mutex_destroy(&s->gate);free(s);*store=NULL;
}
