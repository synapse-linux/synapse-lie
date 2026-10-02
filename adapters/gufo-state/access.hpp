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
#include <cstring>
#ifdef LIE_DS4_RUNTIME_CACHE
#include "lie/kvc_state.h"
#ifndef LIE_GUFO_DS4_STATE
#error "DS4 runtime cache requires the verified complete-history provider variant"
#endif
#endif
namespace gufo::models::qwen38_flash_next {
class LieStateAccess {
public:
#ifdef LIE_DS4_RUNTIME_CACHE
  static lie_kvc_qwen_geometry Geometry(Session& s) {
    const auto& c=s.model_->config();
    return {c.num_layers,c.num_layers_all-c.num_layers,c.full_attention_interval,c.num_kv_heads,c.head_dim,
        c.indexer_head_dim,c.ssm_num_v_heads,c.ssm_head_dim,c.ssm_conv_kernel-1,c.SsmConvChannels(),
        c.PleConvHistory(),c.HcDim(),c.vocab_size};
  }
#endif
  static bool Describe(Session& s,uint64_t domain,uint32_t chunk,
                       const lie_state_layout* source,lie_state_layout& out,uint8_t quant=0) {
    auto& d=*s.session_;const auto& c=s.model_->config();
    if(!s.valid_||s.MtpEnabled()||s.image_prompt_||d.spec_tokens_||
       (source?s.Position()!=0:s.tokens_.empty()||s.tokens_.size()!=s.Position()||s.logits_.size()!=s.model_->VocabSize()))return false;
#ifdef LIE_DS4_RUNTIME_CACHE
    if(d.index_capacity_<s.ContextSize()||c.compress_ratio!=4||c.ple_layer<0||
       (!source&&d.blocks_!=s.Position()/4))return false;
    if(source&&(source->domain!=domain||source->context_tokens>s.ContextSize()||
       source->prefill_chunk!=chunk||source->format!=LIE_STATE_KVC||source->model_id!=5||source->quant_bits!=quant))return false;
    const auto g=Geometry(s);
    const lie_kvc_qwen_frontier f{source?source->context_tokens:s.ContextSize(),chunk,
        source?source->model_data[0]:s.ContextSize(),source?source->token_count:s.Position(),0,0};
    lie_error error{};
    return lie_kvc_qwen_state_plan(&g,&f,domain,5,quant,&out,&error)==LIE_OK&&
        (!source||lie_state_layout_equal(source,&out));
#else
    (void)quant;
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
    auto& d=*s.session_;auto stream=d.owner_->stream();
#ifdef LIE_DS4_RUNTIME_CACHE
    const auto geometry=Geometry(s);uint64_t payload=0;
    if(!lie_state_validate(&layout,&payload)){error="invalid DS4 component layout";return LIE_INVALID;}
    auto limits=lie_kvc_default_limits(payload);
    limits.cancelled=[](void* p){return static_cast<const std::atomic<bool>*>(p)->load()?1:0;};
    limits.userdata=const_cast<std::atomic<bool>*>(&cancelled);
    lie_error detail{};
    if(restore){
      const auto rc=lie_kvc_qwen_state_check(&geometry,&layout,s.model_->config().ple_eos_token,
          {static_cast<const unsigned char*>(bytes),static_cast<size_t>(payload)},&limits,&detail);
      if(rc!=LIE_OK){error=detail.message;return rc;}
    }
#endif
    auto checked=[&](hipError_t rc){if(rc==hipSuccess)return true;error=hipGetErrorString(rc);return false;};
    // All subsequent transfers complete before their source/destination can be
    // released. No borrowed buffer survives this call, even on cancellation.
    if(!checked(hipStreamSynchronize(stream)))return LIE_BACKEND_FAILED;
    if(restore){
      s.tokens_.resize(layout.token_count);s.logits_.resize(s.model_->VocabSize());
      s.valid_=false; // No usable frontier until every component is committed.
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
        case LIE_STATE_HEADER:case LIE_STATE_SCALAR:case LIE_KVC_QWEN_POSITIONS:continue;
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
        case LIE_STATE_K:bound=d.attention_.at(part.layer).k_cache;break;
        case LIE_STATE_V:bound=d.attention_.at(part.layer).v_cache;break;
        case LIE_STATE_BLOCK_KEYS:bound=d.attention_.at(part.layer).block_k;break;
        case LIE_STATE_INDEX:{
#ifdef LIE_DS4_RUNTIME_CACHE
          bound=d.attention_.at(part.layer).index_k;break;
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
      auto rc=lie_kvc_qwen_state_finish(&geometry,&layout,s.model_->config().ple_eos_token,
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
      d.spec_base_=layout.token_count;d.spec_tokens_=0;d.mtp_.position=0;d.mtp_.blocks=0;
      s.hidden_base_=layout.token_count;s.draft_token_=0;s.draft_length_.Reset();s.stats_={};s.valid_=true;
    }
    return LIE_OK;
  }
};
}
#endif
