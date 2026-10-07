// SPDX-License-Identifier: MIT
// Private borrowed-row bridge; all model types remain inside the provider.
#ifndef LIE_GUFO_ACTIVATION_OBSERVER_HPP
#define LIE_GUFO_ACTIVATION_OBSERVER_HPP
#include "lie/activation_observer.h"
#include <cstdint>
#include <stdexcept>
#include <vector>
namespace lie_gufo {
class ActivationObservationScope;
inline thread_local ActivationObservationScope *activation_observer = nullptr;
inline thread_local bool activation_observer_callback = false;
class ActivationObservationScope {
public:
  ActivationObservationScope(const lie_activation_observer &observer,
      const lie_activation_geometry &geometry, uint64_t target)
      : previous_(activation_observer), installed_(observer), geometry_(geometry), target_(target),
        row_(static_cast<size_t>(geometry.width) *
          ((observer.components & LIE_ACTIVATION_FFN) ? geometry.ffn_branches : 1u)) {
    activation_observer = this;
  }
  ~ActivationObservationScope() { activation_observer = previous_; }
  ActivationObservationScope(const ActivationObservationScope &) = delete;
  ActivationObservationScope &operator=(const ActivationObservationScope &) = delete;
  float *destination(uint64_t start, uint32_t tokens, uint32_t layer,
      lie_activation_component component, uint32_t width, uint32_t branches) {
    if (!tokens || start > target_ || target_ - start != tokens - 1 ||
        !(installed_.components & component)) return nullptr;
    if (layer >= geometry_.layers || width != geometry_.width ||
        (component != LIE_ACTIVATION_ATTENTION && component != LIE_ACTIVATION_FFN) ||
        branches != (component == LIE_ACTIVATION_FFN ? geometry_.ffn_branches : 1u))
      throw std::logic_error("activation observation geometry mismatch");
    return row_.data();
  }
  void emit(uint32_t layer, lie_activation_component component, uint32_t branches) {
    lie_activation_observation event{};
    event.abi_version = LIE_ACTIVATION_OBSERVER_ABI; event.struct_bytes = sizeof(event);
    event.component = component; event.layer = layer; event.layers = geometry_.layers;
    event.width = geometry_.width; event.branches = branches; event.token_position = target_;
    event.values = row_.data(); event.value_count = static_cast<size_t>(geometry_.width) * branches;
    activation_observer_callback = true;
    try { installed_.observe(installed_.context, &event); }
    catch (...) { activation_observer_callback = false; throw; }
    activation_observer_callback = false;
  }
private:
  ActivationObservationScope *previous_;
  const lie_activation_observer installed_;
  const lie_activation_geometry geometry_;
  const uint64_t target_;
  std::vector<float> row_;
};
} // namespace lie_gufo
#endif
