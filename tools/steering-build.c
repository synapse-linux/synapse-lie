/* SPDX-License-Identifier: MIT */
/* Native diagnostic: capture paired last-prompt activations, then learn a bank.
 * Calls the selected executor on its existing owner; no HTTP or extra threads.
 * Capture copies/waits/I/O are diagnostic cost, never throughput evidence. */
#include "lie/steering_capture.h"
#include "lie/steering_direction.h"
#include <errno.h>
#include <fcntl.h>
#include <float.h>
#include <json-c/json.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
               FLT_MAX_EXP == 128, "IEEE754 binary32 required");
#define PROMPT_FILE_LIMIT (32u * 1024u * 1024u)
#define PROMPT_LINE_LIMIT 65536u
#define PAIR_LIMIT 4096u
#define TERMINAL_RESERVE 8192u
static volatile sig_atomic_t interrupted;
static void stop(int n) { (void)n; interrupted = 1; }
typedef struct { const char *text; size_t bytes; } prompt;
typedef struct {
  unsigned char *bytes; size_t size, count; prompt *lines;
  char hash[65];
} prompts;
typedef struct {
  const char *model, *target, *contrast, *output;
  uint32_t context, chunk, components, max_pairs;
  uint64_t host_limit, output_limit;
  lie_rope_profile rope;
  bool raw;
} options;
typedef struct {
  int dir, journal, raw;
  uint64_t written, limit, raw_bytes;
  unsigned char *encode; size_t row_values;
  EVP_MD_CTX *raw_digest;
  bool io_failed;
  lie_error error;
} output;
static bool fail(lie_error *e, const char *s) {
  snprintf(e->message, sizeof(e->message), "%s", s); return false;
}
static bool integer(const char *s, uint64_t min, uint64_t max, uint64_t *out) {
  if (!s || !*s || strspn(s, "0123456789") != strlen(s)) return false;
  char *end = NULL; errno = 0; unsigned long long value = strtoull(s, &end, 10);
  if (errno || *end || value < min || value > max) return false;
  *out = value; return true;
}
static void usage(FILE *f) {
  fputs("Usage: lie-steering-build --model PATH --target-prompts FILE --contrast-prompts FILE --output-dir NEW_DIR [OPTIONS]\n"
        "One nonempty UTF-8 prompt per line; target and contrast line counts must match.\n"
        "  --components ffn|attention|both  (default: ffn)\n"
        "  --prompt-format chat|raw        (default: chat, thinking disabled)\n"
        "  --context TOKENS                (default: 8192, maximum: 1048576)\n"
        "  --prefill-chunk TOKENS          (default: 256)\n"
        "  --rope native|yarn2|yarn4       (default: native)\n"
        "  --max-pairs COUNT               (default/maximum: 4096)\n"
        "  --max-host-bytes BYTES          (default: 268435456)\n"
        "  --max-output-bytes BYTES        (default: 1073741824)\n"
        "Output includes source prompts, physical token IDs, raw rows, build.jsonl and headerless LE-F32 banks.\n"
        "Only a successful complete event authorizes using the banks. Capture is diagnostic, not a benchmark.\n", f);
}
static bool parse(int argc, char **argv, options *o) {
  *o = (options){.context=8192, .chunk=256, .components=LIE_ACTIVATION_FFN,
    .max_pairs=PAIR_LIMIT, .host_limit=UINT64_C(268435456),
    .output_limit=UINT64_C(1073741824), .rope=LIE_ROPE_NATIVE};
  const char *names[] = {"--model", "--target-prompts", "--contrast-prompts", "--output-dir",
    "--components", "--prompt-format", "--context", "--prefill-chunk", "--rope",
    "--max-pairs", "--max-host-bytes", "--max-output-bytes"};
  unsigned seen = 0;
  for (int at = 1; at < argc; at += 2) {
    unsigned k = 0; while (k < 12 && strcmp(argv[at], names[k])) ++k;
    if (k == 12 || (seen & (1u << k)) || at + 1 >= argc || !*argv[at+1]) return false;
    seen |= 1u << k; const char *v = argv[at+1]; uint64_t n = 0;
    switch (k) {
    case 0: o->model=v; break; case 1: o->target=v; break;
    case 2: o->contrast=v; break; case 3: o->output=v; break;
    case 4:
      if (!strcmp(v,"ffn")) o->components=LIE_ACTIVATION_FFN;
      else if (!strcmp(v,"attention")) o->components=LIE_ACTIVATION_ATTENTION;
      else if (!strcmp(v,"both")) o->components=LIE_ACTIVATION_FFN|LIE_ACTIVATION_ATTENTION;
      else return false;
      break;
    case 5: if (strcmp(v,"chat") && strcmp(v,"raw")) return false; o->raw=!strcmp(v,"raw"); break;
    case 8: if (!lie_rope_profile_parse(v,&o->rope)) return false; break;
    default:
      if (!integer(v, k == 11 ? 65536 : 1,
          k == 6 || k == 7 ? LIE_CONTEXT_LIMIT : k == 9 ? PAIR_LIMIT : SIZE_MAX, &n)) return false;
      if (k==6) o->context=(uint32_t)n; else if (k==7) o->chunk=(uint32_t)n;
      else if (k==9) o->max_pairs=(uint32_t)n; else if (k==10) o->host_limit=n; else o->output_limit=n;
    }
  }
  return (seen & 15u) == 15u && o->chunk <= o->context;
}
static bool utf8(const unsigned char *s, size_t n) {
  for (size_t i=0; i<n;) {
    unsigned c=s[i++], need=0, value=0, min=0;
    if (c && c<128) continue;
    if (c>=0xc2 && c<=0xdf) {need=1; value=c&31; min=128;}
    else if (c>=0xe0 && c<=0xef) {need=2; value=c&15; min=2048;}
    else if (c>=0xf0 && c<=0xf4) {need=3; value=c&7; min=65536;}
    else return false;
    if (need>n-i) return false;
    while (need--) { c=s[i++]; if ((c&0xc0)!=0x80) return false; value=(value<<6)|(c&63); }
    if (value<min || value>0x10ffff || (value>=0xd800 && value<=0xdfff)) return false;
  }
  return true;
}
static bool same_stat(const struct stat *a, const struct stat *b) {
  return a->st_dev==b->st_dev && a->st_ino==b->st_ino && a->st_size==b->st_size &&
    a->st_mtim.tv_sec==b->st_mtim.tv_sec && a->st_mtim.tv_nsec==b->st_mtim.tv_nsec &&
    a->st_ctim.tv_sec==b->st_ctim.tv_sec && a->st_ctim.tv_nsec==b->st_ctim.tv_nsec;
}
static bool digest(const void *p, size_t n, char hash[65]) {
  unsigned char bytes[32]; unsigned count=0;
  if (!EVP_Digest(p,n,bytes,&count,EVP_sha256(),NULL) || count!=32) return false;
  for (unsigned i=0;i<32;++i) snprintf(hash+2*i,3,"%02x",bytes[i]);
  return true;
}
static bool read_prompts(const char *path, uint32_t max_pairs, uint64_t *host,
                         uint64_t limit, prompts *p, lie_error *e) {
  int fd=open(path,O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_NOFOLLOW);
  struct stat before, after; bool ok=false;
  if (fd<0) return fail(e,"cannot open regular prompt file without following symlinks");
  if (fstat(fd,&before) || !S_ISREG(before.st_mode) || before.st_size<=0 ||
      before.st_size>PROMPT_FILE_LIMIT || (uint64_t)before.st_size+1>limit-*host) {
    fail(e,"invalid prompt file size/type or host budget"); goto done;
  }
  p->size=(size_t)before.st_size; p->bytes=malloc(p->size+1);
  if (!p->bytes) { fail(e,"cannot allocate prompt input"); goto done; }
  *host+=p->size+1;
  for (size_t at=0;at<p->size;) {
    ssize_t got=read(fd,p->bytes+at,p->size-at);
    if (got<0 && errno==EINTR && !interrupted) continue;
    if (got<=0 || interrupted) { fail(e,"prompt input read failed or interrupted"); goto done; }
    at+=(size_t)got;
  }
  if (fstat(fd,&after) || !same_stat(&before,&after) || !utf8(p->bytes,p->size) ||
      !digest(p->bytes,p->size,p->hash)) { fail(e,"prompt file changed or contains invalid UTF-8/NUL"); goto done; }
  p->bytes[p->size]=0;
  for (size_t at=0;at<p->size;) {
    size_t end=at; while (end<p->size && p->bytes[end]!='\n') ++end;
    size_t content=end-at; if (content && p->bytes[end-1]=='\r') --content;
    bool nonblank=false;
    for (size_t k=0;k<content;++k) if (p->bytes[at+k]!=' ' && p->bytes[at+k]!='\t' && p->bytes[at+k]!='\r') nonblank=true;
    if (!nonblank || content>PROMPT_LINE_LIMIT || ++p->count>max_pairs) {
      fail(e,"empty/oversized prompt line or pair limit exceeded"); goto done;
    }
    at=end+(end<p->size);
  }
  if (p->count*sizeof(*p->lines)>limit-*host ||
      !(p->lines=calloc(p->count,sizeof(*p->lines)))) { fail(e,"prompt index exceeds host budget"); goto done; }
  *host+=p->count*sizeof(*p->lines);
  for (size_t at=0,k=0;at<p->size;++k) {
    size_t end=at; while (end<p->size && p->bytes[end]!='\n') ++end;
    size_t n=end-at; if (n && p->bytes[end-1]=='\r') --n;
    p->lines[k]=(prompt){(const char *)p->bytes+at,n}; at=end+(end<p->size);
  }
  ok=true;
done:
  if (close(fd)) ok=fail(e,"cannot close prompt file");
  return ok;
}
static void free_prompts(prompts *p) { free(p->lines); free(p->bytes); memset(p,0,sizeof(*p)); }
static void string(json_object *j, const char *key, const char *value) {
  json_object_object_add(j,key,json_object_new_string(value));
}
static void number(json_object *j, const char *key, uint64_t n) {
  json_object_object_add(j,key,json_object_new_uint64(n));
}
static json_object *event(const char *name) {
  json_object *j=json_object_new_object(); if (j) string(j,"event",name); return j;
}
static bool write_bytes(output *out, int fd, const void *data, size_t n, bool terminal) {
  uint64_t limit=out->limit-(terminal?0:TERMINAL_RESERVE);
  if ((!terminal && (out->io_failed || interrupted)) || out->written>limit || n>limit-out->written) {
    out->io_failed=true; return fail(&out->error,"output interrupted or exceeds byte budget");
  }
  const unsigned char *p=data;
  for (size_t at=0;at<n;) {
    ssize_t used=write(fd,p+at,n-at);
    if (used<0 && errno==EINTR && (terminal || !interrupted)) continue;
    if (used<=0) { out->io_failed=true; return fail(&out->error,"output write failed"); }
    at+=(size_t)used; out->written+=(uint64_t)used;
    if (fd==out->raw) out->raw_bytes+=(uint64_t)used;
  }
  return true;
}
static bool emit(output *out, json_object *j, bool terminal) {
  if (!j) { out->io_failed=true; return fail(&out->error,"cannot allocate journal event"); }
  const char *s=json_object_to_json_string_ext(j,JSON_C_TO_STRING_PLAIN);
  size_t bytes=s?strlen(s):0;
  uint64_t limit=out->limit-(terminal?0:TERMINAL_RESERVE);
  bool room=out->written<limit && bytes<limit-out->written;
  if (!room) { out->io_failed=true; fail(&out->error,"journal event exceeds output budget"); }
  bool ok=s && room && write_bytes(out,out->journal,s,bytes,terminal) &&
    write_bytes(out,out->journal,"\n",1,terminal);
  json_object_put(j); return ok;
}
static int create_file(output *out, const char *name) {
  int fd=openat(out->dir,name,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
  if (fd<0) fail(&out->error,"cannot create exclusive output file");
  return fd;
}
static bool copy_source(output *out, const prompts *p, const char *name) {
  int fd=create_file(out,name); if (fd<0) return false;
  bool ok=write_bytes(out,fd,p->bytes,p->size,false) && !fsync(fd);
  if (close(fd)) ok=false;
  if (!ok && !out->error.message[0]) fail(&out->error,"cannot preserve source prompts");
  return ok;
}
static bool write_floats(output *out, int fd, const float *values, size_t n, EVP_MD_CTX *hash) {
  for (size_t at=0;at<n;) {
    size_t count=n-at; if (count>out->row_values) count=out->row_values;
    for (size_t k=0;k<count;++k) {
      uint32_t bits; memcpy(&bits,values+at+k,4);
      for (unsigned b=0;b<4;++b) out->encode[k*4+b]=(unsigned char)(bits>>(b*8));
    }
    if (!write_bytes(out,fd,out->encode,count*4,false) ||
        !EVP_DigestUpdate(hash,out->encode,count*4)) return false;
    at+=count;
  }
  return true;
}
typedef struct {
  output *out; lie_steering_capture *capture; lie_activation_geometry geometry;
  uint32_t components; size_t pair; const char *side;
  bool failed; lie_error error;
} observer_context;
static void observe(void *context, const lie_activation_observation *row) {
  observer_context *c=context;
  if (c->out->io_failed) { c->failed=true; return; }
  lie_error error={0}; lie_status status=lie_steering_capture_add(c->capture,row,&error);
  if (status!=LIE_OK && !c->failed) { c->failed=true; c->error=error; }
  json_object *j=event("activation_row"); number(j,"pair",c->pair); string(j,"side",c->side);
  number(j,"capture_status",status); number(j,"offset_bytes",c->out->raw_bytes);
  bool valid=row && row->abi_version==LIE_ACTIVATION_OBSERVER_ABI && row->struct_bytes==sizeof(*row) &&
    row->layers==c->geometry.layers && row->width==c->geometry.width && row->layer<row->layers &&
    (row->component==LIE_ACTIVATION_ATTENTION || row->component==LIE_ACTIVATION_FFN) &&
    (row->component & c->components) &&
    row->branches==(row->component==LIE_ACTIVATION_FFN?c->geometry.ffn_branches:1u) &&
    (uint64_t)row->width*row->branches==row->value_count && row->values &&
    row->value_count<=c->out->row_values;
  if (row) {
    number(j,"component",row->component); number(j,"layer",row->layer);
    number(j,"width",row->width); number(j,"branches",row->branches);
    number(j,"token_position",row->token_position); number(j,"values",row->value_count);
  }
  number(j,"bytes",valid?row->value_count*4:0);
  /* Invalid geometry never authorizes dereferencing a borrowed row. Complete
   * bounded rows, including nonfinite/duplicate refusals, remain raw evidence. */
  if (valid && !write_floats(c->out,c->out->raw,row->values,row->value_count,c->out->raw_digest)) c->failed=true;
  if (!emit(c->out,j,false)) c->failed=true;
}
static bool capture_prompt(lie_model *model, const options *o, const lie_activation_geometry *g,
  prompt p, const char *side, size_t pair, int32_t *tokens, uint64_t *host,
  output *out, lie_steering_capture **capture, lie_error *error) {
  size_t n=0; lie_sequence *sequence=NULL; lie_status status=LIE_INVALID;
  uint64_t completed=0; bool ok=false, prefill_attempted=false; lie_error numeric_error={0};
  lie_chat_message message={LIE_CHAT_USER,p.text,p.bytes};
  status=o->raw?lie_model_tokenize(model,p.text,p.bytes,tokens,o->context,&n,error):
    lie_model_chat_tokens(model,&message,1,tokens,o->context,&n,error);
  if (status!=LIE_OK || !n || n>o->context) {
    if (status==LIE_OK) fail(error,"invalid physical prompt size");
    return false;
  }
  lie_steering_capture_options co={.abi_version=LIE_STEERING_CAPTURE_ABI,.struct_bytes=sizeof(co),
    .geometry=*g,.components=o->components,.token_position=n-1,.max_bytes=o->host_limit-*host};
  if (lie_steering_capture_create(&co,capture,error)!=LIE_OK) return false;
  lie_steering_capture_info ci={.abi_version=LIE_STEERING_CAPTURE_ABI,.struct_bytes=sizeof(ci)};
  if (lie_steering_capture_snapshot(*capture,&ci,error)!=LIE_OK) return false;
  *host+=ci.requested_bytes;
  observer_context c={.out=out,.capture=*capture,.geometry=*g,.components=o->components,.pair=pair,.side=side};
  lie_activation_observer observer={.abi_version=LIE_ACTIVATION_OBSERVER_ABI,.struct_bytes=sizeof(observer),
    .components=o->components,.max_row_bytes=out->row_values*4,.observe=observe,.context=&c};
  json_object *j=event("prompt_begin"); number(j,"pair",pair); string(j,"side",side);
  number(j,"physical_tokens",n); number(j,"last_token_position",n-1);
  json_object *ids=json_object_new_array();
  for (size_t k=0;k<n;++k) json_object_array_add(ids,json_object_new_int(tokens[k]));
  json_object_object_add(j,"token_ids",ids);
  if (!emit(out,j,false)) goto done;
  status=lie_sequence_create(model,&sequence,error);
  if (status!=LIE_OK) goto done;
  for (size_t at=0;at<n;) {
    if (interrupted) { status=LIE_CANCELLED; fail(error,"capture interrupted"); break; }
    at=n-at>o->chunk?at+o->chunk:n;
    prefill_attempted=true;
    status=at==n?lie_sequence_prefill_observed(sequence,tokens,at,&observer,error):
      lie_sequence_prefill(sequence,tokens,at,error);
    if (status!=LIE_OK) break;
    completed=at;
  }
done:
  numeric_error=*error;
  lie_error finish_error={0};
  lie_status finish=lie_steering_capture_finish(*capture,status,completed,&finish_error);
  lie_steering_capture_snapshot(*capture,&ci,NULL);
  ok=finish==LIE_OK && !c.failed && !out->io_failed && !interrupted;
  if (!ok) {
    if (out->io_failed) *error=out->error;
    else if (c.failed) *error=c.error;
    else if (status!=LIE_OK) *error=numeric_error;
    else *error=finish_error;
    if (!error->message[0]) fail(error,"activation capture refused or interrupted");
  }
  if (sequence) {
    lie_error close_error={0};
    if (lie_sequence_close(&sequence,&close_error)!=LIE_OK && ok) { ok=false; *error=close_error; }
  }
  j=event("prompt_end"); number(j,"pair",pair); string(j,"side",side);
  json_object_object_add(j,"prefill_attempted",json_object_new_boolean(prefill_attempted));
  if (prefill_attempted) number(j,"prefill_status",status);
  else json_object_object_add(j,"prefill_status",NULL);
  number(j,"completed_prefix_tokens",completed);
  number(j,"rows",ci.rows); number(j,"expected_rows",ci.expected_rows);
  json_object_object_add(j,"accepted",json_object_new_boolean(ok)); string(j,"error",ok?"":error->message);
  if (!emit(out,j,false)) { ok=false; *error=out->error; }
  return ok;
}
static bool stage_bank(output *out, lie_steering_direction *d, const char *name, char hash[65], lie_error *e) {
  lie_steering_direction_info info={.abi_version=LIE_STEERING_DIRECTION_ABI,.struct_bytes=sizeof(info)};
  if (lie_steering_direction_snapshot(d,&info,e)!=LIE_OK || !info.ready) return false;
  char pending[64]; snprintf(pending,sizeof(pending),"%s.partial",name);
  int fd=create_file(out,pending); if (fd<0) { *e=out->error; return false; }
  EVP_MD_CTX *ctx=EVP_MD_CTX_new(); unsigned char bytes[32]; unsigned n=0;
  bool ok=ctx && EVP_DigestInit_ex(ctx,EVP_sha256(),NULL) &&
    write_floats(out,fd,lie_steering_direction_values(d),(size_t)info.layers*info.width,ctx) &&
    EVP_DigestFinal_ex(ctx,bytes,&n) && n==32 && !fsync(fd);
  EVP_MD_CTX_free(ctx); if (close(fd)) ok=false;
  if (!ok) { *e=out->error; if (!e->message[0]) fail(e,"cannot stage direction bank"); return false; }
  for (unsigned k=0;k<n;++k) snprintf(hash+k*2,3,"%02x",bytes[k]);
  return true;
}
int main(int argc, char **argv) {
  if (argc==2 && !strcmp(argv[1],"--help")) { usage(stdout); return 0; }
  options o; if (!parse(argc,argv,&o)) { usage(stderr); return 2; }
  struct sigaction action={0}; action.sa_handler=stop; sigemptyset(&action.sa_mask);
  if (sigaction(SIGINT,&action,NULL) || sigaction(SIGTERM,&action,NULL)) return 1;
  prompts target={0},contrast={0}; uint64_t host=0,peak=0; size_t accepted=0;
  lie_model *model=NULL; lie_steering_direction *directions[2]={NULL,NULL};
  lie_steering_capture *captures[2]={NULL,NULL}; int32_t *tokens=NULL;
  output out={.dir=-1,.journal=-1,.raw=-1,.limit=o.output_limit}; lie_error error={0};
  const uint32_t component[2]={LIE_ACTIVATION_FFN,LIE_ACTIVATION_ATTENTION};
  const char *bank_names[2]={"direction.ffn.f32","direction.attention.f32"};
  bool ok=false;
  if (!read_prompts(o.target,o.max_pairs,&host,o.host_limit,&target,&error) ||
      !read_prompts(o.contrast,o.max_pairs,&host,o.host_limit,&contrast,&error) ||
      target.count!=contrast.count) {
    if (!error.message[0]) fail(&error,"target/contrast prompt counts differ");
    goto done;
  }
  if (mkdir(o.output,0700)) { fail(&error,"output directory must be new"); goto done; }
  struct stat named,opened;
  out.dir=open(o.output,O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW);
  if (out.dir<0 || lstat(o.output,&named) || fstat(out.dir,&opened) ||
      !S_ISDIR(named.st_mode) || named.st_dev!=opened.st_dev || named.st_ino!=opened.st_ino) {
    fail(&error,"cannot bind newly created output directory"); goto done;
  }
  out.journal=create_file(&out,"build.jsonl"); if (out.journal<0) {error=out.error;goto done;}
  json_object *j=event("identity"); string(j,"schema","synapse-lie.steering-build.v1");
  string(j,"program","lie-steering-build"); string(j,"build_id",LIE_BUILD_ID);
  string(j,"engine",lie_backend_name()); string(j,"source_pin",lie_backend_source_pin());
  json_object_object_add(j,"synthetic",json_object_new_boolean(lie_backend_is_synthetic()));
  string(j,"classification",lie_backend_is_synthetic()?"NOT-INFERENCE":"ACTIVATION-CAPTURE-QUALITY-UNQUALIFIED");
  string(j,"method","paired target-minus-contrast; compensated FP64; unit L2 per trunk layer");
  string(j,"capture","last physical prompt token; FFN branch mean; predictor/decode excluded; fresh unsteered sequences");
  string(j,"encoding","headerless IEEE754-F32-little-endian"); string(j,"model",o.model);
  string(j,"target_sha256",target.hash); string(j,"contrast_sha256",contrast.hash);
  number(j,"pairs",target.count); number(j,"components",o.components); number(j,"context",o.context);
  number(j,"prefill_chunk",o.chunk); string(j,"rope",lie_rope_profile_name(o.rope));
  string(j,"prompt_format",o.raw?"raw":"chat-thinking-disabled");
  number(j,"max_host_bytes",o.host_limit); number(j,"max_output_bytes",o.output_limit);
  string(j,"host_budget_scope","owned prompt/index/token/encoding buffers, direction learners and collectors; excludes JSON/stdio/crypto/allocator overhead and executor resources");
  if (!emit(&out,j,false) || !copy_source(&out,&target,"target-prompts.txt") ||
      !copy_source(&out,&contrast,"contrast-prompts.txt")) {error=out.error;goto done;}
  lie_model_options mo={LIE_EXECUTOR_ABI,sizeof(mo),o.context,o.chunk,o.rope};
  lie_model_info info={0}; lie_activation_geometry g={.abi_version=LIE_ACTIVATION_OBSERVER_ABI,.struct_bytes=sizeof(g)};
  if (lie_backend_open(o.model,&mo,&model,&error)!=LIE_OK ||
      lie_model_get_info(model,&info,&error)!=LIE_OK ||
      lie_model_activation_geometry(model,&g,&error)!=LIE_OK) goto done;
  if (info.abi_version!=LIE_EXECUTOR_ABI || info.context_tokens!=o.context || info.prefill_capacity<o.chunk ||
      g.abi_version!=LIE_ACTIVATION_OBSERVER_ABI || g.struct_bytes!=sizeof(g) || !g.layers || !g.width ||
      !g.ffn_branches || (g.components&o.components)!=o.components) {
    fail(&error,"model admission/capture geometry does not match requested controls"); goto done;
  }
  uint64_t rows=(uint64_t)g.width*((o.components&LIE_ACTIVATION_FFN)?g.ffn_branches:1u);
  uint64_t token_bytes=(uint64_t)o.context*sizeof(*tokens);
  if (rows>SIZE_MAX/4 || token_bytes>o.host_limit-host || rows>(o.host_limit-host-token_bytes)/4) {
    fail(&error,"token/row buffers exceed host budget"); goto done;
  }
  out.row_values=(size_t)rows; out.encode=malloc((size_t)rows*4); tokens=malloc((size_t)token_bytes);
  if (!out.encode || !tokens) {fail(&error,"cannot allocate bounded token/row buffers");goto done;}
  host+=rows*4+token_bytes;
  j=event("geometry"); number(j,"layers",g.layers); number(j,"width",g.width);
  number(j,"ffn_branches",g.ffn_branches); number(j,"observer_row_bytes",rows*4);
  number(j,"executor_weights_bytes",info.weights_bytes); number(j,"executor_session_bytes",info.session_bytes);
  if (!emit(&out,j,false)) {error=out.error;goto done;}
  /* The provider separately allocates its bounded borrowed-row buffer for the
   * observed call. Charge that simultaneous row reservation to our peak. */
  if (rows*4>o.host_limit-host) {fail(&error,"observer row exceeds aggregate host budget");goto done;}
  host+=rows*4;
  for (unsigned k=0;k<2;++k) if (o.components&component[k]) {
    lie_steering_direction_options d={.abi_version=LIE_STEERING_DIRECTION_ABI,.struct_bytes=sizeof(d),
      .layers=g.layers,.width=g.width,.max_pairs=target.count,.max_bytes=o.host_limit-host};
    lie_steering_direction_info di={.abi_version=LIE_STEERING_DIRECTION_ABI,.struct_bytes=sizeof(di)};
    if (lie_steering_direction_create(&d,&directions[k],&error)!=LIE_OK ||
        lie_steering_direction_snapshot(directions[k],&di,&error)!=LIE_OK) goto done;
    host+=di.requested_bytes;
  }
  out.raw=create_file(&out,"activations.f32le"); out.raw_digest=EVP_MD_CTX_new();
  if (out.raw<0 || !out.raw_digest || !EVP_DigestInit_ex(out.raw_digest,EVP_sha256(),NULL)) {
    fail(&error,"cannot create raw activation output/digest");goto done;
  }
  peak=host;
  for (size_t pair=0;pair<target.count;++pair) {
    bool pair_ok=capture_prompt(model,&o,&g,target.lines[pair],"target",pair,tokens,&host,&out,&captures[0],&error);
    if (host>peak) peak=host;
    if (pair_ok) pair_ok=capture_prompt(model,&o,&g,contrast.lines[pair],"contrast",pair,tokens,&host,&out,&captures[1],&error);
    if (host>peak) peak=host;
    for (unsigned k=0;k<2 && pair_ok;++k) if (directions[k])
      pair_ok=lie_steering_direction_add_pair(directions[k],lie_steering_capture_values(captures[0],component[k]),
        lie_steering_capture_values(captures[1],component[k]),(size_t)g.layers*g.width,&error)==LIE_OK;
    for (unsigned k=0;k<2;++k) if (captures[k]) {
      lie_steering_capture_info ci={.abi_version=LIE_STEERING_CAPTURE_ABI,.struct_bytes=sizeof(ci)};
      lie_steering_capture_snapshot(captures[k],&ci,NULL); host-=ci.requested_bytes;
      lie_steering_capture_destroy(&captures[k]);
    }
    if (!pair_ok) goto done;
    ++accepted; j=event("pair_accepted"); number(j,"pair",pair); number(j,"accepted_pairs",accepted);
    if (!emit(&out,j,false)) {error=out.error;goto done;}
  }
  for (unsigned k=0;k<2;++k) if (directions[k] && lie_steering_direction_finish(directions[k],&error)!=LIE_OK) goto done;
  /* Retire the executor successfully before any final bank name is published. */
  if (lie_model_close(&model,&error)!=LIE_OK) goto done;
  char hashes[2][65]={{0}};
  for (unsigned k=0;k<2;++k) if (directions[k] && !stage_bank(&out,directions[k],bank_names[k],hashes[k],&error)) goto done;
  if (interrupted) {fail(&error,"capture interrupted before bank publication");goto done;}
  unsigned char raw_hash[32]; unsigned raw_hash_bytes=0; char raw_hex[65];
  if (!EVP_DigestFinal_ex(out.raw_digest,raw_hash,&raw_hash_bytes) || raw_hash_bytes!=32 || fsync(out.raw)) {
    fail(&error,"cannot seal raw activation output");goto done;
  }
  for (unsigned k=0;k<32;++k) snprintf(raw_hex+k*2,3,"%02x",raw_hash[k]);
  j=event("raw_complete"); string(j,"file","activations.f32le"); string(j,"sha256",raw_hex); number(j,"bytes",out.raw_bytes);
  if (!emit(&out,j,false)) {error=out.error;goto done;}
  for (unsigned k=0;k<2;++k) if (directions[k]) {
    char pending[64]; snprintf(pending,sizeof(pending),"%s.partial",bank_names[k]);
    if (linkat(out.dir,pending,out.dir,bank_names[k],0)) {fail(&error,"cannot publish bank without replacing files");goto done;}
    j=event("bank"); string(j,"file",bank_names[k]); string(j,"sha256",hashes[k]);
    number(j,"layers",g.layers); number(j,"width",g.width); number(j,"bytes",(uint64_t)g.layers*g.width*4);
    number(j,"pairs",accepted);
    if (!emit(&out,j,false)) {error=out.error;goto done;}
    if (unlinkat(out.dir,pending,0)) {fail(&error,"cannot retire owned bank staging name");goto done;}
  }
  if (fsync(out.dir)) {fail(&error,"cannot seal output directory");goto done;}
  ok=true;
done:
  if (host>peak) peak=host;
  for (unsigned k=0;k<2;++k) lie_steering_capture_destroy(&captures[k]);
  if (model) {
    lie_error close_error={0};
    if (lie_model_close(&model,&close_error)!=LIE_OK && ok) {ok=false;error=close_error;}
  }
  if (out.raw>=0 && close(out.raw)) {ok=false;fail(&error,"cannot close raw activation output");}
  EVP_MD_CTX_free(out.raw_digest);
  if (out.journal>=0) {
    if (!ok && !error.message[0]) fail(&error,"steering build failed");
    json_object *terminal=event(ok?"complete":"failed"); number(terminal,"exit_code",ok?0:1);
    number(terminal,"accepted_pairs",accepted); number(terminal,"raw_bytes",out.raw_bytes);
    number(terminal,"owned_host_peak_bytes",peak); string(terminal,"error",ok?"":error.message);
    /* Terminal reserve permits preserving a failed budget-limited capture. */
    if (!emit(&out,terminal,true) || fsync(out.journal)) ok=false;
    if (close(out.journal)) ok=false;
  }
  if (out.dir>=0 && close(out.dir)) ok=false;
  for (unsigned k=0;k<2;++k) lie_steering_direction_destroy(&directions[k]);
  free(tokens); free(out.encode); free_prompts(&target); free_prompts(&contrast);
  if (!ok) fprintf(stderr,"Steering build failed: %s\n",error.message[0]?error.message:"output finalization failed");
  else printf("Steering banks prepared: %zu pairs; output=%s; quality remains unqualified.\n",accepted,o.output);
  return ok?0:1;
}
