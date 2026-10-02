/* SPDX-License-Identifier: MIT */
#include "lie/kvc_qwen.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static void usage(void) {
    fputs("Usage: synapse-lie-kvc inspect INPUT [--max-mib N] [--qwen-geometry FILE]\n"
          "       synapse-lie-kvc copy INPUT OUTPUT [--max-mib N] [--qwen-geometry FILE]\n"
          "Offline KVC interchange only; no model restore or inference.\n"
          "Geometry: 13 decimal integers in the order documented in docs/KVC.md.\n",stderr);
}
static int number(const char *s,uint64_t max,uint64_t *out) {
    if(!s||!*s)return 0;
    uint64_t v=0;
    for(;*s;++s){if(*s<'0'||*s>'9'||v>(max-(unsigned)(*s-'0'))/10)return 0;v=v*10+(unsigned)(*s-'0');}
    if(!v||v>max)return 0;
    *out=v;return 1;
}
static int geometry(const char *path,lie_kvc_qwen_geometry *g) {
    int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);struct stat st;
    if(fd<0)return 0;
    if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_size>512){close(fd);return 0;}
    FILE *fp=fdopen(fd,"r");if(!fp){close(fd);return 0;}
    uint32_t v[13];char token[32];int ok=1;
    for(unsigned i=0;i<13;++i){uint64_t n=0;
        if(fscanf(fp,"%31s",token)!=1){ok=0;break;}
        /* MTP layer count may be zero. Other dimensions must be nonzero. */
        if(i==1&&!strcmp(token,"0"))n=0;
        else if(!number(token,UINT32_MAX,&n)){ok=0;break;}
        v[i]=(uint32_t)n;
    }
    if(ok&&fscanf(fp,"%31s",token)!=EOF)ok=0;
    if(ferror(fp))ok=0;
    if(fclose(fp))ok=0;
    if(ok)*g=(lie_kvc_qwen_geometry){v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7],v[8],v[9],v[10],v[11],v[12]};
    return ok;
}
static int publish(const char *path,const lie_kvc *k,const lie_kvc_limits *limits,lie_error *e) {
    size_t n=strlen(path);if(n>SIZE_MAX-24)return 0;
    char *tmp=malloc(n+24);if(!tmp)return 0;
    snprintf(tmp,n+24,"%s.partial.XXXXXX",path);int fd=mkstemp(tmp),ok=0;
    if(fd>=0){
        ok=lie_kvc_write_fd(fd,k,limits,e)==LIE_OK;
        if(ok&&fsync(fd))ok=0;
        if(close(fd))ok=0;
        /* Same-directory hard link publishes completely written bytes and
         * refuses an existing name atomically. No foreign file is replaced. */
        if(ok&&link(tmp,path))ok=0;
        if(unlink(tmp)&&ok)ok=0;
    }
    if(!ok&&!e->message[0])snprintf(e->message,sizeof(e->message),"KVC output creation or publication failed");
    free(tmp);return ok;
}
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"--help")){usage();return 0;}
    if(argc<3){usage();return 2;}
    int copying=!strcmp(argv[1],"copy");
    if((!copying&&strcmp(argv[1],"inspect"))||(copying&&argc<4)){usage();return 2;}
    const char *input=argv[2],*output=copying?argv[3]:NULL,*shape=NULL;uint64_t mib=256;
    for(int i=copying?4:3;i<argc;i+=2){
        if(i+1==argc){usage();return 2;}
        if(!strcmp(argv[i],"--max-mib")){if(!number(argv[i+1],1048576,&mib)){usage();return 2;}}
        else if(!strcmp(argv[i],"--qwen-geometry"))shape=argv[i+1];
        else{usage();return 2;}
    }
    lie_kvc_limits limits=lie_kvc_default_limits(mib*1024*1024);lie_kvc *k=NULL;lie_error e={0};
    int fd=open(input,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    if(fd<0){fputs("Cannot open KVC input\n",stderr);return 1;}
    lie_status rc=lie_kvc_read_fd(fd,&limits,&k,&e);int closed=close(fd);
    if(rc!=LIE_OK||closed){fprintf(stderr,"%s\n",e.message[0]?e.message:"KVC input close failed");lie_kvc_destroy(&k);return 1;}
    const lie_kvc_view *v=lie_kvc_get_view(k);lie_kvc_qwen_layout q={0};char name[44];
    if(lie_kvc_filename(v->text,name,&e)!=LIE_OK)goto failed;
    if(shape){
        lie_kvc_qwen_geometry g;
        if(!geometry(shape,&g)){snprintf(e.message,sizeof(e.message),"Invalid Qwen geometry file");goto failed;}
        if(lie_kvc_qwen_decode_record(v,&g,&limits,&q,&e)!=LIE_OK)goto failed;
    }
    if(copying&&!publish(output,k,&limits,&e))goto failed;
    printf("{\"format\":\"KVC\",\"version\":1,\"payload_abi\":2,\"model_id\":%u,"
           "\"quant_bits\":%u,\"tokens\":%u,\"context_tokens\":%u,\"hits\":%u,\"reason\":%u,\"flags\":%u,"
           "\"created_at\":%" PRIu64 ",\"last_used\":%" PRIu64 ",\"text_bytes\":%zu,\"payload_bytes\":%zu,"
           "\"trailer_bytes\":%zu,\"memory_bytes\":%" PRIu64 ",\"text_key\":\"%s\","
           "\"qwen_layout_validated\":%s,\"inference_qualified\":false,\"copied\":%s",
           v->header.model_id,v->header.quant_bits,v->header.tokens,v->header.context_tokens,v->header.hits,
           v->header.reason,v->header.flags,v->header.created_at,v->header.last_used,
           v->text.bytes,v->payload.bytes,v->trailer.bytes,lie_kvc_memory_bytes(k),name,
           shape?"true":"false",copying?"true":"false");
    if(shape)printf(",\"sections\":%u,\"mtp_tokens\":%u,\"text_positions\":%s",
                    q.section_count,q.frontier.mtp_tokens,q.text_positions?"true":"false");
    puts("}");lie_kvc_destroy(&k);return 0;
failed:
    fprintf(stderr,"%s\n",e.message);lie_kvc_destroy(&k);return 1;
}
