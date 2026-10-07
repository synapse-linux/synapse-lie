/* SPDX-License-Identifier: MIT */
/* Native management configuration fixture. Private ports; NOT-INFERENCE. */
#include "bench_native.h"
#include <curl/curl.h>
#include <arpa/inet.h>
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static pid_t owned=-1;
static void pause_short(void) {
    struct timespec t={0,10000000};
    while(nanosleep(&t,&t)&&errno==EINTR){}
}
static void cleanup(void) {
    if(owned<=0)return;
    kill(owned,SIGTERM);
    int status;
    for(unsigned n=0;n<100;++n) {
        pid_t r=waitpid(owned,&status,WNOHANG);
        if(r==owned||(r<0&&errno==ECHILD)){owned=-1;return;}
        pause_short();
    }
    kill(owned,SIGKILL);
    while(waitpid(owned,&status,0)<0&&errno==EINTR){}
    owned=-1;
}
static void require(bool ok,const char *why) {
    if(!ok){fprintf(stderr,"Prefill HTTP: %s\n",why);exit(1);}
}
static unsigned reserve(int *fd) {
    *fd=socket(AF_INET,SOCK_STREAM,0);require(*fd>=0,"socket");
    struct sockaddr_in a={.sin_family=AF_INET,.sin_addr.s_addr=htonl(INADDR_LOOPBACK)};
    require(!bind(*fd,(struct sockaddr *)&a,sizeof(a)),"bind");
    socklen_t size=sizeof(a);require(!getsockname(*fd,(struct sockaddr *)&a,&size),"port");
    return ntohs(a.sin_port);
}
typedef struct {char data[65536];size_t bytes;} buffer;
static size_t collect(char *data,size_t size,size_t count,void *arg) {
    buffer *b=arg;
    if(size&&count>SIZE_MAX/size)return 0;
    size_t n=size*count;
    if(n>=sizeof(b->data)-b->bytes)return 0;
    memcpy(b->data+b->bytes,data,n);b->bytes+=n;b->data[b->bytes]=0;return n;
}
static json_object *exchange(unsigned port,const char *path,const char *method,
                             const char *raw,long expected) {
    char url[256];snprintf(url,sizeof(url),"http://127.0.0.1:%u%s",port,path);
    CURL *curl=curl_easy_init();require(curl!=NULL,"curl init");
    struct curl_slist *headers=curl_slist_append(NULL,"Content-Type: application/json");
    require(headers!=NULL,"headers");buffer b={0};long code=0;
    curl_easy_setopt(curl,CURLOPT_URL,url);
    curl_easy_setopt(curl,CURLOPT_HTTPHEADER,headers);
    if(raw)curl_easy_setopt(curl,CURLOPT_POSTFIELDS,raw);
    curl_easy_setopt(curl,CURLOPT_CUSTOMREQUEST,method);
    curl_easy_setopt(curl,CURLOPT_TIMEOUT_MS,3000L);
    curl_easy_setopt(curl,CURLOPT_WRITEFUNCTION,collect);
    curl_easy_setopt(curl,CURLOPT_WRITEDATA,&b);
    require(curl_easy_perform(curl)==CURLE_OK,"HTTP transfer");
    curl_easy_getinfo(curl,CURLINFO_RESPONSE_CODE,&code);
    curl_slist_free_all(headers);curl_easy_cleanup(curl);
    if(code!=expected)fprintf(stderr,"%s %s: expected %ld, received %ld: %s\n",method,path,expected,code,b.data);
    require(code==expected,"HTTP status");
    nb_error e={0};json_object *j=nb_parse(b.data,b.bytes,&e);
    require(j!=NULL,e.message);return j;
}
static void discard(unsigned p,const char *path,const char *method,const char *body,long status) {
    json_object_put(exchange(p,path,method,body,status));
}
static void config(unsigned p,unsigned chunk,unsigned capacity,unsigned revision) {
    json_object *j=exchange(p,"/actuator/llm/prefill","GET",NULL,200);
    require(nb_number(j,"prefill_chunk")==chunk&&nb_number(j,"prefill_capacity")==capacity&&
            nb_number(j,"revision")==revision&&!strcmp(nb_string(j,"applies_to"),"new_requests"),"configuration snapshot");
    json_object_put(j);
}
static void start(const char *exe,bool model,unsigned *ap,unsigned *mp) {
    int a,b;*ap=reserve(&a);*mp=reserve(&b);
    char api[16],mgmt[16];snprintf(api,sizeof(api),"%u",*ap);snprintf(mgmt,sizeof(mgmt),"%u",*mp);
    close(a);close(b);owned=fork();require(owned>=0,"fork");
    if(!owned) {
        setenv("PATH","/nonexistent-native-prefill-test",1);setenv("LC_ALL","C",1);
        if(model)execl(exe,exe,"--model",":fixture:","--model-id","cpu-test-fixture",
            "--host","127.0.0.1","--port",api,"--management-port",mgmt,
            "--context","128","--prefill-chunk","4","--prefill-capacity","16",
            "--kv-cache-ram-mb","0",(char *)NULL);
        else execl(exe,exe,"--host","127.0.0.1","--port",api,"--management-port",mgmt,(char *)NULL);
        _exit(127);
    }
    char health[128];snprintf(health,sizeof(health),"http://127.0.0.1:%u/actuator/health/liveness",*mp);
    bool ready=false;
    for(unsigned n=0;n<500;++n) {
        int status;pid_t r=waitpid(owned,&status,WNOHANG);
        if(r==owned)owned=-1;
        require(!r,"server exited before liveness");
        nb_error e={0};json_object *j=nb_http_get(health,.25,&e);
        if(j){json_object_put(j);ready=true;break;}pause_short();
    }
    require(ready,"liveness deadline");
    if(model) {
        snprintf(health,sizeof(health),"http://127.0.0.1:%u/actuator/health/readiness",*mp);
        ready=false;
        for(unsigned n=0;n<500;++n) {
            nb_error e={0};json_object *j=nb_http_get(health,.25,&e);
            if(j){json_object_put(j);ready=true;break;}pause_short();
        }
        require(ready,"readiness deadline");
    }
}
static void stop(void) {
    require(owned>0&&!kill(owned,SIGTERM),"graceful stop");
    int status=0;while(waitpid(owned,&status,0)<0)require(errno==EINTR,"wait");owned=-1;
    require(WIFEXITED(status)&&!WEXITSTATUS(status),"server/sanitizer exit");
}
static void inference(unsigned p,unsigned calls) {
    json_object *j=exchange(p,"/v1/chat/completions","POST",
        "{\"model\":\"cpu-test-fixture\",\"messages\":[{\"role\":\"user\",\"content\":\"normal\"}],\"max_tokens\":2}",200);
    require(nb_number(nb_get(j,"usage"),"prompt_tokens")==4&&
            nb_number(nb_get(j,"lie_timings"),"prefill_calls")==calls,"chosen chunk reached the shared core");
    json_object_put(j);
}
int main(int argc,char **argv) {
    require(argc==2,"server argument");atexit(cleanup);
    require(curl_global_init(CURL_GLOBAL_DEFAULT)==CURLE_OK,"curl global init");
    unsigned ap,mp;start(argv[1],true,&ap,&mp);
    config(mp,4,16,1);inference(ap,1);
    discard(mp,"/actuator/llm/prefill","POST","{\"prefill_chunk\":2}",200);
    config(mp,2,16,2);inference(ap,2);
    discard(mp,"/actuator/llm/prefill","POST","{\"prefill_chunk\":2}",200);config(mp,2,16,2);
    const char *invalid[]={"{}","[]","{\"prefill_chunk\":0}","{\"prefill_chunk\":-1}",
        "{\"prefill_chunk\":2.0}","{\"prefill_chunk\":2e0}","{\"prefill_chunk\":\"2\"}",
        "{\"prefill_chunk\":null}","{\"prefill_chunk\":true}","{\"prefill_chunk\":32769}",
        "{\"prefill_chunk\":2,\"prefill_chunk\":4}","{\"prefill_chunk\":4,\"other\":1}",
        "{\"prefill_chunk\":4}junk"};
    for(size_t n=0;n<sizeof(invalid)/sizeof(*invalid);++n)
        discard(mp,"/actuator/llm/prefill","POST",invalid[n],400);
    discard(mp,"/actuator/llm/prefill","POST","{\"prefill_chunk\":17}",409);
    discard(mp,"/actuator/llm/prefill?x=1","GET",NULL,400);
    discard(mp,"/actuator/llm/prefill","PUT","{\"prefill_chunk\":4}",405);
    discard(ap,"/actuator/llm/prefill","POST","{\"prefill_chunk\":4}",404);
    config(mp,2,16,2);
    char large[1100];memset(large,' ',sizeof(large)-1);large[sizeof(large)-1]=0;
    discard(mp,"/actuator/llm/prefill","POST",large,400);config(mp,2,16,2);
    discard(mp,"/actuator/llm/prefill","POST","{\"prefill_chunk\":16}",200);
    config(mp,16,16,3);inference(ap,1);stop();
    start(argv[1],false,&ap,&mp);
    discard(mp,"/actuator/llm/prefill","GET",NULL,503);
    discard(mp,"/actuator/llm/prefill","POST","{\"prefill_chunk\":4}",503);stop();
    curl_global_cleanup();
    puts("Live prefill management, parser refusal and actual core use: PASS (NOT-INFERENCE)");
    return 0;
}
