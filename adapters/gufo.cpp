// SPDX-License-Identifier: MIT
// Opt-in transitional adapter; NOT the autonomous LIE backend.
// Whole-model delegation is permitted for bootstrap, then refactored by contract.
// First-party boundary over the pinned upstream API and the verified state/
// sampler source variant. Numerical forward remains delegated; no kernels copied.
#ifndef LIE_GUFO_ADAPTER_OPT_IN
#error "Gufo adapter requires explicit opt-in; see docs/BACKEND.md"
#endif
#include "lie/executor.h"
#include "lie/mtp.h"
#include "lie/vision.h"
#include "lie/state.h"
#include "lie/store.h"
#include "lie/steering.h"
#include "lie/steering_state.h"
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
extern "C" lie_status lie_gufo_device_validate(lie_error *) noexcept;
namespace qfn = gufo::models::qwen38_flash_next;
static std::atomic<uint64_t> next_state_domain{1};
static bool same_file_snapshot(const struct stat& a,const struct stat& b) noexcept {
    return b.st_nlink&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino&&a.st_size==b.st_size&&
        a.st_mtim.tv_sec==b.st_mtim.tv_sec&&a.st_mtim.tv_nsec==b.st_mtim.tv_nsec&&
        a.st_ctim.tv_sec==b.st_ctim.tv_sec&&a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
}
struct Runtime {
    lie_attention_dispatch_counter attention_dispatch{};
    std::shared_ptr<qfn::Model> model;
    std::thread::id owner{std::this_thread::get_id()};
    std::uint32_t chunk{}, width{1}, drafts{};
    uint8_t state_quant{};
    bool failed{false}, vision_admitted{false};
    uint64_t state_domain{next_state_domain.fetch_add(1)};
    lie_rope_plan rope{};
    lie_steering_bank *steering_bank{};
    lie_steering_info steering_bank_info{};
    lie_steering_settings steering_defaults{};
    struct StateFile { int fd;struct stat stat; };
    std::vector<StateFile> state_files;
    std::shared_ptr<const gufo::sampling::ConstraintVocabulary> vocabulary;
    Runtime(){
        lie_attention_dispatch_init(&attention_dispatch,
#if defined(LIE_GUFO_STATE_ACCESS) && LIE_ATTENTION_DISPATCH_STATS
                                    true,
#else
                                    false,
#endif
                                    state_domain);
    }
    ~Runtime(){for(auto& f:state_files)::close(f.fd);if(steering_bank)lie_steering_bank_release(&steering_bank);}
};
struct lie_model { std::shared_ptr<Runtime> runtime; };
struct lie_vision_prompt { std::shared_ptr<Runtime> runtime;std::shared_ptr<const gufo::models::qwen::vision::Prompt> prompt; };
struct lie_sequence {
    std::shared_ptr<Runtime> runtime;
    std::unique_ptr<qfn::Session> session;
    gufo::sampling::SamplerState sampler;
    std::atomic<bool> cancelled{false};
    bool stopped{false}, sampling_started{false};
    bool stop_at_eos{true};
    lie_steering_policy *steering{};
    ~lie_sequence(){if(steering)lie_steering_policy_release(&steering);}
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
/* Only lifetime glue stays C++. C17 owns admission, reservations, history and
 * actual-frontier confirmation. Rejected target rows/predictor work are excluded. */
struct SteeringStep {
    lie_steering_update *update{};
    SteeringStep() = default;
    SteeringStep(const SteeringStep&) = delete;
    SteeringStep& operator=(const SteeringStep&) = delete;
    ~SteeringStep(){if(update)lie_steering_update_discard(&update);}
    lie_status prepare(lie_sequence *s,uint64_t maximum,lie_error *e) {
        if(!s->steering)return LIE_OK;
        auto rc=lie_steering_forward_prepare(s->steering,s->session->Position(),maximum,&update,e);
        if(rc==LIE_BACKEND_FAILED)return failed(s->runtime,e,e?e->message:"model steering frontier divergence");
        return rc;
    }
    lie_status complete(lie_sequence *s,lie_error *e) {
        if(!s->steering)return LIE_OK;
        auto rc=lie_steering_forward_complete(s->steering,&update,s->session->Position(),e);
        if(rc!=LIE_OK)return failed(s->runtime,e,e?e->message:"unconfirmed model steering frontier");
        return LIE_OK;
    }
};
/* C17 owns staging/confirmation. No observations from decode/captured graphs;
 * destruction keeps exceptions and incomplete calls explicitly unconfirmed. */
struct AttentionDispatchStep {
    lie_attention_dispatch_counter *counter;
    bool active;
    explicit AttentionDispatchStep(lie_attention_dispatch_counter *c,bool changed)
        :counter(c),active(changed&&lie_attention_dispatch_begin(c)==LIE_DISPATCH_OK){}
    ~AttentionDispatchStep(){if(active)(void)lie_attention_dispatch_finish(counter,false);}
    void complete(){if(active){(void)lie_attention_dispatch_finish(counter,true);active=false;}}
};
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
static lie_status open_model(const char *path, const lie_model_options *o, uint32_t width, const char *mtp_path, uint32_t drafts, const char *vision, lie_model **out, lie_error *e,
                             const lie_steering_model_options *steering=nullptr) {
    if (!width || width>LIE_DECODE_MAX_ROWS || !path || !*path || !o || !out || *out || o->abi_version != LIE_EXECUTOR_ABI ||
        o->struct_bytes != sizeof(*o) || !o->context_tokens || o->context_tokens > INT32_MAX ||
        !o->prefill_chunk_tokens || o->prefill_chunk_tokens > 2048 ||
        !lie_rope_profile_name(o->rope_profile))
        return error(e, LIE_INVALID, "invalid model options/output handle");
#if !LIE_DIRECTIONAL_STEERING || !defined(LIE_GUFO_STATE_ACCESS) || !defined(LIE_DS4_RUNTIME_CACHE)
    if(steering)return error(e,LIE_UNSUPPORTED,"steering requires the enabled verified DS4 state provider");
#endif
    try {
        std::string template_error;
        auto metadata = gufo::core::GgufReader::OpenFile(path, &template_error);
        if (!metadata || !gufo::tokenization::QwenChatTemplate::ValidateGgufTemplate(*metadata, &template_error))
            return error(e, LIE_INVALID, template_error.c_str());
        auto r = std::make_shared<Runtime>(); r->chunk = o->prefill_chunk_tokens; r->width=width;r->drafts=mtp_path?drafts:0;r->vision_admitted=vision!=nullptr;
        const auto config=qfn::Config::FromGguf(*metadata,true,&template_error);
        lie_rope_plan rope{};
        if(!config || !lie_rope_plan_build(o->rope_profile,config->context_length,
                config->rotary_dim,config->rope_theta,&rope) ||
           o->context_tokens>rope.context_limit)
            return error(e,LIE_INVALID,"context exceeds the selected model RoPE profile");
#ifndef LIE_GUFO_STATE_ACCESS
        if(o->rope_profile!=LIE_ROPE_NATIVE)
            return error(e,LIE_UNSUPPORTED,"static YaRN requires the verified LIE context provider variant");
#endif
        r->rope=rope;
        if(steering){
            auto rc=lie_steering_model_bank_load(steering,config->num_layers,config->hidden_size,&r->steering_bank,e);
            if(rc!=LIE_OK)return rc; // Complete host admission before device validation/upload.
            r->steering_bank_info.abi_version=LIE_STEERING_ABI;
            r->steering_bank_info.struct_bytes=sizeof(lie_steering_info);
            rc=lie_steering_bank_info(r->steering_bank,&r->steering_bank_info,e);
            if(rc!=LIE_OK)return rc;
            r->steering_defaults=steering->defaults;
            if(r->steering_defaults.ffn==0)r->steering_defaults.ffn=0;
            if(r->steering_defaults.attention==0)r->steering_defaults.attention=0;
        }
#ifdef LIE_DS4_RUNTIME_CACHE
        const auto* expert=metadata->FindTensor("blk.0.ffn_gate_exps.weight");
        if(!expert)return error(e,LIE_UNSUPPORTED,"KVC requires an identified routed-expert quantization");
        const auto precheck_quant=expert->type;
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
#ifdef LIE_DS4_RUNTIME_CACHE
        std::vector<struct stat> witnesses;
        auto witness_files=[&](const gufo::core::GgufReader& reader){
            for(const auto& region:reader.GetMappedRegions()){
                struct stat st{};if(::fstat(region.file_descriptor,&st)||!st.st_nlink)
                    return error(e,LIE_INVALID,"cannot witness model file before load");
                witnesses.push_back(st);
            }
            return LIE_OK;
        };
        auto witnessed=witness_files(*metadata);if(witnessed!=LIE_OK)return witnessed;
        for(const char *sidecar:{mtp_path,vision})if(sidecar){
            auto predictor=gufo::core::GgufReader::OpenFile(sidecar,&template_error);
            if(!predictor)return error(e,LIE_INVALID,template_error.c_str());
            witnessed=witness_files(*predictor);if(witnessed!=LIE_OK)return witnessed;
        }
#endif
        auto pin_files=[&](const gufo::core::GgufReader& reader){
            for(const auto& region:reader.GetMappedRegions()){
                int fd=::fcntl(region.file_descriptor,F_DUPFD_CLOEXEC,0);struct stat st{};
                if(fd<0)return error(e,LIE_RESOURCE_LIMIT,"cannot pin model identity file");
                if(::fstat(fd,&st)){::close(fd);return error(e,LIE_INVALID,"cannot inspect model identity file");}
#ifdef LIE_DS4_RUNTIME_CACHE
                if(r->state_files.size()>=witnesses.size()||!same_file_snapshot(witnesses[r->state_files.size()],st)){
                    ::close(fd);return error(e,LIE_INVALID,"target, predictor or projector files changed during load");
                }
#endif
                try{r->state_files.push_back({fd,st});}catch(...){::close(fd);throw;}
            }
            return LIE_OK;
        };
#ifndef LIE_DS4_RUNTIME_CACHE
        auto pinned=pin_files(*metadata);if(pinned!=LIE_OK)return pinned;
#endif
        metadata.reset(); // Validation before GPU admission; no model forward on CPU.
        const auto device_status = lie_gufo_device_validate(e);
        if (device_status != LIE_OK) return device_status;
        qfn::ModelOptions options;
#ifdef LIE_GUFO_STATE_ACCESS
        if(r->steering_bank)options.lie_steering_values={lie_steering_bank_values(r->steering_bank),
                static_cast<size_t>(r->steering_bank_info.bytes/sizeof(float))};
#endif
        if(vision)options.vision_model_path=vision;
        options.max_context = o->context_tokens;
#ifdef LIE_GUFO_STATE_ACCESS
        options.lie_prefill_capacity = o->prefill_chunk_tokens;
#endif
#ifdef LIE_GUFO_STATE_ACCESS
        if(o->rope_profile!=LIE_ROPE_NATIVE) {
            options.lie_context_limit=rope.context_limit;
            options.lie_rope_inv_frequency.assign(rope.inv_frequency,
                                                  rope.inv_frequency+rope.rotary_dim/2);
            options.lie_rope_attention=rope.attention_factor;
        }
#endif
        options.decode_concurrency = width;
        options.max_draft_tokens = mtp_path?drafts:1;
        if(mtp_path)options.mtp_model_path=mtp_path;
        std::string message; r->model = qfn::Model::Load(path, options, &message);
        if (!r->model) return error(e, LIE_BACKEND_FAILED, message.c_str());
#if defined(LIE_GUFO_STATE_ACCESS) && LIE_ATTENTION_DISPATCH_STATS
        r->model->LieBindAttentionDispatch(&r->attention_dispatch);
#endif
#ifdef LIE_DS4_RUNTIME_CACHE
        const auto readers=qfn::LieStateAccess::ModelReaders(*r->model);
        if(!readers[0]||bool(readers[1])!=bool(mtp_path)||bool(readers[2])!=bool(vision))return error(e,LIE_INVALID,"admitted model readers incomplete");
        if(r->steering_bank){
            const auto admitted=qfn::Config::FromGguf(*readers[0],true,&message);
            if(!admitted||admitted->num_layers!=r->steering_bank_info.layers||
               admitted->hidden_size!=r->steering_bank_info.width||
               r->model->LieSteeringBytes()!=r->steering_bank_info.bytes)
                return error(e,LIE_INVALID,"admitted model steering geometry/allocation changed during load");
        }
        // The metadata precheck may have observed an earlier pathname target.
        const auto* admitted_expert=readers[0]->FindTensor("blk.0.ffn_gate_exps.weight");
        if(!admitted_expert||admitted_expert->type!=precheck_quant)
            return error(e,LIE_INVALID,"model quantization changed during load");
        for(const auto* reader:readers)if(reader){auto pinned=pin_files(*reader);if(pinned!=LIE_OK)return pinned;}
        if(r->state_files.size()!=witnesses.size())return error(e,LIE_INVALID,"admitted model file set changed during load");
#endif
        auto result = std::make_unique<lie_model>(); result->runtime = std::move(r);
        *out = result.release(); if (e) e->message[0] = 0; return LIE_OK;
    } catch (const std::exception &ex) { return error(e, LIE_BACKEND_FAILED, ex.what()); }
      catch (...) { return error(e, LIE_BACKEND_FAILED, "unknown model load exception"); }
}
extern "C" lie_status lie_gufo_open_batch(const char *p,const lie_model_options *o,uint32_t width,lie_model **m,lie_error *e) {
    return open_model(p,o,width,nullptr,0,nullptr,m,e);
}
extern "C" lie_status lie_backend_open_mtp(const char *p,const lie_model_options *o,uint32_t width,const char *predictor,uint32_t drafts,lie_model **m,lie_error *e) {
    if(!LIE_MTP)return error(e,LIE_UNSUPPORTED,"MTP was disabled at build time");
    if(!drafts)drafts=qfn::kMaxMtpDraftTokens;
    if(!predictor||!*predictor||drafts>qfn::kMaxMtpDraftTokens||drafts>=LIE_MTP_MAX_OUTPUT)return error(e,LIE_INVALID,"invalid explicit MTP predictor/options");
    return open_model(p,o,width,predictor,drafts,nullptr,m,e);
}
extern "C" lie_status lie_backend_open_vision(const char *p,const lie_model_options *o,uint32_t w,const char *v,lie_model **m,lie_error *e){
    if(!LIE_VISION)return error(e,LIE_UNSUPPORTED,"vision was disabled at build time");
    if(!v||!*v)return error(e,LIE_INVALID,"explicit vision projector required");
    return open_model(p,o,w,nullptr,0,v,m,e);
}
extern "C" lie_status lie_backend_open_mtp_vision(const char *p,const lie_model_options *o,uint32_t w,const char *d,uint32_t n,const char *v,lie_model **m,lie_error *e){
    if(!LIE_MTP||!LIE_VISION)return error(e,LIE_UNSUPPORTED,"joint features were disabled at build time");
    if(!n)n=qfn::kMaxMtpDraftTokens;
    if(!d||!*d||!v||!*v||n>qfn::kMaxMtpDraftTokens||n>=LIE_MTP_MAX_OUTPUT)return error(e,LIE_INVALID,"invalid explicit predictor/projector options");
    return open_model(p,o,w,d,n,v,m,e);
}
extern "C" lie_status lie_gufo_open(const char *path,const lie_model_options *o,lie_model **out,lie_error *e) {
    return lie_gufo_open_batch(path,o,1,out,e);
}
extern "C" lie_status lie_backend_open_steered(const char *p,const lie_model_options *o,uint32_t width,
    const char *predictor,uint32_t drafts,const char *projector,const lie_steering_model_options *steering,
    lie_model **m,lie_error *e) {
    if(!steering || (predictor&&!*predictor) || (projector&&!*projector) || (!predictor&&drafts))
        return error(e,LIE_INVALID,"invalid explicit steering/predictor/projector admission");
    if((predictor&&!LIE_MTP)||(projector&&!LIE_VISION))return error(e,LIE_UNSUPPORTED,"requested feature was disabled at build time");
    if(predictor){if(!drafts)drafts=qfn::kMaxMtpDraftTokens;
        if(drafts>qfn::kMaxMtpDraftTokens||drafts>=LIE_MTP_MAX_OUTPUT)return error(e,LIE_INVALID,"invalid explicit MTP draft capacity");}
    return open_model(p,o,width,predictor,drafts,projector,m,e,steering);
}
extern "C" lie_status lie_model_steering_info(lie_model *m,lie_steering_model_info *out,lie_error *e) {
    if(!m||!out||out->abi_version!=LIE_STEERING_MODEL_ABI||out->struct_bytes!=sizeof(*out))
        return error(e,LIE_INVALID,"invalid model steering info output");
    return guarded(m->runtime,e,[&]{
        lie_steering_model_info value{};value.abi_version=LIE_STEERING_MODEL_ABI;value.struct_bytes=sizeof(value);
        value.admitted=m->runtime->steering_bank!=nullptr;
        value.bank.abi_version=LIE_STEERING_ABI;value.bank.struct_bytes=sizeof(value.bank);
        lie_steering_settings_init(&value.defaults,false);
        if(value.admitted){value.bank=m->runtime->steering_bank_info;value.defaults=m->runtime->steering_defaults;}
#ifdef LIE_GUFO_STATE_ACCESS
        value.device_vector_bytes=m->runtime->model->LieSteeringBytes();
#endif
        value.prefix_state_supported=lie_backend_prefix_state_supported()!=0;
        *out=value;return LIE_OK;
    });
}
extern "C" lie_status lie_model_state_identity(lie_model *m,lie_state_identity *id,uint64_t *domain,lie_error *e){
    if(!m||!id||!domain)return error(e,LIE_INVALID,"invalid SSD identity output");
    return guarded(m->runtime,e,[&]{
        if(!lie_backend_prefix_state_supported())return error(e,LIE_UNSUPPORTED,"component state access required for SSD");
#ifndef LIE_DS4_RUNTIME_CACHE
        if(m->runtime->drafts)return error(e,LIE_UNSUPPORTED,"complete predictor state required for MTP SSD identity");
#endif
        std::vector<int> fds;
        for(const auto& f:m->runtime->state_files){struct stat st{};
            if(::fstat(f.fd,&st)||!same_file_snapshot(f.stat,st))
                return error(e,LIE_INVALID,"model files changed after load; SSD identity refused");
            fds.push_back(f.fd);
        }
        char device[1024],policy[2048],mtp_policy[128]={};if(!lie_gufo_device_identity(device,sizeof(device)))return error(e,LIE_INVALID,"SSD device identity unavailable");
#ifdef LIE_DS4_RUNTIME_CACHE
        const char *format="ds4-qwen-payload-v2/full-index/eager-pool";
#else
        const char *format="qwen-ar-v1";
#endif
        // Target then predictor descriptors are hashed in that order. Draft
        // bounds/concurrency affect the adaptive controller, never alias AR.
        if(m->runtime->drafts)std::snprintf(mtp_policy,sizeof(mtp_policy),"/mode=mtp/drafts=%u/predictor-history-v1",m->runtime->drafts);
        int n=std::snprintf(policy,sizeof(policy),"gufo-f783fedb/state-access-v1/%s/thinking-off/context-growth-v1/chunk=%u/width=%u%s/%s",format,
            m->runtime->chunk,m->runtime->width,mtp_policy,device);
        if(n<0||static_cast<size_t>(n)>=sizeof(policy))return error(e,LIE_INVALID,"SSD policy identity overflow");
        if(m->runtime->rope.profile!=LIE_ROPE_NATIVE) {
            const auto at=static_cast<size_t>(n);
            n=std::snprintf(policy+at,sizeof(policy)-at,"/rope=%s/rope-plan-v1=%016llx",
                lie_rope_profile_name(m->runtime->rope.profile),
                static_cast<unsigned long long>(lie_rope_plan_domain(&m->runtime->rope)));
            if(n<0||static_cast<size_t>(n)>=sizeof(policy)-at)return error(e,LIE_INVALID,"RoPE policy identity overflow");
            n+=static_cast<int>(at);
        }
        if(m->runtime->vision_admitted){
            const auto at=static_cast<size_t>(n);
            n=std::snprintf(policy+at,sizeof(policy)-at,"/vision-full-prompt-scope-v1");
            if(n<0||static_cast<size_t>(n)>=sizeof(policy)-at)return error(e,LIE_INVALID,"vision policy identity overflow");
        }
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
        if(m->runtime->steering_bank){
            lie_steering_policy_options options{LIE_STEERING_POLICY_ABI,sizeof(options),m->runtime->model->MaxContext(),
                m->runtime->steering_bank,m->runtime->steering_defaults};
            auto rc=lie_steering_policy_create(&options,&result->steering,e);
            if(rc!=LIE_OK)return rc;
        }
        std::string message;
        result->session = m->runtime->model->CreateSession(m->runtime->model->HasMtp()?gufo::core::SessionMode::kSpeculative:gufo::core::SessionMode::kAutoregressive,
                                                         m->runtime->model->MaxContext(), &message);
        if (!result->session) return failed(m->runtime, e, message);
#ifdef LIE_GUFO_STATE_ACCESS
        if(result->steering&&!result->session->LieConfigureSteering(m->runtime->steering_defaults.ffn,
                m->runtime->steering_defaults.attention,&message))return failed(m->runtime,e,message);
#endif
        *out = result.release(); return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_configure_steering(lie_sequence *s,const lie_steering_settings *settings,lie_error *e) {
    if(!s||!settings)return error(e,LIE_INVALID,"invalid sequence steering controls");
    return guarded(s->runtime,e,[&]{
        if(!s->steering)return error(e,LIE_UNSUPPORTED,"direction bank is not admitted");
        if(s->session->Position()||s->sampling_started||s->stopped)
            return error(e,LIE_INVALID,"steering configuration requires an unstarted sequence");
        SteeringStep plan;
        auto rc=lie_steering_policy_prepare_change(s->steering,settings,&plan.update,e);
        if(rc!=LIE_OK)return rc;
#ifdef LIE_GUFO_STATE_ACCESS
        const auto *next=lie_steering_update_settings(plan.update);
        std::string message;
        if(!s->session->LieConfigureSteering(next->ffn,next->attention,&message))
            return failed(s->runtime,e,message);
#endif
        rc=lie_steering_update_commit(&plan.update,0,e);
        if(rc!=LIE_OK)return failed(s->runtime,e,e?e->message:"steering initial policy commit failed");
        return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_change_steering(lie_sequence *s,const lie_steering_settings *settings,lie_error *e) {
    if(!s||!settings)return error(e,LIE_INVALID,"invalid live steering controls");
    return guarded(s->runtime,e,[&]{
        if(!s->steering)return error(e,LIE_UNSUPPORTED,"direction bank is not admitted");
        if(s->stopped||s->cancelled.load())return error(e,LIE_CANCELLED,"sequence steering is stopped");
        lie_steering_policy_info current{};
        current.abi_version=LIE_STEERING_POLICY_ABI;
        current.struct_bytes=sizeof(current);
        auto rc=lie_steering_policy_snapshot(s->steering,&current,e);if(rc!=LIE_OK)return rc;
        if(current.completed_positions!=s->session->Position())
            return failed(s->runtime,e,"live steering retained frontier divergence");
        if(current.outstanding_updates)return error(e,LIE_RESOURCE_LIMIT,"live steering requires an idle boundary");
        SteeringStep plan;rc=lie_steering_policy_prepare_change(s->steering,settings,&plan.update,e);
        if(rc!=LIE_OK)return rc;
        const auto *next=lie_steering_update_settings(plan.update);
        if(next->ffn==current.settings.ffn&&next->attention==current.settings.attention)return LIE_OK;
#ifdef LIE_GUFO_STATE_ACCESS
        std::string message;
        if(!s->session->LieChangeSteering(next->ffn,next->attention,&message))
            return failed(s->runtime,e,message);
#else
        return error(e,LIE_UNSUPPORTED,"live steering requires owned state access");
#endif
        /* Do not discard sampler.DeferSample: it is an actual residual draw
         * for the retained boundary logits, which this operation preserves.
         * Future verifier/proposal state is rebuilt under the new policy. */
        rc=lie_steering_update_commit(&plan.update,current.completed_positions,e);
        if(rc!=LIE_OK)return failed(s->runtime,e,e?e->message:"live steering commit failed");
        return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_steering_info(lie_sequence *s,lie_steering_policy_info *out,lie_error *e) {
    if(!s||!out)return error(e,LIE_INVALID,"invalid sequence steering info");
    return guarded(s->runtime,e,[&]{
        if(!s->steering)return error(e,LIE_UNSUPPORTED,"direction bank is not admitted");
        return lie_steering_policy_snapshot(s->steering,out,e);
    });
}
extern "C" lie_status lie_sequence_steering_cache_scope(lie_sequence *s,const unsigned char semantic[32],unsigned char out[32],lie_error *e) {
    if(!s||!semantic||!out)return error(e,LIE_INVALID,"invalid sequence steering scope");
    return guarded(s->runtime,e,[&]{
        if(s->steering)return lie_steering_policy_cache_scope(s->steering,semantic,out,e);
        std::memmove(out,semantic,32);return LIE_OK;
    });
}
extern "C" lie_status lie_sequence_set_eos_policy(lie_sequence *s,lie_eos_policy p,lie_error *e) {
    if (!s) return error(e,LIE_INVALID,"invalid sequence");
    auto rc=owner(s->runtime,e); if (rc!=LIE_OK) return rc;
    if ((p!=LIE_EOS_STOP && p!=LIE_EOS_IGNORE) ||
        (p==LIE_EOS_IGNORE && s->sampler.config().constraint) || s->session->Position() ||
        s->sampling_started || s->stopped)
        return error(e,LIE_INVALID,"invalid EOS policy or started sequence");
    s->stop_at_eos=p==LIE_EOS_STOP;
    return LIE_OK;
}
extern "C" lie_status lie_sequence_configure(lie_sequence *s,const lie_generation_options *o,lie_error *e) {
    if (!s || !o) return error(e,LIE_INVALID,"invalid generation controls");
    auto rc=owner(s->runtime,e); if (rc!=LIE_OK) return rc;
    if (o->abi_version!=LIE_GENERATION_ABI || o->struct_bytes!=sizeof(*o) || s->session->Position() ||
        !std::isfinite(o->temperature) || o->temperature<0 || o->temperature>2 ||
        !std::isfinite(o->top_p) || o->top_p<=0 || o->top_p>1 ||
        o->top_k<0 || !std::isfinite(o->min_p) || o->min_p<0 || o->min_p>1 ||
        !std::isfinite(o->frequency_penalty) || std::abs(o->frequency_penalty)>2 ||
        !std::isfinite(o->presence_penalty) || std::abs(o->presence_penalty)>2 || o->seed < -1)
        return error(e,LIE_INVALID,"invalid generation controls or started sequence");
    try {
        gufo::sampling::SamplingConfig c;
        c.temperature=static_cast<float>(o->temperature); c.top_p=static_cast<float>(o->top_p);
        c.top_k=o->top_k; c.min_p=static_cast<float>(o->min_p);
        c.frequency_penalty=static_cast<float>(o->frequency_penalty); c.presence_penalty=static_cast<float>(o->presence_penalty);
        c.seed = o->seed;
#ifdef LIE_GUFO_STATE_ACCESS
        if (o->logit_bias_count) {
          if (!o->logit_bias || o->logit_bias_count > LIE_LOGIT_BIAS_MAX)
            return error(e, LIE_INVALID, "invalid logit bias");
          c.logit_bias.resize(s->runtime->model->VocabSize());
          for (size_t i = 0; i < o->logit_bias_count; ++i) {
            const auto b = o->logit_bias[i];
            if (b.token < 0 ||
                static_cast<uint32_t>(b.token) >= c.logit_bias.size() ||
                !std::isfinite(b.bias) || std::abs(b.bias) > 100)
              return error(e, LIE_INVALID, "invalid logit bias token/value");
            c.logit_bias[b.token] = static_cast<float>(b.bias);
          }
        }
#else
    if(o->logprobs)return error(e,LIE_UNSUPPORTED,"logprobs require verified sampling variant");
    if (o->logit_bias_count)
          return error(e, LIE_UNSUPPORTED,
                       "logit bias requires verified sampling variant");
#endif
        s->sampler = gufo::sampling::SamplerState(c);
        return LIE_OK;
    } catch (const std::exception &ex) { return error(e,LIE_INVALID,ex.what()); }
}
extern "C" lie_status
lie_sequence_constrain(lie_sequence *s, const lie_generation_constraints *o,
                       lie_error *e) {
  if (!s || !o)
    return error(e, LIE_INVALID, "invalid generation constraint");
  auto rc = owner(s->runtime, e);
  if (rc != LIE_OK)
    return rc;
  if (s->session->Position())
    return error(e, LIE_INVALID, "generation already started");
  if (!s->stop_at_eos)
    return error(e, LIE_INVALID, "fixed-budget decode cannot use constraints");
  try {
    using gufo::sampling::JsonConstraint;
    std::shared_ptr<const JsonConstraint> grammar;
    if (o->format == LIE_FORMAT_JSON_OBJECT)
      grammar = JsonConstraint::Object();
    else if (o->format == LIE_FORMAT_JSON_SCHEMA) {
      if (!o->schema_json)
        return error(e, LIE_INVALID, "missing JSON schema");
      grammar = JsonConstraint::Compile(gufo::json::parse(o->schema_json),
                                        o->strict != 0);
    }
    std::vector<JsonConstraint::Tool> tools;
    for (size_t i = 0; i < o->tool_count; ++i) {
      auto schema = gufo::json::parse(o->tools[i].parameters_json);
      auto def = gufo::json::parse(o->tools[i].definition_json);
      const auto *fn = def.find("function");
      const auto *strict = fn ? fn->find("strict") : nullptr;
      tools.emplace_back(
          o->tools[i].name,
          JsonConstraint::Compile(schema, strict && strict->as_bool()));
    }
    grammar = JsonConstraint::WithTools(grammar, std::move(tools),
                                        o->required != 0, o->parallel != 0);
    if (!grammar)
      return LIE_OK;
    if (!s->runtime->vocabulary) {
      auto model = s->runtime->model;
      s->runtime->vocabulary =
          std::make_shared<gufo::sampling::ConstraintVocabulary>(
              model->VocabSize(), [model](uint32_t t) {
                return gufo::sampling::ConstraintVocabulary::Piece{
                    model->TokenText(static_cast<int32_t>(t)),
                    model->IsStopToken(static_cast<int32_t>(t))};
              });
    }
    auto constraint = std::make_shared<gufo::sampling::TokenConstraint>();
    constraint->grammar = std::move(grammar);
    constraint->vocabulary = s->runtime->vocabulary;
    auto config = s->sampler.config();
    config.constraint = std::move(constraint);
    s->sampler = gufo::sampling::SamplerState(std::move(config));
    return LIE_OK;
  } catch (const std::exception &ex) {
    return error(e, LIE_INVALID, ex.what());
  }
}
extern "C" lie_status lie_sequence_sampling_logits(lie_sequence *s, float *out,
                                                   size_t capacity,
                                                   size_t *required,
                                                   lie_error *e) {
  if (!s || !required || (!out && capacity))
    return error(e, LIE_INVALID, "invalid reporting destination");
#ifdef LIE_GUFO_STATE_ACCESS
  return guarded(s->runtime, e, [&] {
    if (!s->sampling_started) {
      const auto tokens=s->session->Tokens();
      std::vector<gufo::sampling::TokenId> history(tokens.begin(),tokens.end());
      s->sampler.ResetHistory(history);
      s->sampling_started = true;
    }
    const auto row = s->sampler.ReportingLogits(s->session->Logits());
    *required = row.size();
    if (row.size() > capacity)
      return error(e, LIE_BUFFER_SMALL, "reporting destination too small");
    std::copy(row.begin(), row.end(), out);
    return LIE_OK;
  });
#else
  (void)capacity;
  return error(e, LIE_UNSUPPORTED,
               "logprobs require verified sampling variant");
#endif
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
        SteeringStep steering;auto rc=steering.prepare(s,n,e);if(rc!=LIE_OK)return rc;
        AttentionDispatchStep dispatch(&s->runtime->attention_dispatch,n>prior.size());
        if (!s->session->Sync({prefix, n}, &message)) return failed(s->runtime, e, message);
        dispatch.complete(); /* Numerical completion precedes policy/output publication. */
        rc=steering.complete(s,e);if(rc!=LIE_OK)return rc;
        return s->cancelled.load() ? error(e, LIE_CANCELLED, "cancelled after completed step") : LIE_OK;
    });
}
extern "C" lie_status lie_model_attention_dispatch_snapshot(lie_model *m,
    lie_attention_dispatch_info *out,lie_error *e) {
    if(!m||!out||out->abi_version!=LIE_ATTENTION_DISPATCH_ABI||out->struct_bytes!=sizeof(*out))
        return error(e,LIE_INVALID,"invalid attention dispatch snapshot");
    auto rc=owner(m->runtime,e,true);if(rc!=LIE_OK)return rc;
    return lie_attention_dispatch_snapshot(&m->runtime->attention_dispatch,out)==LIE_DISPATCH_OK?
        LIE_OK:error(e,LIE_INVALID,"invalid attention dispatch observer");
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
        SteeringStep steering;auto rc=steering.prepare(s,static_cast<uint64_t>(s->session->Position())+1,e);if(rc!=LIE_OK)return rc;
        qfn::Session::DecodeResult result; std::string message;
        if (!s->session->DecodeStep(1, s->sampler, &result, &message, s->stop_at_eos)) return failed(s->runtime, e, message);
        rc=steering.complete(s,e);if(rc!=LIE_OK)return rc;
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
        std::array<SteeringStep,LIE_DECODE_MAX_ROWS> steering;
        std::array<size_t,LIE_DECODE_MAX_ROWS> map{};size_t active=0;
        for(size_t i=0;i<n;++i){
            auto s=rows[i];out[i]={LIE_CANCELLED,{}};
            if(s->cancelled.load())continue;
            auto rc=steering[active].prepare(s,static_cast<uint64_t>(s->session->Position())+1,e);if(rc!=LIE_OK)return rc;
            if(!s->sampling_started){auto ids=s->session->Tokens();
                std::vector<gufo::sampling::TokenId> history(ids.begin(),ids.end());
                s->sampler.ResetHistory(history);s->sampling_started=true;}
            map[active]=i;requests[active]={s->session.get(),1,&s->sampler,&results[active],s->stop_at_eos,&outcomes[active]};++active;
        }
        std::string message;
        if(active==1){auto &q=requests[0];
            if(!q.session->DecodeStep(1,*q.sampler,q.result,&message,q.stop_at_eos))return failed(r,e,message);
            outcomes[0].completed=true;
        }else if(active>1&&!qfn::Session::DecodeBatch({requests.data(),active},&message))return failed(r,e,message);
        for(size_t k=0;k<active;++k){auto i=map[k];auto s=rows[i];auto &d=results[k];
            if(!outcomes[k].completed||d.tokens.size()>1)return failed(r,e,"unconfirmed batch outcome");
            auto rc=steering[k].complete(s,e);if(rc!=LIE_OK)return rc;
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
        std::array<SteeringStep,LIE_DECODE_MAX_ROWS> steering;
        std::array<size_t,LIE_DECODE_MAX_ROWS> map{};size_t active=0;
        for(size_t i=0;i<n;++i){
            auto s=rows[i];out[i]={};out[i].status=LIE_CANCELLED;
            if(s->cancelled.load())continue;
            const uint64_t maximum=std::min<uint64_t>(s->session->ContextSize(),static_cast<uint64_t>(s->session->Position())+limits[i]);
            auto rc=steering[active].prepare(s,maximum,e);if(rc!=LIE_OK)return rc;
            if(!s->sampling_started){auto ids=s->session->Tokens();
                std::vector<gufo::sampling::TokenId> history(ids.begin(),ids.end());
                s->sampler.ResetHistory(history);s->sampling_started=true;}
            before[active]=s->session->Statistics();
            map[active]=i;requests[active]={s->session.get(),limits[i],&s->sampler,&results[active],s->stop_at_eos,&outcomes[active]};++active;
        }
        std::string message;
        if(active==1){auto &q=requests[0];
            if(!q.session->DecodeStep(q.max_tokens,*q.sampler,q.result,&message,q.stop_at_eos))return failed(r,e,message);
            outcomes[0].completed=true;
        }else if(active>1&&!qfn::Session::DecodeBatch({requests.data(),active},&message))return failed(r,e,message);
        for(size_t k=0;k<active;++k){auto i=map[k];auto s=rows[i];auto &d=results[k];
            if(!outcomes[k].completed||d.tokens.size()>limits[i])return failed(r,e,"unconfirmed batch outcome");
            auto rc=steering[k].complete(s,e);if(rc!=LIE_OK)return rc;
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
        if(source&&(s->stopped||s->sampling_started))return error(e,LIE_INVALID,"non-prefix state destination");
        if(s->steering){
            lie_steering_state_view view{};view.abi_version=LIE_STEERING_STATE_BINDING_ABI;view.struct_bytes=sizeof(view);
            lie_status rc=LIE_OK;
            if(source){rc=lie_steering_state_inspect(source,qfn::LieStateAccess::StateFormat(*s->session),&view,e);
                if(rc!=LIE_OK)return rc;}
            lie_state_layout model{},expected{};
            if(!qfn::LieStateAccess::Describe(*s->session,s->runtime->state_domain,s->runtime->chunk,
                    source?&view.model:nullptr,model,s->runtime->state_quant,s->runtime->drafts,true))
                return error(e,LIE_INVALID,"unsupported, foreign or non-prefix model state");
            if(source){
                if(view.policy_offset!=LIE_STEERING_STATE_NO_OFFSET)rc=lie_steering_state_extend(&model,&expected,e);
                else expected=model;
                if(rc!=LIE_OK)return rc;
                if(!lie_state_layout_equal(source,&expected))return error(e,LIE_INVALID,"steering state layout mismatch");
            }else{
                rc=lie_steering_state_plan(s->steering,&model,&expected,e);
                if(rc==LIE_BACKEND_FAILED)return failed(s->runtime,e,e?e->message:"steering capture frontier divergence");
                if(rc!=LIE_OK)return rc;
            }
            *out=expected;return LIE_OK;
        }
        if(!qfn::LieStateAccess::Describe(*s->session,s->runtime->state_domain,s->runtime->chunk,source,*out,s->runtime->state_quant,s->runtime->drafts))
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
        SteeringStep policy;
        lie_steering_state_view view;view.abi_version=LIE_STEERING_STATE_BINDING_ABI;view.struct_bytes=sizeof(view);
        std::array<unsigned char,32> semantic{},scope{};
        const lie_state_layout *model=layout;
        if(s->steering){
            auto admitted=lie_steering_state_inspect(layout,qfn::LieStateAccess::StateFormat(*s->session),&view,e);
            if(admitted!=LIE_OK)return admitted;
            if(!qfn::LieStateAccess::SemanticScope(*s->session,semantic))return error(e,LIE_INVALID,"missing model semantic scope");
            admitted=restore?lie_steering_state_prepare_restore(s->steering,layout,view.model.format,
                semantic.data(),data,bytes,&policy.update,scope.data(),e):
                lie_steering_policy_cache_scope(s->steering,semantic.data(),scope.data(),e);
            if(admitted!=LIE_OK)return admitted;
            model=&view.model;
        }
        lie_status copied=qfn::LieStateAccess::Copy(*s->session,*model,data,restore,s->cancelled,message,
            s->steering?scope.data():nullptr);
        if(copied!=LIE_OK){
            // Cancelled transfers have completed every submitted copy. Their
            // private sequence is retired; no incomplete state is published.
            if(copied==LIE_CANCELLED)return error(e,LIE_CANCELLED,message.c_str());
            if(copied==LIE_INVALID||copied==LIE_UNSUPPORTED||copied==LIE_RESOURCE_LIMIT)
                return error(e,copied,message.c_str()); // Payload admission precedes every device mutation.
            return failed(s->runtime,e,message);
        }
        if(s->steering){
            auto confirmed=restore?lie_steering_update_commit(&policy.update,s->session->Position(),e):
                lie_steering_state_capture(s->steering,layout,view.model.format,semantic.data(),data,bytes,e);
            if(confirmed!=LIE_OK){
                if(restore||confirmed==LIE_BACKEND_FAILED)return failed(s->runtime,e,e?e->message:"steering model-state confirmation failed");
                return confirmed;
            }
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
        *out={LIE_MTP_ABI,sizeof(*out),m->runtime->drafts,m->runtime->drafts+1,
#ifdef LIE_DS4_RUNTIME_CACHE
            1
#else
            0
#endif
        };return LIE_OK;
    });
}

extern "C" lie_status lie_model_vision_info(lie_model *m,lie_vision_info *out,lie_error *e){
    if(!m||!out||out->abi_version!=LIE_VISION_ABI||out->struct_bytes!=sizeof(*out))return error(e,LIE_INVALID,"invalid vision capability output");
    return guarded(m->runtime,e,[&]{
        if(!m->runtime->vision_admitted||!m->runtime->model->VisionEncoder())return error(e,LIE_UNSUPPORTED,"vision encoder not admitted");
        *out={LIE_VISION_ABI,sizeof(*out),LIE_VISION_MAX_IMAGES,LIE_VISION_MAX_PIXELS,LIE_VISION_MAX_BYTES,(1u<<LIE_IMAGE_PNG)|(1u<<LIE_IMAGE_JPEG),
#ifdef LIE_DS4_RUNTIME_CACHE
        1
#else
        0
#endif
        };return LIE_OK;
    });
}
extern "C" lie_status lie_model_prepare_vision(lie_model *m,const lie_chat_template *input,const lie_image_input *images,size_t n,
    int32_t *tokens,size_t capacity,size_t *required,lie_vision_prompt **out,lie_error *e){
    if(!m||!input||!images||!n||n>LIE_VISION_MAX_IMAGES||!required||!out||*out||(!tokens&&capacity))return error(e,LIE_INVALID,"invalid vision prompt input");
    return guarded(m->runtime,e,[&]{
        auto encoder=m->runtime->model->VisionEncoder();
        if(!m->runtime->vision_admitted||!encoder)return error(e,LIE_UNSUPPORTED,"vision encoder not admitted");
        auto unchanged=[&]{for(const auto& f:m->runtime->state_files){struct stat st{};
            if(::fstat(f.fd,&st)||!st.st_nlink||st.st_dev!=f.stat.st_dev||st.st_ino!=f.stat.st_ino||st.st_size!=f.stat.st_size||
               st.st_mtim.tv_sec!=f.stat.st_mtim.tv_sec||st.st_mtim.tv_nsec!=f.stat.st_mtim.tv_nsec||
               st.st_ctim.tv_sec!=f.stat.st_ctim.tv_sec||st.st_ctim.tv_nsec!=f.stat.st_ctim.tv_nsec)return false;}return true;};
        if(!unchanged())return error(e,LIE_INVALID,"loaded model/projector files changed before image preparation");
        try{
            auto chat=lie_gufo::translate_chat(*input);if(!chat)return error(e,LIE_INVALID,"invalid vision chat template");
            uint64_t pixels=0,bytes=0;
            for(size_t i=0;i<n;++i){const auto &v=images[i];lie_image_dimensions dims{};
                if(v.message_index>=input->count||input->messages[v.message_index].role!=LIE_CHAT_USER||
                   v.text_offset>input->messages[v.message_index].bytes||
                   (v.text_offset<input->messages[v.message_index].bytes&&(static_cast<unsigned char>(input->messages[v.message_index].content[v.text_offset])&0xc0)==0x80)||
                   lie_image_inspect(&v,&dims,e)!=LIE_OK)return error(e,LIE_INVALID,"invalid image placement/header");
                if(i&&(v.message_index<images[i-1].message_index||(v.message_index==images[i-1].message_index&&v.text_offset<images[i-1].text_offset)))return error(e,LIE_INVALID,"unordered image placement");
                pixels+=static_cast<uint64_t>(dims.width)*dims.height;bytes+=v.bytes;
                if(pixels>LIE_VISION_MAX_PIXELS||bytes>LIE_VISION_MAX_BYTES)return error(e,LIE_RESOURCE_LIMIT,"vision input budget exceeded");
                auto owned=std::make_shared<const std::vector<uint8_t>>(v.data,v.data+v.bytes);
                chat->messages[v.message_index].images.push_back({v.text_offset,std::move(owned)});
            }
            gufo::tokenization::ChatTemplateOptions opts;opts.enable_thinking=false;opts.require_tool_call=input->require_tool_call!=0;
            opts.max_output_bytes=gufo::tokenization::RenderedPromptBoundBytes(m->runtime->model->MaxContext());
            auto prompt=std::make_shared<gufo::models::qwen::vision::Prompt>(gufo::models::qwen::vision::Prepare(
                m->runtime->model->tokenizer(),chat->messages,chat->tools,opts,encoder->identity(),m->runtime->model->MaxContext()));
            if(!unchanged())return error(e,LIE_INVALID,"loaded model/projector files changed during image preparation");
            *required=prompt->tokens.size();if(*required>capacity)return error(e,LIE_BUFFER_SMALL,"vision physical token budget exceeded");
            auto result=std::make_unique<lie_vision_prompt>();result->runtime=m->runtime;result->prompt=std::move(prompt);
            std::copy(result->prompt->tokens.begin(),result->prompt->tokens.end(),tokens);*out=result.release();return LIE_OK;
        }catch(const std::bad_alloc&){return error(e,LIE_RESOURCE_LIMIT,"vision preparation allocation failed");}
        catch(const std::exception& ex){return error(e,LIE_INVALID,ex.what());}
    });
}
extern "C" lie_status lie_sequence_attach_vision(lie_sequence *s,const lie_vision_prompt *p,lie_error *e){
    if(!s||!p||s->runtime!=p->runtime)return error(e,LIE_INVALID,"foreign vision prompt");
    return guarded(s->runtime,e,[&]{
        if(s->session->Position()||s->sampling_started||s->stopped)return error(e,LIE_INVALID,"vision attachment must precede prefill");
        if(s->cancelled.load())return error(e,LIE_CANCELLED,"cancelled before vision attachment");
        s->session->ConfigureVision(p->prompt);return LIE_OK;
    });
}
extern "C" lie_status lie_vision_prompt_close(lie_vision_prompt **p,lie_error *e){
    if(!p||!*p)return error(e,LIE_INVALID,"invalid vision prompt handle");
    auto rc=owner((*p)->runtime,e,true);if(rc!=LIE_OK)return rc;delete *p;*p=nullptr;return LIE_OK;
}

extern "C" lie_status lie_vision_prompt_cache_scope(const lie_vision_prompt *p,unsigned char out[32],lie_error *e){
    if(!p||!out)return error(e,LIE_INVALID,"invalid vision scope output");
    return guarded(p->runtime,e,[&]{
        if(p->prompt->cache_identity.size()!=32)return error(e,LIE_INVALID,"incomplete prepared vision scope");
        std::copy(p->prompt->cache_identity.begin(),p->prompt->cache_identity.end(),out);return LIE_OK;
    });
}
