// SPDX-License-Identifier: MIT
// Storage/exception glue only; history and penalty algorithms belong to C17.
#ifndef LIE_GUFO_HISTORY_HPP
#define LIE_GUFO_HISTORY_HPP
#include "lie/sampling_history.h"
#include "src/core/sampling.hpp"
#include <new>
#include <span>
#include <stdexcept>
#include <vector>
namespace lie_gufo {
inline lie_sampling_history_options
history_options(const gufo::sampling::SamplingConfig &c) {
  lie_sampling_history_options o;
  lie_sampling_history_options_init(&o);
  o.repeat_last_n = c.repeat_last_n;
  o.generated = c.frequency_penalty != 0 || c.presence_penalty != 0;
  o.repetition = c.repeat_penalty != 1 && c.repeat_last_n != 0;
  return o;
}
class HistoryStorage {
  std::vector<gufo::sampling::TokenId> &tokens_;
  std::vector<gufo::sampling::TokenPenalty> &penalties_;
  static int grow_tokens(void *ctx, size_t n, uint32_t **p,
                         size_t *cap) noexcept {
    try {
      auto &v = static_cast<HistoryStorage *>(ctx)->tokens_;
      v.resize(n);
      *p = v.data();
      *cap = v.size();
      return 0;
    } catch (...) {
      return 1;
    }
  }
  static int grow_penalties(void *ctx, size_t n, lie_sampling_penalty **p,
                            size_t *cap) noexcept {
    try {
      auto &v = static_cast<HistoryStorage *>(ctx)->penalties_;
      v.resize(n);
      *p = v.data();
      *cap = v.size();
      return 0;
    } catch (...) {
      return 1;
    }
  }

public:
  lie_sampling_history state;
  HistoryStorage(std::vector<gufo::sampling::TokenId> &tokens,
                 std::vector<gufo::sampling::TokenPenalty> &penalties)
      : tokens_(tokens), penalties_(penalties),
        state{tokens.data(),    tokens.size(),    tokens.size(),
              penalties.data(), penalties.size(), penalties.size(),
              grow_tokens,      grow_penalties,   this} {}
  ~HistoryStorage() {
    // Only remove unpublished trivial entries; never allocate during unwind.
    tokens_.resize(state.token_count);
    penalties_.resize(state.penalty_count);
  }
  HistoryStorage(const HistoryStorage &) = delete;
  HistoryStorage &operator=(const HistoryStorage &) = delete;
};
inline void history_check(lie_sampling_history_status rc) {
  switch (rc) {
  case LIE_HISTORY_OK:
    return;
  case LIE_HISTORY_INVALID:
    throw std::invalid_argument("invalid C17 sampling history/options");
  case LIE_HISTORY_RESOURCE:
    throw std::bad_alloc();
  case LIE_HISTORY_OVERFLOW:
    throw std::overflow_error("generated token count overflow");
  }
  throw std::logic_error("unknown C17 sampling history status");
}
inline void history_reset(const gufo::sampling::SamplingConfig &c,
                          std::vector<gufo::sampling::TokenId> &tokens,
                          std::vector<gufo::sampling::TokenPenalty> &penalties,
                          std::span<const gufo::sampling::TokenId> input) {
  auto options = history_options(c);
  HistoryStorage storage(tokens, penalties);
  history_check(lie_sampling_history_reset(&options, &storage.state,
                                           input.data(), input.size()));
}
inline void history_accept(const gufo::sampling::SamplingConfig &c,
                           std::vector<gufo::sampling::TokenId> &tokens,
                           std::vector<gufo::sampling::TokenPenalty> &penalties,
                           std::span<const gufo::sampling::TokenId> input) {
  auto options = history_options(c);
  HistoryStorage storage(tokens, penalties);
  history_check(lie_sampling_history_accept(&options, &storage.state,
                                            input.data(), input.size()));
}
} // namespace lie_gufo
#endif
