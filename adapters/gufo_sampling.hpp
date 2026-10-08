// SPDX-License-Identifier: MIT
// Transitional dense glue; C17 history has separate storage-only glue.
#ifndef LIE_GUFO_SAMPLING_HPP
#define LIE_GUFO_SAMPLING_HPP
#include "lie/sampling.h"
#include "gufo_sampling_storage.hpp"
#include "src/core/sampling.hpp"
#include <span>
#include <stdexcept>
namespace lie_gufo {
inline lie_sampling_options dense_options(const gufo::sampling::SamplingConfig& c) {
  lie_sampling_options o;lie_sampling_options_init(&o);
  o.temperature=c.temperature;o.top_k=c.top_k;o.top_p=c.top_p;
  o.min_p=c.min_p;o.min_keep=c.min_keep;o.repeat_penalty=c.repeat_penalty;
  o.frequency_penalty=c.frequency_penalty;o.presence_penalty=c.presence_penalty;
  return o;
}
inline lie_sampling_row dense_row(std::span<const float> logits,
    const gufo::sampling::SamplingConfig& c,
    std::span<const gufo::sampling::TokenPenalty> p,
    std::span<const uint8_t> allowed={}) {
  return {logits.data(),logits.size(),p.data(),p.size(),c.logit_bias.data(),
    c.logit_bias.size(),allowed.empty()?nullptr:allowed.data(),allowed.size()};
}
inline void dense_check(lie_sampling_status rc) {
  if(rc==LIE_SAMPLING_OK)return;
  if(rc==LIE_SAMPLING_INVALID)throw std::invalid_argument("invalid C17 sampling row/options");
  if(rc==LIE_SAMPLING_RESOURCE)throw std::bad_alloc();
  if(rc==LIE_SAMPLING_NO_FINITE)throw std::runtime_error("logit distribution contains no finite values");
  throw std::runtime_error("sampling penalties or normalization produced a non-finite value");
}
inline uint32_t dense_greedy(std::span<const float> logits,
    const gufo::sampling::SamplingConfig& c,
    std::span<const gufo::sampling::TokenPenalty> p,
    std::span<const uint8_t> allowed={}) {
  auto o=dense_options(c);auto r=dense_row(logits,c,p,allowed);uint32_t token=0;
  dense_check(lie_sampling_greedy(&r,&o,&token));return token;
}
inline ProbabilityStorage dense_distribution(
    std::span<const float> logits,const gufo::sampling::SamplingConfig& c,
    std::span<const gufo::sampling::TokenPenalty> p) {
  auto o=dense_options(c);auto r=dense_row(logits,c,p);
  ProbabilityStorage entries;
  auto w=entries.workspace();size_t count=0;
  dense_check(lie_sampling_build(&r,&o,&w,&count));entries.publish(count);return entries;
}
}
#endif
