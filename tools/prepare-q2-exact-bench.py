#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a private, reproducible exact-token benchmark source capsule."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Nonunique source anchor: ' + old)
    return text.replace(old, new, 1)


def main():
    parent = json.loads((ROOT / 'config/q2-native-bench-source.json').read_text())
    source = ROOT / parent['source']
    out = ROOT / '.deps/lie-exact-bench'
    if out.exists():
        raise ValueError('Refusing to overwrite an existing source capsule')
    for name, digest in parent['files'].items():
        if sha(source / name) != digest:
            raise ValueError('Retained source changed: ' + name)
    edits = {}

    def edit(name, old, new):
        edits[name] = once(edits.get(name, (source / name).read_text()), old, new)

    name = 'tools/lie-bench.c'
    edit(name, '#define PAD_BYTES (2u*1024u*1024u)\n', '')
    edit(name, '*compare,*execution;unsigned pp,tg,',
         '*compare,*execution,*prompt_file;bool sizes_set,depths_set;unsigned chunk,context_override,pp,tg,')
    edit(name, 'num(j,"prefill_chunk",2048);',
         'num(j,"prefill_chunk",c->chunk?c->chunk:c->pp);\n'
         '    str(j,"prompt_contract","exact-token-prefix-v1");\n'
         '    str(j,"prompt_file",c->prompt_file);')
    edit(name, 'context,2048};', 'context,c->chunk};')
    edit(name, 'info->vocab_tokens>1048576)return false;',
         'info->vocab_tokens>1048576||info->prefill_capacity<c->chunk)return false;')
    old = edits[name]
    start = old.index('static bool make_prompt(')
    end = old.index('static bool prefill(', start)
    edits[name] = old[:start] + '#include "q2_exact_prompt.inc"\n' + old[end:]
    edit(name, 'size_t from,size_t end,lie_error *e)',
         'size_t from,size_t end,unsigned chunk,lie_error *e)')
    edit(name, 'while(from<end){from=end-from>2048?from+2048:end;',
         'if(from%chunk||end%chunk||end>p->n)return false;\n'
         '    while(from<end){from+=chunk;')
    edit(name, 'prefill(seq[i],p,0,depth,e)', 'prefill(seq[i],p,0,depth,c->chunk,e)')
    edit(name, 'prefill(seq[i],p,depth,p->n,e)', 'prefill(seq[i],p,depth,p->n,c->chunk,e)')
    edit(name, 'num(j,"prefill_ns",(int64_t)pp_ns);',
         'num(j,"prefill_calls_per_user",(int64_t)(p->n-depth)/c->chunk);num(j,"prefill_tail_tokens",0);\n'
         '    num(j,"prefill_ns",(int64_t)pp_ns);')
    edit(name, '"  [--sizes 1500,8000,8192,32768,131072,258794] [--users 1,2,4,6,8]\\n"',
         '"  --prompt-file TEXT [--sizes EXACT-TOKENS,...] [--users 1,2,4,6,8]\\n"\n'
         '                 "  [--prefill-chunk 2048|4096|8192] [--context-capacity N]\\n"\n'
         '                 "Tokenize one corpus, take exact token prefixes; selected sizes/depths must align to the chunk.\\n"')
    edit(name, 'else if(!strcmp(key,"--depths")){if(!list(value,131072,c.depths,&c.depth_count))goto usage;}',
         'else if(!strcmp(key,"--prompt-file"))c.prompt_file=value;\n'
         '        else if(!strcmp(key,"--prefill-chunk")){if(!integer(value,8192,&c.chunk)||!c.chunk)goto usage;}\n'
         '        else if(!strcmp(key,"--context-capacity")){if(!integer(value,MAX_CONTEXT,&c.context_override)||!c.context_override)goto usage;}\n'
         '        else if(!strcmp(key,"--depths")){c.depths_set=true;if(!list(value,131072,c.depths,&c.depth_count))goto usage;}')
    edit(name, 'else if(!strcmp(key,"--sizes")){if(!list(',
         'else if(!strcmp(key,"--sizes")){c.sizes_set=true;if(!list(')
    edit(name, '    if(!strcmp(c.suite,"fresh"))for(unsigned k=0;',
         '    if(!exact_grid(&c)){fputs("Exact prompts require --prompt-file and chunk-aligned sizes/depths; chunk must be 2048, 4096 or 8192.\\n",stderr);return 2;}\n'
         '    if(!strcmp(c.suite,"fresh"))for(unsigned k=0;')
    edit(name, 'lie_model *m=NULL;lie_model_info info={0};',
         'struct prompt corpus={0};lie_model *m=NULL;lie_model_info info={0};')
    edit(name, '    for(unsigned point=0;point<points;++point){unsigned depth=',
         '    unsigned corpus_needed=c.pp;\n'
         '    if(!strcmp(c.suite,"fresh"))corpus_needed=c.sizes[c.size_count-1];\n'
         '    else if(!strcmp(c.suite,"single"))corpus_needed=c.depths[c.depth_count-1]+c.pp;\n'
         '    else if(!strcmp(c.suite,"memory"))corpus_needed=20480;\n'
         '    if(c.context_override&&(uint64_t)corpus_needed+c.tg>c.context_override){snprintf(e.message,sizeof(e.message),"workload exceeds context capacity");goto done;}\n'
         '    for(unsigned point=0;point<points;++point){unsigned depth=')
    edit(name, '        c.context=context;',
         '        if(c.context_override)context=c.context_override;\n'
         '        c.context=context;')
    edit(name, 'struct prompt p={0};struct witness w={.ids=calloc(c.tg,sizeof(int32_t))};bool ok=w.ids&&make_prompt(m,depth+pp,context,&p,&e)&&p.n>depth;',
         'if(!corpus.ids&&!exact_corpus(m,&c,corpus_needed,&corpus,f,&e))goto done;\n'
         '            if(corpus.n<depth+pp){snprintf(e.message,sizeof(e.message),"Corpus has %zu tokens; need %u",corpus.n,depth+pp);goto done;}\n'
         '            struct prompt p={corpus.ids,depth+pp};struct witness w={.ids=calloc(c.tg,sizeof(int32_t))};bool ok=w.ids!=NULL;')
    edit(name, 'free(p.ids);free(w.ids);', 'free(w.ids);')
    edit(name, 'done:\n    if(m&&lie_model_close(&m,&e)!=LIE_OK)code=1;',
         'done:\n    free(corpus.ids);\n    if(m&&lie_model_close(&m,&e)!=LIE_OK)code=1;')
    # A changed target must never be accepted by replay/report validation.
    name = 'tools/native/report.c'
    edit(name, '    CHECK(nb_number(in, "depth") < nb_number(in, "prompt_tokens") &&',
         '    if (eqs(id, "prompt_contract", "exact-token-prefix-v1")) {\n'
         '      int64_t chunk = nb_number(id, "prefill_chunk");\n'
         '      CHECK((chunk == 2048 || chunk == 4096 || chunk == 8192) &&\n'
         '            nb_count(in, "target_prompt_tokens", 1, 1048576, NULL) &&\n'
         '            nb_number(in, "prompt_tokens") == nb_number(in, "target_prompt_tokens") &&\n'
         '            nb_number(in, "prompt_tokens") % chunk == 0 &&\n'
         '            nb_number(in, "depth") % chunk == 0, "Exact prompt contract differs");\n'
         '    }\n'
         '    CHECK(nb_number(in, "depth") < nb_number(in, "prompt_tokens") &&')
    edit(name, '      CHECK(nb_count(r, "rep", (int64_t)j, (int64_t)j, NULL) &&',
         '      if (eqs(id, "prompt_contract", "exact-token-prefix-v1"))\n'
         '        CHECK(nb_count(r, "prefill_calls_per_user", pp / nb_number(id, "prefill_chunk"),\n'
         '                       pp / nb_number(id, "prefill_chunk"), NULL) &&\n'
         '              nb_count(r, "prefill_tail_tokens", 0, 0, NULL), "Exact prefill calls differ");\n'
         '      CHECK(nb_count(r, "rep", (int64_t)j, (int64_t)j, NULL) &&')
    name = 'tools/native/http_bench.c'
    edit(name, '    unsigned count = (unsigned)((target - p0) / unit);',
         '    unsigned count = (unsigned)((target - p0) / unit);\n'
         '    if (p0 + count * unit != target) {\n'
         '      nb_fail(&c->error, "HTTP text calibration cannot meet the exact token target; use the native corpus benchmark");\n'
         '      goto fail;\n'
         '    }')
    name = 'tools/native/http_curve.c'
    edit(name, 'double cache_tolerance = fmax(32, floor(depth * fraction)),\n           pp_tolerance = fmax(32, floor(pp * fraction));',
         'double cache_tolerance = floor(depth * fraction),\n           pp_tolerance = floor(pp * fraction);')
    edit(name, 'nb_real(id, "depth_tolerance", .005);', 'nb_real(id, "depth_tolerance", 0);')
    edit(name, '[--depth-tolerance 0.005]', '[--depth-tolerance 0]')
    # The synthetic provider must admit the same host chunk sizes, without
    # claiming that its byte/4 fixture is a neural tokenizer.
    name = 'tests/bench_executor.c'
    edit(name, '.prefill_capacity=2048,', '.prefill_capacity=m->chunk,')
    edit(name, 'n-s->position>2048', 'n-s->position>s->m->chunk')
    shutil.copytree(source, out)
    patches = []
    for name, value in edits.items():
        (out / name).write_text(value)
        patches.append(''.join(difflib.unified_diff((source / name).read_text().splitlines(True),
                       value.splitlines(True), fromfile='a/'+name, tofile='b/'+name)))
    inc = ROOT / 'experiments/q2_exact_prompt.inc'
    shutil.copyfile(inc, out / 'tools/q2_exact_prompt.inc')
    (ROOT / 'experiments/q2-exact-bench.patch').write_text(''.join(patches))
    report = dict(schema='synapse-lie.q2-exact-bench-source.v1',
                  parent_commit=parent['commit'], parent_manifest_sha256=sha(ROOT/'config/q2-native-bench-source.json'),
                  source=str(out.relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
                  include_sha256=sha(inc), modified_files=sorted(edits),
                  files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()},
                  gpu_runtime_qualified=False)
    (ROOT / 'config/q2-exact-bench-source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(source=report['source'],files=len(report['files']),modified=report['modified_files'])))


if __name__ == '__main__':
    main()
