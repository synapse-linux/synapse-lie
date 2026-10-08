// SPDX-License-Identifier: MIT
// Private spans/error/move projections; buffer ownership/growth lives in C17.
#ifndef LIE_GUFO_SAMPLING_STORAGE_HPP
#define LIE_GUFO_SAMPLING_STORAGE_HPP
#include "lie/sampling_storage.h"
#include <new>
#include <span>
#include <stdexcept>
namespace lie_gufo {
inline void storage_check(lie_sampling_status rc) {
  if (rc == LIE_SAMPLING_OK) return;
  if (rc == LIE_SAMPLING_RESOURCE) throw std::bad_alloc();
  throw std::invalid_argument("invalid native sampling storage");
}
inline void storage_history_check(lie_sampling_history_status rc) {
  if (rc == LIE_HISTORY_OK) return;
  if (rc == LIE_HISTORY_RESOURCE) throw std::bad_alloc();
  if (rc == LIE_HISTORY_OVERFLOW) throw std::overflow_error("generated token count overflow");
  throw std::invalid_argument("invalid C17 sampling history/options");
}
class ProbabilityStorage {
  lie_sampling_probability_storage storage_{};
public:
  ProbabilityStorage() { storage_check(lie_sampling_probability_storage_init(&storage_, nullptr)); }
  explicit ProbabilityStorage(const lie_sampling_storage_description &d) {
    storage_check(lie_sampling_probability_storage_init(&storage_, &d));
  }
  template<class Range> explicit ProbabilityStorage(const Range &values) : ProbabilityStorage() {
    storage_check(lie_sampling_probability_storage_assign(&storage_, values.data(), values.size()));
  }
  ~ProbabilityStorage() { lie_sampling_probability_storage_release(&storage_); }
  ProbabilityStorage(const ProbabilityStorage &s) : ProbabilityStorage() {
    storage_check(lie_sampling_probability_storage_clone(&storage_, &s.storage_));
  }
  ProbabilityStorage &operator=(const ProbabilityStorage &s) {
    if (this != &s) storage_check(lie_sampling_probability_storage_clone(&storage_, &s.storage_));
    return *this;
  }
  ProbabilityStorage(ProbabilityStorage &&s) noexcept {
    (void)lie_sampling_probability_storage_init(&storage_, nullptr);
    lie_sampling_probability_storage_move(&storage_, &s.storage_);
  }
  ProbabilityStorage &operator=(ProbabilityStorage &&s) noexcept {
    lie_sampling_probability_storage_move(&storage_, &s.storage_); return *this;
  }
  size_t size() const noexcept { return storage_.count; }
  bool empty() const noexcept { return !size(); }
  lie_sampling_probability *data() noexcept { return storage_.entries; }
  const lie_sampling_probability *data() const noexcept { return storage_.entries; }
  const lie_sampling_probability *begin() const noexcept { return data(); }
  const lie_sampling_probability *end() const noexcept { return data() ? data() + size() : nullptr; }
  operator std::span<const lie_sampling_probability>() const noexcept { return {data(), size()}; }
  lie_sampling_workspace workspace() noexcept { return lie_sampling_probability_storage_workspace(&storage_); }
  void clear() noexcept { (void)lie_sampling_probability_storage_publish(&storage_, 0); }
  void publish(size_t count) { storage_check(lie_sampling_probability_storage_publish(&storage_, count)); }
  const lie_sampling_storage_info &info() const noexcept { return storage_.info; }
};
class OwnedHistory {
  lie_sampling_history_storage storage_{};
public:
  OwnedHistory() { storage_history_check(lie_sampling_history_storage_init(&storage_, nullptr)); }
  explicit OwnedHistory(const lie_sampling_storage_description &d) {
    storage_history_check(lie_sampling_history_storage_init(&storage_, &d));
  }
  ~OwnedHistory() { lie_sampling_history_storage_release(&storage_); }
  OwnedHistory(const OwnedHistory &s) : OwnedHistory() {
    storage_history_check(lie_sampling_history_storage_clone(&storage_, &s.storage_));
  }
  OwnedHistory &operator=(const OwnedHistory &s) {
    if (this != &s) storage_history_check(lie_sampling_history_storage_clone(&storage_, &s.storage_));
    return *this;
  }
  OwnedHistory(OwnedHistory &&s) noexcept {
    (void)lie_sampling_history_storage_init(&storage_, nullptr);
    lie_sampling_history_storage_move(&storage_, &s.storage_);
  }
  OwnedHistory &operator=(OwnedHistory &&s) noexcept {
    lie_sampling_history_storage_move(&storage_, &s.storage_); return *this;
  }
  std::span<const uint32_t> tokens() const noexcept { return {storage_.state.tokens, storage_.state.token_count}; }
  std::span<const lie_sampling_penalty> penalties() const noexcept {
    return {storage_.state.penalties, storage_.state.penalty_count};
  }
  void reset(const lie_sampling_history_options &o, std::span<const uint32_t> tokens) {
    storage_history_check(lie_sampling_history_storage_reset(&storage_, &o, tokens.data(), tokens.size()));
  }
  void accept(std::span<const uint32_t> tokens) {
    storage_history_check(lie_sampling_history_storage_accept(&storage_, tokens.data(), tokens.size()));
  }
  const lie_sampling_storage_info &info() const noexcept { return storage_.info; }
};
} // namespace lie_gufo
#endif
