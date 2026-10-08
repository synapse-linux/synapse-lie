#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare full-prefill counting measurements; preserve all retained executables."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parent=json.loads((ROOT/'config/q2-exact-bench-source.json').read_text())
    source=ROOT/parent['source']; out=ROOT/'.deps/lie-counting-bench'
    assert not out.exists(), 'Preserve existing source capsules'
    for name,digest in parent['files'].items():
        assert sha(source/name)==digest, name
    edits={}
    def edit(name,old,new):
        value=edits.get(name,(source/name).read_text()); assert value.count(old)==1,old
        edits[name]=value.replace(old,new,1)
    file='tools/lie-bench.c'
    edit(file,'#define MAX_POINTS 32u','#define MAX_POINTS 128u')
    edit(file,'bool sizes_set,depths_set;','bool sizes_set,depths_set,counting;')
    edit(file,'.suite="single",.execution=', '.suite="fresh",.execution=')
    edit(file,'num(j,"pp_target",c->pp);', 'num(j,"pp_target",!strcmp(c->suite,"fresh")?0:c->pp);')
    edit(file,'str(j,"prompt_contract","exact-token-prefix-v1");','str(j,"prompt_contract",c->counting?"exact-counting-chat-v1":"exact-token-prefix-v1");\n    str(j,"prompt_preset",c->counting?"q2-counting":"none");')
    edit(file,'str(j,"prompt_file",c->prompt_file);', '''str(j,"prompt_file",c->prompt_file?c->prompt_file:"");
    str(j,"measurement_contract",!strcmp(c->suite,"fresh")?"full-prefill-v1":"incremental-prefill-v1");
    str(j,"decode_contract","completed-forward-per-emitted-token-v1");''')
    edit(file,'#include "q2_exact_prompt.inc"','#include "q2_exact_prompt.inc"\n#include "q2_counting_prompt.inc"')
    edit(file,'"  [--depths 0,4096,8192,12288,16384,32768,65536,131072]\\n"',
         '"  [--depths ALIGNED-PREFIX-TOKENS,... (single suite only)]\\n"')
    edit(file,'else if(!strcmp(key,"--prompt-file"))c.prompt_file=value;',
         'else if(!strcmp(key,"--prompt-preset")){if(strcmp(value,"q2-counting"))goto usage;c.counting=true;}\n        else if(!strcmp(key,"--prompt-file"))c.prompt_file=value;')
    edit(file,'"  --prompt-file TEXT [--sizes EXACT-TOKENS,...] [--users 1,2,4,6,8]\\n"',
         '"  (--prompt-file TEXT | --prompt-preset q2-counting)\\n"\n                 "  [--sizes EXACT-TOKENS,...] [--users 1,2,4,6,8]\\n"')
    edit(file,'"Tokenize one corpus, take exact token prefixes; selected sizes/depths must align to the chunk.\\n"',
         '"Default suite fresh: time the entire prompt from an empty sequence, including every chunk.\\n"\n                 "Default sizes: every chunk multiple through 131072. All sizes/depths must align.\\n"\n                 "Explicit suite single: incremental PP at reused depth; not a full-prefill curve.\\n"')
    edit(file,'"Exact prompts require --prompt-file and chunk-aligned sizes/depths; chunk must be 2048, 4096 or 8192.\\n"',
         '"Exact prompts require one prompt source and a chunk-aligned grid for the selected suite; chunk must be 2048, 4096 or 8192.\\n"')
    edit(file,'unsigned context=!strcmp(c.suite,"fresh")?MAX_CONTEXT:',
         'unsigned context=!strcmp(c.suite,"fresh")?133760:')
    edit(file,'if(!corpus.ids&&!exact_corpus(m,&c,corpus_needed,&corpus,f,&e))goto done;',
         'if(c.counting){if(!exact_counting(m,depth+pp,&corpus,f,&e))goto done;}\n            else if(!corpus.ids&&!exact_corpus(m,&c,corpus_needed,&corpus,f,&e))goto done;')
    edit('tools/q2_exact_prompt.inc','if (!c->prompt_file || !*c->prompt_file) return false;',
         '''if (c->counting ? c->prompt_file != NULL : (!c->prompt_file || !*c->prompt_file)) return false;
    if ((!strcmp(c->suite, "fresh") && c->depths_set) ||
        (strcmp(c->suite, "fresh") && c->sizes_set)) return false;''')
    edit('tools/q2_exact_prompt.inc','n <= 131072; n *= 2)\n            c->sizes',
         'n <= 131072; n += c->chunk)\n            c->sizes')
    edit('tools/q2_exact_prompt.inc','n <= 131072; n *= 2)\n            c->depths',
         'n <= 131072; n += c->pp)\n            c->depths')
    file='tools/native/report.c';value=(source/file).read_text()
    assert value.count('eqs(id, "prompt_contract", "exact-token-prefix-v1")')==2
    edits[file]=value.replace('eqs(id, "prompt_contract", "exact-token-prefix-v1")',
        '(eqs(id, "prompt_contract", "exact-token-prefix-v1") || eqs(id, "prompt_contract", "exact-counting-chat-v1"))')
    edit(file,'  CHECK(repetition_config(id), "Invalid direct benchmark identity");', '''  CHECK(repetition_config(id), "Invalid direct benchmark identity");
  if (nb_get(id, "measurement_contract"))
    CHECK(eqs(id, "measurement_contract", eqs(id, "suite", "fresh") ?
              "full-prefill-v1" : "incremental-prefill-v1"),
          "Measurement contract and suite disagree");''')
    edit(file,'    CHECK(nb_number(in, "depth") < nb_number(in, "prompt_tokens") &&', '''    if (eqs(id, "suite", "fresh"))
      CHECK(nb_number(in, "depth") == 0, "Full prefill must start at zero depth");
    CHECK(nb_number(in, "depth") < nb_number(in, "prompt_tokens") &&''')
    edit(file,'  CHECK(!cache_build || iscore, "Cache build comparison requires core results");', '''  CHECK(!cache_build || iscore, "Cache build comparison requires core results");
  if (!iscore && !http && (nb_get(ai, "measurement_contract") || nb_get(bi, "measurement_contract")))
    CHECK(nb_same(ai, bi, "measurement_contract") &&
          nb_same(ai, bi, "prompt_contract") && nb_same(ai, bi, "decode_contract") &&
          nb_same(ai, bi, "warmups") && nb_same(ai, bi, "repetitions"),
          "Comparison measurement, prompt, decode or sampling contract differs");''')
    # Test-only trace lets tests check the real call timestamps, independently
    # of the benchmark's claimed counters and throughput formula.
    file='tests/bench_executor.c'
    edit(file,'#include <string.h>', '#include <string.h>\n#include "q2_bench_fixture_trace.inc"')
    edit(file,'    memcpy(s->prompt,p,n*sizeof(*p));s->position=(unsigned)n; return LIE_OK;', '''    uint64_t begin=fixture_clock(); unsigned from=s->position;
    memcpy(s->prompt,p,n*sizeof(*p));s->position=(unsigned)n;
    return fixture_trace(s->m->runs,from,n,begin,fixture_clock())?LIE_OK:LIE_BACKEND_FAILED;''')
    shutil.copytree(source,out); patches=[]
    for name,value in edits.items():
        (out/name).write_text(value)
        patches.append(''.join(difflib.unified_diff((source/name).read_text().splitlines(True),value.splitlines(True),fromfile='a/'+name,tofile='b/'+name)))
    inc=ROOT/'experiments/q2_counting_prompt.inc';shutil.copyfile(inc,out/'tools/q2_counting_prompt.inc')
    shutil.copyfile(ROOT/'experiments/q2_bench_fixture_trace.inc',out/'tests/q2_bench_fixture_trace.inc')
    (ROOT/'experiments/q2-counting-bench.patch').write_text(''.join(patches))
    manifest=dict(schema='synapse-lie.q2-counting-bench-source.v1',source=str(out.relative_to(ROOT)),
                  parent_manifest_sha256=sha(ROOT/'config/q2-exact-bench-source.json'),generator_sha256=sha(Path(__file__)),
                  files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    (ROOT/'config/q2-counting-bench-source.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(source=manifest['source'],files=len(manifest['files']))))

if __name__=='__main__': main()
