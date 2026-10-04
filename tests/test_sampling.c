/* SPDX-License-Identifier: MIT */
/* Mathematical/ownership fixtures; no model forward, weights or GPU. */
#include "lie/sampling.h"
#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int grow(void *ctx, size_t n, lie_sampling_probability **p, size_t *cap) {
  size_t limit = *(size_t *)ctx;
  if (n > limit) return 1;
  void *next = realloc(*p, n*sizeof(**p));
  if (!next) return 1;
  *p = next; *cap = n; return 0;
}
int main(void) {
  lie_sampling_options o; lie_sampling_options_init(&o);
  float logits[] = {0, 1, 1, NAN, INFINITY, -INFINITY};
  lie_sampling_row r = {.logits=logits,.count=6};
  uint32_t token = 99;
  assert(lie_sampling_greedy(&r,&o,&token)==LIE_SAMPLING_OK && token==1);
  uint8_t mask[] = {1,0,1,1,1,1};
  r.allowed=mask;r.allowed_count=6;
  assert(lie_sampling_greedy(&r,&o,&token)==LIE_SAMPLING_OK && token==2);
  memset(mask,0,sizeof(mask));token=99;
  assert(lie_sampling_greedy(&r,&o,&token)==LIE_SAMPLING_NO_FINITE && token==99);
  r.allowed=NULL;r.allowed_count=0;
  lie_sampling_penalty penalties[] = {{1,2,1},{2,1,1}};
  r.penalties=penalties;r.penalty_count=2;
  o.repeat_penalty=2;o.frequency_penalty=.5f;o.presence_penalty=.25f;
  assert(lie_sampling_greedy(&r,&o,&token)==LIE_SAMPLING_OK && token==0);
  float bias[] = {0,0,1};r.bias=bias;r.bias_count=3;
  assert(lie_sampling_greedy(&r,&o,&token)==LIE_SAMPLING_OK && token==2);
  assert(lie_sampling_penalize(-2,2,.5f,.25f,1,2)==-5.25);
  size_t limit=8192,count=99;
  lie_sampling_workspace w={.grow=grow,.context=&limit};
  r.penalties=NULL;r.penalty_count=0;r.bias=NULL;r.bias_count=0;
  lie_sampling_options_init(&o);o.temperature=1;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==3);
  double denom=1+2*exp(1);
  assert(w.entries[0].token==0 && fabs(w.entries[0].value-1/denom)<1e-15);
  assert(w.entries[1].token==1 && w.entries[1].value==w.entries[2].value);
  o.top_k=2;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==2);
  assert(w.entries[0].token==1 && w.entries[1].token==2 && w.entries[0].value==.5);
  o.top_p=.4f;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==1);
  o.min_keep=2;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==2);
  lie_sampling_options_init(&o);o.temperature=.25f;o.min_p=.9f;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==2);
  assert(w.entries[0].token==1 && w.entries[1].token==2);
  float *large=calloc(4097,sizeof(*large));assert(large);
  r=(lie_sampling_row){.logits=large,.count=4097};
  lie_sampling_options_init(&o);o.temperature=1;o.top_p=.75f;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==3073);
  for(size_t i=0;i<count;++i)assert(w.entries[i].token==i);
  for(size_t i=0;i<4097;++i)large[i]=(float)i;
  o.top_k=7;o.top_p=1;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==7);
  for(size_t i=0;i<count;++i)assert(w.entries[i].token==4096-i);
  o.top_k=0;o.top_p=.999f;o.min_p=1;o.min_keep=5;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==5);
  free(large);free(w.entries);w=(lie_sampling_workspace){.grow=grow,.context=&limit};
  limit=1;r=(lie_sampling_row){.logits=logits,.count=6};count=99;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_RESOURCE && !count);
  free(w.entries);w=(lie_sampling_workspace){0};o.temperature=0;
  lie_sampling_probability single;
  w.entries=&single;w.capacity=1;
  assert(lie_sampling_build(&r,&o,&w,&count)==LIE_SAMPLING_OK && count==1);
  uint64_t seed=77, saved=seed;
  assert(lie_sampling_draw(w.entries,count,&seed,&token)==LIE_SAMPLING_OK && seed==saved);
  lie_sampling_probability probabilities[]={{10,.25},{20,.75}};
  unsigned totals[2]={0};seed=77;
  for(unsigned i=0;i<100000;++i){
    assert(lie_sampling_draw(probabilities,2,&seed,&token)==LIE_SAMPLING_OK);
    assert(token==10||token==20);++totals[token==20];
  }
  assert(totals[0]>24000 && totals[0]<26000);
  seed=0;uint64_t first=lie_sampling_next_random(&seed);
  assert(first==UINT64_C(973819730272012410));
  assert(seed==UINT64_C(285734347287933762));
  probabilities[0].value=NAN;saved=seed;token=99;
  assert(lie_sampling_draw(probabilities,2,&seed,&token)==LIE_SAMPLING_INVALID);
  assert(seed==saved && token==99);
  penalties[1].token=1;r.penalties=penalties;r.penalty_count=2;
  assert(lie_sampling_greedy(&r,&o,&token)==LIE_SAMPLING_INVALID);
  r.penalties=NULL;r.penalty_count=0;o.top_p=NAN;
  assert(lie_sampling_options_validate(&o)==LIE_SAMPLING_INVALID);
  o.top_p=1;o.struct_bytes=0;
  assert(lie_sampling_options_validate(&o)==LIE_SAMPLING_INVALID);
  puts("C17_DENSE_SAMPLING_CONTRACT_PASS_NOT_INFERENCE");
}
