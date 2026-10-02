/* SPDX-License-Identifier: MIT */
#include "lie/store.h"
#include "state_codec.h"
#include "state_internal.h"
#include "retention.h"
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

typedef struct { char name[69];uint64_t bytes,allocated,age;unsigned tokens,context;lie_retention utility;lie_cache_metadata metadata; } entry;
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
    entry *entries;
    unsigned capacity;
    uint64_t index_bytes;
    lie_cache_metadata metadata;
    char *text;size_t text_bytes;
    int32_t *tokens;
    size_t count;
    uint32_t chunk, key_flags;
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
static uint64_t metadata_bytes(const lie_cache_metadata *m){return m->text_bytes+m->trailer_bytes+(m->text_bytes?1:0);}
static bool grow(lie_store *s){
    unsigned n=s->capacity?s->capacity*2:16;
    uint64_t add=(uint64_t)(n-s->capacity)*sizeof(entry);
    if(n<s->capacity||add>s->info.index_budget_bytes-s->index_bytes)return false;
    entry *p=realloc(s->entries,(size_t)n*sizeof(*p));if(!p)return false;
    memset(p+s->capacity,0,(n-s->capacity)*sizeof(*p));s->entries=p;s->capacity=n;s->index_bytes+=add;return true;
}
static void account(lie_store *s){
    uint64_t bytes=0,allocated=0;unsigned count=0;
    for(unsigned i=0;i<s->capacity;++i)if(s->entries[i].name[0]){bytes+=s->entries[i].bytes;allocated+=s->entries[i].allocated;++count;}
    pthread_mutex_lock(&s->gate);s->info.disk_bytes=bytes;s->info.allocated_bytes=allocated;s->info.entries=count;s->info.index_bytes=s->index_bytes;pthread_mutex_unlock(&s->gate);
}
static bool remove_entry(lie_store *s,unsigned i){
    entry *e=&s->entries[i];int fd=open_file(s,e->name);
    bool ok=fd>=0&&same_file(s,e->name,fd)&&!unlinkat(s->directory,e->name,0);
    if(fd>=0)close(fd);
    if(ok){s->index_bytes-=metadata_bytes(&e->metadata);lie_cache_metadata_clear(&e->metadata);memset(e,0,sizeof(*e));pthread_mutex_lock(&s->gate);++s->info.evictions;pthread_mutex_unlock(&s->gate);account(s);}
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
        if(count==s->capacity&&!grow(s)){close(fd);ok=false;break;}
        entry *e=&s->entries[count++];memcpy(e->name,name,69);e->bytes=(uint64_t)st.st_size;
        e->allocated=(uint64_t)st.st_blocks*512;e->age=++s->clock;uint64_t bytes=0;
        if(!lie_state_file_probe(fd,&s->identity,&bytes,&e->tokens,&e->context))e->tokens=0;
        if(e->tokens&&!lie_state_file_metadata(fd,&s->identity,s->info.index_budget_bytes-s->index_bytes,&e->metadata)){close(fd);ok=false;break;}
        s->index_bytes+=metadata_bytes(&e->metadata);
        e->utility=(lie_retention){.created=e->metadata.created_at,.touched=e->metadata.last_used,.hits=e->metadata.hits,.reason=e->metadata.reason};
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
static bool reserve_disk(lie_store *s,uint64_t bytes,unsigned *slot,bool *continued,unsigned protected_slot){
    if(bytes>UINT64_MAX-(s->block_bytes-1))return false;
    uint64_t allocated=((bytes+s->block_bytes-1)/s->block_bytes)*s->block_bytes;
    if(bytes>s->info.quota_bytes||allocated>s->info.quota_bytes)return false;
    const lie_state_layout *layout=s->state?lie_state_description(s->state):NULL;
    for(;;){uint64_t used=0,blocks=0;unsigned free_slot=s->capacity,oldest=s->capacity;double score=0;
        for(unsigned i=0;i<s->capacity;++i){entry *e=&s->entries[i];if(!e->name[0]){free_slot=i;continue;}
            used+=e->bytes;blocks+=e->allocated;
            uint64_t cost=e->bytes;
            bool superseded=false;
            if(layout&&layout->context_tokens<=e->context&&(e->metadata.flags&6u)==(s->metadata.flags&6u)){
                if(s->metadata.text_bytes&&e->metadata.text_bytes)
                    superseded=e->metadata.text_bytes<s->metadata.text_bytes&&!memcmp(e->metadata.text,s->metadata.text,e->metadata.text_bytes);
                else if(!s->metadata.text_bytes&&!e->metadata.text_bytes&&e->tokens<layout->token_count){char key[69]={0};if(lie_state_prefix_key(&s->identity,lie_state_tokens(s->state),e->tokens,key)){
                    memcpy(key+64,".lie",5);superseded=!strcmp(key,e->name);}}
            }
            if(superseded&&continued)*continued=true;
            double value=lie_retention_score(&e->utility,lie_cache_now(),e->tokens,cost,superseded);
            if(i!=protected_slot&&(oldest==s->capacity||(LIE_CACHE_UTILITY?(value<score||(value==score&&e->age<s->entries[oldest].age)):
                                                                      e->age<s->entries[oldest].age))){oldest=i;score=value;}}
        if(free_slot==s->capacity&&grow(s))free_slot=s->capacity/2;
        if(free_slot<s->capacity&&used<=s->info.quota_bytes-bytes&&blocks<=s->info.quota_bytes-allocated){*slot=free_slot;return true;}
        if(oldest==s->capacity||!remove_entry(s,oldest))return false;
    }
}
static bool write_state(lie_store *s){
    char name[69]={0},temporary[78];const lie_state_layout *l=lie_state_description(s->state);
    if(!lie_state_prefix_key(&s->identity,lie_state_tokens(s->state),l->token_count,name))return false;
    memcpy(name+64,".lie",5);
    unsigned replacement=s->capacity;
    for(unsigned i=0;i<s->capacity;++i)if(!strcmp(s->entries[i].name,name)){
        /* Immutable tensor payload is deduplicated. Extension changes require
         * replacing the record so its digest still binds the new metadata. */
        entry *e=&s->entries[i];
        if(e->metadata.flags==s->metadata.flags&&e->metadata.text_bytes==s->metadata.text_bytes&&
           e->metadata.trailer_bytes==s->metadata.trailer_bytes&&
           (!s->metadata.text_bytes||!memcmp(e->metadata.text,s->metadata.text,s->metadata.text_bytes))&&
           (!s->metadata.trailer_bytes||!memcmp(e->metadata.trailer,s->metadata.trailer,s->metadata.trailer_bytes))){e->age=++s->clock;return true;}
        replacement=i;s->metadata.created_at=e->metadata.created_at;
        s->metadata.hits=e->metadata.hits;s->metadata.last_used=e->metadata.last_used;
        break;
    }
    unsigned slot=0;uint64_t bytes=lie_state_file_bytes_ex(s->state,&s->metadata);
    uint64_t meta_bytes=metadata_bytes(&s->metadata);
    if(meta_bytes>s->info.index_budget_bytes-s->index_bytes)return false;
    bool continued=false;if(!reserve_disk(s,bytes,&slot,&continued,replacement))return false;
    if(replacement<s->capacity&&s->entries[replacement].name[0])slot=replacement;
    snprintf(temporary,sizeof(temporary),".pending-%s",name);
    int fd=openat(s->directory,temporary,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);if(fd<0)return false;
    bool renamed=false;struct stat st;
    bool ok=lie_state_file_write_ex(fd,&s->identity,s->state,&s->metadata,&s->cancel)&&!fsync(fd)&&owned_file(fd,&st)&&same_file(s,temporary,fd);
    if(ok){
        uint64_t allocated=(uint64_t)st.st_blocks*512,used=0;
        for(unsigned i=0;i<s->capacity;++i)used+=s->entries[i].allocated;
        ok=(uint64_t)st.st_size==bytes&&allocated<=s->info.quota_bytes&&used<=s->info.quota_bytes-allocated;
    }
    if(ok){ok=renameat(s->directory,temporary,s->directory,name)==0;renamed=ok;}
    if(renamed){entry *e=&s->entries[slot];memcpy(e->name,name,sizeof(name));
        e->bytes=(uint64_t)st.st_size;e->allocated=(uint64_t)st.st_blocks*512;e->age=++s->clock;e->tokens=l->token_count;e->context=l->context_tokens;
        s->index_bytes-=metadata_bytes(&e->metadata);lie_cache_metadata_clear(&e->metadata);
        e->metadata=s->metadata;memset(&s->metadata,0,sizeof(s->metadata));s->index_bytes+=meta_bytes;
        e->utility=(lie_retention){.created=e->metadata.created_at,.touched=e->metadata.last_used,.hits=e->metadata.hits,.reason=e->metadata.reason};
        account(s);ok=fsync(s->directory)==0;
    }else if(same_file(s,temporary,fd)){(void)unlinkat(s->directory,temporary,0);(void)fsync(s->directory);}
    close(fd);
    if(ok){pthread_mutex_lock(&s->gate);++s->info.writes;s->info.written_bytes+=bytes;pthread_mutex_unlock(&s->gate);}
    return ok;
}
static lie_state *read_state(lie_store *s){
    uint64_t ceiling=UINT64_MAX;unsigned prior=UINT32_MAX;
    for(unsigned attempt=0;attempt<s->capacity&&!atomic_load(&s->cancel);++attempt){
        unsigned best=s->capacity;uint64_t length=0;
        for(unsigned i=0;i<s->capacity;++i){entry *e=&s->entries[i];if(!e->tokens)continue;
            uint64_t n=s->text?e->metadata.text_bytes:e->tokens;
            if(n>ceiling||(n==ceiling&&i>=prior))continue;
            bool match=false;
            if(s->text)match=(e->metadata.flags&6u)==(s->key_flags&6u)&&n&&n<=s->text_bytes&&!memcmp(e->metadata.text,s->text,(size_t)n);
            else if((e->metadata.flags&6u)==(s->key_flags&6u)&&e->tokens<=s->count&&(e->tokens==s->count||e->tokens%s->chunk==0)){
                char name[69]={0};if(lie_state_prefix_key(&s->identity,s->tokens,e->tokens,name)){
                    memcpy(name+64,".lie",5);match=!strcmp(e->name,name);}}
            if(match&&(best==s->capacity||n>length||(n==length&&i>best))){best=i;length=n;}
        }
        if(best==s->capacity)break;
        ceiling=length;prior=best;entry *e=&s->entries[best];
        uint64_t input=s->count*sizeof(*s->tokens)+s->text_bytes+metadata_bytes(&e->metadata);
        if(input>=s->info.staging_budget_bytes)continue;
        int fd=open_file(s,e->name);
        lie_state *state=fd<0?NULL:lie_state_file_read(fd,&s->identity,s->domain,s->info.staging_budget_bytes-input,&s->cancel);
        if(fd>=0)close(fd);
        if(state){const lie_state_layout *l=lie_state_description(state);
            if(l->token_count!=e->tokens||l->prefill_chunk!=s->chunk||
               (!s->text&&memcmp(lie_state_tokens(state),s->tokens,e->tokens*sizeof(*s->tokens))))lie_state_destroy(&state);
        }
        if(state&&!lie_cache_metadata_copy(&s->metadata,&e->metadata))lie_state_destroy(&state);
        if(state){e->age=++s->clock;lie_retention_hit(&e->utility,lie_cache_now());
            e->metadata.hits=e->utility.hits;e->metadata.last_used=e->utility.touched;
            s->metadata.hits=e->utility.hits;s->metadata.last_used=e->utility.touched;
            int update=openat(s->directory,e->name,O_RDWR|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
            if(update>=0){if(!same_file(s,e->name,update)||!lie_state_file_touch(update,&s->identity,e->utility.hits,e->utility.touched)){
                    pthread_mutex_lock(&s->gate);++s->info.errors;pthread_mutex_unlock(&s->gate);}
                close(update);}
            (void)lie_state_compress_cancel(&state,s->info.staging_budget_bytes-input,&s->cancel);
            pthread_mutex_lock(&s->gate);s->info.read_bytes+=e->bytes;pthread_mutex_unlock(&s->gate);return state;}
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
        free(s->tokens);s->tokens=NULL;free(s->text);s->text=NULL;s->text_bytes=0;
        if(!read||!s->state)lie_cache_metadata_clear(&s->metadata);
        s->done=true;
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
    s->info=(lie_store_info){.enabled=true,.quota_bytes=o->quota_bytes,.staging_budget_bytes=o->staging_bytes,
        .index_budget_bytes=o->staging_bytes,.utility_policy=LIE_CACHE_UTILITY!=0,.compression_enabled=lie_state_compression_enabled()};
    if(pthread_mutex_init(&s->gate,NULL)){free(s);return LIE_RESOURCE_LIMIT;}
    if(pthread_cond_init(&s->ready,NULL)){pthread_mutex_destroy(&s->gate);free(s);return LIE_RESOURCE_LIMIT;}
    s->directory=private_directory(o->directory);if(s->directory<0)goto bad;
    s->lock=openat(s->directory,".lie-prefix.lock",O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK,0600);
    struct stat st;struct statvfs fs;
    if(s->lock<0||!owned_file(s->lock,&st)||!same_file(s,".lie-prefix.lock",s->lock)||flock(s->lock,LOCK_EX|LOCK_NB)||
       fstatvfs(s->directory,&fs)||!fs.f_frsize||fs.f_frsize>1048576)goto bad;
    s->block_bytes=fs.f_frsize;
    if(!scan(s))goto bad;
    /* Opening an explicitly enabled owned store enforces its current quota. */
    if(s->info.disk_bytes>o->quota_bytes||s->info.allocated_bytes>o->quota_bytes){
        unsigned slot;bool continued=false;if(!reserve_disk(s,0,&slot,&continued,UINT32_MAX))goto bad;
    }
    s->notice=eventfd(0,EFD_CLOEXEC|EFD_NONBLOCK);
    if(s->notice<0||pthread_create(&s->thread,NULL,io_worker,s))goto bad;
    *out=s;return LIE_OK;
bad:
    if(s->notice>=0)close(s->notice);
    if(s->lock>=0)close(s->lock);
    if(s->directory>=0)close(s->directory);
    for(unsigned i=0;i<s->capacity;++i)lie_cache_metadata_clear(&s->entries[i].metadata);
    free(s->entries);lie_cache_metadata_clear(&s->metadata);
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
uint64_t lie_store_read_key(lie_store *s,const int32_t *tokens,size_t n,uint32_t chunk,uint32_t flags){
    if(!s||!tokens||!n||n>UINT32_MAX||!chunk||n>SIZE_MAX/sizeof(*tokens)||(flags&~15u))return 0;
    pthread_mutex_lock(&s->gate);uint64_t ticket=0;
    if(!s->stop&&!s->busy&&n*sizeof(*tokens)<s->info.staging_budget_bytes){
        s->tokens=malloc(n*sizeof(*tokens));
        if(s->tokens){memcpy(s->tokens,tokens,n*sizeof(*tokens));s->count=n;s->chunk=chunk;s->key_flags=flags;
            /* Reserve the entire staging cap before asynchronous allocation. */
            admitted(s,s->info.staging_budget_bytes,true);++s->info.lookups;ticket=s->ticket;}
    }
    pthread_mutex_unlock(&s->gate);return ticket;
}
uint64_t lie_store_read(lie_store *s,const int32_t *tokens,size_t n,uint32_t chunk){
    return lie_store_read_key(s,tokens,n,chunk,0);
}
uint64_t lie_store_read_text_key(lie_store *s,const char *text,size_t n,uint32_t chunk,uint32_t flags){
    if(!s||!text||!n||n>LIE_CACHE_TEXT_MAX||!chunk||(flags&~15u))return 0;
    pthread_mutex_lock(&s->gate);uint64_t ticket=0;
    if(!s->stop&&!s->busy&&n<s->info.staging_budget_bytes){
        s->text=malloc(n);
        if(s->text){memcpy(s->text,text,n);s->text_bytes=n;s->count=0;s->chunk=chunk;s->key_flags=flags;
            admitted(s,s->info.staging_budget_bytes,true);++s->info.lookups;ticket=s->ticket;}
    }
    pthread_mutex_unlock(&s->gate);return ticket;
}
uint64_t lie_store_read_text(lie_store *s,const char *text,size_t n,uint32_t chunk){
    return lie_store_read_text_key(s,text,n,chunk,0);
}
bool lie_store_can_write(lie_store *s,uint64_t bytes){
    if(!s)return false;
    pthread_mutex_lock(&s->gate);bool ok=!s->stop&&!s->busy&&bytes<=s->info.staging_budget_bytes&&bytes<=s->info.quota_bytes;
    pthread_mutex_unlock(&s->gate);return ok;
}
bool lie_store_write_ex(lie_store *s,lie_state *state,const lie_cache_metadata *metadata){
    if(!s||!state||!lie_cache_metadata_valid(metadata))return false;
    uint64_t bytes=lie_state_bytes(state);pthread_mutex_lock(&s->gate);
    bool ok=!s->stop&&!s->busy&&lie_state_description(state)->domain==s->domain&&
        bytes<=s->info.staging_budget_bytes&&metadata_bytes(metadata)<=s->info.staging_budget_bytes-bytes&&
        lie_state_file_bytes_ex(state,metadata)<=s->info.quota_bytes&&lie_cache_metadata_copy(&s->metadata,metadata);
    if(ok){if(!s->metadata.created_at)s->metadata.created_at=lie_cache_now();
        if(!s->metadata.last_used)s->metadata.last_used=s->metadata.created_at;
        lie_state_retain(state);s->state=state;admitted(s,bytes+metadata_bytes(metadata),false);}else ++s->info.skipped;
    pthread_mutex_unlock(&s->gate);return ok;
}
bool lie_store_write(lie_store *s,lie_state *state){
    const lie_cache_metadata m={.reason=LIE_CACHE_COLD};return lie_store_write_ex(s,state,&m);
}
void lie_store_cancel(lie_store *s,uint64_t ticket){
    if(!s)return;
    pthread_mutex_lock(&s->gate);if(s->busy&&s->read&&s->ticket==ticket)atomic_store(&s->cancel,true);pthread_mutex_unlock(&s->gate);
}
bool lie_store_take(lie_store *s,lie_store_result *r){
    if(!s||!r)return false;
    pthread_mutex_lock(&s->gate);bool ok=s->busy&&s->done&&!s->taken;
    if(ok){*r=(lie_store_result){.ticket=s->ticket,.read_ns=s->elapsed,.read=s->read,.state=s->state,.metadata=s->metadata};s->state=NULL;memset(&s->metadata,0,sizeof(s->metadata));s->taken=true;
        uint64_t value;ssize_t n;
        do{n=read(s->notice,&value,sizeof(value));}while(n<0&&errno==EINTR);
        if(n<0&&errno!=EAGAIN)abort();}
    pthread_mutex_unlock(&s->gate);return ok;
}
void lie_store_result_release(lie_store *s,lie_store_result *r){
    assert(s&&r);lie_state_destroy(&r->state);lie_cache_metadata_clear(&r->metadata);
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
    for(unsigned i=0;i<s->capacity;++i)lie_cache_metadata_clear(&s->entries[i].metadata);
    free(s->entries);lie_cache_metadata_clear(&s->metadata);
    pthread_cond_destroy(&s->ready);pthread_mutex_destroy(&s->gate);free(s);*store=NULL;
}
