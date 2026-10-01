#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""HTTP benchmark client harness. Never starts a server, changes cache mode or executes tools."""
import argparse
import copy
import csv
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import statistics
import time
from urllib.parse import urlsplit

SCHEMA = 'synapse-lie.http-bench.v1'
PAD = 'The maintenance team documented the inspection and scheduled additional measurements.\n'
SHAPES = {
    'prose': 'Write a long account of a lighthouse keeper recording a winter storm.',
    'code': 'Implement a bounded FIFO queue in C17 and explain ownership and error handling.',
    'proof': 'Prove by induction the formula for the sum of the first n squares, explaining every step.',
    'chat': 'Help a volunteer team plan a community garden; discuss choices and responsibilities.',
    'analysis': 'Compare centralized and distributed inventory systems with concrete failure examples.',
    'structured': 'Produce a JSON array of 30 fictional weather station readings with name, temperature and notes.',
    'translation': 'Translate and explain this sentence in ten languages: The train reaches the mountain village before noon.',
    'debug': 'Diagnose a C program that retains pointers into a reallocating array; give a corrected implementation.',
    'review': 'Review a design that retries every failed database transaction forever; propose bounded recovery.',
    'tool-dialogue': 'After reading a configuration with timeout=20 and retries=3, explain a careful change to timeout=30 and its verification.'}

def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def request(url, body, timeout):
    u = urlsplit(url)
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError('URL must be an HTTP(S) base URL without credentials, query or fragment')
    connection = (http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection)(u.hostname, u.port, timeout=timeout)
    wire = encoded(body); started = time.perf_counter(); first = None; chunks = []; text = ''; tool_calls = {}; usage = None; finish = None; timings = None; done = False
    try:
        connection.request('POST', u.path.rstrip('/') + '/chat/completions', wire, {'Content-Type': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f'HTTP {response.status}: {response.read(65536).decode(errors="replace")}')
        if 'text/event-stream' not in response.getheader('Content-Type', ''):
            raise ValueError('expected SSE response')
        size = 0
        while True:
            line = response.readline(1048577); size += len(line)
            if len(line) > 1048576 or size > 32*1024*1024:
                raise ValueError('SSE evidence size limit')
            if not line: break
            if not line.startswith(b'data:'): continue
            data = line[5:].strip()
            if data == b'[DONE]': done = True; break
            chunk = json.loads(data); chunks.append(chunk)
            if chunk.get('error'): raise ValueError(chunk['error'])
            if chunk.get('usage'): usage = chunk['usage']
            if chunk.get('lie_timings'): timings = chunk['lie_timings']
            for choice in chunk.get('choices', []):
                if choice.get('index', 0) != 0: raise ValueError('multiple choices unsupported')
                delta = choice.get('delta', {})
                value = delta.get('content') or ''
                calls = delta.get('tool_calls') or []
                if (value or any(c.get('function', {}).get('arguments') for c in calls)) and first is None:
                    first = time.perf_counter() - started
                text += value
                for call in calls:
                    index = call['index']; item = tool_calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                    if call.get('id'): item['id'] = call['id']
                    for key in ('name', 'arguments'): item['function'][key] += call.get('function', {}).get(key, '')
                if choice.get('finish_reason'): finish = choice['finish_reason']
        wall = time.perf_counter() - started
        if not done or not finish or usage is None: raise ValueError('incomplete stream or missing actual token usage')
        pp, tg = usage['prompt_tokens'], usage['completion_tokens']
        if type(pp) is not int or type(tg) is not int or pp <= 0 or tg < 0 or tg > body['max_tokens'] or not math.isfinite(wall) or wall <= 0:
            raise ValueError('invalid usage/timing')
        assistant = {'role': 'assistant', 'content': text}
        if tool_calls: assistant['tool_calls'] = [tool_calls[k] for k in sorted(tool_calls)]
        return {'request': body, 'request_sha256': digest(body), 'request_bytes': len(wire), 'response_chunks': chunks,
                'assistant': assistant, 'usage': usage, 'finish_reason': finish, 'wall_seconds': wall,
                'first_output_seconds': first, 'prompt_over_wall_tps': pp/wall, 'output_over_wall_tps': tg/wall,
                'full_output_budget': tg == body['max_tokens'], 'server_timings': timings}
    finally:
        connection.close()


def measured_cases(args, emit):
    if args.requests:
        cases = [json.loads(x) for x in Path(args.requests).read_text().splitlines() if x.strip()]
        if not cases or len(cases) > 256: raise ValueError('expected 1..256 request cases')
        return cases
    if args.preset == 'decode':
        return [{'id': name, 'body': {'messages': [{'role': 'user', 'content': prompt + ' Give a substantial detailed answer.'}], 'max_tokens': args.tg}} for name, prompt in SHAPES.items()]
    def messages(lines):
        return [{'role': 'user', 'content': 'Read these maintenance notes.\n' + PAD*lines + '\nReply with exactly READY.'}]
    counts = []
    for n in (0, 8, 16):
        body = make_body(args, {'messages': messages(n), 'max_tokens': 1})
        row = request(args.url, body, args.timeout)
        emit({'event': 'calibration', 'lines': n, **row}); counts.append(row['usage']['prompt_tokens'])
    p0, p8, p16 = counts
    if p8 <= p0 or p16-p8 != p8-p0 or (p8-p0) % 8: raise ValueError('nonlinear prompt calibration; supply explicit --requests')
    unit = (p8-p0)//8
    sizes = [100000] if args.preset == 'conversation' else args.sizes
    cases = []
    for target in sizes:
        if target <= p0: raise ValueError('target below rendered template size')
        n = (target-p0)//unit
        case = {'id': f'{args.preset}-{target}', 'target_prompt_tokens': target, 'expected_prompt_tokens': p0+n*unit,
                'body': {'messages': messages(n), 'max_tokens': 1 if args.preset == 'prefill' else 32}}
        if args.preset == 'conversation':
            case['followups'] = ['Additional maintenance notes:\n' + PAD*max(1,400//unit) + f'\nConfirm update {i+1} with exactly READY.' for i in range(args.turns-1)]
        cases.append(case)
    return cases


def make_body(args, supplied):
    body = {'model': args.model, 'temperature': 0, 'max_tokens': args.tg, **args.options, **copy.deepcopy(supplied)}
    # Protocol requirements of this client cannot be overridden by a corpus.
    body.update(model=args.model, stream=True, stream_options={'include_usage': True})
    if not isinstance(body.get('messages'), list) or not body['messages']: raise ValueError('case messages required')
    if type(body['max_tokens']) is not int or not 1 <= body['max_tokens'] <= 65536: raise ValueError('invalid output budget')
    return body


def summarize(rows):
    if rows[0].get('schema') != SCHEMA or rows[-1] != {'event': 'complete', 'exit_code': 0}: raise ValueError('incomplete HTTP evidence')
    result = []
    keys = sorted({(r['case'], r['turn']) for r in rows if r['event'] == 'sample'})
    for key in keys:
        all_rows = [r for r in rows if r['event']=='sample' and (r['case'],r['turn'])==key]
        if len(all_rows)!=rows[0]['warmups']+rows[0]['repetitions']: raise ValueError('missing HTTP repetitions')
        group = [r for r in all_rows if not r['warmup']]
        item = {'case': key[0], 'turn': key[1], 'samples': len(group), 'prompt_tokens': [r['usage']['prompt_tokens'] for r in group],
                'output_tokens': [r['usage']['completion_tokens'] for r in group], 'request_hashes': [r['request_sha256'] for r in group],
                'output_hashes': [digest(r['assistant']) for r in group], 'full_output_budget': all(r['full_output_budget'] for r in group)}
        for metric in ('wall_seconds','first_output_seconds','prompt_over_wall_tps','output_over_wall_tps'):
            values=[r[metric] for r in group if r[metric] is not None]
            item[metric] = {'mean': statistics.fmean(values), 'median': statistics.median(values), 'min': min(values), 'max': max(values)} if values else None
        result.append(item)
    return {'identity': rows[0], 'cases': result}


def export(summary, directory, compare=None):
    out=Path(directory);out.mkdir(parents=True,exist_ok=True)
    if compare:
        ref=summarize([json.loads(x) for x in Path(compare).read_text().splitlines()]);summary['reference']=ref
        if summary['identity']['cache_policy']!=ref['identity']['cache_policy']: raise ValueError('comparison cache policy mismatch')
        other={(r['case'],r['turn']):r for r in ref['cases']}
        if len(other)!=len(summary['cases']): raise ValueError('comparison point mismatch')
        checks=[]
        for r in summary['cases']:
            q=other.get((r['case'],r['turn']))
            if q is None or (r['request_hashes'],r['prompt_tokens'])!=(q['request_hashes'],q['prompt_tokens']): raise ValueError('comparison request/physical count mismatch')
            checks.append({'case':r['case'],'turn':r['turn'],'output_equal':r['output_hashes']==q['output_hashes'],'full_output_budget':r['full_output_budget'] and q['full_output_budget']})
        summary['comparison']=checks
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'summary.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['case','turn','prompt_tokens','output_tokens','full_output_budget','wall_median_s','ttft_median_s','pp_wall_mean_tps','tg_wall_mean_tps'])
        for r in summary['cases']:writer.writerow([r['case'],r['turn'],r['prompt_tokens'],r['output_tokens'],r['full_output_budget'],r['wall_seconds']['median'],r['first_output_seconds']['median'] if r['first_output_seconds'] else '',r['prompt_over_wall_tps']['mean'],r['output_over_wall_tps']['mean']])
    os.environ.setdefault('MPLCONFIGDIR',str(out/'matplotlib-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(14,5),layout='constrained')
    for label,series in [(summary['identity']['server_label'],summary)]+([(ref['identity']['server_label'],ref)] if compare else []):
        cases=series['cases'];x=list(range(len(cases)));labels=[f"{r['case']}:{r['turn']}" for r in cases]
        for ax,key,title in zip(axes,['first_output_seconds','prompt_over_wall_tps','output_over_wall_tps'],['First output (seconds)','Prompt tokens / complete HTTP wall','Output tokens / complete HTTP wall']):
            ax.plot(x,[r[key]['mean'] if r[key] else math.nan for r in cases],marker='o',label=label);ax.set_xticks(x,labels,rotation=70,ha='right');ax.set_title(title);ax.grid(alpha=.25);ax.legend()
    fig.suptitle('HTTP measurements — actual usage; cache policy declared by operator; early EOS retained')
    fig.savefig(out/'benchmark.svg');fig.savefig(out/'benchmark.png',dpi=160);plt.close(fig)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',required=True,help='Base URL ending in /v1')
    p.add_argument('--model',required=True);p.add_argument('--output',required=True)
    p.add_argument('--server-label',required=True,help='Server version/checkpoint/configuration identity, recorded without verification')
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--requests');group.add_argument('--preset',choices=['prefill','decode','conversation'])
    p.add_argument('--sizes',default='8192,32768,131072,258794');p.add_argument('--tg',type=int,default=256)
    p.add_argument('--turns',type=int,default=20);p.add_argument('--repetitions',type=int,default=3);p.add_argument('--warmups',type=int,default=0)
    p.add_argument('--cache-policy',choices=['off','on','unknown'],required=True,help='Operator declaration; this client does not toggle server cache')
    p.add_argument('--request-options',help='JSON object for explicit server-supported sampling/drafter options')
    p.add_argument('--export-requests',help='Exclusive corpus export for exact replay on another server')
    p.add_argument('--graphs');p.add_argument('--compare');p.add_argument('--timeout',type=float,default=630)
    args=p.parse_args(argv)
    try:args.sizes=[int(x) for x in args.sizes.split(',')]
    except ValueError:p.error('sizes must be integers')
    if not 1<=args.repetitions<=100 or not 0<=args.warmups<=10 or not 1<=args.turns<=100 or not 1<=args.tg<=65536 or not math.isfinite(args.timeout) or not 0<args.timeout<=7200 or not args.sizes or len(args.sizes)>32 or any(not 128<=x<=1048576 for x in args.sizes) or (args.compare and not args.graphs):p.error('invalid workload bounds')
    args.options=json.loads(Path(args.request_options).read_text()) if args.request_options else {}
    if not isinstance(args.options,dict):p.error('request options must be an object')
    rows=[]
    with open(args.output,'x') as f:
        def emit(row):rows.append(row);f.write(json.dumps(row,separators=(',',':'))+'\n');f.flush()
        emit({'event':'identity','schema':SCHEMA,'url':args.url,'model':args.model,'server_label':args.server_label,'cache_policy':args.cache_policy,'warmups':args.warmups,'repetitions':args.repetitions,'preset':args.preset,'request_options':args.options,'scope':'HTTP client harness; no model open, server control, tool execution or implicit cache reset'})
        try:
            cases=measured_cases(args,emit)
            if len({c['id'] for c in cases})!=len(cases):raise ValueError('duplicate case IDs')
            if args.export_requests:
                with open(args.export_requests,'x') as corpus:
                    for case in cases:corpus.write(json.dumps(case)+'\n')
            for case in cases:
                if len(case.get('followups',[]))>99:raise ValueError('too many followups')
                for rep in range(args.warmups+args.repetitions):
                    body=make_body(args,case['body'])
                    for turn in range(1+len(case.get('followups',[]))):
                        row=request(args.url,body,args.timeout)
                        # Preserve the actual failed observation before checking the calibration oracle.
                        emit({'event':'sample','case':case['id'],'turn':turn,'rep':rep,'warmup':rep<args.warmups,**row})
                        if turn==0 and 'expected_prompt_tokens' in case and row['usage']['prompt_tokens']!=case['expected_prompt_tokens']:raise ValueError('physical prompt calibration changed')
                        if turn<len(case.get('followups',[])):
                            if row['assistant'].get('tool_calls'):raise ValueError('automatic tool execution unsupported; supply a static dialogue corpus')
                            body=copy.deepcopy(body);body['messages'] += [row['assistant'],{'role':'user','content':case['followups'][turn]}]
            emit({'event':'complete','exit_code':0})
        except Exception as ex:
            emit({'event':'failed','exit_code':1,'error':repr(ex)});print(str(ex));return 1
    summary=summarize(rows)
    if args.graphs:export(summary,args.graphs,args.compare)
    print(json.dumps(summary,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
