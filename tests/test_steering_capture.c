/* SPDX-License-Identifier: MIT */
#include "lie/steering_capture.h"
#include "lie/steering_direction.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static lie_steering_capture_options options(void) {
  return (lie_steering_capture_options){.abi_version=LIE_STEERING_CAPTURE_ABI,
    .struct_bytes=sizeof(lie_steering_capture_options),
    .geometry={LIE_ACTIVATION_OBSERVER_ABI,sizeof(lie_activation_geometry),2,3,2,3},
    .components=3,.token_position=17,.max_bytes=4096};
}
static lie_steering_capture_info info(lie_steering_capture *c) {
  lie_steering_capture_info out={.abi_version=LIE_STEERING_CAPTURE_ABI,.struct_bytes=sizeof(out)};
  assert(lie_steering_capture_snapshot(c,&out,NULL)==LIE_OK);return out;
}
static lie_activation_observation row(float *v,unsigned layer,lie_activation_component component) {
  return (lie_activation_observation){.abi_version=LIE_ACTIVATION_OBSERVER_ABI,
    .struct_bytes=sizeof(lie_activation_observation),.component=component,.layer=layer,
    .layers=2,.width=3,.branches=component==LIE_ACTIVATION_FFN?2u:1u,
    .token_position=17,.values=v,.value_count=component==LIE_ACTIVATION_FFN?6u:3u};
}
int main(void) {
  lie_steering_capture *c=NULL;lie_steering_capture_options o=options();
  assert(lie_steering_capture_create(&o,&c,NULL)==LIE_OK);
  const uint64_t budget=info(c).requested_bytes;
  assert(!info(c).ready&&info(c).rows==0&&info(c).expected_rows==4);
  assert(!lie_steering_capture_values(c,LIE_ACTIVATION_FFN));
  float input[]={2,4,6,4,6,8};lie_activation_observation r=row(input,1,LIE_ACTIVATION_FFN);
  r.token_position=18;assert(lie_steering_capture_add(c,&r,NULL)==LIE_INVALID);
  r.token_position=17;r.branches=1;assert(lie_steering_capture_add(c,&r,NULL)==LIE_INVALID);
  r=row(input,1,LIE_ACTIVATION_FFN);input[5]=NAN;
  assert(lie_steering_capture_add(c,&r,NULL)==LIE_INVALID&&info(c).rows==0);
  input[5]=8;assert(lie_steering_capture_add(c,&r,NULL)==LIE_OK);
  assert(lie_steering_capture_add(c,&r,NULL)==LIE_INVALID&&info(c).rows==1);
  r=row(input,0,LIE_ACTIVATION_ATTENTION);assert(lie_steering_capture_add(c,&r,NULL)==LIE_OK);
  r=row(input,0,LIE_ACTIVATION_FFN);assert(lie_steering_capture_add(c,&r,NULL)==LIE_OK);
  r=row(input,1,LIE_ACTIVATION_ATTENTION);assert(lie_steering_capture_add(c,&r,NULL)==LIE_OK);
  memset(input,0,sizeof(input)); /* Ownership is independent of reused callback memory. */
  assert(lie_steering_capture_finish(c,LIE_OK,18,NULL)==LIE_OK&&info(c).ready);
  const float *ffn=lie_steering_capture_values(c,LIE_ACTIVATION_FFN);
  const float *attn=lie_steering_capture_values(c,LIE_ACTIVATION_ATTENTION);
  for(unsigned l=0;l<2;++l){
    assert(ffn[l*3]==3&&ffn[l*3+1]==5&&ffn[l*3+2]==7);
    assert(attn[l*3]==2&&attn[l*3+1]==4&&attn[l*3+2]==6);
  }
  assert(lie_steering_capture_finish(c,LIE_OK,18,NULL)==LIE_INVALID);
  assert(lie_steering_capture_add(c,&r,NULL)==LIE_INVALID&&info(c).rows==4);
  assert(!lie_steering_capture_values(c,(lie_activation_component)3));
  lie_steering_capture_destroy(&c);assert(!c);
  lie_steering_capture_destroy(&c);lie_steering_capture_destroy(NULL);
  o.max_bytes=budget-1;
  assert(lie_steering_capture_create(&o,&c,NULL)==LIE_RESOURCE_LIMIT&&!c);
  o.max_bytes=budget;assert(lie_steering_capture_create(&o,&c,NULL)==LIE_OK);
  assert(lie_steering_capture_finish(c,LIE_OK,18,NULL)==LIE_INVALID&&!info(c).ready);
  assert(lie_steering_capture_add(c,&r,NULL)==LIE_INVALID);
  lie_steering_capture_destroy(&c);
  /* Complete rows cannot turn a failed/cancelled prefill into a learned input. */
  for(unsigned failure=0;failure<3;++failure){
    o=options();o.components=LIE_ACTIVATION_ATTENTION;
    assert(lie_steering_capture_create(&o,&c,NULL)==LIE_OK);
    r=row(input,0,LIE_ACTIVATION_ATTENTION);assert(lie_steering_capture_add(c,&r,NULL)==LIE_OK);
    r.layer=1;assert(lie_steering_capture_add(c,&r,NULL)==LIE_OK);
    lie_status s=failure==0?LIE_BACKEND_FAILED:failure==1?LIE_CANCELLED:LIE_OK;
    assert(lie_steering_capture_finish(c,s,failure==2?17:18,NULL)==(s==LIE_OK?LIE_INVALID:s));
    assert(!info(c).ready&&info(c).rows==2&&!lie_steering_capture_values(c,LIE_ACTIVATION_ATTENTION));
    assert(lie_steering_capture_finish(c,LIE_OK,18,NULL)==LIE_INVALID);
    lie_steering_capture_destroy(&c);
  }
  o=options();o.geometry.layers=UINT32_MAX;o.geometry.width=UINT32_MAX;o.max_bytes=UINT64_MAX;
  assert(lie_steering_capture_create(&o,&c,NULL)==LIE_RESOURCE_LIMIT&&!c);
  o=options();o.components=4;
  assert(lie_steering_capture_create(&o,&c,NULL)==LIE_INVALID&&!c);
  o=options();o.token_position=UINT64_MAX;
  assert(lie_steering_capture_create(&o,&c,NULL)==LIE_INVALID&&!c);
  puts("Steering activation collection: PASS (CPU fixtures; no original model capture)");return 0;
}
