// SPDX-License-Identifier: MIT
// Transitional field/transfer binding only. State representation, allocation,
// compatibility, cache policy and ownership live in LIE C17. No Gufo serializer.
// Uses the explicit, hash-verified friend-access variant of official f783fedb.
#ifndef LIE_GUFO_STATE_ACCESS_HPP
#define LIE_GUFO_STATE_ACCESS_HPP
#include "lie/qwen_state.h"
#include "src/models/qwen38_flash_next/engine.hpp"
#include "src/models/qwen38_flash_next/kernels/rocm/executor.hpp"
#include <atomic>
#include <algorithm>
#include <array>
#include <cstring>
#ifndef LIE_GUFO_DIRECTIONAL_STEERING
#error "State binding requires the verified directional-steering provider variant"
#endif
#include "src/models/qwen/vision/encoder.hpp"
#ifdef LIE_DS4_RUNTIME_CACHE
#include "lie/kvc_state.h"
#ifndef LIE_GUFO_DS4_STATE
#error "DS4 runtime cache requires the verified complete-history provider variant"
#endif
#ifndef LIE_GUFO_DS4_MTP_STATE
#error "MTP state access requires the verified complete predictor-history variant"
#endif
#endif
namespace gufo::models::qwen38_flash_next {
class LieStateAccess {
public:
#ifdef LIE_DS4_RUNTIME_CACHE
  // Borrow only the actual readers retained by the admitted model. Reopening
  // the pathname would let a rename during load bind SSD to different weights.
  static auto ModelReaders(Model& m) {
    return std::array<const core::GgufReader*,3>{m.reader_.get(),m.mtp_reader_.get(),m.vision_?&m.vision_->LieReader():nullptr};
  }
  static lie_kvc_qwen_geometry Geometry(Session& s) {
    const auto& c=s.model_->config();
    // A separate predictor can be admitted with trunk-only GGUF metadata.
    // Bind the loaded predictor, rather than inferring its presence solely
    // from block_count/nextn_predict_layers in the trunk metadata.
    const uint32_t predictor_layers=s.MtpEnabled()?1u:c.num_layers_all-c.num_layers;
    return {c.num_layers,predictor_layers,c.full_attention_interval,c.num_kv_heads,c.head_dim,
        c.indexer_head_dim,c.ssm_num_v_heads,c.ssm_head_dim,c.ssm_conv_kernel-1,c.SsmConvChannels(),
        c.PleConvHistory(),c.HcDim(),c.vocab_size};
  }
#endif
  static bool Describe(Session& s,uint64_t domain,uint32_t chunk,
                       const lie_state_layout* source,lie_state_layout& out,uint8_t quant=0,uint32_t drafts=0) {
    auto& d=*s.session_;const auto& c=s.model_->config();
    if(!s.valid_||s.LieSteeringActive()||d.spec_tokens_||
       (source?s.Position()!=0:s.tokens_.empty()||s.tokens_.size()!=s.Position()||s.logits_.size()!=s.model_->VocabSize()))return false;
#ifdef LIE_DS4_RUNTIME_CACHE
    const bool mtp=s.MtpEnabled(),vision=bool(s.image_prompt_);
    if(mtp?(!drafts||drafts>LIE_KVC_QWEN_MTP_DEPTHS):drafts!=0)return false;
    if(d.index_capacity_<s.ContextSize()||c.compress_ratio!=4||c.ple_layer<0||
       (!source&&(d.blocks_!=s.Position()/4||
         (mtp&&(s.hidden_base_>s.Position()||d.mtp_.position<s.hidden_base_||
                d.mtp_.position>s.Position()||d.mtp_.blocks!=d.mtp_.position/4)))))return false;
    if(source&&(source->domain!=domain||source->context_tokens>s.ContextSize()||
       source->prefill_chunk!=chunk||source->format!=((mtp||vision)?LIE_STATE_KVC_AUX:LIE_STATE_KVC)||
       source->model_id!=5||source->quant_bits!=quant||(mtp&&source->model_data[4]!=drafts)))return false;
    const auto g=Geometry(s);
    const lie_kvc_qwen_frontier f{source?source->context_tokens:s.ContextSize(),chunk,
        source?source->model_data[0]:s.ContextSize(),source?source->token_count:s.Position(),
        source?source->model_data[1]:(mtp?d.mtp_.position:0),vision?s.image_prompt_->rope.Delta():0};
    lie_error error{};
    const uint32_t hidden=mtp?(source?source->model_data[3]:s.KeptHiddenRows()):0;
    if(hidden>f.tokens||hidden>d.owner_->max_speculative()||(mtp&&f.mtp_tokens<f.tokens-hidden))return false;
    const auto rc=mtp&&vision?lie_kvc_qwen_mtp_vision_state_plan(&g,&f,domain,5,quant,hidden,drafts,&out,&error):
        vision?lie_kvc_qwen_vision_state_plan(&g,&f,domain,5,quant,&out,&error):
        mtp?lie_kvc_qwen_mtp_state_plan(&g,&f,domain,5,quant,hidden,drafts,&out,&error):
        lie_kvc_qwen_state_plan(&g,&f,domain,5,quant,&out,&error);
    return rc==LIE_OK&&
        (!source||lie_state_layout_equal(source,&out));
#else
    (void)quant;(void)drafts;
    if(s.MtpEnabled()||s.image_prompt_)return false;
    if(source&&(source->domain!=domain||source->context_tokens>s.ContextSize()||
                source->prefill_chunk!=chunk||source->representation_version!=LIE_QWEN_STATE_REPRESENTATION))return false;
    out={};out.domain=domain;out.context_tokens=source?source->context_tokens:s.ContextSize();out.prefill_chunk=chunk;
    out.token_count=source?source->token_count:s.Position();
    out.model_data[0]=source?source->model_data[0]:d.blocks_;
    if(source)for(unsigned i=1;i<8;++i)if(source->model_data[i])return false;
    const lie_qwen_state_geometry geometry{
        c.num_layers,c.full_attention_interval,c.ssm_conv_kernel-1,c.SsmConvChannels(),
        c.ssm_num_v_heads,c.ssm_head_dim,c.AttentionKvDim(),c.indexer_head_dim,c.compress_ratio,
        c.ple_layer>=0?c.PleConvHistory():0,c.HcDim(),static_cast<uint32_t>(d.ngram_.prev.size()),
        c.vocab_size,d.index_capacity_};
    return lie_qwen_state_layout(&geometry,&out)!=0;
#endif
  }
  static lie_status Copy(Session& s,const lie_state_layout& layout,void* bytes,bool restore,
                   const std::atomic<bool>& cancelled,std::string& error) {
    auto& d=*s.session_;const auto& c=s.model_->config();auto stream=d.owner_->stream();
#ifdef LIE_DS4_RUNTIME_CACHE
    const auto geometry=Geometry(s);uint64_t payload=0;
    if(!lie_state_validate(&layout,&payload)){error="invalid DS4 component layout";return LIE_INVALID;}
    auto limits=lie_kvc_default_limits(payload);
    limits.cancelled=[](void* p){return static_cast<const std::atomic<bool>*>(p)->load()?1:0;};
    limits.userdata=const_cast<std::atomic<bool>*>(&cancelled);
    lie_error detail{};
    const bool vision=bool(s.image_prompt_);
    lie_kvc_span positions{};std::array<unsigned char,32> scope{};
    if(vision){
      if(s.image_prompt_->cache_identity.size()!=32){error="missing prepared vision scope";return LIE_INVALID;}
      std::copy(s.image_prompt_->cache_identity.begin(),s.image_prompt_->cache_identity.end(),scope.begin());
      const lie_state_section *part=nullptr;
      for(unsigned i=0;i<layout.section_count;++i)if(layout.sections[i].role==LIE_KVC_QWEN_POSITIONS)part=&layout.sections[i];
      if(!part||part->bytes!=16ull*layout.token_count){error="missing vision position section";return LIE_INVALID;}
      auto* rows=static_cast<unsigned char*>(bytes)+part->offset;
      // Validate each row against fresh prepared geometry before any upload.
      // Capture uses the exact position-section alias: no N*16 scratch copy.
      for(uint32_t i=0;i<layout.token_count;++i){
        if(!(i%4096)&&cancelled.load()){error="cancelled vision position binding";return LIE_CANCELLED;}
        const auto p=s.image_prompt_->rope.Position(i);const int32_t row[4]={p[0],p[1],p[2],0};
        if(restore){if(std::memcmp(rows+16ull*i,row,16)){error="vision positions differ from prepared input";return LIE_INVALID;}}
        else std::memcpy(rows+16ull*i,row,16);
      }
      positions={rows,static_cast<size_t>(part->bytes)};
    }
    const bool mtp=layout.model_data[3]!=0;
    auto controller=s.draft_length_;
    if(restore){
      const auto rc=mtp&&vision?lie_kvc_qwen_mtp_vision_state_check(&geometry,&layout,s.model_->config().ple_eos_token,
          {static_cast<const unsigned char*>(bytes),static_cast<size_t>(payload)},positions,scope.data(),&limits,&detail):vision?lie_kvc_qwen_vision_state_check(&geometry,&layout,s.model_->config().ple_eos_token,
          {static_cast<const unsigned char*>(bytes),static_cast<size_t>(payload)},positions,scope.data(),&limits,&detail):lie_kvc_qwen_state_check(&geometry,&layout,s.model_->config().ple_eos_token,
          {static_cast<const unsigned char*>(bytes),static_cast<size_t>(payload)},&limits,&detail);
      if(rc!=LIE_OK){error=detail.message;return rc;}
      if(mtp){
        lie_kvc_qwen_mtp_controller c{};
        const auto decoded=lie_kvc_qwen_mtp_state_controller(&layout,
            {static_cast<const unsigned char*>(bytes),static_cast<size_t>(payload)},&c,&detail);
        if(decoded!=LIE_OK){error=detail.message;return decoded;}
        MtpLengthState state{};
        std::copy(std::begin(c.successes),std::end(c.successes),state.successes.begin());
        std::copy(std::begin(c.failures),std::end(c.failures),state.failures.begin());
        state.retry_tokens=c.retry_tokens;state.probe_depth=c.probe_depth;
        state.explored_depth=c.explored_depth;state.probe_delay=c.probe_delay;state.failed_depths=c.failed_depths;
        if(!controller.Restore(state)){error="MTP controller does not fit destination";return LIE_INVALID;}
      }
    }
#endif
    auto checked=[&](hipError_t rc){if(rc==hipSuccess)return true;error=hipGetErrorString(rc);return false;};
    // All subsequent transfers complete before their source/destination can be
    // released. No borrowed buffer survives this call, even on cancellation.
    if(!checked(hipStreamSynchronize(stream)))return LIE_BACKEND_FAILED;
    if(restore){
#ifdef LIE_DS4_RUNTIME_CACHE
      if(vision)d.RestoreVisionLayout(s.image_prompt_->rope,stream);
#endif
      s.tokens_.resize(layout.token_count);s.logits_.resize(s.model_->VocabSize());
      s.valid_=false; // No usable frontier until every component is committed.
      // A prefix destination has no useful speculative scratch. This releases
      // existing rollback rows only; the next decode admits what it needs.
      d.TrimRollback(0);
    }
    auto transfer=[&](void* bound,unsigned char* host,size_t size,bool device){
      if(!bound){error="missing bound state component";return false;}
      if(!device){if(restore)std::memcpy(bound,host,size);else std::memcpy(host,bound,size);return true;}
      const auto rc=restore?hipMemcpyAsync(bound,host,size,hipMemcpyHostToDevice,stream):
                            hipMemcpyAsync(host,bound,size,hipMemcpyDeviceToHost,stream);
      return checked(rc)&&checked(hipStreamSynchronize(stream));
    };
    for(unsigned i=0;i<layout.section_count;++i){
      if(cancelled.load()){error="cancelled state transfer";return LIE_CANCELLED;}
      const auto& part=layout.sections[i];auto* host=static_cast<unsigned char*>(bytes)+part.offset;
      void* bound=nullptr;bool device=true;
      switch(part.role){
#ifdef LIE_DS4_RUNTIME_CACHE
        case LIE_STATE_HEADER:case LIE_STATE_SCALAR:case LIE_KVC_QWEN_POSITIONS:case LIE_STATE_AUXILIARY:case LIE_STATE_CACHE_SCOPE:continue;
        case LIE_KVC_QWEN_MTP_RESIDUAL:bound=d.mtp_.h;break;
        case LIE_KVC_QWEN_MTP_HIDDEN:bound=d.mtp_.target_hidden;break;
        case LIE_STATE_NGRAM:
          if(restore){for(size_t j=0;j<d.ngram_.prev.size();++j){
              int32_t token=-1;if(j<layout.token_count)std::memcpy(&token,host+4*j,4);d.ngram_.prev[j]=token;}}
          continue;
#endif
        case LIE_STATE_TOKENS:bound=s.tokens_.data();device=false;break;
        case LIE_STATE_LOGITS:bound=s.logits_.data();device=false;break;
#ifndef LIE_DS4_RUNTIME_CACHE
        case LIE_STATE_NGRAM:bound=d.ngram_.prev.data();device=false;break;
#endif
        case LIE_STATE_PLE:bound=d.ple_history_;break;
        case LIE_STATE_CONV:bound=d.linear_.at(part.layer).conv_state;break;
        case LIE_STATE_RECURRENT:bound=d.linear_.at(part.layer).state;break;
        case LIE_STATE_K:bound=part.layer==c.num_layers?d.mtp_.k_cache:d.attention_.at(part.layer).k_cache;break;
        case LIE_STATE_V:bound=part.layer==c.num_layers?d.mtp_.v_cache:d.attention_.at(part.layer).v_cache;break;
        case LIE_STATE_BLOCK_KEYS:bound=part.layer==c.num_layers?d.mtp_.block_k:d.attention_.at(part.layer).block_k;break;
        case LIE_STATE_INDEX:{
#ifdef LIE_DS4_RUNTIME_CACHE
          bound=part.layer==c.num_layers?d.mtp_.index_k:d.attention_.at(part.layer).index_k;break;
#else
          const auto width=part.shape[1];const auto rows=part.shape[0];
          const auto begin=layout.model_data[0]*s.model_->config().compress_ratio;
          const auto first=begin&(d.index_capacity_-1);
          const auto tail=std::min<uint64_t>(rows,d.index_capacity_-first);
          auto* ring=d.attention_.at(part.layer).index_k;
          if(!ring){error="missing bound index ring";return LIE_BACKEND_FAILED;}
          if(!transfer(ring+first*width,host,tail*width*sizeof(float),true))return LIE_BACKEND_FAILED;
          if(rows>tail&&!transfer(ring,host+tail*width*sizeof(float),(rows-tail)*width*sizeof(float),true))return LIE_BACKEND_FAILED;
          continue;
#endif
        }
        default:error="unknown bound state component";return LIE_BACKEND_FAILED;
      }
      if(!transfer(bound,host,static_cast<size_t>(part.bytes),device))return LIE_BACKEND_FAILED;
    }
#ifdef LIE_DS4_RUNTIME_CACHE
    if(!restore){
      lie_status rc;
      if(mtp){
        const auto state=s.draft_length_.State();lie_kvc_qwen_mtp_controller c{};
        std::copy(state.successes.begin(),state.successes.end(),std::begin(c.successes));
        std::copy(state.failures.begin(),state.failures.end(),std::begin(c.failures));
        c.retry_tokens=state.retry_tokens;c.probe_depth=state.probe_depth;c.explored_depth=state.explored_depth;
        c.probe_delay=state.probe_delay;c.failed_depths=state.failed_depths;
        rc=vision?lie_kvc_qwen_mtp_vision_state_finish(&geometry,&layout,s.model_->config().ple_eos_token,&c,positions,scope.data(),
            bytes,static_cast<size_t>(payload),&limits,&detail):lie_kvc_qwen_mtp_state_finish(&geometry,&layout,s.model_->config().ple_eos_token,&c,
            bytes,static_cast<size_t>(payload),&limits,&detail);
      }else rc=vision?lie_kvc_qwen_vision_state_finish(&geometry,&layout,s.model_->config().ple_eos_token,positions,scope.data(),
          bytes,static_cast<size_t>(payload),&limits,&detail):lie_kvc_qwen_state_finish(&geometry,&layout,s.model_->config().ple_eos_token,
          bytes,static_cast<size_t>(payload),&limits,&detail);
      if(rc!=LIE_OK){error=detail.message;return rc;}
    }
#endif
    if(restore){
      d.position_=layout.token_count;
#ifdef LIE_DS4_RUNTIME_CACHE
      d.blocks_=layout.token_count/4;
#else
      d.blocks_=layout.model_data[0];
#endif
      d.spec_base_=layout.token_count;d.spec_tokens_=0;
#ifdef LIE_DS4_RUNTIME_CACHE
      d.mtp_.position=layout.model_data[1];d.mtp_.blocks=d.mtp_.position/4;
      s.hidden_base_=layout.token_count-layout.model_data[3];
      if(mtp)s.draft_length_=controller;else s.draft_length_.Reset();
#else
      d.mtp_.position=0;d.mtp_.blocks=0;s.hidden_base_=layout.token_count;s.draft_length_.Reset();
#endif
      s.draft_token_=0;s.stats_={};s.valid_=true;
    }
    return LIE_OK;
  }
};
}
#endif
