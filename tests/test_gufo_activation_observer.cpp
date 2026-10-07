// SPDX-License-Identifier: MIT
#include "gufo_activation_observer.hpp"
#include "lie/steering_capture.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <stdexcept>
struct State { lie_steering_capture *capture{};unsigned calls{};bool throws{}; };
static void observe(void *context,const lie_activation_observation *row) {
  auto *s=static_cast<State *>(context);
  assert(lie_gufo::activation_observer_callback);
  ++s->calls;
  if(s->throws)throw std::runtime_error("fixture callback failure");
  assert(lie_steering_capture_add(s->capture,row,nullptr)==LIE_OK);
}
int main() {
  State s;
  const lie_activation_geometry g={LIE_ACTIVATION_OBSERVER_ABI,sizeof(g),2,3,2,3};
  const lie_steering_capture_options options={LIE_STEERING_CAPTURE_ABI,sizeof(options),g,3,4,4096};
  assert(lie_steering_capture_create(&options,&s.capture,nullptr)==LIE_OK);
  lie_activation_observer o={LIE_ACTIVATION_OBSERVER_ABI,sizeof(o),3,24,observe,&s};
  assert(!lie_gufo::activation_observer&&!lie_gufo::activation_observer_callback);
  {
    lie_gufo::ActivationObservationScope scope(o,g,4);
    o.observe=nullptr;o.context=nullptr; /* Admission copies the callback configuration. */
    assert(lie_gufo::activation_observer==&scope);
    assert(!scope.destination(0,4,0,LIE_ACTIVATION_FFN,3,2));
    assert(!scope.destination(5,1,0,LIE_ACTIVATION_FFN,3,2));
    assert(!scope.destination(4,0,0,LIE_ACTIVATION_FFN,3,2));
    for(unsigned layer=0;layer<2;++layer){
      /* Final one-token tail selects exactly the same physical prompt token. */
      float *a=scope.destination(4,1,layer,LIE_ACTIVATION_ATTENTION,3,1);
      assert(a);std::fill_n(a,3,2.0f);scope.emit(layer,LIE_ACTIVATION_ATTENTION,1);
      float *f=scope.destination(0,5,layer,LIE_ACTIVATION_FFN,3,2);
      assert(f);std::fill_n(f,3,3.0f);std::fill_n(f+3,3,7.0f);
      scope.emit(layer,LIE_ACTIVATION_FFN,2);
    }
    bool threw=false;
    try{(void)scope.destination(4,1,0,LIE_ACTIVATION_FFN,4,2);}catch(const std::logic_error&){threw=true;}
    assert(threw);
  }
  assert(!lie_gufo::activation_observer&&!lie_gufo::activation_observer_callback&&s.calls==4);
  assert(lie_steering_capture_finish(s.capture,LIE_OK,5,nullptr)==LIE_OK);
  for(unsigned i=0;i<6;++i){
    assert(lie_steering_capture_values(s.capture,LIE_ACTIVATION_ATTENTION)[i]==2);
    assert(lie_steering_capture_values(s.capture,LIE_ACTIVATION_FFN)[i]==5);
  }
  lie_steering_capture_destroy(&s.capture);
  s.throws=true;o={LIE_ACTIVATION_OBSERVER_ABI,sizeof(o),1,12,observe,&s};
  try{
    lie_gufo::ActivationObservationScope scope(o,g,4);
    assert(!scope.destination(4,1,0,LIE_ACTIVATION_FFN,3,2));
    scope.emit(0,LIE_ACTIVATION_ATTENTION,1);
    assert(false);
  }catch(const std::runtime_error&){}
  assert(!lie_gufo::activation_observer&&!lie_gufo::activation_observer_callback);
  std::puts("Activation observation scope: PASS (borrowed host fixtures; no GPU copies)");
}
