/* SPDX-License-Identifier: MIT */
/* Synthetic host state only. No model forward, device calls or GPU evidence. */
#include "lie/kvc_state.h"
#include "../src/state_codec.h"
#include "../src/state_internal.h"
#include <assert.h>
#include <fcntl.h>
#include <math.h>
#include <openssl/evp.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct lie_sequence {const lie_state_layout *layout;const unsigned char *payload;size_t bytes;int empty;};
static unsigned writes;
lie_status lie_sequence_state_describe(lie_sequence *s,const lie_state_layout *in,lie_state_layout *out,lie_error *e){
    (void)e;if(in&&(!s->empty||!lie_state_layout_equal(in,s->layout)))return LIE_INVALID;
    *out=*s->layout;return LIE_OK;
}
lie_status lie_sequence_state_read(lie_sequence *s,const lie_state_layout *l,void *out,size_t n,lie_error *e){
    (void)e;if(n!=s->bytes||!lie_state_layout_equal(l,s->layout))return LIE_INVALID;
    memcpy(out,s->payload,n);return LIE_OK;
}
lie_status lie_sequence_state_write(lie_sequence *s,const lie_state_layout *l,const void *p,size_t n,lie_error *e){
    (void)e;if(!s->empty||n!=s->bytes||!lie_state_layout_equal(l,s->layout)||memcmp(p,s->payload,n))return LIE_INVALID;
    s->empty=0;++writes;return LIE_OK;
}
static uint32_t u32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void wait_store(lie_store *s,lie_store_result *r){
    for(unsigned i=0;i<100&&!lie_store_take(s,r);++i){struct pollfd p={lie_store_fd(s),POLLIN,0};assert(poll(&p,1,100)>=0);}
    assert(r->ticket);
}
static void roundtrip(const char *root,unsigned index,const lie_state_layout *l,const unsigned char *payload,size_t n){
    lie_error e={0};struct lie_sequence producer={l,payload,n,0},clone={l,payload,n,1};
    lie_state_layout plan;uint64_t retained,base,aux;
    assert(lie_state_kvc_parts(l,&base,&aux)&&base+aux==n);
    assert(lie_state_plan(&producer,&plan,&retained,&e)==LIE_OK);
    lie_state *s=NULL;assert(lie_state_capture(&producer,&plan,retained-1,&s,&e)==LIE_RESOURCE_LIMIT&&!s);
    assert(lie_state_capture(&producer,&plan,retained,&s,&e)==LIE_OK);
    assert(!lie_state_compress(&s,UINT64_MAX)&&lie_state_restore_workspace(s)==0);
    assert(lie_state_restore(&clone,s,&e)==LIE_OK&&lie_state_restore(&clone,s,&e)==LIE_INVALID);
    lie_state_identity id={{1}},wrong={{2}};lie_cache_metadata meta={.text="aux fixture",.text_bytes=11,
        .trailer="client",.trailer_bytes=6,.reason=LIE_CACHE_COLD,.created_at=3};
    char path[4096];assert(snprintf(path,sizeof(path),"%s/%u.kv",root,index)<(int)sizeof(path));
    int fd=open(path,O_CREAT|O_EXCL|O_RDWR,0600);assert(fd>=0);
    atomic_bool cancel=false;assert(lie_state_file_write_ex(fd,&id,s,&meta,&cancel));
    unsigned char h[52];assert(pread(fd,h,sizeof(h),0)==sizeof(h)&&!memcmp(h,"KVC\1",4)&&u32(h+40)==base);
    unsigned char *disk=malloc(n);assert(disk);
    assert(pread(fd,disk,(size_t)base,52+11)==(ssize_t)base&&!memcmp(disk,payload,(size_t)base));
    assert(pread(fd,disk,(size_t)aux,52+11+(off_t)base+6)==(ssize_t)aux&&!memcmp(disk,payload+base,(size_t)aux));
    free(disk);
    /* The regular DS4 reader still exposes exactly the original payload and
     * the client extension as the first bytes of its opaque trailer. */
    lie_kvc_limits wire_limits=lie_kvc_default_limits(1u<<20);lie_kvc *wire=NULL;
    assert(lie_kvc_read_fd(fd,&wire_limits,&wire,&e)==LIE_OK);
    const lie_kvc_view *view=lie_kvc_get_view(wire);
    assert(view->payload.bytes==base&&!memcmp(view->payload.data,payload,(size_t)base));
    assert(view->trailer.bytes>=6&&!memcmp(view->trailer.data,"client",6));lie_kvc_destroy(&wire);
    uint64_t disk_bytes;unsigned tokens,context;
    assert(lie_state_file_probe(fd,&id,&disk_bytes,&tokens,&context)&&tokens==l->token_count&&context==l->context_tokens);
    assert(disk_bytes==lie_state_file_bytes_ex(s,&meta)&&!lie_state_file_probe(fd,&wrong,&disk_bytes,&tokens,&context));
    assert(!lie_state_file_read(fd,&id,l->domain,retained-1,&cancel));
    atomic_store(&cancel,true);assert(!lie_state_file_read(fd,&id,l->domain,retained,&cancel));atomic_store(&cancel,false);
    lie_state *loaded=lie_state_file_read(fd,&id,l->domain,retained,&cancel);assert(loaded);
    clone.empty=1;assert(lie_state_restore(&clone,loaded,&e)==LIE_OK);lie_state_destroy(&loaded);
    lie_cache_metadata got;assert(lie_state_file_metadata(fd,&id,64,&got));
    assert(got.trailer_bytes==6&&!memcmp(got.trailer,"client",6));lie_cache_metadata_clear(&got);
    assert(lie_state_file_touch(fd,&id,3,19));loaded=lie_state_file_read(fd,&id,l->domain,retained,NULL);assert(loaded);lie_state_destroy(&loaded);
    /* Auxiliary tensors and framing are in the checksum; length mismatches
     * must be rejected before allocation or publication. */
    off_t offsets[]={52+11+(off_t)base+6,(off_t)disk_bytes-16,(off_t)disk_bytes-8,(off_t)disk_bytes-1};
    for(unsigned i=0;i<4;++i){unsigned char b;assert(pread(fd,&b,1,offsets[i])==1);unsigned char bad=b^1;
        assert(pwrite(fd,&bad,1,offsets[i])==1&&!lie_state_file_read(fd,&id,l->domain,retained,NULL));
        assert(pwrite(fd,&b,1,offsets[i])==1);
    }
    close(fd);assert(!unlink(path));
    char directory[4096];assert(snprintf(directory,sizeof(directory),"%s/store-%u",root,index)<(int)sizeof(directory));
    lie_store_options options={.directory=directory,.quota_bytes=1u<<20,.staging_bytes=1u<<20};
    lie_store *store=NULL;assert(lie_store_open(&options,&id,l->domain,&store,&e)==LIE_OK);
    assert(lie_store_write_ex(store,s,&meta));lie_store_result result={0};wait_store(store,&result);
    lie_store_result_release(store,&result);lie_store_info info;lie_store_snapshot(store,&info);assert(info.writes==1&&!info.errors);
    lie_store_close(&store);assert(lie_store_open(&options,&id,l->domain+1,&store,&e)==LIE_OK);
    assert(lie_store_read(store,lie_state_tokens(s),l->token_count,l->prefill_chunk));result=(lie_store_result){0};wait_store(store,&result);
    assert(result.state&&lie_state_description(result.state)->format==l->format&&lie_state_description(result.state)->domain==l->domain+1);
    lie_store_result_release(store,&result);lie_store_close(&store);lie_state_destroy(&s);
    /* Only test-owned known cache paths are removed. */
    unsigned char digest[20];unsigned digest_bytes=0;char name[41];
    assert(EVP_Digest(meta.text,meta.text_bytes,digest,&digest_bytes,EVP_sha1(),NULL)==1&&digest_bytes==20);
    for(unsigned i=0;i<20;++i)snprintf(name+2*i,3,"%02x",digest[i]);
    assert(snprintf(path,sizeof(path),"%s/%s.kv",directory,name)<(int)sizeof(path)&&!unlink(path));
    assert(snprintf(path,sizeof(path),"%s/.lie-prefix.lock",directory)<(int)sizeof(path)&&!unlink(path));
    assert(!rmdir(directory));
}
int main(void){
    char root[]="/tmp/lie-state-aux-XXXXXX";assert(mkdtemp(root));lie_error e={0};unsigned index=0;
    lie_kvc_limits limits=lie_kvc_default_limits(1u<<20);
    const lie_kvc_qwen_geometry g={4,1,2,1,4,3,2,3,2,5,2,6,32};
    const uint32_t counts[]={0,1,3,4,8};
    for(unsigned k=0;k<5;++k){
        lie_kvc_qwen_frontier f={.context_tokens=64,.prefill_tokens=8,.graph_capacity=64,.tokens=9,.mtp_tokens=counts[k]};
        lie_state_layout l;assert(lie_kvc_qwen_mtp_state_plan(&g,&f,42,5,4,4,7,&l,&e)==LIE_OK);
        uint64_t n,base,aux;assert(lie_state_validate(&l,&n)&&lie_state_kvc_parts(&l,&base,&aux));
        unsigned char *p=calloc(1,(size_t)n);assert(p);
        for(unsigned i=0;i<l.section_count;++i){const lie_state_section *s=&l.sections[i];
            if(s->role==LIE_STATE_TOKENS){for(unsigned j=0;j<f.tokens;++j){int32_t id=(int32_t)j+1;memcpy(p+s->offset+4*j,&id,4);}}
            else if(s->dtype==LIE_STATE_F32||s->dtype==LIE_STATE_F16)memset(p+s->offset,17+i,(size_t)s->bytes);
        }
        lie_kvc_qwen_mtp_controller c={.retry_tokens=3,.probe_depth=2,.explored_depth=4,.probe_delay=16,.failed_depths=1};
        for(unsigned i=0;i<7;++i){c.successes[i]=1.5f+i;c.failures[i]=0.5f;}
        assert(lie_kvc_qwen_mtp_state_finish(&g,&l,31,&c,p,(size_t)n,&limits,&e)==LIE_OK);
        assert(lie_kvc_qwen_state_check(&g,&l,31,(lie_kvc_span){p,(size_t)n},&limits,&e)==LIE_OK);
        lie_kvc_qwen_layout parsed;assert(lie_kvc_qwen_decode((lie_kvc_span){p,(size_t)base},&g,&limits,&parsed,&e)==LIE_OK&&parsed.frontier.mtp_tokens==counts[k]);
        lie_kvc_qwen_mtp_controller got;assert(lie_kvc_qwen_mtp_state_controller(&l,(lie_kvc_span){p,(size_t)n},&got,&e)==LIE_OK&&!memcmp(&c,&got,sizeof(c)));
        unsigned char saved[100];memcpy(saved,p+base,100);
        p[base+27]=0x7f;p[base+26]=0xc0; /* NaN success history. */
        assert(lie_kvc_qwen_state_check(&g,&l,31,(lie_kvc_span){p,(size_t)n},&limits,&e)==LIE_INVALID);
        memcpy(p+base,saved,100);
        c.probe_depth=8;assert(lie_kvc_qwen_mtp_state_finish(&g,&l,31,&c,p,(size_t)n,&limits,&e)==LIE_INVALID&&!memcmp(saved,p+base,100));c.probe_depth=2;
        lie_state_layout bad=l;bad.model_data[3]=9;assert(lie_kvc_qwen_state_check(&g,&bad,31,(lie_kvc_span){p,(size_t)n},&limits,&e)==LIE_INVALID);
        bad=l;bad.format=LIE_STATE_KVC;assert(!lie_state_validate(&bad,&n));
        lie_kvc_limits small=lie_kvc_default_limits(base);
        assert(lie_kvc_qwen_state_check(&g,&l,31,(lie_kvc_span){p,(size_t)(base+aux)},&small,&e)==LIE_RESOURCE_LIMIT);
        roundtrip(root,index++,&l,p,(size_t)(base+aux));free(p);
    }
    /* Two unrelated synthetic model schemas use the same core auxiliary path. */
    for(unsigned family=0;family<2;++family){
        lie_state_layout l={.abi_version=LIE_STATE_ABI,.representation_version=100+family,.domain=99,
            .token_count=2,.context_tokens=16,.prefill_chunk=2,.format=LIE_STATE_KVC_AUX,.model_id=250,.quant_bits=8};
        uint64_t dims[]={2,3};assert(lie_state_add(&l,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,dims));
        assert(lie_state_add(&l,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,dims));
        dims[0]=3+family;assert(lie_state_add(&l,LIE_STATE_AUXILIARY,0,LIE_STATE_U8,1,dims));
        dims[0]=5+family;assert(lie_state_add(&l,LIE_STATE_MODEL_COMPONENT+100,0,LIE_STATE_U8,1,dims));
        uint64_t n;assert(lie_state_validate(&l,&n));unsigned char *p=calloc(1,(size_t)n);assert(p);int32_t ids[]={1,2};memcpy(p,ids,sizeof(ids));
        roundtrip(root,index++,&l,p,(size_t)n);free(p);
    }
    /* Multimodal positions require an independently prepared expected layout;
     * equal text token IDs never establish image identity. */
    lie_kvc_qwen_frontier vf={.context_tokens=64,.prefill_tokens=8,.graph_capacity=64,.tokens=9,.mrope_delta=-2};
    lie_state_layout vl;assert(lie_kvc_qwen_state_plan(&g,&vf,42,5,4,&vl,&e)==LIE_OK);
    uint64_t vn;assert(lie_state_validate(&vl,&vn));unsigned char *vp=calloc(1,(size_t)vn);assert(vp);
    size_t position_offset=0;unsigned char positions[9*16]={0};
    for(unsigned i=0;i<9;++i){uint32_t values[]={i,i/3,i%3,0};
        for(unsigned j=0;j<4;++j)for(unsigned b=0;b<4;++b)positions[16*i+4*j+b]=(unsigned char)(values[j]>>(8*b));
    }
    for(unsigned i=0;i<vl.section_count;++i){const lie_state_section *s=&vl.sections[i];
        if(s->role==LIE_STATE_TOKENS)for(unsigned j=0;j<9;++j){int32_t id=(int32_t)j+1;memcpy(vp+s->offset+4*j,&id,4);}
        if(s->role==LIE_KVC_QWEN_POSITIONS)position_offset=(size_t)s->offset;
    }
    lie_kvc_span ps={positions,sizeof(positions)},payload={vp,(size_t)vn};
    assert(lie_kvc_qwen_state_finish(&g,&vl,31,vp,(size_t)vn,&limits,&e)==LIE_INVALID&&vp[0]==0);
    assert(lie_kvc_qwen_state_finish_positions(&g,&vl,31,ps,vp,(size_t)vn,&limits,&e)==LIE_OK);
    assert(lie_kvc_qwen_state_check_positions(&g,&vl,31,payload,ps,&limits,&e)==LIE_OK);
    assert(lie_kvc_qwen_state_check(&g,&vl,31,payload,&limits,&e)==LIE_INVALID);
    positions[16]^=1;assert(lie_kvc_qwen_state_check_positions(&g,&vl,31,payload,ps,&limits,&e)==LIE_INVALID);positions[16]^=1;
    positions[12]=1;assert(lie_kvc_qwen_state_finish_positions(&g,&vl,31,ps,vp,(size_t)vn,&limits,&e)==LIE_INVALID);positions[12]=0;
    positions[3]=128;assert(lie_kvc_qwen_state_check_positions(&g,&vl,31,payload,ps,&limits,&e)==LIE_INVALID);positions[3]=0;
    assert(lie_kvc_qwen_state_check_positions(&g,&vl,31,payload,(lie_kvc_span){positions,sizeof(positions)-1},&limits,&e)==LIE_INVALID);
    unsigned char *overlap=malloc((size_t)vn),*before=malloc((size_t)vn);assert(overlap&&before);
    memcpy(overlap,vp,(size_t)vn);memcpy(overlap+52,positions,sizeof(positions));memcpy(before,overlap,(size_t)vn);
    assert(lie_kvc_qwen_state_finish_positions(&g,&vl,31,(lie_kvc_span){overlap+52,sizeof(positions)},overlap,(size_t)vn,&limits,&e)==LIE_INVALID);
    assert(strstr(e.message,"overlaps")&&!memcmp(before,overlap,(size_t)vn));free(before);free(overlap);
    assert(lie_kvc_qwen_state_finish_positions(&g,&vl,31,(lie_kvc_span){vp+position_offset,sizeof(positions)},vp,(size_t)vn,&limits,&e)==LIE_OK);
    lie_kvc_qwen_layout decoded;assert(lie_kvc_qwen_decode(payload,&g,&limits,&decoded,&e)==LIE_OK&&decoded.frontier.mrope_delta==-2&&!decoded.text_positions);
    roundtrip(root,index++,&vl,vp,(size_t)vn);free(vp);
    assert(writes==16&&!rmdir(root));puts("Typed KVC auxiliary and multimodal position RAM/SSD state: PASS (NOT-INFERENCE)");return 0;
}
