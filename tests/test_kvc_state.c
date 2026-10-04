/* SPDX-License-Identifier: MIT */
/* Synthetic completed transfer provider. No model forward or device calls. */
#include "lie/kvc_state.h"
#include "../src/state_codec.h"
#include "../src/state_internal.h"
#include <assert.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <poll.h>
struct lie_sequence {int empty;};
static lie_state_layout shape;
static lie_kvc_span source;
static lie_kvc_qwen_geometry geometry={4,1,2,1,4,3,2,3,2,5,2,6,32};
static lie_kvc_limits limits;
static unsigned writes;
static void wait_store(lie_store *s,lie_store_result *r){
    for(unsigned i=0;i<100&&!lie_store_take(s,r);++i){struct pollfd p={lie_store_fd(s),POLLIN,0};assert(poll(&p,1,100)>=0);}
    assert(r->ticket);
}
lie_status lie_sequence_state_describe(lie_sequence *s,const lie_state_layout *in,lie_state_layout *out,lie_error *e){
    (void)e;if(in&&(!s->empty||!lie_state_layout_equal(in,&shape)))return LIE_INVALID;
    *out=shape;return LIE_OK;
}
lie_status lie_sequence_state_read(lie_sequence *s,const lie_state_layout *l,void *out,size_t n,lie_error *e){
    (void)s;if(n!=source.bytes||!lie_state_layout_equal(l,&shape))return LIE_INVALID;
    memcpy(out,source.data,n);
    return lie_kvc_qwen_state_finish(&geometry,l,31,out,n,&limits,e);
}
lie_status lie_sequence_state_write(lie_sequence *s,const lie_state_layout *l,const void *in,size_t n,lie_error *e){
    lie_status rc=lie_kvc_qwen_state_check(&geometry,l,31,(lie_kvc_span){in,n},&limits,e);
    if(rc==LIE_OK){assert(!memcmp(in,source.data,n));s->empty=0;++writes;}return rc;
}
int main(int argc,char **argv){
    assert(argc==3);limits=lie_kvc_default_limits(32u*1024u*1024u);lie_error e={0};lie_kvc *wire=NULL;
    int input=open(argv[1],O_RDONLY);assert(input>=0&&lie_kvc_read_fd(input,&limits,&wire,&e)==LIE_OK);close(input);
    const lie_kvc_view *v=lie_kvc_get_view(wire);source=v->payload;lie_kvc_qwen_layout q;
    assert(lie_kvc_qwen_decode_record(v,&geometry,&limits,&q,&e)==LIE_OK);
    assert(lie_kvc_qwen_state_plan(&geometry,&q.frontier,42,v->header.model_id,v->header.quant_bits,&shape,&e)==LIE_OK);
    assert(lie_kvc_qwen_state_check(&geometry,&shape,31,source,&limits,&e)==LIE_OK);
    struct lie_sequence producer={0},clone={1};lie_state_layout planned;uint64_t bytes;
    assert(lie_state_plan(&producer,&planned,&bytes,&e)==LIE_OK);
    lie_state *state=NULL;assert(lie_state_capture(&producer,&planned,bytes-1,&state,&e)==LIE_RESOURCE_LIMIT&&!state);
    assert(lie_state_capture(&producer,&planned,bytes,&state,&e)==LIE_OK);
    assert(lie_state_bytes(state)==bytes&&lie_state_restore_workspace(state)==0);
    assert(!lie_state_compress(&state,UINT64_MAX)); /* Keep exact DS4 representation. */
    assert(lie_state_restore(&clone,state,&e)==LIE_OK&&writes==1);
    assert(lie_state_restore(&clone,state,&e)==LIE_INVALID&&writes==1);
    lie_state_identity id={{1}},wrong={{2}};
    lie_cache_metadata m={.text=(const char *)v->text.data,.text_bytes=v->text.bytes,
        .trailer="fixture-extension",.trailer_bytes=17,.reason=LIE_CACHE_COLD,.hits=7,.created_at=1,.last_used=2};
    int fd=open(argv[2],O_RDWR|O_CREAT|O_EXCL,0600);assert(fd>=0);
    atomic_bool cancelled=false;
    assert(lie_state_file_write_ex(fd,&id,state,&m,&cancelled));
    unsigned nt=0,ctx=0;uint64_t disk=0;
    assert(lie_state_file_probe(fd,&id,&disk,&nt,&ctx)&&disk==lie_state_file_bytes_ex(state,&m)&&nt==shape.token_count);
    assert(!lie_state_file_probe(fd,&wrong,&disk,&nt,&ctx));
    assert(!lie_state_file_read(fd,&wrong,42,bytes,&cancelled));
    assert(!lie_state_file_read(fd,&id,42,bytes-1,&cancelled));
    atomic_store(&cancelled,true);assert(!lie_state_file_read(fd,&id,42,bytes,&cancelled));atomic_store(&cancelled,false);
    lie_state *loaded=lie_state_file_read(fd,&id,42,bytes,&cancelled);assert(loaded);
    clone.empty=1;assert(lie_state_restore(&clone,loaded,&e)==LIE_OK&&writes==2);lie_state_destroy(&loaded);
    lie_cache_metadata got;assert(lie_state_file_metadata(fd,&id,64,&got));
    assert(got.hits==7&&got.text_bytes==m.text_bytes&&got.trailer_bytes==m.trailer_bytes&&!memcmp(got.trailer,m.trailer,m.trailer_bytes));lie_cache_metadata_clear(&got);
    assert(lie_state_file_touch(fd,&id,19,999)&&lie_state_file_metadata(fd,&id,64,&got));
    assert(got.hits==19&&got.last_used==999);lie_cache_metadata_clear(&got);
    loaded=lie_state_file_read(fd,&id,43,bytes,&cancelled);assert(loaded);clone.empty=1;
    assert(lie_state_restore(&clone,loaded,&e)==LIE_INVALID&&writes==2);lie_state_destroy(&loaded);
    /* Corruption in text, tensor payload, client extensions, descriptors or
     * identity must never produce an admitted state. Restore original bytes. */
    const uint64_t offsets[]={52,52+v->text.bytes+56,52+v->text.bytes+v->payload.bytes,disk-193,disk-160};
    for(unsigned i=0;i<sizeof(offsets)/sizeof(*offsets);++i){unsigned char b;assert(pread(fd,&b,1,(off_t)offsets[i])==1);
        unsigned char bad=b^1;assert(pwrite(fd,&bad,1,(off_t)offsets[i])==1);
        assert(!lie_state_file_read(fd,&id,42,bytes,&cancelled));assert(pwrite(fd,&b,1,(off_t)offsets[i])==1);}
    assert(lie_state_file_touch(fd,&id,7,2));
    /* The bounded I/O worker publishes real .kv names, supports token lookup,
     * and rebuilds that index after reopening under an independently bound domain. */
    char directory[4096];assert(snprintf(directory,sizeof(directory),"%s-store",argv[2])<(int)sizeof(directory));
    lie_store_options options={.directory=directory,.quota_bytes=64u*1024u*1024u,.staging_bytes=32u*1024u*1024u};
    lie_store *store=NULL;assert(lie_store_open(&options,&id,42,&store,&e)==LIE_OK);
    assert(lie_store_write_ex(store,state,&m));lie_store_result result={0};wait_store(store,&result);lie_store_result_release(store,&result);
    lie_store_info info;lie_store_snapshot(store,&info);assert(info.writes==1&&!info.errors&&info.entries==1);
    lie_store_close(&store);assert(!store);
    assert(lie_store_open(&options,&id,43,&store,&e)==LIE_OK);
    assert(lie_store_read(store,lie_state_tokens(state),shape.token_count,shape.prefill_chunk));
    result=(lie_store_result){0};wait_store(store,&result);assert(result.state&&lie_state_description(result.state)->domain==43);
    assert(lie_state_description(result.state)->format==LIE_STATE_KVC);
    lie_store_result_release(store,&result);lie_store_close(&store);assert(!store);
    unsigned char *bad=malloc(source.bytes);assert(bad);memcpy(bad,source.data,source.bytes);
    bad[0]^=1;assert(lie_kvc_qwen_state_check(&geometry,&shape,31,(lie_kvc_span){bad,source.bytes},&limits,&e)==LIE_UNSUPPORTED);
    free(bad);close(fd);lie_state_destroy(&state);lie_kvc_destroy(&wire);
    /* A second, deliberately synthetic component schema exercises generic
     * packed storage without any Qwen roles/geometry or a second model forward. */
    lie_state_layout other={.abi_version=LIE_STATE_ABI,.representation_version=0x54455354u,.domain=9,
        .token_count=2,.context_tokens=16,.prefill_chunk=2,.format=LIE_STATE_KVC,.model_id=250,.quant_bits=8};
    uint64_t dims[]={2,3};assert(lie_state_add(&other,LIE_STATE_TOKENS,0,LIE_STATE_I32,1,dims));
    assert(lie_state_add(&other,LIE_STATE_LOGITS,0,LIE_STATE_F32,1,dims));
    assert(lie_state_add(&other,LIE_STATE_K,0,LIE_STATE_F16,2,dims));
    assert(lie_state_add(&other,LIE_STATE_V,0,LIE_STATE_F16,2,dims));
    assert(lie_state_validate(&other,&bytes));state=lie_state_allocate(&other,32768);assert(state);
    memset(state->payload,0,(size_t)bytes);int32_t ids[]={1,2};memcpy(state->payload,ids,sizeof(ids));
    assert(!lie_state_compress(&state,UINT64_MAX));
    char path[4096];assert(snprintf(path,sizeof(path),"%s-other",argv[2])<(int)sizeof(path));
    fd=open(path,O_RDWR|O_CREAT|O_EXCL,0600);assert(fd>=0&&lie_state_file_write(fd,&id,state,NULL));
    loaded=lie_state_file_read(fd,&id,9,32768,NULL);assert(loaded&&lie_state_layout_equal(lie_state_description(loaded),&other));
    assert(!memcmp(lie_state_tokens(loaded),ids,sizeof(ids)));close(fd);lie_state_destroy(&loaded);lie_state_destroy(&state);
    puts("Direct KVC RAM capture/restore and SSD integrity: PASS (NOT-INFERENCE)");return 0;
}
