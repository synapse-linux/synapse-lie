// SPDX-License-Identifier: MIT
// Benchmark-only direct upstream API binding. Never linked into the server.
// Shares independently fetched, unchanged Gufo numerical archives with LIE;
// this compares call paths/batching, not independent numerical engines.
#include "lie/executor.h"
#include "lie/prefill.h"
#include "src/models/qwen38_flash_next/engine.hpp"
#include "src/models/qwen/chat_template.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <memory>
#include <string_view>
#include <vector>

#ifndef LIE_BENCH_WIDTH
#define LIE_BENCH_WIDTH 1
#endif
static unsigned reference_width=LIE_BENCH_WIDTH;
extern "C" void lie_bench_reference_width(unsigned width) { reference_width=width; }
namespace qfn=gufo::models::qwen38_flash_next;
struct lie_model { std::shared_ptr<qfn::Model> model; };
struct lie_sequence {
    std::shared_ptr<qfn::Model> model;
    std::vector<std::unique_ptr<qfn::Session>> sessions;
    std::vector<gufo::sampling::SamplerState> samplers;
    bool started=false,stopped=false;
};
extern "C" void lie_gufo_quiesce_or_exit(void) noexcept;
extern "C" lie_status lie_gufo_device_validate(lie_error *) noexcept;
namespace {
lie_status fail(lie_error *e,const char *s) { if(e)std::snprintf(e->message,sizeof(e->message),"%s",s);return LIE_BACKEND_FAILED; }
template<class F> lie_status protect(lie_error *e,F f) {
    try { return f(); } catch(const std::exception &x) {lie_gufo_quiesce_or_exit();return fail(e,x.what());}
}
}
extern "C" const char *lie_backend_name(void) {return reference_width==1?"gufo-direct-c1-reference":"gufo-direct-c2-batch-reference";}
extern "C" const char *lie_backend_source_pin(void) {return "f783fedb9bea2ec7de941f6da4e02f4a4596b29e";}
extern "C" const char *lie_backend_ownership(void) {return "delegated";}
extern "C" const char *lie_backend_dense_sampling(void) {return "gufo";}
extern "C" int lie_backend_is_synthetic(void) {return 0;}
extern "C" lie_status lie_sequence_configure_prefill(lie_sequence *,uint32_t,
    const unsigned char[32],lie_error *e) {
    if(e)std::snprintf(e->message,sizeof(e->message),"direct reference has no shared-core cache namespace");
    return LIE_UNSUPPORTED;
}
extern "C" lie_status lie_backend_open(const char *path,const lie_model_options *o,lie_model **out,lie_error *e) {
    if(!path||!o||!out||o->abi_version!=LIE_EXECUTOR_ABI||o->struct_bytes!=sizeof(*o))return LIE_INVALID;
    if(o->rope_profile!=LIE_ROPE_NATIVE){
        if(e)std::snprintf(e->message,sizeof(e->message),"scaled RoPE is not available in this direct reference");
        return LIE_UNSUPPORTED;
    }
    const auto status = lie_gufo_device_validate(e);
    if (status != LIE_OK) return status;
    return protect(e,[&] { qfn::ModelOptions options;options.max_context=o->context_tokens;
#ifdef LIE_GUFO_STATE_ACCESS
        options.lie_prefill_capacity=o->prefill_chunk_tokens;
#else
        if(o->prefill_chunk_tokens>2048)return fail(e,"reference provider prefill capacity unavailable");
#endif
        options.decode_concurrency=reference_width;options.max_draft_tokens=1;
        std::string error;auto model=qfn::Model::Load(path,options,&error);
        if(!model)return fail(e,error.c_str());
        *out=new lie_model{std::move(model)};return LIE_OK; });
}
extern "C" lie_status lie_model_get_info(lie_model *m,lie_model_info *out,lie_error *) {
    *out={LIE_EXECUTOR_ABI,m->model->MaxContext(),m->model->VocabSize(),m->model->PrefillCapacity(),reference_width,0,
        m->model->ResidentBytes(),m->model->SessionBytes(gufo::core::SessionMode::kAutoregressive,m->model->MaxContext()),m->model->DeferredScratchBytes()};return LIE_OK;
}
extern "C" lie_status lie_model_attention_dispatch_snapshot(lie_model *m,
    lie_attention_dispatch_info *out,lie_error *e) {
    if(!m||!out||out->abi_version!=LIE_ATTENTION_DISPATCH_ABI||out->struct_bytes!=sizeof(*out)){
        if(e)std::snprintf(e->message,sizeof(e->message),"invalid reference attention dispatch snapshot");
        return LIE_INVALID;
    }
    lie_attention_dispatch_info_init(out);return LIE_OK;
}
extern "C" lie_status lie_model_chat_tokens(lie_model *m,const lie_chat_message *input,size_t count,int32_t *out,size_t cap,size_t *needed,lie_error *e) {
    return protect(e,[&] { if(count!=1||input[0].role!=LIE_CHAT_USER)return fail(e,"reference expects one user message");
        gufo::tokenization::ChatMessage msg(gufo::tokenization::ChatRole::kUser,std::string(input[0].content,input[0].bytes));
        gufo::tokenization::ChatTemplateOptions options;options.enable_thinking=false;
        options.max_output_bytes=gufo::tokenization::RenderedPromptBoundBytes(m->model->MaxContext());
        std::string error;auto ids=gufo::tokenization::QwenChatTemplate::RenderAndTokenize(m->model->tokenizer(),{&msg,1},{},options,&error);
        if(!ids)return fail(e,error.c_str());
        *needed=ids->size();if(*needed>cap)return LIE_BUFFER_SMALL;
        std::copy(ids->begin(),ids->end(),out);return LIE_OK; });
}
extern "C" lie_status lie_model_tokenize(lie_model *m,const char *text,size_t bytes,
    int32_t *out,size_t capacity,size_t *required,lie_error *e) {
    if(!m||!text||!required||(!out&&capacity)||bytes>LIE_CHAT_BODY_BYTES)return LIE_INVALID;
    return protect(e,[&] {
        auto tokens=m->model->Tokenize(std::string_view(text,bytes));
        *required=tokens.size();if(tokens.size()>capacity)return LIE_BUFFER_SMALL;
        if(!tokens.empty())std::copy(tokens.begin(),tokens.end(),out);
        return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_create(lie_model *m,lie_sequence **out,lie_error *e) {
    return protect(e,[&] { auto s=std::make_unique<lie_sequence>();s->model=m->model;
        for(unsigned i=0;i<reference_width;++i){std::string error;auto session=m->model->CreateSession(gufo::core::SessionMode::kAutoregressive,m->model->MaxContext(),&error);
            if(!session)return fail(e,error.c_str());
            s->sessions.push_back(std::move(session));s->samplers.emplace_back();}
        *out=s.release();return LIE_OK; });
}
extern "C" lie_status lie_sequence_prefill(lie_sequence *s,const int32_t *p,size_t n,lie_error *e) {
    return protect(e,[&] {for(auto &session:s->sessions){std::string error;if(!session->Sync({p,n},&error))return fail(e,error.c_str());}return LIE_OK;});
}
extern "C" lie_status lie_sequence_decode(lie_sequence *s,lie_decode_result *out,lie_error *e) {
    return protect(e,[&] {
        if(s->stopped)return fail(e,"reference stopped");
        if(!s->started){for(unsigned i=0;i<reference_width;++i){auto ids=s->sessions[i]->Tokens();std::vector<gufo::sampling::TokenId> history(ids.begin(),ids.end());s->samplers[i].ResetHistory(history);}s->started=true;}
        std::vector<qfn::Session::DecodeResult> results(reference_width);
        std::vector<qfn::Session::BatchOutcome> outcomes(reference_width);
        std::string error;
        if(reference_width==1){if(!s->sessions[0]->DecodeStep(1,s->samplers[0],&results[0],&error,true))return fail(e,error.c_str());}
        else {std::vector<qfn::Session::DecodeRequest> requests;
            for(unsigned i=0;i<reference_width;++i)requests.push_back({s->sessions[i].get(),1,&s->samplers[i],&results[i],true,&outcomes[i]});
            if(!qfn::Session::DecodeBatch(requests,&error))return fail(e,error.c_str());
            for(unsigned i=0;i<reference_width;++i)if(!outcomes[i].completed||results[i].tokens!=results[0].tokens||results[i].stop!=results[0].stop||s->sessions[i]->Position()!=s->sessions[0]->Position())return fail(e,"batch peer completion/token mismatch");
        }
        auto &d=results[0];if(d.tokens.size()>1)return fail(e,"reference AR width");s->stopped=d.stop;
        *out={d.tokens.empty()?-1:d.tokens.front(),static_cast<uint32_t>(d.tokens.size()),d.stop?1u:0u,s->sessions[0]->Position()};return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_logits(lie_sequence *s,float *out,size_t cap,size_t *needed,lie_error *e) {
    auto row=s->sessions[0]->Logits();*needed=row.size();if(*needed>cap)return LIE_BUFFER_SMALL;
    for(auto &session:s->sessions){auto other=session->Logits();if(other.size()!=row.size()||!std::equal(row.begin(),row.end(),other.begin()))return fail(e,"batch peer frontier mismatch");}
    std::copy(row.begin(),row.end(),out);return LIE_OK;
}
extern "C" lie_status lie_sequence_close(lie_sequence **s,lie_error *) {delete *s;*s=nullptr;return LIE_OK;}
extern "C" lie_status lie_model_close(lie_model **m,lie_error *) {delete *m;*m=nullptr;return LIE_OK;}
