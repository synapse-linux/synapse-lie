/* SPDX-License-Identifier: MIT */
/* Synthetic layout/byte checks. No provider linked, no numerical inference. */
#include "lie/kvc_qwen_map.h"
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static const lie_state_section *find(const lie_state_section *s,unsigned n,uint32_t role,uint32_t layer) {
    for(unsigned i=0;i<n;++i)if(s[i].role==role&&s[i].layer==layer)return &s[i];
    return NULL;
}
static int cancel(void *u){unsigned *n=u;if(*n)--*n;return !*n;}
static void put32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;++i)p[i]=(unsigned char)(v>>(8*i));}
int main(int argc,char **argv) {
    assert(argc==7);uint32_t n=(uint32_t)strtoul(argv[4],NULL,10),threshold=(uint32_t)strtoul(argv[5],NULL,10);
    uint32_t ring=(uint32_t)strtoul(argv[6],NULL,10);
    lie_kvc_qwen_geometry g={4,1,2,1,4,3,2,3,2,5,2,6,32};
    lie_kvc_qwen_mapping m={.native={4,2,2,5,2,3,4,3,4,2,6,2,32,ring},.indexer_top_k=threshold,.eos_token=31};
    lie_kvc_limits limits=lie_kvc_default_limits(32u*1024u*1024u);lie_error e={0};lie_kvc *record=NULL;
    int fd=open(argv[1],O_RDONLY);assert(fd>=0);
    assert(lie_kvc_read_fd(fd,&limits,&record,&e)==LIE_OK);assert(!close(fd));
    const lie_kvc_view *v=lie_kvc_get_view(record);lie_kvc_qwen_layout wire;
    assert(lie_kvc_qwen_decode_record(v,&g,&limits,&wire,&e)==LIE_OK);
    lie_state_layout layout,unchanged;memset(&unchanged,0x5a,sizeof(unchanged));layout=unchanged;
    size_t required=0;
    assert(lie_kvc_qwen_project(v,&g,&m,&limits,&layout,NULL,0,&required,&e)==LIE_BUFFER_SMALL);
    assert(!memcmp(&layout,&unchanged,sizeof(layout))&&required);
    unsigned char *native=malloc(required),*expected=malloc(required),*encoded=malloc(v->payload.bytes),*bad=malloc(v->payload.bytes);
    assert(native&&expected&&encoded&&bad);
    assert(lie_kvc_qwen_project(v,&g,&m,&limits,&layout,native,required-1,&required,&e)==LIE_BUFFER_SMALL);
    assert(lie_kvc_qwen_project(v,&g,&m,&limits,&layout,native,required,&required,&e)==LIE_OK);
    assert(layout.domain==0&&layout.token_count==n&&layout.model_data[0]==(n>threshold?n/4:0));
    uint64_t size=0;assert(!lie_state_validate(&layout,&size)); /* No live binding. */
    lie_state_layout bound=layout;bound.domain=1;assert(lie_state_validate(&bound,&size)&&size==required);
    FILE *fp=fopen(argv[2],"rb");assert(fp);assert(fread(expected,1,required,fp)==required&&fgetc(fp)==EOF);assert(!fclose(fp));
    assert(!memcmp(native,expected,required));
    lie_kvc_qwen_extra extra[8];size_t count=0;
    for(unsigned i=0;i<wire.section_count;++i){const lie_state_section *p=&wire.sections[i];
        if(p->role==LIE_STATE_INDEX||p->role==LIE_STATE_BLOCK_KEYS)
            extra[count++]=(lie_kvc_qwen_extra){p->role,p->layer,{v->payload.data+p->offset,(size_t)p->bytes}};
    }
    lie_kvc_span src={native,required};size_t wire_bytes=0;
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&limits,
                               NULL,0,&wire_bytes,&e)==LIE_BUFFER_SMALL&&wire_bytes==v->payload.bytes);
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_OK);
    assert(!memcmp(encoded,v->payload.data,wire_bytes));
    lie_status missing=lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,NULL,0,&limits,
                                         encoded,wire_bytes,&wire_bytes,&e);
    assert(missing==(n<4?LIE_OK:LIE_UNSUPPORTED));
    if(n<4)assert(!memcmp(encoded,v->payload.data,wire_bytes));
    /* Correct exact scratch budget succeeds; one fewer byte is refused. */
    lie_kvc_limits tight=limits;tight.memory_bytes=wire_bytes+16ull*n-1;
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&tight,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_RESOURCE_LIMIT);
    ++tight.memory_bytes;
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&tight,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_OK);
    extra[count]=extra[0];
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count+1,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_INVALID);
    --extra[0].span.bytes;
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_INVALID);++extra[0].span.bytes;
    lie_state_layout malformed=layout;malformed.sections[0].dtype=LIE_STATE_U8;
    assert(lie_kvc_qwen_export(&malformed,src,&g,&wire.frontier,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_INVALID);
    lie_kvc_span short_source=src;--short_source.bytes;
    assert(lie_kvc_qwen_export(&layout,short_source,&g,&wire.frontier,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_INVALID);
    /* Known tail/pool bytes must match the independently retained full arrays. */
    const lie_state_section *known=find(layout.sections,layout.section_count,LIE_STATE_INDEX,1);
    if(!known)known=find(layout.sections,layout.section_count,LIE_STATE_BLOCK_KEYS,1);
    assert(known);native[known->offset]^=1;
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_INVALID);native[known->offset]^=1;
    const lie_state_section *history=find(layout.sections,layout.section_count,LIE_STATE_NGRAM,0);assert(history);
    native[history->offset]^=1;
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_INVALID);native[history->offset]^=1;
    lie_kvc_view damaged=*v;damaged.payload.data=bad;
    memcpy(bad,v->payload.data,wire_bytes);
    const lie_state_section *wh=find(wire.sections,wire.section_count,LIE_STATE_NGRAM,0);assert(wh);
    bad[wh->offset]^=1;
    assert(lie_kvc_qwen_project(&damaged,&g,&m,&limits,&layout,native,required,&required,&e)==LIE_INVALID);
    memcpy(bad,v->payload.data,wire_bytes);put32(bad+wire.mrope_delta_offset,1);
    assert(lie_kvc_qwen_project(&damaged,&g,&m,&limits,&layout,native,required,&required,&e)==LIE_UNSUPPORTED);
    memcpy(bad,v->payload.data,wire_bytes);
    const lie_state_section *positions=find(wire.sections,wire.section_count,LIE_KVC_QWEN_POSITIONS,0);assert(positions);
    bad[positions->offset]^=1;
    assert(lie_kvc_qwen_project(&damaged,&g,&m,&limits,&layout,native,required,&required,&e)==LIE_UNSUPPORTED);
    lie_kvc_qwen_mapping wrong=m;wrong.native.kv_width++;
    assert(lie_kvc_qwen_project(v,&g,&wrong,&limits,&layout,native,required,&required,&e)==LIE_INVALID);
    lie_kvc_qwen_frontier mtp=wire.frontier;mtp.mtp_tokens=1;
    assert(lie_kvc_qwen_export(&layout,src,&g,&mtp,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_UNSUPPORTED);
    tight=limits;tight.memory_bytes=v->payload.bytes-1;
    assert(lie_kvc_qwen_project(v,&g,&m,&tight,&layout,native,required,&required,&e)==LIE_RESOURCE_LIMIT);
    if(n>1&&n<=threshold){wrong=m;wrong.native.index_capacity=n-1;
        assert(lie_kvc_qwen_project(v,&g,&wrong,&limits,&layout,native,required,&required,&e)==LIE_INVALID);}
    assert(lie_kvc_qwen_project(v,&g,&m,&limits,&layout,(void *)v->payload.data,v->payload.bytes,&required,&e)==LIE_INVALID);
    if(v->payload.bytes>=sizeof(layout)){
        memcpy(bad,v->payload.data,wire_bytes);
        assert(lie_kvc_qwen_project(&damaged,&g,&m,&limits,(lie_state_layout *)(void *)bad,native,required,&required,&e)==LIE_INVALID);
        assert(!memcmp(bad,v->payload.data,wire_bytes));
    }
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&limits,
                               native,wire_bytes,&wire_bytes,&e)==LIE_INVALID);
    /* Cancellation can occur before or during bounded transfers; no descriptor
     * is published until the final completed copy. Each attempt starts clean. */
    for(unsigned stop=1;stop<=24;++stop){unsigned remaining=stop;
        tight=limits;tight.cancelled=cancel;tight.userdata=&remaining;lie_state_layout result=unchanged;
        lie_status rc=lie_kvc_qwen_project(v,&g,&m,&tight,&result,native,required,&required,&e);
        assert(rc==LIE_CANCELLED||rc==LIE_OK);
        if(rc==LIE_CANCELLED)assert(!memcmp(&result,&unchanged,sizeof(result)));
    }
    assert(lie_kvc_qwen_project(v,&g,&m,&limits,&layout,native,required,&required,&e)==LIE_OK);
    for(unsigned stop=1;stop<=24;++stop){unsigned remaining=stop;
        tight=limits;tight.cancelled=cancel;tight.userdata=&remaining;
        lie_status rc=lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&tight,
                                         encoded,wire_bytes,&wire_bytes,&e);
        assert(rc==LIE_CANCELLED||rc==LIE_OK);
    }
    assert(lie_kvc_qwen_export(&layout,src,&g,&wire.frontier,&m,extra,count,&limits,
                               encoded,wire_bytes,&wire_bytes,&e)==LIE_OK);
    lie_kvc_view out=*v;out.payload=(lie_kvc_span){encoded,wire_bytes};lie_kvc *rebuilt=NULL;
    assert(lie_kvc_create(&out,&limits,&rebuilt,&e)==LIE_OK);
    fd=open(argv[3],O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0);
    assert(lie_kvc_write_fd(fd,rebuilt,&limits,&e)==LIE_OK);assert(!close(fd));
    lie_kvc_destroy(&rebuilt);lie_kvc_destroy(&record);free(native);free(expected);free(encoded);free(bad);
    printf("Qwen native mapping at %u tokens, threshold %u: PASS (NOT-INFERENCE)\n",n,threshold);return 0;
}
