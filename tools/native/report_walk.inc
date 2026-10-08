/* SPDX-License-Identifier: MIT */
/* Physical corpus stored once. Prefix hashes advance in O(corpus tokens),
 * never by copying every growing prefix into a JSON array. */
static const char *direct_contract(json_object *id) {
  return eqs(id,"suite","ds4-walk") ? "ds4-walk-v1" :
         eqs(id,"suite","fresh") ? "full-prefill-v1" : "legacy-incremental-v1";
}
static bool walk_hash_string(json_object *row,const char *key) {
  const char *s=nb_string(row,key);
  return strlen(s)==64 && strspn(s,"0123456789abcdef")==64;
}
static bool walk_prefix_inputs(json_object *corpus,json_object *inputs,int64_t pp,
                               int64_t context) {
  EVP_MD_CTX *ctx=EVP_MD_CTX_new(),*copy=EVP_MD_CTX_new();
  bool ok=ctx&&copy&&EVP_DigestInit_ex(ctx,EVP_sha256(),NULL);
  json_object *tokens=nb_get(corpus,"physical_ids");size_t previous=0;
  for(size_t point=0;ok&&point<json_object_array_length(inputs);++point){
    json_object *in=json_object_array_get_idx(inputs,point);
    size_t end=(point+1)*(size_t)pp;
    ok=nb_count(in,"point",(int64_t)point,(int64_t)point,NULL)&&
       nb_count(in,"users",1,1,NULL)&&
       nb_count(in,"depth",(int64_t)previous,(int64_t)previous,NULL)&&
       nb_count(in,"target_prompt_tokens",(int64_t)end,(int64_t)end,NULL)&&
       nb_count(in,"prompt_tokens",(int64_t)end,(int64_t)end,NULL)&&
       nb_count(in,"context_capacity",context,context,NULL)&&
       eqs(in,"physical_ids_source","corpus-prefix")&&!nb_get(in,"physical_ids")&&
       end<=json_object_array_length(tokens);
    for(size_t i=previous;ok&&i<end;++i){
      uint32_t id=(uint32_t)json_object_get_int64(json_object_array_get_idx(tokens,i));
      unsigned char le[4];for(unsigned k=0;k<4;++k)le[k]=(unsigned char)(id>>(8*k));
      ok=EVP_DigestUpdate(ctx,le,sizeof(le));
    }
    unsigned char bytes[32];unsigned count=0;char digest[65];
    ok=ok&&EVP_MD_CTX_copy_ex(copy,ctx)&&EVP_DigestFinal_ex(copy,bytes,&count)&&count==32;
    if(ok){for(unsigned k=0;k<32;++k)snprintf(digest+2*k,3,"%02x",bytes[k]);
      ok=!strcmp(digest,nb_string(in,"physical_ids_sha256"));}
    previous=end;
  }
  ok=ok&&previous==json_object_array_length(tokens);
  EVP_MD_CTX_free(ctx);EVP_MD_CTX_free(copy);return ok;
}
static bool walk_evidence(json_object *rows,json_object *id,json_object *inputs,
                           size_t reps,nb_error *e) {
  size_t points=json_object_array_length(inputs),seen=0,begins=0;
  json_object *corpus=NULL,*last=NULL,*begin_row=NULL,*restore=NULL;
  int64_t pp=nb_number(id,"pp_target"),context=nb_number(id,"context_capacity");
  CHECK(points&&points<=512&&nb_count(id,"frontier_count",(int64_t)points,(int64_t)points,NULL)&&
        nb_count(id,"pp_target",1,8192,NULL)&&nb_count(id,"context_capacity",128,LIE_CONTEXT_LIMIT,NULL)&&
        nb_count(id,"snapshot_budget_bytes",1073741824,1073741824,NULL)&&
        eqs(id,"measurement_contract","ds4-walk-v1")&&
        (eqs(id,"rope_scaling","native")||eqs(id,"rope_scaling","yarn2")||eqs(id,"rope_scaling","yarn4"))&&
        (eqs(id,"restore_policy","auto")||eqs(id,"restore_policy","replay")),
        "Invalid DS4 walk identity");
  for(size_t i=1;i<json_object_array_length(rows);++i){
    json_object *row=json_object_array_get_idx(rows,i);
    if(eqs(row,"event","corpus")){
      CHECK(!corpus&&!seen&&ids(row)&&eqs(row,"tokenization","raw-utf8-no-chat-template")&&
            nb_count(row,"source_bytes",1,LIE_CHAT_BODY_BYTES,NULL)&&
            nb_count(row,"tokenized_source_tokens",nb_number(row,"prompt_tokens"),LIE_CHAT_BODY_BYTES,NULL)&&
            walk_hash_string(row,"source_text_sha256"),"Invalid DS4 physical corpus");
      corpus=row;
    }else if(eqs(row,"event","sample_begin")){
      CHECK(corpus&&!begin_row&&seen<points*reps&&
            nb_count(row,"point",(int64_t)(seen%points),(int64_t)(seen%points),NULL)&&
            nb_count(row,"rep",(int64_t)(seen/points),(int64_t)(seen/points),NULL)&&
            nb_count(row,"users",1,1,NULL),"Missing or reordered DS4 sample begin");
      begin_row=row;++begins;
    }else if(eqs(row,"event","sample")){
      size_t point=seen%points;int64_t rep=(int64_t)(seen/points);
      CHECK(begin_row&&seen<points*reps&&nb_count(row,"point",(int64_t)point,(int64_t)point,NULL)&&
            nb_count(row,"rep",rep,rep,NULL)&&
            nb_number(begin_row,"monotonic_ns")==nb_number(row,"sample_begin_monotonic_ns")&&
            nb_number(begin_row,"wall_time_ns")==nb_number(row,"sample_begin_wall_time_ns")&&
            nb_same(begin_row,row,"depth")&&nb_same(begin_row,row,"warmup")&&
            direct_phase_bounds(id,row)&&
            walk_hash_string(row,"prefill_logits_sha256")&&walk_hash_string(row,"decode_logits_sha256"),
            "Reordered or unbound DS4 sample");
      if(point){
        CHECK(restore&&nb_number(restore,"end_monotonic_ns")<=nb_number(row,"sample_begin_monotonic_ns"),
              "DS4 prefix restore overlaps measured work");
      }else CHECK(!restore,"Unexpected DS4 initial restore");
      int64_t start=nb_number(row,"checkpoint_begin_monotonic_ns"),end=nb_number(row,"checkpoint_end_monotonic_ns");
      CHECK(nb_count(row,"checkpoint_begin_monotonic_ns",0,INT64_MAX,NULL)&&
            nb_count(row,"checkpoint_end_monotonic_ns",0,INT64_MAX,NULL)&&
            nb_count(row,"checkpoint_ns",0,INT64_MAX,NULL)&&
            nb_number(row,"checkpoint_ns")==end-start&&
            nb_count(row,"checkpoint_bytes",0,1073741824,NULL)&&
            ((!start&&!end)||(nb_number(row,"prefill_end_monotonic_ns")<=start&&start<end&&
                              end<=nb_number(row,"decode_begin_monotonic_ns"))),
            "DS4 checkpoint overlaps prefill/decode or exceeds budget");
      if(point+1==points){
        CHECK(eqs(row,"checkpoint_method","none")&&!start&&!end&&!nb_number(row,"checkpoint_bytes"),
              "Unexpected final DS4 checkpoint");
      }else{
        CHECK((eqs(row,"checkpoint_method","snapshot")&&start&&nb_number(row,"checkpoint_bytes")>0&&
               eqs(id,"restore_policy","auto"))||
              (eqs(row,"checkpoint_method","replay")&&!nb_number(row,"checkpoint_bytes")),
              "Invalid DS4 checkpoint selection");
      }
      last=row;restore=NULL;begin_row=NULL;++seen;
    }else if(eqs(row,"event","walk_restore")){
      CHECK(last&&!begin_row&&!restore&&seen%points&&
            nb_count(row,"point",(int64_t)(seen%points),(int64_t)(seen%points),NULL)&&
            nb_count(row,"rep",(int64_t)(seen/points),(int64_t)(seen/points),NULL)&&
            nb_count(row,"tokens",nb_number(last,"prompt_tokens"),nb_number(last,"prompt_tokens"),NULL)&&
            nb_count(row,"begin_monotonic_ns",nb_number(last,"decode_end_monotonic_ns"),INT64_MAX-1,NULL)&&
            nb_count(row,"end_monotonic_ns",nb_number(row,"begin_monotonic_ns")+1,INT64_MAX,NULL)&&
            nb_count(row,"elapsed_ns",1,INT64_MAX,NULL)&&
            nb_number(row,"elapsed_ns")==nb_number(row,"end_monotonic_ns")-nb_number(row,"begin_monotonic_ns")&&
            nb_same(row,last,"prefill_logits_sha256")&&
            !strcmp(nb_string(row,"method"),nb_string(last,"checkpoint_method"))&&
            nb_count(row,"retained_bytes",nb_number(last,"checkpoint_bytes"),nb_number(last,"checkpoint_bytes"),NULL),
            "Unbound, reordered or invalid DS4 prefix restore");
      restore=row;
    }else{
      CHECK((!seen&&!begin_row&&(eqs(row,"event","model_loaded")||eqs(row,"event","input")))||
            (eqs(row,"event","complete")&&i+1==json_object_array_length(rows)),
            "Unexpected DS4 evidence event");
    }
  }
  CHECK(corpus&&seen==points*reps&&begins==seen&&!restore&&!begin_row&&
        walk_prefix_inputs(corpus,inputs,pp,context),"Missing DS4 work or physical prefix mismatch");
  return true;
bad:
  return false;
}
