/* SPDX-License-Identifier: MIT */
/* Link-time unavailable implementation. Never supplies model output. */
#include "lie/executor.h"
#include "lie/state.h"
#include "lie/store.h"
#include <stdio.h>
#define UNUSED __attribute__((unused))
static lie_status unavailable(lie_error *e) {
    if (e) snprintf(e->message,sizeof(e->message),"This binary was built without the Gufo HIP adapter");
    return LIE_UNSUPPORTED;
}
const char *lie_backend_name(void) { return "unavailable"; }
const char *lie_backend_ownership(void) { return "none"; }
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

lie_status lie_backend_open_batch(const char *p UNUSED,const lie_model_options *o UNUSED,uint32_t w UNUSED,lie_model **m UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequences_decode(lie_sequence *const *s UNUSED,size_t n UNUSED,lie_decode_outcome *o UNUSED,lie_error *e) { return unavailable(e); }

int lie_backend_prefix_state_supported(void) { return 0; }
lie_status lie_model_state_identity(lie_model *m UNUSED,lie_state_identity *id UNUSED,uint64_t *d UNUSED,lie_error *e){return unavailable(e);}
lie_status lie_sequence_state_describe(lie_sequence *s UNUSED,const lie_state_layout *from UNUSED,lie_state_layout *out UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequence_state_read(lie_sequence *s UNUSED,const lie_state_layout *l UNUSED,void *p UNUSED,size_t n UNUSED,lie_error *e) { return unavailable(e); }
lie_status lie_sequence_state_write(lie_sequence *s UNUSED,const lie_state_layout *l UNUSED,const void *p UNUSED,size_t n UNUSED,lie_error *e) { return unavailable(e); }
