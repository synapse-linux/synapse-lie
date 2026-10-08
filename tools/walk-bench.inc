/* SPDX-License-Identifier: MIT */
/* Current C17 adaptation of the first-party Q2 raw-corpus/DS4 advancing method.
 * No DS4 code or historical provider capsule is imported. Multi-user clients
 * continue to submit independent jobs to the production shared core. */
static bool walk_corpus(lie_model *m,const struct config *c,unsigned vocab,
                        struct prompt *p,FILE *f,lie_error *e) {
    int fd=open(c->corpus,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    if(fd<0){snprintf(e->message,sizeof(e->message),"cannot open raw corpus");return false;}
    struct stat before,after;char *text=NULL;bool ok=false;size_t bytes=0,at=0;
    if(fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_size<=0||
       (uint64_t)before.st_size>LIE_CHAT_BODY_BYTES)goto done;
    bytes=(size_t)before.st_size;text=malloc(bytes+1);if(!text)goto done;
    while(at<bytes){
        ssize_t got=read(fd,text+at,bytes-at);
        if(got<0&&errno==EINTR&&!interrupted)continue;
        if(got<=0||interrupted)goto done;
        at+=(size_t)got;
    }
    if(fstat(fd,&after)||before.st_dev!=after.st_dev||before.st_ino!=after.st_ino||
       before.st_size!=after.st_size||before.st_mtim.tv_sec!=after.st_mtim.tv_sec||
       before.st_mtim.tv_nsec!=after.st_mtim.tv_nsec||before.st_ctim.tv_sec!=after.st_ctim.tv_sec||
       before.st_ctim.tv_nsec!=after.st_ctim.tv_nsec||!lie_utf8_valid(text,bytes,false))goto done;
    text[bytes]=0;
    size_t needed=0;lie_status rc=lie_model_tokenize(m,text,bytes,NULL,0,&needed,e);
    if((rc!=LIE_BUFFER_SMALL&&rc!=LIE_OK)||!needed||needed>LIE_CHAT_BODY_BYTES)goto done;
    p->ids=malloc(needed*sizeof(*p->ids));if(!p->ids)goto done;
    rc=lie_model_tokenize(m,text,bytes,p->ids,needed,&p->n,e);
    if(rc!=LIE_OK||p->n!=needed||p->n<c->sizes[c->size_count-1])goto done;
    for(size_t i=0;i<p->n;++i)if(p->ids[i]<0||(unsigned)p->ids[i]>=vocab)goto done;
    /* Retain each used physical ID once, even for 512 advancing frontiers.
     * Whole-source tokenization remains separately counted and identified. */
    p->n=c->sizes[c->size_count-1];
    char source_hash[65],token_hash[65];
    /* Supported GPU platforms are little-endian; the output contract records
     * exact I32-LE IDs, matching the native report's explicit LE hashing. */
    uint32_t endian=1;if(*(unsigned char *)&endian!=1)goto done;
    if(!hash(text,bytes,source_hash)||!hash(p->ids,p->n*sizeof(*p->ids),token_hash))goto done;
    json_object *j=event("corpus");str(j,"tokenization","raw-utf8-no-chat-template");
    str(j,"source_text_sha256",source_hash);num(j,"source_bytes",bytes);
    num(j,"tokenized_source_tokens",needed);
    num(j,"prompt_tokens",p->n);str(j,"physical_ids_sha256",token_hash);
    json_object_object_add(j,"physical_ids",ids_json(p->ids,p->n));
    ok=emit(f,j);
done:
    if(close(fd))ok=false;
    free(text);
    if(!ok){free(p->ids);p->ids=NULL;p->n=0;
        if(!e->message[0])snprintf(e->message,sizeof(e->message),"invalid, changed or insufficient raw corpus");}
    return ok;
}

static void walk_state_dispose(struct walk_checkpoint *walk) {
#ifndef LIE_BENCH_REFERENCE
    lie_state_destroy(&walk->state);
#else
    (void)walk;
#endif
}

static int walk_main(struct config *c) {
    if(c->depths_given||(c->users_given&&(c->user_count!=1||c->users[0]!=1)))return 2;
    if(!c->warmups_given)c->warmups=0;
    if(!c->sizes_given){
        c->size_count=131072u/c->pp;
        if(!c->size_count||c->size_count>MAX_POINTS)return 2;
        for(unsigned i=0;i<c->size_count;++i)c->sizes[i]=(i+1)*c->pp;
    }
    if(!c->corpus||!*c->corpus||!c->restore||
       (strcmp(c->restore,"auto")&&strcmp(c->restore,"replay"))||
       (uint64_t)c->sizes[c->size_count-1]+c->tg>c->walk_context)return 2;
    for(unsigned i=0;i<c->size_count;++i)
        if(c->sizes[i]!=(i+1)*c->pp)return 2;
    c->context=c->walk_context;
    int fd=open(c->output,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0){perror("exclusive walk output");return 1;}
    FILE *f=fdopen(fd,"w");if(!f){close(fd);return 1;}
    lie_model *m=NULL;lie_model_info info={0};lie_error e={{0}};struct prompt corpus={0};
    struct walk_checkpoint walk={0};struct witness *w=calloc(c->size_count,sizeof(*w));
    float *logits=NULL;int code=1;EVP_MD_CTX *prefix=NULL,*digest_ctx=NULL;
    json_object *id=identity(c);
    str(id,"scope","one raw corpus; advancing C1 logical prefix; PP times appended tokens only; checkpoint/replay excluded and separately recorded");
    num(id,"context_capacity",c->context);str(id,"rope_scaling",lie_rope_profile_name(c->rope));
    str(id,"restore_policy",c->restore);num(id,"snapshot_budget_bytes",1073741824);
    num(id,"frontier_count",c->size_count);
    if(!emit(f,id)||!w||!open_model(c,c->context,1,&m,&info,f,&e)||
       !walk_corpus(m,c,info.vocab_tokens,&corpus,f,&e))goto done;
    logits=malloc((size_t)info.vocab_tokens*sizeof(*logits));if(!logits)goto done;
    prefix=EVP_MD_CTX_new();digest_ctx=EVP_MD_CTX_new();
    if(!prefix||!digest_ctx||!EVP_DigestInit_ex(prefix,EVP_sha256(),NULL))goto done;
    for(unsigned point=0;point<c->size_count;++point){
        w[point].ids=calloc(c->tg,sizeof(*w[point].ids));if(!w[point].ids)goto done;
        unsigned depth=point*c->pp,n=c->sizes[point];char digest[65];
        unsigned char bytes[32];unsigned used=0;
        if(!EVP_DigestUpdate(prefix,corpus.ids+depth,(size_t)c->pp*sizeof(*corpus.ids))||
           !EVP_MD_CTX_copy_ex(digest_ctx,prefix)||
           !EVP_DigestFinal_ex(digest_ctx,bytes,&used)||used!=32)goto done;
        for(unsigned k=0;k<32;++k)snprintf(digest+2*k,3,"%02x",bytes[k]);
        json_object *input=event("input");num(input,"point",point);num(input,"depth",depth);num(input,"users",1);
        num(input,"context_capacity",c->context);num(input,"target_prompt_tokens",n);num(input,"prompt_tokens",n);
        str(input,"physical_ids_sha256",digest);str(input,"physical_ids_source","corpus-prefix");
        if(!emit(f,input))goto done;
    }
    for(unsigned rep=0;rep<c->warmups+c->repetitions;++rep){
        if(lie_sequence_create(m,&walk.sequence,&e)!=LIE_OK)goto done;
        for(unsigned point=0;point<c->size_count;++point){
            struct prompt p={corpus.ids,c->sizes[point]};unsigned depth=point*c->pp;
            walk.capture=point+1<c->size_count;
            if(!sample(m,&p,depth,1,point,rep,rep<c->warmups,c,info.vocab_tokens,
                       &w[point],&walk,f,&e))goto done;
            if(!walk.capture)continue;
            uint64_t begin=ns(),retained=0;const char *method="replay";
            if(!begin||lie_sequence_create(m,&walk.sequence,&e)!=LIE_OK)goto done;
#ifndef LIE_BENCH_REFERENCE
            if(walk.state){
                retained=lie_state_bytes(walk.state);method="snapshot";
                if(lie_state_restore(walk.sequence,walk.state,&e)!=LIE_OK)goto done;
            }else
#endif
            if(!prefill(walk.sequence,&p,0,p.n,c->chunk,&e))goto done;
            char restored[65];
            if(!frontier(walk.sequence,logits,info.vocab_tokens,restored,&e)||
               strcmp(restored,w[point].pp)){snprintf(e.message,sizeof(e.message),"restored/replayed prefix frontier differs");goto done;}
            walk_state_dispose(&walk);uint64_t end=ns();if(end<=begin)goto done;
            json_object *row=event("walk_restore");num(row,"rep",rep);num(row,"point",point+1);
            num(row,"tokens",p.n);str(row,"method",method);num(row,"retained_bytes",retained);
            str(row,"prefill_logits_sha256",restored);num(row,"begin_monotonic_ns",begin);num(row,"end_monotonic_ns",end);
            num(row,"elapsed_ns",end-begin);
            if(!emit(f,row))goto done;
        }
    }
    code=0;
done:
    if(walk.sequence&&lie_sequence_close(&walk.sequence,&e)!=LIE_OK)code=1;
    walk_state_dispose(&walk);
    if(m&&lie_model_close(&m,&e)!=LIE_OK)code=1;
    if(w){for(unsigned i=0;i<c->size_count;++i)free(w[i].ids);free(w);}
    EVP_MD_CTX_free(prefix);EVP_MD_CTX_free(digest_ctx);
    free(logits);free(corpus.ids);
    json_object *last=event(code?"failed":"complete");num(last,"exit_code",code);if(code)str(last,"error",e.message);
    bool written=emit(f,last);if(fclose(f)||!written)code=1;
    if(!code&&c->graphs)code=lie_bench_graphs(c->output,c->graphs,c->compare);
    return code;
}
