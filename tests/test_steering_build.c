/* SPDX-License-Identifier: MIT */
/* Native CLI/input/format/failure oracle; synthetic rows are NOT-INFERENCE. */
#include "lie/steering.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
#include <math.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
static void put_file(const char *path, const void *data, size_t n) {
  int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600); assert(fd>=0);
  assert(write(fd,data,n)==(ssize_t)n); assert(!close(fd));
}
static int run(const char *binary, const char *model, const char *target, const char *contrast,
               const char *directory, const char *extra, const char *value) {
  pid_t child=fork(); assert(child>=0);
  if (!child) {
    const char *argv[32]={binary,"--model",model,"--target-prompts",target,
      "--contrast-prompts",contrast,"--output-dir",directory,"--context","32",
      "--prefill-chunk","2","--components","both",NULL};
    if (extra && !strcmp(extra,"--components")) argv[14]=value;
    else if (extra) { argv[15]=extra; argv[16]=value; }
    execv(binary,(char *const *)argv); _exit(127);
  }
  struct timespec pause={0,10000000}; int status=0;
  for (unsigned k=0;k<1500;++k) {
    pid_t got=waitpid(child,&status,WNOHANG);
    if (got==child) {assert(WIFEXITED(status));return WEXITSTATUS(status);}
    assert(got==0 || (got<0 && errno==EINTR)); nanosleep(&pause,NULL);
  }
  /* Only the unreaped direct child owned by this fixture may be signalled. */
  assert(!kill(child,SIGKILL)); assert(waitpid(child,&status,0)==child);
  assert(!"owned native fixture timeout"); return 1;
}
static bool exists(const char *dir, const char *name) {
  char path[4096]; assert(snprintf(path,sizeof(path),"%s/%s",dir,name)>0);
  struct stat s; if (!lstat(path,&s)) return true; assert(errno==ENOENT); return false;
}
static void hash_bytes(const void *data, size_t n, char hex[65]) {
  unsigned char bytes[32]; unsigned count=0;
  assert(EVP_Digest(data,n,bytes,&count,EVP_sha256(),NULL) && count==32);
  for (unsigned i=0;i<32;++i) snprintf(hex+2*i,3,"%02x",bytes[i]);
}
static uint64_t field(json_object *j, const char *key) {
  json_object *v=NULL; assert(json_object_object_get_ex(j,key,&v)); return json_object_get_uint64(v);
}
static void verify_bank(const char *dir, const char *name, const char *hash) {
  /* Independently specified binary32 values: [0.6,0.8],[-0.8,0.6]. */
  const unsigned char expected[16]={0x9a,0x99,0x19,0x3f,0xcd,0xcc,0x4c,0x3f,
    0xcd,0xcc,0x4c,0xbf,0x9a,0x99,0x19,0x3f};
  char path[4096],actual_hash[65]; snprintf(path,sizeof(path),"%s/%s",dir,name);
  int fd=open(path,O_RDONLY|O_NOFOLLOW); assert(fd>=0); unsigned char data[17];
  assert(read(fd,data,sizeof(data))==16 && !close(fd)); assert(!memcmp(data,expected,16));
  hash_bytes(data,16,actual_hash); assert(!strcmp(actual_hash,hash));
  lie_steering_geometry g={LIE_STEERING_ABI,sizeof(g),2,2,16}; lie_steering_bank *bank=NULL;
  lie_error error={0}; assert(lie_steering_bank_load(path,&g,&bank,&error)==LIE_OK);
  const float *values=lie_steering_bank_values(bank); assert(values);
  assert(fabsf(values[0]-.6f)<1e-7f && fabsf(values[1]-.8f)<1e-7f &&
    fabsf(values[2]+.8f)<1e-7f && fabsf(values[3]-.6f)<1e-7f);
  lie_steering_bank_release(&bank); assert(!bank);
}
typedef struct { unsigned rows,pairs,banks,prompts; uint64_t raw; } observed;
static observed inspect(const char *dir, int expected_exit, uint64_t expected_pairs, bool raw_mode) {
  char path[4096]; snprintf(path,sizeof(path),"%s/build.jsonl",dir);
  FILE *file=fopen(path,"r"); assert(file); char *line=NULL; size_t capacity=0;
  observed out={0}; bool identity=false,terminal=false; unsigned failed_prefills=0;
  int raw=-1; snprintf(path,sizeof(path),"%s/activations.f32le",dir);
  raw=open(path,O_RDONLY|O_NOFOLLOW); assert(raw>=0 || errno==ENOENT);
  while (getline(&line,&capacity,file)>0) {
    json_object *j=json_tokener_parse(line); assert(j && !terminal);
    const char *name=json_object_get_string(json_object_object_get(j,"event")); assert(name);
    if (!strcmp(name,"identity")) {
      assert(!identity && json_object_get_boolean(json_object_object_get(j,"synthetic")));
      assert(!strcmp(json_object_get_string(json_object_object_get(j,"classification")),"NOT-INFERENCE"));
      assert(!strcmp(json_object_get_string(json_object_object_get(j,"prompt_format")),raw_mode?"raw":"chat-thinking-disabled"));
      identity=true;
    } else if (!strcmp(name,"prompt_begin")) {
      ++out.prompts; json_object *ids=json_object_object_get(j,"token_ids");
      assert(field(j,"physical_tokens")==json_object_array_length(ids));
      assert(field(j,"last_token_position")+1==field(j,"physical_tokens"));
      if (!expected_exit) assert(field(j,"physical_tokens")==3u+(out.prompts==2 || out.prompts==3)+(raw_mode?0u:2u));
    } else if (!strcmp(name,"activation_row")) {
      ++out.rows; uint64_t bytes=field(j,"bytes");
      assert(field(j,"offset_bytes")==out.raw && bytes<=16 && bytes==field(j,"values")*4);
      unsigned char data[16]; assert(raw>=0 && pread(raw,data,(size_t)bytes,(off_t)out.raw)==(ssize_t)bytes);
      out.raw+=bytes;
      if (!expected_exit) assert(field(j,"capture_status")==LIE_OK);
    } else if (!strcmp(name,"prompt_end")) {
      if (!expected_exit) assert(json_object_get_boolean(json_object_object_get(j,"accepted")) &&
        field(j,"prefill_status")==LIE_OK && field(j,"rows")==field(j,"expected_rows"));
      if (field(j,"prefill_status")==LIE_BACKEND_FAILED) {
        ++failed_prefills; assert(!json_object_get_boolean(json_object_object_get(j,"accepted")));
      }
    } else if (!strcmp(name,"pair_accepted")) {
      ++out.pairs; assert(field(j,"accepted_pairs")==out.pairs);
    } else if (!strcmp(name,"bank")) {
      assert(!expected_exit && field(j,"pairs")==expected_pairs && field(j,"bytes")==16);
      verify_bank(dir,json_object_get_string(json_object_object_get(j,"file")),
        json_object_get_string(json_object_object_get(j,"sha256"))); ++out.banks;
    } else if (!strcmp(name,"raw_complete")) {
      assert(!expected_exit && field(j,"bytes")==out.raw);
      unsigned char data[256]; assert(out.raw<=sizeof(data));
      assert(pread(raw,data,(size_t)out.raw,0)==(ssize_t)out.raw); char hash[65]; hash_bytes(data,(size_t)out.raw,hash);
      assert(!strcmp(hash,json_object_get_string(json_object_object_get(j,"sha256"))));
    } else if (!strcmp(name,"complete") || !strcmp(name,"failed")) {
      assert(!strcmp(name,expected_exit?"failed":"complete")); terminal=true;
      assert(field(j,"exit_code")== (uint64_t)expected_exit && field(j,"accepted_pairs")==expected_pairs);
      /* A budget refusal may retain raw bytes whose event could not fit. */
      assert(field(j,"raw_bytes")>=out.raw);
    } else assert(!strcmp(name,"geometry"));
    json_object_put(j);
  }
  assert(identity && terminal && !ferror(file)); free(line); assert(!fclose(file)); if (raw>=0) assert(!close(raw));
  if (!expected_exit) assert(out.pairs==2 && out.prompts==4 && out.banks>0);
  else assert(!out.banks && !exists(dir,"direction.ffn.f32") && !exists(dir,"direction.attention.f32"));
  if (strstr(dir,"after-rows")) assert(failed_prefills==1 && out.rows==4 && out.raw==48);
  return out;
}
int main(int argc, char **argv) {
  assert(argc==3); char *root=strdup(argv[2]); assert(root && mkdtemp(root));
  char target[4096],contrast[4096],directory[4096],special[8192];
  snprintf(target,sizeof(target),"%s/target.txt",root); snprintf(contrast,sizeof(contrast),"%s/contrast.txt",root);
  const char targets[]="Taa\nTbbb\n",contrasts[]="Caaa\r\nCbb";
  put_file(target,targets,sizeof(targets)-1); put_file(contrast,contrasts,sizeof(contrasts)-1);
  snprintf(directory,sizeof(directory),"%s/good",root);
  assert(run(argv[1],":fixture:",target,contrast,directory,NULL,NULL)==0);
  observed good=inspect(directory,0,2,false); assert(good.rows==16 && good.raw==192 && good.banks==2);
  assert(run(argv[1],":fixture:",target,contrast,directory,NULL,NULL)==1); inspect(directory,0,2,false);
  snprintf(directory,sizeof(directory),"%s/raw",root);
  assert(run(argv[1],":fixture:",target,contrast,directory,"--prompt-format","raw")==0); inspect(directory,0,2,true);
  for (unsigned k=0;k<2;++k) {
    const char *names[]={"ffn","attention"}; snprintf(directory,sizeof(directory),"%s/%s",root,names[k]);
    assert(run(argv[1],":fixture:",target,contrast,directory,"--components",names[k])==0);
    observed got=inspect(directory,0,2,false); assert(got.banks==1 && got.rows==8 && got.raw==(k?64:128));
  }
  const char *modes[]={":nan:",":missing:",":duplicate:",":wrong-token:",":fail:",":early-fail:",
    ":zero:",":geometry:",":close-failure:",":model-close-failure:"};
  for (unsigned k=0;k<10;++k) {
    snprintf(directory,sizeof(directory),"%s/%s-%u",root,k==4?"after-rows":"refused",k);
    assert(run(argv[1],modes[k],target,contrast,directory,NULL,NULL)==1); inspect(directory,1,k==6 || k==9?2:0,false);
  }
  const unsigned char *invalid[]={ (const unsigned char *)"",(const unsigned char *)"T\n\n",
    (const unsigned char *)"T\0x\n",(const unsigned char *)"\xed\xa0\x80\n",
    (const unsigned char *)"\xc0\x80\n",(const unsigned char *)" \t\r\n",
    (const unsigned char *)"T\n"};
  const size_t sizes[]={0,3,4,4,3,4,2};
  snprintf(special,sizeof(special),"%s/invalid.txt",root);
  for (unsigned k=0;k<7;++k) {
    put_file(special,invalid[k],sizes[k]); snprintf(directory,sizeof(directory),"%s/bad-input-%u",root,k);
    assert(run(argv[1],":fixture:",special,contrast,directory,NULL,NULL)==1);
    struct stat stat; assert(lstat(directory,&stat)<0 && errno==ENOENT);
  }
  unsigned char *large=malloc(65538); assert(large); memset(large,'T',65537); large[65537]='\n';
  put_file(special,large,65538); free(large); snprintf(directory,sizeof(directory),"%s/line-too-long",root);
  assert(run(argv[1],":fixture:",special,contrast,directory,NULL,NULL)==1); assert(!exists(directory,"build.jsonl"));
  snprintf(special,sizeof(special),"%s/input-link",root); assert(!symlink(target,special));
  snprintf(directory,sizeof(directory),"%s/refuse-link",root);
  assert(run(argv[1],":fixture:",special,contrast,directory,NULL,NULL)==1); assert(!exists(directory,"build.jsonl"));
  snprintf(special,sizeof(special),"%s/input-fifo",root); assert(!mkfifo(special,0600));
  snprintf(directory,sizeof(directory),"%s/refuse-fifo",root);
  assert(run(argv[1],":fixture:",special,contrast,directory,NULL,NULL)==1); assert(!exists(directory,"build.jsonl"));
  const char *extra[]={"--max-pairs","--max-host-bytes","--context","--max-output-bytes","--unknown"};
  const char *values[]={"1","1","0","-1","anything"};
  for (unsigned k=0;k<5;++k) {
    snprintf(directory,sizeof(directory),"%s/bad-options-%u",root,k);
    /* --context is deliberately duplicated and must be rejected. */
    assert(run(argv[1],":fixture:",target,contrast,directory,extra[k],values[k])==(k<2?1:2));
    assert(!exists(directory,"build.jsonl"));
  }
  snprintf(directory,sizeof(directory),"%s/host-budget",root);
  assert(run(argv[1],":fixture:",target,contrast,directory,"--max-host-bytes","256")==1); inspect(directory,1,0,false);
  /* Exhausting the output budget preserves a parseable failed terminal event,
   * earlier rows and accepted pairs, without publishing a partial learned bank. */
  char many[800]; for (unsigned k=0;k<200;++k) memcpy(many+4*k,"Taa\n",4);
  put_file(target,many,sizeof(many)); for (unsigned k=0;k<200;++k) many[4*k]='C';
  put_file(contrast,many,sizeof(many)); snprintf(directory,sizeof(directory),"%s/output-budget",root);
  assert(run(argv[1],":fixture:",target,contrast,directory,"--max-output-bytes","65536")==1);
  snprintf(special,sizeof(special),"%s/build.jsonl",directory);
  FILE *f=fopen(special,"r"); assert(f); char *line=NULL; size_t cap=0; bool failed=false;
  while (getline(&line,&cap,f)>0) {
    json_object *j=json_tokener_parse(line); assert(j && !failed);
    const char *name=json_object_get_string(json_object_object_get(j,"event"));
    assert(strcmp(name,"bank") && strcmp(name,"complete"));
    if (!strcmp(name,"failed")) {failed=true;assert(field(j,"accepted_pairs")>0 && field(j,"raw_bytes")>0);}
    json_object_put(j);
  }
  free(line); assert(!fclose(f) && failed && !exists(directory,"direction.ffn.f32"));
  printf("STEERING_BUILD_INPUT_FORMAT_FAILURE_PASS_NOT_INFERENCE path=%s\n",root);
  free(root); return 0;
}
