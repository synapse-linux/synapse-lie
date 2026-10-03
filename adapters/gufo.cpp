// SPDX-License-Identifier: MIT
// Opt-in transitional adapter; NOT the autonomous LIE backend.
// Whole-model delegation is permitted for bootstrap, then refactored by contract.
// First-party boundary over the unmodified pinned upstream API; no kernels copied.
#ifndef LIE_GUFO_ADAPTER_OPT_IN
#error "Gufo adapter requires explicit opt-in; see docs/BACKEND.md"
#endif
#include "lie/executor.h"
#include "lie/mtp.h"
#include "lie/state.h"
#include "lie/store.h"
#include "gufo_chat.hpp"
#include "src/models/qwen38_flash_next/engine.hpp"
#include "src/models/qwen/chat_template.hpp"
#include "src/core/gguf_reader.hpp"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <exception>
#include <limits>
#include <array>
#include <memory>
#include <cmath>
#include <thread>
#include <vector>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef LIE_GUFO_STATE_ACCESS
#include "gufo-state/access.hpp"
#endif

extern "C" void lie_gufo_quiesce_or_exit(void) noexcept;
extern "C" int lie_gufo_device_identity(char *,size_t) noexcept;
namespace qfn = gufo::models::qwen38_flash_next;
static std::atomic<uint64_t> next_state_domain{1};
struct Runtime {
    std::shared_ptr<qfn::Model> model;
    std::thread::id owner{std::this_thread::get_id()};
    std::uint32_t chunk{}, width{1}, drafts{};
    uint8_t state_quant{};
    bool failed{false};
    uint64_t state_domain{next_state_domain.fetch_add(1)};
    struct StateFile { int fd;struct stat stat; };
    std::vector<StateFile> state_files;
    ~Runtime(){for(auto& f:state_files)::close(f.fd);}
};
struct lie_model { std::shared_ptr<Runtime> runtime; };
struct lie_sequence {
    std::shared_ptr<Runtime> runtime;
    std::unique_ptr<qfn::Session> session;
    gufo::sampling::SamplerState sampler;
    std::atomic<bool> cancelled{false};
    bool stopped{false}, sampling_started{false};
};
namespace {
lie_status error(lie_error *e, lie_status s, const char *message) noexcept {
    if (e) std::snprintf(e->message, sizeof(e->message), "%s", message);
    return s;
}
lie_status owner(const std::shared_ptr<Runtime> &r, lie_error *e, bool closing = false) noexcept {
    if (r->owner != std::this_thread::get_id()) return error(e, LIE_WRONG_OWNER, "device worker ownership violation");
    if (r->failed && !closing) return error(e, LIE_BACKEND_FAILED, "model is poisoned; no retry permitted");
    return LIE_OK;
}
template<class F> lie_status guarded(const std::shared_ptr<Runtime> &r, lie_error *e, F f) noexcept {
    auto status = owner(r, e); if (status != LIE_OK) return status;
    if (e) e->message[0] = 0;
    try { return f(); }
    catch (const std::exception &ex) { r->failed = true; lie_gufo_quiesce_or_exit(); return error(e, LIE_BACKEND_FAILED, ex.what()); }
    catch (...) { r->failed = true; lie_gufo_quiesce_or_exit(); return error(e, LIE_BACKEND_FAILED, "unknown backend exception"); }
}
lie_status failed(const std::shared_ptr<Runtime> &r, lie_error *e, const std::string &message) noexcept {
    r->failed = true; lie_gufo_quiesce_or_exit(); return error(e, LIE_BACKEND_FAILED, message.c_str());
}
}
extern "C" const char *lie_backend_name(void) { return "gufo-embedded-f783fedb"; }
extern "C" int lie_backend_is_synthetic(void) { return 0; }
extern "C" const char *lie_backend_state_format(void) {
#ifdef LIE_DS4_RUNTIME_CACHE
    return "ds4-kvc-payload";
#elif defined(LIE_GUFO_STATE_ACCESS)
    return "lie-aligned-components";
#else
    return "none";
#endif
}
extern "C" int lie_backend_prefix_state_supported(void) {
#ifdef LIE_GUFO_STATE_ACCESS
    return 1;
#else
    return 0;
#endif
}
static lie_status open_model(const char *path, const lie_model_options *o, uint32_t width, const char *mtp_path, uint32_t drafts, lie_model **out, lie_error *e) {
    if (!width || width>LIE_DECODE_MAX_ROWS || !path || !*path || !o || !out || *out || o->abi_version != LIE_EXECUTOR_ABI ||
        o->struct_bytes != sizeof(*o) || !o->context_tokens || o->context_tokens > INT32_MAX ||
        !o->prefill_chunk_tokens || o->prefill_chunk_tokens > 2048)
        return error(e, LIE_INVALID, "invalid model options/output handle");
    try {
        std::string template_error;
        auto metadata = gufo::core::GgufReader::OpenFile(path, &template_error);
        if (!metadata || !gufo::tokenization::QwenChatTemplate::ValidateGgufTemplate(*metadata, &template_error))
            return error(e, LIE_INVALID, template_error.c_str());
        auto r = std::make_shared<Runtime>(); r->chunk = o->prefill_chunk_tokens; r->width=width;r->drafts=mtp_path?drafts:0;
#ifdef LIE_DS4_RUNTIME_CACHE
        const auto* expert=metadata->FindTensor("blk.0.ffn_gate_exps.weight");
        if(!expert)return error(e,LIE_UNSUPPORTED,"KVC requires an identified routed-expert quantization");
        using Q=gufo::core::GgmlType;
        switch(expert->type){
          case Q::kQ2_K:case Q::kIQ2_XXS:r->state_quant=2;break;
          case Q::kQ4_0:case Q::kQ4_1:case Q::kQ4_K:case Q::kIQ4_NL:case Q::kIQ4_XS:r->state_quant=4;break;
          case Q::kQ5_0:case Q::kQ5_1:case Q::kQ5_K:r->state_quant=5;break;
          case Q::kQ6_K:r->state_quant=6;break;
          case Q::kQ8_0:case Q::kQ8_1:case Q::kQ8_K:r->state_quant=8;break;
          default:return error(e,LIE_UNSUPPORTED,"routed-expert quantization has no supported KVC tag");
        }
#endif
        // Retain only descriptors/stat witnesses, not a second mapped payload.
        // No weight hashing unless the shared core explicitly admits SSD.
        for(const auto& region:metadata->GetMappedRegions()){
            int fd=::fcntl(region.file_descriptor,F_DUPFD_CLOEXEC,0);struct stat st{};
            if(fd<0)return error(e,LIE_RESOURCE_LIMIT,"cannot pin model identity file");
            if(::fstat(fd,&st)){::close(fd);return error(e,LIE_INVALID,"cannot inspect model identity file");}
            try{r->state_files.push_back({fd,st});}catch(...){::close(fd);throw;}
        }
        metadata.reset(); // Validation before GPU admission; no model forward on CPU.
        qfn::ModelOptions options;
        options.max_context = o->context_tokens;
        options.decode_concurrency = width;
        options.max_draft_tokens = mtp_path?drafts:1;
        if(mtp_path)options.mtp_model_path=mtp_path;
        std::string message; r->model = qfn::Model::Load(path, options, &message);
        if (!r->model) return error(e, LIE_BACKEND_FAILED, message.c_str());
        auto result = std::make_unique<lie_model>(); result->runtime = std::move(r);
        *out = result.release(); if (e) e->message[0] = 0; return LIE_OK;
    } catch (const std::exception &ex) { return error(e, LIE_BACKEND_FAILED, ex.what()); }
      catch (...) { return error(e, LIE_BACKEND_FAILED, "unknown model load exception"); }
}
extern "C" lie_status lie_gufo_open_batch(const char *p,const lie_model_options *o,uint32_t width,lie_model **m,lie_error *e) {
    return open_model(p,o,width,nullptr,0,m,e);
}
extern "C" lie_status lie_backend_open_mtp(const char *p,const lie_model_options *o,uint32_t width,const char *predictor,uint32_t drafts,lie_model **m,lie_error *e) {
    if(!LIE_MTP)return error(e,LIE_UNSUPPORTED,"MTP was disabled at build time");
    if(!drafts)drafts=qfn::kMaxMtpDraftTokens;
    if(!predictor||!*predictor||drafts>qfn::kMaxMtpDraftTokens||drafts>=LIE_MTP_MAX_OUTPUT)return error(e,LIE_INVALID,"invalid explicit MTP predictor/options");
    return open_model(p,o,width,predictor,drafts,m,e);
}
extern "C" lie_status lie_gufo_open(const char *path,const lie_model_options *o,lie_model **out,lie_error *e) {
    return lie_gufo_open_batch(path,o,1,out,e);
}
extern "C" lie_status lie_model_state_identity(lie_model *m,lie_state_identity *id,uint64_t *domain,lie_error *e){
    if(!m||!id||!domain)return error(e,LIE_INVALID,"invalid SSD identity output");
    return guarded(m->runtime,e,[&]{
        if(!lie_backend_prefix_state_supported())return error(e,LIE_UNSUPPORTED,"component state access required for SSD");
        std::vector<int> fds;
        for(const auto& f:m->runtime->state_files){struct stat st{};const auto& old=f.stat;
            if(::fstat(f.fd,&st)||!st.st_nlink||st.st_dev!=old.st_dev||st.st_ino!=old.st_ino||st.st_size!=old.st_size||
               st.st_mtim.tv_sec!=old.st_mtim.tv_sec||st.st_mtim.tv_nsec!=old.st_mtim.tv_nsec||
               st.st_ctim.tv_sec!=old.st_ctim.tv_sec||st.st_ctim.tv_nsec!=old.st_ctim.tv_nsec)
                return error(e,LIE_INVALID,"model files changed after load; SSD identity refused");
            fds.push_back(f.fd);
        }
        char device[1024],policy[2048];if(!lie_gufo_device_identity(device,sizeof(device)))return error(e,LIE_INVALID,"SSD device identity unavailable");
#ifdef LIE_DS4_RUNTIME_CACHE
        const char *format="ds4-qwen-payload-v2/full-index/eager-pool";
#else
        const char *format="qwen-ar-v1";
#endif
        int n=std::snprintf(policy,sizeof(policy),"gufo-f783fedb/state-access-v1/%s/text-only/thinking-off/context-growth-v1/chunk=%u/width=%u/%s",format,
            m->runtime->chunk,m->runtime->width,device);
        if(n<0||static_cast<size_t>(n)>=sizeof(policy))return error(e,LIE_INVALID,"SSD policy identity overflow");
        auto rc=lie_state_identity_files(fds.data(),fds.size(),policy,id,e);if(rc==LIE_OK)*domain=m->runtime->state_domain;return rc;
    });
}
extern "C" lie_status lie_model_get_info(lie_model *m, lie_model_info *info, lie_error *e) {
    if (!m || !info) return error(e, LIE_INVALID, "invalid model/info");
    return guarded(m->runtime, e, [&] {
        const auto &model = m->runtime->model;
        *info = {LIE_EXECUTOR_ABI, model->MaxContext(), model->VocabSize(), model->PrefillCapacity(), m->runtime->width, model->HasMtp()?1u:0u,
                 model->ResidentBytes(), model->SessionBytes(model->HasMtp()?gufo::core::SessionMode::kSpeculative:gufo::core::SessionMode::kAutoregressive, model->MaxContext()),
                 model->DeferredScratchBytes()};
        return LIE_OK;
    });
}
extern "C" lie_status lie_model_close(lie_model **m, lie_error *e) {
    if (!m || !*m) return error(e, LIE_INVALID, "invalid model handle");
    auto status = owner((*m)->runtime, e, true); if (status != LIE_OK) return status;
    delete *m; *m = nullptr; return LIE_OK; // Sequences pin Runtime independently.
}
extern "C" lie_status lie_model_tokenize(lie_model *m, const char *text, size_t bytes,
    int32_t *out, size_t capacity, size_t *required, lie_error *e) {
    if (!m || !text || !required || (!out && capacity) || bytes > LIE_CHAT_BODY_BYTES)
        return error(e, LIE_INVALID, "invalid/bounded tokenizer input");
    return guarded(m->runtime, e, [&] {
        auto tokens = m->runtime->model->Tokenize(std::string_view(text, bytes));
        *required = tokens.size();
        if (tokens.size() > capacity) return error(e, LIE_BUFFER_SMALL, "token buffer too small");
        if (!tokens.empty()) std::copy(tokens.begin(), tokens.end(), out);
        return LIE_OK;
    });
}
extern "C" lie_status lie_model_chat_anchor(lie_model *m,const int32_t *tokens,size_t n,size_t *out,lie_error *e){
    if(!m||!tokens||!out)return error(e,LIE_INVALID,"invalid chat anchor input");
    return guarded(m->runtime,e,[&]{
        auto user=m->runtime->model->Tokenize("<|im_start|>user\n");
        auto assistant=m->runtime->model->Tokenize("<|im_start|>assistant\n");
        *out=0;
        for(size_t i=0;i<n;++i){
            if(!assistant.empty()&&assistant.size()<=n-i&&std::equal(assistant.begin(),assistant.end(),tokens+i))break;
            if(!user.empty()&&user.size()<=n-i&&std::equal(user.begin(),user.end(),tokens+i))*out=i;
        }
        return LIE_OK;
    });
}
extern "C" lie_status lie_model_token_text(lie_model *m, int32_t token, char *out, size_t capacity,
    size_t *required, lie_error *e) {
    if (!m || !required || (!out && capacity) || token < 0)
        return error(e, LIE_INVALID, "invalid token/output");
    return guarded(m->runtime, e, [&] {
        if (static_cast<uint32_t>(token) >= m->runtime->model->VocabSize()) return error(e, LIE_INVALID, "token out of vocabulary");
        auto text = m->runtime->model->TokenText(token); *required = text.size();
        if (text.size() > capacity) return error(e, LIE_BUFFER_SMALL, "text buffer too small");
        if (!text.empty()) std::memcpy(out, text.data(), text.size());
        return LIE_OK; // Raw token bytes, no NUL terminator or assumed UTF-8 boundary.
    });
}
extern "C" lie_status lie_model_chat_tokens(lie_model *m, const lie_chat_message *messages, size_t count,
    int32_t *out, size_t capacity, size_t *required, lie_error *e) {
    const lie_chat_template input{messages,nullptr,count,nullptr,0,0};
    return lie_model_chat_tokens_ex(m,&input,out,capacity,required,e);
}
extern "C" lie_status lie_model_chat_tokens_ex(lie_model *m, const lie_chat_template *input,
    int32_t *out, size_t capacity, size_t *required, lie_error *e) {
    if (!m || !input || !required || (!out && capacity))
        return error(e,LIE_INVALID,"invalid chat template/output");
    return guarded(m->runtime,e,[&] {
        auto chat=lie_gufo::translate_chat(*input);
        if (!chat) return error(e,LIE_INVALID,"invalid/bounded chat template");
        gufo::tokenization::ChatTemplateOptions options;
        options.enable_thinking = false;
        options.require_tool_call = input->require_tool_call!=0;
        options.max_output_bytes = gufo::tokenization::RenderedPromptBoundBytes(m->runtime->model->MaxContext());
        std::string message;
        auto tokens = gufo::tokenization::QwenChatTemplate::RenderAndTokenize(
            m->runtime->model->tokenizer(), chat->messages, chat->tools, options, &message);
        if (!tokens) return error(e, LIE_INVALID, message.c_str());
        *required = tokens->size();
        if (tokens->size() > capacity) return error(e, LIE_BUFFER_SMALL, "chat token buffer too small");
        if (!tokens->empty()) std::copy(tokens->begin(), tokens->end(), out);
        return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_create(lie_model *m, lie_sequence **out, lie_error *e) {
    if (!m || !out || *out) return error(e, LIE_INVALID, "invalid sequence output");
    return guarded(m->runtime, e, [&] {
        auto result = std::make_unique<lie_sequence>(); result->runtime = m->runtime;
        std::string message;
        result->session = m->runtime->model->CreateSession(m->runtime->model->HasMtp()?gufo::core::SessionMode::kSpeculative:gufo::core::SessionMode::kAutoregressive,
                                                         m->runtime->model->MaxContext(), &message);
        if (!result->session) return failed(m->runtime, e, message);
        *out = result.release(); return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_configure(lie_sequence *s,const lie_generation_options *o,lie_error *e) {
    if (!s || !o) return error(e,LIE_INVALID,"invalid generation controls");
    auto rc=owner(s->runtime,e); if (rc!=LIE_OK) return rc;
    if (o->abi_version!=LIE_GENERATION_ABI || o->struct_bytes!=sizeof(*o) || s->session->Position() ||
        !std::isfinite(o->temperature) || o->temperature<0 || o->temperature>2 ||
        !std::isfinite(o->top_p) || o->top_p<=0 || o->top_p>1 ||
        !std::isfinite(o->frequency_penalty) || std::abs(o->frequency_penalty)>2 ||
        !std::isfinite(o->presence_penalty) || std::abs(o->presence_penalty)>2 || o->seed < -1)
        return error(e,LIE_INVALID,"invalid generation controls or started sequence");
    try {
        gufo::sampling::SamplingConfig c;
        c.temperature=static_cast<float>(o->temperature); c.top_p=static_cast<float>(o->top_p);
        c.frequency_penalty=static_cast<float>(o->frequency_penalty); c.presence_penalty=static_cast<float>(o->presence_penalty);
        c.seed=o->seed; s->sampler=gufo::sampling::SamplerState(c); return LIE_OK;
    } catch (const std::exception &ex) { return error(e,LIE_INVALID,ex.what()); }
}
extern "C" lie_status lie_sequence_close(lie_sequence **s, lie_error *e) {
    if (!s || !*s) return error(e, LIE_INVALID, "invalid sequence handle");
    auto status = owner((*s)->runtime, e, true); if (status != LIE_OK) return status;
    delete *s; *s = nullptr; return LIE_OK;
}
extern "C" lie_status lie_sequence_prefill(lie_sequence *s, const int32_t *prefix, size_t n, lie_error *e) {
    if (!s || !prefix || !n) return error(e, LIE_INVALID, "empty/invalid prefill");
    return guarded(s->runtime, e, [&] {
        if (s->cancelled.load()) return error(e, LIE_CANCELLED, "cancelled before submission");
        if (s->stopped || !s->session->IsValid()) return error(e, LIE_INVALID, "sequence cannot prefill");
        const auto prior = s->session->Tokens();
        if (n < prior.size() || n > s->session->ContextSize() || n - prior.size() > s->runtime->chunk ||
            !std::equal(prior.begin(), prior.end(), prefix)) return error(e, LIE_INVALID, "prefix frontier/chunk mismatch");
        for (size_t i = 0; i < n; ++i) if (prefix[i] < 0 || static_cast<uint32_t>(prefix[i]) >= s->runtime->model->VocabSize())
            return error(e, LIE_INVALID, "prefill token outside vocabulary");
        std::string message;
        if (!s->session->Sync({prefix, n}, &message)) return failed(s->runtime, e, message);
        return s->cancelled.load() ? error(e, LIE_CANCELLED, "cancelled after completed step") : LIE_OK;
    });
}
extern "C" lie_status lie_sequence_decode(lie_sequence *s, lie_decode_result *out, lie_error *e) {
    if (!s || !out) return error(e, LIE_INVALID, "invalid decode output");
    *out = {};
    return guarded(s->runtime, e, [&] {
        if (s->cancelled.load()) return error(e, LIE_CANCELLED, "cancelled before submission");
        if (s->stopped || !s->session->Position() || s->session->Position() >= s->session->ContextSize())
            return error(e, LIE_INVALID, "decode frontier unavailable/full/stopped");
        if (!s->sampling_started) { const auto tokens=s->session->Tokens();
            std::vector<gufo::sampling::TokenId> history(tokens.begin(),tokens.end());
            s->sampler.ResetHistory(history); s->sampling_started=true; }
        qfn::Session::DecodeResult result; std::string message;
        if (!s->session->DecodeStep(1, s->sampler, &result, &message, true)) return failed(s->runtime, e, message);
        if (s->cancelled.load()) return error(e, LIE_CANCELLED, "cancelled after completed decode; output suppressed");
        if (result.tokens.size() > 1) return failed(s->runtime, e, "unexpected AR result");
        s->stopped = result.stop;
        *out = {result.tokens.empty() ? -1 : result.tokens.front(), static_cast<uint32_t>(result.tokens.size()),
                result.stop ? 1u : 0u, s->session->Position()};
        return LIE_OK;
    });
}
extern "C" lie_status lie_sequences_decode(lie_sequence *const *rows,size_t n,lie_decode_outcome *out,lie_error *e) {
    if(!rows||!out||!n||n>LIE_DECODE_MAX_ROWS||!rows[0])return error(e,LIE_INVALID,"invalid batch");
    for(size_t i=0;i<n;++i)out[i]={LIE_INVALID,{}};
    auto r=rows[0]->runtime;
    auto status=owner(r,e);if(status!=LIE_OK)return status;
    if(n>r->width)return error(e,LIE_INVALID,"batch exceeds admitted capacity");
    for(size_t i=0;i<n;++i){
        if(!rows[i]||rows[i]->runtime!=r)return error(e,LIE_INVALID,"batch model mismatch");
        for(size_t j=0;j<i;++j)if(rows[i]==rows[j])return error(e,LIE_INVALID,"duplicate batch sequence");
        if(!rows[i]->cancelled.load()&&(rows[i]->stopped||!rows[i]->session->IsValid()||
           !rows[i]->session->Position()||rows[i]->session->Position()>=rows[i]->session->ContextSize()))
            return error(e,LIE_INVALID,"batch frontier unavailable/full/stopped");
    }
    status=guarded(r,e,[&]{
        std::array<qfn::Session::DecodeResult,LIE_DECODE_MAX_ROWS> results;
        std::array<qfn::Session::BatchOutcome,LIE_DECODE_MAX_ROWS> outcomes;
        std::array<qfn::Session::DecodeRequest,LIE_DECODE_MAX_ROWS> requests;
        std::array<size_t,LIE_DECODE_MAX_ROWS> map{};size_t active=0;
        for(size_t i=0;i<n;++i){
            auto s=rows[i];out[i]={LIE_CANCELLED,{}};
            if(s->cancelled.load())continue;
            if(!s->sampling_started){auto ids=s->session->Tokens();
                std::vector<gufo::sampling::TokenId> history(ids.begin(),ids.end());
                s->sampler.ResetHistory(history);s->sampling_started=true;}
            map[active]=i;requests[active]={s->session.get(),1,&s->sampler,&results[active],true,&outcomes[active]};++active;
        }
        std::string message;
        if(active==1){auto &q=requests[0];
            if(!q.session->DecodeStep(1,*q.sampler,q.result,&message,true))return failed(r,e,message);
            outcomes[0].completed=true;
        }else if(active>1&&!qfn::Session::DecodeBatch({requests.data(),active},&message))return failed(r,e,message);
        for(size_t k=0;k<active;++k){auto i=map[k];auto s=rows[i];auto &d=results[k];
            if(!outcomes[k].completed||d.tokens.size()>1)return failed(r,e,"unconfirmed batch outcome");
            s->stopped=d.stop;
            if(s->cancelled.load())continue;
            out[i]={LIE_OK,{d.tokens.empty()?-1:d.tokens.front(),static_cast<uint32_t>(d.tokens.size()),d.stop?1u:0u,s->session->Position()}};
        }
        return LIE_OK;
    });
    if(status!=LIE_OK)for(size_t i=0;i<n;++i)out[i]={status,{}};
    return status;
}
extern "C" lie_status lie_sequences_decode_mtp(lie_sequence *const *rows,const uint32_t *limits,size_t n,lie_mtp_outcome *out,lie_error *e) {
    if(!rows||!limits||!out||!n||n>LIE_DECODE_MAX_ROWS||!rows[0])return error(e,LIE_INVALID,"invalid batch");
    for(size_t i=0;i<n;++i){out[i]={};out[i].status=LIE_INVALID;}
    auto r=rows[0]->runtime;
    auto status=owner(r,e);if(status!=LIE_OK)return status;
    for(size_t i=0;i<n;++i)if(!limits[i]||limits[i]>r->drafts+1||limits[i]>LIE_MTP_MAX_OUTPUT)return error(e,LIE_INVALID,"invalid verified-output reservation");
    if(!r->model->HasMtp())return error(e,LIE_UNSUPPORTED,"predictor not admitted");
    if(n>r->width)return error(e,LIE_INVALID,"batch exceeds admitted capacity");
    for(size_t i=0;i<n;++i){
        if(!rows[i]||rows[i]->runtime!=r)return error(e,LIE_INVALID,"batch model mismatch");
        for(size_t j=0;j<i;++j)if(rows[i]==rows[j])return error(e,LIE_INVALID,"duplicate batch sequence");
        if(!rows[i]->cancelled.load()&&(rows[i]->stopped||!rows[i]->session->IsValid()||
           !rows[i]->session->Position()||rows[i]->session->Position()>=rows[i]->session->ContextSize()))
            return error(e,LIE_INVALID,"batch frontier unavailable/full/stopped");
    }
    status=guarded(r,e,[&]{
        std::array<qfn::Session::DecodeResult,LIE_DECODE_MAX_ROWS> results;
        std::array<qfn::Session::BatchOutcome,LIE_DECODE_MAX_ROWS> outcomes;
        std::array<qfn::Session::DecodeRequest,LIE_DECODE_MAX_ROWS> requests;
        std::array<qfn::Session::SpeculativeStats,LIE_DECODE_MAX_ROWS> before{};
        std::array<size_t,LIE_DECODE_MAX_ROWS> map{};size_t active=0;
        for(size_t i=0;i<n;++i){
            auto s=rows[i];out[i]={};out[i].status=LIE_CANCELLED;
            if(s->cancelled.load())continue;
            if(!s->sampling_started){auto ids=s->session->Tokens();
                std::vector<gufo::sampling::TokenId> history(ids.begin(),ids.end());
                s->sampler.ResetHistory(history);s->sampling_started=true;}
            before[active]=s->session->Statistics();
            map[active]=i;requests[active]={s->session.get(),limits[i],&s->sampler,&results[active],true,&outcomes[active]};++active;
        }
        std::string message;
        if(active==1){auto &q=requests[0];
            if(!q.session->DecodeStep(q.max_tokens,*q.sampler,q.result,&message,true))return failed(r,e,message);
            outcomes[0].completed=true;
        }else if(active>1&&!qfn::Session::DecodeBatch({requests.data(),active},&message))return failed(r,e,message);
        for(size_t k=0;k<active;++k){auto i=map[k];auto s=rows[i];auto &d=results[k];
            if(!outcomes[k].completed||d.tokens.size()>limits[i])return failed(r,e,"unconfirmed batch outcome");
            s->stopped=d.stop;
            if(s->cancelled.load())continue;
            auto after=s->session->Statistics();
            if(after.drafted<before[k].drafted||after.accepted<before[k].accepted)return failed(r,e,"MTP counters went backwards");
            out[i]={};out[i].status=LIE_OK;out[i].emitted=static_cast<uint32_t>(d.tokens.size());
            out[i].stop=d.stop?1u:0u;out[i].position=s->session->Position();
            out[i].drafted=after.drafted-before[k].drafted;out[i].accepted=after.accepted-before[k].accepted;
            std::copy(d.tokens.begin(),d.tokens.end(),out[i].tokens);
        }
        return LIE_OK;
    });
    if(status!=LIE_OK)for(size_t i=0;i<n;++i){out[i]={};out[i].status=status;}
    return status;
}
extern "C" lie_status lie_sequence_logits(lie_sequence *s, float *out, size_t capacity, size_t *required, lie_error *e) {
    if (!s || !required || (!out && capacity)) return error(e, LIE_INVALID, "invalid logit destination");
    return guarded(s->runtime, e, [&] {
        const auto row = s->session->Logits(); *required = row.size();
        if (row.empty()) return error(e, LIE_INVALID, "no completed frontier logits");
        if (row.size() > capacity) return error(e, LIE_BUFFER_SMALL, "logit buffer too small");
        std::copy(row.begin(), row.end(), out); return LIE_OK;
    });
}
extern "C" void lie_sequence_cancel(lie_sequence *s) { if (s) s->cancelled.store(true); }

extern "C" lie_status lie_sequence_state_describe(lie_sequence *s,const lie_state_layout *source,
                                                  lie_state_layout *out,lie_error *e) {
    if(!s||!out)return error(e,LIE_INVALID,"invalid state description");
    return guarded(s->runtime,e,[&]{
        if(s->cancelled.load())return error(e,LIE_CANCELLED,"cancelled before state description");
#ifdef LIE_GUFO_STATE_ACCESS
        /* Captures own only the completed token frontier, never sampler/RNG
         * state. Restoring still requires a fresh unstarted destination. */
        if((source&&(s->stopped||s->sampling_started))||!qfn::LieStateAccess::Describe(*s->session,s->runtime->state_domain,s->runtime->chunk,source,*out,s->runtime->state_quant))
            return error(e,LIE_INVALID,"unsupported, foreign or non-prefix state");
        return LIE_OK;
#else
        (void)source;return error(e,LIE_UNSUPPORTED,"provider built without component state access");
#endif
    });
}
static lie_status state_copy(lie_sequence *s,const lie_state_layout *layout,void *data,size_t bytes,
                              bool restore,lie_error *e) {
    uint64_t required=0;
    if(!s||!data||!lie_state_validate(layout,&required)||bytes!=required)return error(e,LIE_INVALID,"invalid state transfer");
    lie_state_layout expected{};lie_status rc=lie_sequence_state_describe(s,restore?layout:nullptr,&expected,e);
    if(rc!=LIE_OK)return rc;
    if(!lie_state_layout_equal(layout,&expected))return error(e,LIE_INVALID,"state transfer layout mismatch");
    return guarded(s->runtime,e,[&]{
#ifdef LIE_GUFO_STATE_ACCESS
        std::string message;
        lie_status copied=qfn::LieStateAccess::Copy(*s->session,*layout,data,restore,s->cancelled,message);
        if(copied!=LIE_OK){
            // Cancelled transfers have completed every submitted copy. Their
            // private sequence is retired; no incomplete state is published.
            if(copied==LIE_CANCELLED)return error(e,LIE_CANCELLED,message.c_str());
            if(copied==LIE_INVALID||copied==LIE_UNSUPPORTED||copied==LIE_RESOURCE_LIMIT)
                return error(e,copied,message.c_str()); // Payload admission precedes every device mutation.
            return failed(s->runtime,e,message);
        }
        if(s->cancelled.load())return error(e,LIE_CANCELLED,"cancelled after completed state transfer");
        return LIE_OK;
#else
        return error(e,LIE_UNSUPPORTED,"provider built without component state access");
#endif
    });
}
extern "C" lie_status lie_sequence_state_read(lie_sequence *s,const lie_state_layout *l,void *out,size_t bytes,lie_error *e) {
    return state_copy(s,l,out,bytes,false,e);
}
extern "C" lie_status lie_sequence_state_write(lie_sequence *s,const lie_state_layout *l,const void *in,size_t bytes,lie_error *e) {
    return state_copy(s,l,const_cast<void*>(in),bytes,true,e);
}

extern "C" lie_status lie_model_mtp_info(lie_model *m,lie_mtp_info *out,lie_error *e) {
    if(!m||!out||out->abi_version!=LIE_MTP_ABI||out->struct_bytes!=sizeof(*out))return error(e,LIE_INVALID,"invalid MTP capability output");
    return guarded(m->runtime,e,[&]{
        if(!m->runtime->model->HasMtp())return error(e,LIE_UNSUPPORTED,"predictor not admitted");
        *out={LIE_MTP_ABI,sizeof(*out),m->runtime->drafts,m->runtime->drafts+1,0};return LIE_OK;
    });
}
