/* SPDX-License-Identifier: MIT */
/* Accounting/lifetime tests with synthetic ABI children only. No inference. */
#include "bench_native.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static char root[2400];
static unsigned runs;
static void require(bool ok,const char *why){
  if(!ok){fprintf(stderr,"Walk fixture failed: %s; retained: %s\n",why,root);exit(1);}
}
static void path(char out[2600],const char *name){
  require(snprintf(out,2600,"%s/%s",root,name)<2600,"path bound");
}
static void save(const char *name,const void *bytes,size_t n){
  char p[2600];path(p,name);FILE *f=fopen(p,"wb");require(f!=NULL,"fixture file");
  require(fwrite(bytes,1,n,f)==n&&!fclose(f),"fixture write");
}
static bool contains(const char *name,const char *text){
  char p[2600];path(p,name);FILE *f=fopen(p,"r");require(f!=NULL,"export read");
  char line[8192];bool found=false;while(fgets(line,sizeof(line),f))found=found||strstr(line,text)!=NULL;
  require(!ferror(f)&&!fclose(f),"export read completion");return found;
}
static void run(char *const argv[],int expected){
  char log[2600],name[80];snprintf(name,sizeof(name),"child-%u.log",runs++);path(log,name);
  pid_t pid=fork();require(pid>=0,"fork");
  if(!pid){
    int fd=open(log,O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0)_exit(126);
    if(dup2(fd,STDOUT_FILENO)<0||dup2(fd,STDERR_FILENO)<0)_exit(126);
    close(fd);
    setenv("PATH","/nonexistent-walk-native-only",1);
    execv(argv[0],argv);_exit(127);
  }
  int status;while(waitpid(pid,&status,0)<0)require(errno==EINTR,"wait");
  if(!WIFEXITED(status)||WEXITSTATUS(status)!=expected){
    FILE *f=fopen(log,"r");if(f){char line[1024];while(fgets(line,sizeof(line),f))fputs(line,stderr);fclose(f);}
    require(false,"actual child exit");
  }
}
static json_object *load(const char *p){
  nb_error e={0};json_object *rows=nb_read(p,true,&e);require(rows!=NULL,e.message);return rows;
}
static json_object *nth(json_object *rows,const char *kind,size_t n){
  for(size_t i=0;i<json_object_array_length(rows);++i){
    json_object *r=json_object_array_get_idx(rows,i);
    if(!strcmp(nb_string(r,"event"),kind)&&!n--)return r;
  }
  require(false,"missing event");return NULL;
}
static size_t count(json_object *rows,const char *kind){
  size_t n=0;for(size_t i=0;i<json_object_array_length(rows);++i)
    n+=!strcmp(nb_string(json_object_array_get_idx(rows,i),"event"),kind);
  return n;
}
static void write_rows(const char *p,json_object *rows){
  FILE *f=fopen(p,"wx");require(f!=NULL,"mutation output");
  for(size_t i=0;i<json_object_array_length(rows);++i)
    require(fputs(nb_encoded(json_object_array_get_idx(rows,i)),f)>=0&&fputc('\n',f)!=EOF,"mutation write");
  require(!fclose(f),"mutation close");
}
static void report(const char *reporter,const char *input,const char *name,int expected,const char *reference){
  char out[2600];path(out,name);
  char *args[]={(char *)reporter,(char *)input,"--output",out,NULL,NULL,NULL,NULL};
  if(reference){args[4]="--compare";args[5]=(char *)reference;}
  run(args,expected);
}
static void mutation(const char *reporter,json_object *original,unsigned which){
  json_object *rows=nb_copy(original);require(rows!=NULL,"mutation copy");
  json_object *id=json_object_array_get_idx(rows,0),*input=nth(rows,"input",1),
              *sample=nth(rows,"sample",0),*restore=nth(rows,"walk_restore",0);
  switch(which){
    case 0:nb_str(input,"physical_ids_sha256","bad");break;
    case 1:nb_num(input,"depth",0);break;
    case 2:nb_num(sample,"checkpoint_begin_monotonic_ns",nb_number(sample,"prefill_begin_monotonic_ns"));break;
    case 3:nb_num(restore,"end_monotonic_ns",INT64_MAX);break;
    case 4:nb_str(restore,"prefill_logits_sha256","bad");break;
    case 5:nb_num(restore,"retained_bytes",0);break;
    case 6:nb_num(restore,"point",2);break;
    case 7:nb_str(id,"measurement_contract","full-prefill-v1");break;
    case 8:nb_num(id,"snapshot_budget_bytes",INT64_MAX);break;
    case 9:nb_num(input,"users",2);break;
    case 10:nb_num(nth(rows,"corpus",0),"prompt_tokens",1);break;
    case 11:nb_str(nth(rows,"walk_restore",0),"event","ignored");break;
    case 12:nb_num(restore,"begin_monotonic_ns",INT64_MAX);break;
    case 13:nb_num(nth(rows,"sample",3),"rep",0);break;
    case 14:nb_num(sample,"decode_end_monotonic_ns",INT64_MIN);break;
    default:require(false,"mutation selector");
  }
  char file[2600],name[80];snprintf(name,sizeof(name),"mutation-%u.jsonl",which);path(file,name);write_rows(file,rows);
  snprintf(name,sizeof(name),"mutation-%u-report",which);report(reporter,file,name,1,NULL);json_object_put(rows);
}
static void clean(const char *p){
  DIR *d=opendir(p);require(d!=NULL,"cleanup directory");struct dirent *ent;
  while((ent=readdir(d))){
    if(!strcmp(ent->d_name,".")||!strcmp(ent->d_name,".."))continue;
    char q[4096];require(snprintf(q,sizeof(q),"%s/%s",p,ent->d_name)<(int)sizeof(q),"cleanup path");
    struct stat st;require(!lstat(q,&st),"cleanup stat");
    if(S_ISDIR(st.st_mode))clean(q);else require(!unlink(q),"cleanup file");
  }
  closedir(d);require(!rmdir(p),"cleanup root");
}
int main(int argc,char **argv){
  require(argc==4,"arguments: fixture bench, reporter, private temp template");
  require(strlen(argv[3])<sizeof(root),"template bound");strcpy(root,argv[3]);require(mkdtemp(root)!=NULL,"private directory");
  char corpus[2600],auto_out[2600],replay_out[2600],eos_out[2600],failed[2600];
  path(corpus,"corpus.txt");path(auto_out,"auto.jsonl");path(replay_out,"replay.jsonl");path(eos_out,"eos.jsonl");path(failed,"failure.jsonl");
  char text[2048];memset(text,'x',sizeof(text));save("corpus.txt",text,sizeof(text));
  char *args[]={argv[1],"--model",":fixture:","--suite","ds4-walk","--corpus",corpus,
    "--output",auto_out,"--pp","128","--sizes","128,256,384","--context","512",
    "--tg","16","--warmups","1","--repetitions","2","--restore","auto",NULL};
  run(args,0);args[8]=replay_out;args[22]="replay";run(args,0);
  json_object *a=load(auto_out),*b=load(replay_out);
  require(count(a,"corpus")==1&&count(a,"input")==3&&count(a,"sample")==9&&count(a,"walk_restore")==6,"complete advancing work");
  require(nb_number(nth(a,"corpus",0),"prompt_tokens")==384&&nb_number(nth(a,"corpus",0),"tokenized_source_tokens")==513,"source tokenization and used-prefix counts");
  for(size_t i=0;i<9;++i){
    json_object *x=nth(a,"sample",i),*y=nth(b,"sample",i);
    require(nb_same(x,y,"output_ids")&&nb_same(x,y,"prefill_logits_sha256")&&nb_same(x,y,"decode_logits_sha256"),"snapshot/replay exact witnesses");
    require(nb_number(x,"prefill_tokens_per_user")==128,"appended-token PP numerator");
    if(i%3<2)require(!strcmp(nb_string(x,"checkpoint_method"),"snapshot")&&!strcmp(nb_string(y,"checkpoint_method"),"replay"),"snapshot and forced replay");
  }
  report(argv[2],auto_out,"auto-report",0,replay_out);
  char summary_path[2600];path(summary_path,"auto-report/summary.json");nb_error e={0};
  json_object *summary=nb_read(summary_path,false,&e);require(summary!=NULL,e.message);
  json_object *config=nb_get(nb_get(summary,"primary"),"configurations");
  require(json_object_array_length(config)==3,"native summary configurations");
  require(nb_number(nb_get(json_object_array_get_idx(config,0),"restore_seconds"),"n")==0&&
          nb_number(nb_get(json_object_array_get_idx(config,1),"restore_seconds"),"n")==2,"warmup-free restore summaries");
  json_object_put(summary);
  const char *exports[]={"summary.csv","benchmark.svg","benchmark.png"};
  for(size_t i=0;i<3;++i){char name[80],p[2600];snprintf(name,sizeof(name),"auto-report/%s",exports[i]);path(p,name);struct stat st;require(!stat(p,&st)&&st.st_size>20,"native exports without PATH/Python");}
  require(contains("auto-report/summary.csv","measurement_contract,new_prefill_tokens,checkpoint_median_s,restore_median_s")&&
          contains("auto-report/summary.csv","\"ds4-walk-v1\",128,"),"complete CSV phase accounting");
  require(contains("auto-report/benchmark.svg","Physical frontier (incremental prefill)"),"explicit advancing graph axis");
  for(unsigned i=0;i<15;++i)mutation(argv[2],a,i);
  json_object *scaled=nb_copy(a);nb_str(json_object_array_get_idx(scaled,0),"rope_scaling","yarn4");
  char scaled_file[2600];path(scaled_file,"scaled.jsonl");write_rows(scaled_file,scaled);json_object_put(scaled);
  report(argv[2],scaled_file,"scaled-report",0,NULL);
  report(argv[2],auto_out,"mixed-rope-report",1,scaled_file);
  args[2]=":eos:";args[8]=eos_out;run(args,0);json_object *eos=load(eos_out);
  require(nb_number(nth(eos,"sample",0),"output_tokens_per_user")==7&&!json_object_get_boolean(nb_get(nth(eos,"sample",0),"full_output_budget")),"visible natural EOS");
  report(argv[2],eos_out,"eos-report",0,NULL);json_object_put(eos);
  char limited[2600];path(limited,"snapshot-limit.jsonl");args[2]=":snapshot-limit:";args[8]=limited;args[22]="auto";run(args,0);
  json_object *limit=load(limited);require(!strcmp(nb_string(nth(limit,"sample",0),"checkpoint_method"),"replay"),"over-budget checkpoint chooses bounded replay");
  report(argv[2],limited,"snapshot-limit-report",0,NULL);json_object_put(limit);
  path(limited,"capture-failure.jsonl");args[2]=":capture-failure:";run(args,1);
  limit=load(limited);require(count(limit,"sample")==0,"checkpoint transfer error is terminal");json_object_put(limit);
  path(limited,"restore-failure.jsonl");args[2]=":restore-failure:";run(args,1);
  limit=load(limited);require(count(limit,"sample")==1,"mutating restore error has no replay/retry");json_object_put(limit);
  args[22]="replay";
  args[2]=":failure:";args[8]=failed;run(args,1);report(argv[2],failed,"failed-report",1,NULL);
  args[2]=":fixture:";args[8]=auto_out;run(args,1); /* Refuse overwrite. */
  char fresh[2600];path(fresh,"fresh.jsonl");
  char *fresh_args[]={argv[1],"--model",":fixture:","--suite","fresh","--sizes","128,256,384","--tg","16",
    "--warmups","0","--output",fresh,NULL};run(fresh_args,0);
  report(argv[2],fresh,"fresh-report",0,NULL);
  report(argv[2],auto_out,"mixed-contract-report",1,fresh);
  char invalid[2600];path(invalid,"invalid.jsonl");args[8]=invalid;
  args[12]="128,384";run(args,2);args[12]="128,256,384";
  args[14]="384";run(args,2);args[14]="512";
  char *users[]={argv[1],"--model",":fixture:","--suite","ds4-walk","--corpus",corpus,"--output",invalid,"--users","2",NULL};run(users,2);
  users[10]="1,2";run(users,2);users[9]="--depths";users[10]="0";run(users,2);
  unsigned char bad_utf8[]={0xc0,0xaf};save("bad.txt",bad_utf8,sizeof(bad_utf8));char bad[2600];path(bad,"bad.txt");args[6]=bad;
  path(invalid,"invalid-utf8.jsonl");run(args,1);
  unsigned char nul[]={0,'x'};save("nul.txt",nul,sizeof(nul));path(bad,"nul.txt");path(invalid,"invalid-nul.jsonl");run(args,1);
  char link[2600];path(link,"link.txt");require(!symlink(corpus,link),"corpus symlink");args[6]=link;path(invalid,"invalid-link.jsonl");run(args,1);
  char fifo[2600];path(fifo,"fifo");require(!mkfifo(fifo,0600),"corpus FIFO");args[6]=fifo;path(invalid,"invalid-fifo.jsonl");run(args,1);
  /* Largest admitted frontier: 511*2048 plus actual output below a 1M cap.
   * A real model is not loaded. The used physical corpus is recorded once. */
  size_t bytes=1046528u*4u;char *large=malloc(bytes);require(large!=NULL,"large corpus allocation");memset(large,'x',bytes);save("large.txt",large,bytes);free(large);
  char large_file[2600],large_out[2600];path(large_file,"large.txt");path(large_out,"large.jsonl");
  char sizes[6000];size_t at=0;for(unsigned i=1;i<=511;++i){int n=snprintf(sizes+at,sizeof(sizes)-at,"%s%u",i==1?"":",",i*2048);require(n>0&&(size_t)n<sizeof(sizes)-at,"frontier list");at+=(size_t)n;}
  char *large_args[]={argv[1],"--model",":fixture:","--suite","ds4-walk","--corpus",large_file,"--output",large_out,
    "--pp","2048","--sizes",sizes,"--context","1048576","--tg","1",NULL};run(large_args,0);
  json_object *big=load(large_out);require(count(big,"corpus")==1&&count(big,"input")==511&&count(big,"sample")==511,"1M geometry and single physical corpus");
  require(!nb_get(nth(big,"input",510),"physical_ids"),"no quadratic prefix copies");
  report(argv[2],large_out,"large-report",0,NULL);json_object_put(big);
  json_object_put(a);json_object_put(b);clean(root);
  puts("DS4 walk contract passed; synthetic accounting only, NOT-INFERENCE");return 0;
}
