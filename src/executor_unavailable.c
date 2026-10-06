/* SPDX-License-Identifier: MIT */
/* Link-time unavailable implementation. Never supplies model output. */
#include "lie/executor.h"
#include "lie/mtp.h"
#include "lie/vision.h"
#include "lie/state.h"
#include "lie/store.h"
#include "lie/steering.h"
#include <stdio.h>
#define UNUSED __attribute__((unused))
static lie_status unavailable(lie_error *e) {
    if (e) snprintf(e->message,sizeof(e->message),"This binary was built without the Gufo HIP adapter");
    return LIE_UNSUPPORTED;
}
const char *lie_backend_name(void) { return "unavailable"; }
const char *lie_backend_ownership(void) { return "none"; }
const char *lie_backend_dense_sampling(void) { return "none"; }
const char *lie_backend_source_pin(void) { return "none"; }
lie_status lie_backend_open(const char *p UNUSED, const lie_model_options *o UNUSED, lie_model **m UNUSED, lie_error *e) { return unavailable(e); }
int lie_backend_is_synthetic(void) { return 0; }
lie_status lie_gufo_open(const char *p UNUSED, const lie_model_options *o UNUSED, lie_model **m UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_model_get_info(lie_model *m UNUSED, lie_model_info *i UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_model_close(lie_model **m UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_model_tokenize(lie_model *m UNUSED, const char *s UNUSED, size_t n UNUSED, int32_t *t UNUSED, size_t c UNUSED, size_t *r UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_model_token_text(lie_model *m UNUSED, int32_t t UNUSED, char *s UNUSED, size_t c UNUSED, size_t *r UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_model_chat_tokens(lie_model *m UNUSED, const lie_chat_message *s UNUSED, size_t n UNUSED, int32_t *t UNUSED, size_t c UNUSED, size_t *r UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_model_chat_tokens_ex(lie_model *m UNUSED, const lie_chat_template *s UNUSED, int32_t *t UNUSED, size_t c UNUSED, size_t *r UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_sequence_create(lie_model *m UNUSED, lie_sequence **s UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_sequence_close(lie_sequence **s UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_sequence_prefill(lie_sequence *s UNUSED, const int32_t *t UNUSED, size_t n UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_sequence_decode(lie_sequence *s UNUSED, lie_decode_result *r UNUSED, lie_error *e) { return unavailable(e); }
lie_status lie_sequence_logits(lie_sequence *s UNUSED, float *o UNUSED, size_t c UNUSED, size_t *r UNUSED, lie_error *e) { return unavailable(e); }
void lie_sequence_cancel(lie_sequence *s UNUSED) { }

lie_status lie_sequence_configure(lie_sequence *s UNUSED,const lie_generation_options *o UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequence_set_eos_policy(lie_sequence *s UNUSED,lie_eos_policy p UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequence_constrain(lie_sequence *s UNUSED,
                                  const lie_generation_constraints *o UNUSED,
                                  lie_error *e) {
  return unavailable(e);
}
lie_status lie_sequence_sampling_logits(lie_sequence *s UNUSED, float *p UNUSED,
                                        size_t c UNUSED, size_t *n UNUSED,
                                        lie_error *e) {
  return unavailable(e);
}

lie_status lie_backend_open_batch(const char *p UNUSED,const lie_model_options *o UNUSED,uint32_t w UNUSED,lie_model **m UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequences_decode(lie_sequence *const *s UNUSED,size_t n UNUSED,lie_decode_outcome *o UNUSED,lie_error *e) { return unavailable(e); }

int lie_backend_prefix_state_supported(void) { return 0; }
const char *lie_backend_state_format(void) { return "none"; }
lie_status lie_model_attention_dispatch_snapshot(lie_model *m UNUSED,
    lie_attention_dispatch_info *out,lie_error *e) {
  if(!out||out->abi_version!=LIE_ATTENTION_DISPATCH_ABI||out->struct_bytes!=sizeof(*out)) {
    if(e)snprintf(e->message,sizeof(e->message),"invalid attention dispatch snapshot");
    return LIE_INVALID;
  }
  lie_attention_dispatch_info_init(out);
  return LIE_OK;
}
lie_status lie_model_state_identity(lie_model *m UNUSED,lie_state_identity *id UNUSED,uint64_t *d UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequence_state_describe(lie_sequence *s UNUSED,const lie_state_layout *from UNUSED,lie_state_layout *out UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequence_state_read(lie_sequence *s UNUSED,const lie_state_layout *l UNUSED,void *p UNUSED,size_t n UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequence_state_write(lie_sequence *s UNUSED,const lie_state_layout *l UNUSED,const void *p UNUSED,size_t n UNUSED,lie_error *e) { return unavailable(e); }

lie_status lie_model_chat_anchor(lie_model *m UNUSED,const int32_t *t UNUSED,size_t n UNUSED,size_t *o UNUSED,lie_error *e){return unavailable(e);}

lie_status lie_backend_open_mtp(const char *p UNUSED,const lie_model_options *o UNUSED,uint32_t w UNUSED,const char *d UNUSED,uint32_t n UNUSED,lie_model **m UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequences_decode_mtp(lie_sequence *const *s UNUSED,const uint32_t *l UNUSED,size_t n UNUSED,lie_mtp_outcome *o UNUSED,lie_error *e){return unavailable(e);}

lie_status lie_model_mtp_info(lie_model *m UNUSED,lie_mtp_info *i UNUSED,lie_error *e){return unavailable(e);}

lie_status lie_backend_open_vision(const char *p UNUSED,const lie_model_options *o UNUSED,uint32_t w UNUSED,const char *v UNUSED,lie_model **m UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_model_vision_info(lie_model *m UNUSED,lie_vision_info *v UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_model_prepare_vision(lie_model *m UNUSED,const lie_chat_template *t UNUSED,const lie_image_input *i UNUSED,size_t n UNUSED,int32_t *p UNUSED,size_t c UNUSED,size_t *r UNUSED,lie_vision_prompt **o UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequence_attach_vision(lie_sequence *s UNUSED,const lie_vision_prompt *p UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_vision_prompt_close(lie_vision_prompt **p UNUSED,lie_error *e){return unavailable(e);}

lie_status lie_vision_prompt_cache_scope(const lie_vision_prompt *p UNUSED,unsigned char o[32] UNUSED,lie_error *e){return unavailable(e);}

lie_status lie_backend_open_mtp_vision(const char *p UNUSED,const lie_model_options *o UNUSED,uint32_t w UNUSED,const char *d UNUSED,uint32_t n UNUSED,const char *v UNUSED,lie_model **m UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_backend_open_steered(const char *p UNUSED,const lie_model_options *o UNUSED,uint32_t w UNUSED,
  const char *d UNUSED,uint32_t n UNUSED,const char *v UNUSED,const lie_steering_model_options *s UNUSED,
  lie_model **m UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_model_steering_info(lie_model *m UNUSED,lie_steering_model_info *s UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequence_configure_steering(lie_sequence *s UNUSED,const lie_steering_settings *o UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequence_change_steering(lie_sequence *s UNUSED,const lie_steering_settings *o UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequence_steering_info(lie_sequence *s UNUSED,lie_steering_policy_info *o UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequence_steering_cache_scope(lie_sequence *s UNUSED,const unsigned char in[32] UNUSED,unsigned char out[32] UNUSED,lie_error *e){return unavailable(e);}
