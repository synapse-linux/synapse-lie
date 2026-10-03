#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage task-owned sources and fixed qualification jobs on .157 only."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
HOST = 'paperboy@192.168.5.157'
REMOTE = '/home/paperboy/workspace/projects/synapse-linux/synapse-lie/run/'


def collection_receipt(archive):
    members = archive.getmembers()
    names = set()
    for member in members:
        path = Path(member.name)
        if (path.is_absolute() or '..' in path.parts or not path.parts or
                path.parts[0] != 'results' or path in names or member.size < 0 or
                not (member.isdir() or member.isfile())):
            raise ValueError('Unsafe collection')
        names.add(path)
    receipts = [member for member in members if member.name == 'results/result.json']
    if len(receipts) != 1 or not receipts[0].isfile() or receipts[0].size > 1000000:
        raise ValueError('Missing or oversized collection receipt')
    receipt = json.load(archive.extractfile(receipts[0]))
    # Eight complete 36-row outputs alone occupy 286 MB in this fixed probe.
    # Keep other modes at their existing bound and retain a finite total cap.
    limit = 384000000 if receipt.get('mode') == 'q2-ple-first-access' else 128000000
    if sum(member.size for member in members) > limit:
        raise ValueError('Oversized collection')
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['cpu', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access', 'ple-cpu', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'q2-ple', 'ud-ple', 'hip-build', 'operators', 'operators-reference', 'hc-operators', 'hc-bench', 'hc-pp-operators', 'hc-pp-bench', 'hc-library-bench', 'hc-input-bench', 'hc-up-chain-bench', 'hc-up-operators', 'hc-up-bench', 'hc-moe-operators', 'hc-moe-bench', 'hc-norm-operators', 'hc-norm-bench', 'routed-operators', 'iq2-pair-operators', 'packed-operators', 'packed-bench', 'packed-tiles-bench', 'packed-tiles16-bench', 'q2-smoke', 'q2-bench', 'q2-bench2k', 'ud-bench2k', 'q2-profile', 'ud-profile', 'ud-base', 'ud-patched', 'status', 'collect'])
    p.add_argument('label')
    p.add_argument('--source-variant', choices=['qualified', 'bounded-k', 'wide-barrier', 'hc', 'hc-prefill', 'stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'],
                   default='qualified', help='Isolated source; hc also supports HC operators and microbenchmark')
    p.add_argument('--rebuild-mmq', action='store_true',
                   help='Recompile all MMQ sources for bench2k; no prior archive reuse')
    p.add_argument('--existing-collection', action='store_true',
                   help='Validate/extract an already downloaded collection; no SSH or overwriting results')
    args = p.parse_args()
    if args.existing_collection and args.mode != 'collect':
        p.error('Existing collection requires collect mode')
    if args.mode in ('ple-cpu', 'q2-ple', 'ud-ple', 'ple-io-cpu', 'q2-ple-io', 'ud-ple-io', 'ple-cache-cpu', 'q2-ple-cache64k', 'ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access') and args.source_variant != 'qualified':
        p.error('PLE diagnostics select their fixed instrumented Q2/UD source')
    if args.rebuild_mmq and args.mode not in ('q2-bench2k', 'ud-bench2k'):
        p.error('Full MMQ rebuild selection requires bench2k')
    if args.mode in ('hc-norm-operators', 'hc-norm-bench') and args.source_variant != 'hc-norm-half':
        p.error('F32/F16 norm checks require the isolated hc-norm-half source')
    if args.mode in ('hc-moe-operators', 'hc-moe-bench') and args.source_variant != 'hc-moe-fused':
        p.error('F32 MoE/HC checks require the isolated hc-moe-fused source')
    if args.mode == 'hc-up-operators' and args.source_variant not in ('hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half'):
        p.error('Fused HC up operators require the isolated hc-up-fused source or hc-up-vec candidate')
    if args.mode == 'hc-up-bench' and args.source_variant not in ('hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half'):
        p.error('HC up benchmark requires the measured hc-up-fused source or hc-up-vec candidate')
    if args.mode == 'hc-up-chain-bench' and args.source_variant not in ('affine-palette', 'hc-up-chains'):
        p.error('HC up chain benchmark requires palette or hc-up-chains')
    if args.mode == 'hc-input-bench' and args.source_variant != 'hc-input':
        p.error('HC input benchmark requires the isolated hc-input source')
    if args.mode == 'hc-library-bench' and args.source_variant != 'affine-palette':
        p.error('HC library sweep requires the measured affine-palette source')
    if args.mode in ('packed-tiles-bench', 'packed-tiles16-bench') and args.source_variant != 'hc-up-chains':
        p.error('Tile benchmark requires retained hc-up-chains source')
    if args.mode == 'packed-bench' and args.source_variant not in ('hc-decode16', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', 'hc-moe-fused', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane'):
        p.error('Packed benchmark requires a measured or isolated Q2 decode source')
    if args.mode == 'packed-operators' and args.source_variant not in ('packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
        p.error('Packed operators require the isolated packed source')
    if args.mode == 'routed-operators' and args.source_variant not in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
        p.error('Compensated routed operators require the isolated stack source')
    if args.mode == 'iq2-pair-operators' and args.source_variant not in ('iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced'):
        p.error('Paired IQ2 operators require the isolated IQ2 source')
    hc_component = args.source_variant in ('packed', 'hc-moe-fused', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced') and args.mode in ('hc-operators', 'hc-bench')
    hc_component = hc_component or (args.source_variant in ('affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced', 'hc-moe-fused', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced') and args.mode in ('hc-pp-operators', 'hc-pp-bench'))
    hc_component = hc_component or (args.mode == 'hc-library-bench' and args.source_variant == 'affine-palette')
    hc_component = hc_component or (args.mode == 'hc-input-bench' and args.source_variant == 'hc-input')
    hc_component = hc_component or (args.mode == 'hc-up-chain-bench' and args.source_variant in ('affine-palette', 'hc-up-chains'))
    hc_component = hc_component or (args.mode in ('packed-tiles-bench', 'packed-tiles16-bench') and args.source_variant == 'hc-up-chains')
    if args.source_variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced') and not hc_component and args.mode not in ('hc-up-operators', 'hc-up-bench', 'hc-moe-operators', 'hc-moe-bench', 'hc-norm-operators', 'hc-norm-bench', 'iq2-pair-operators', 'routed-operators', 'packed-operators', 'packed-bench', 'operators', 'q2-bench', 'q2-bench2k', 'q2-profile'):
        p.error('Stack source requires routed checks or Q2 model measurements')
    if args.source_variant in ('stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced') and args.mode == 'q2-bench2k' and not args.rebuild_mmq:
        p.error('Stack changes executor/header; explicitly rebuild MMQ')
    if args.source_variant in ('hc', 'hc-prefill') and args.mode not in ('hc-operators', 'hc-bench', 'hc-pp-operators', 'hc-pp-bench', 'q2-bench', 'q2-bench2k', 'q2-profile'):
        p.error('HC source requires HC checks or Q2 benchmark/profile')
    if args.source_variant not in ('qualified', 'hc', 'hc-prefill', 'stack', 'iq2-pair', 'packed', 'hc-up-fused', 'hc-up-vec', 'hc-up-vec-exact', 'hc-moe-fused', 'hc-norm-half', 'hc-down64', 'hc-down64-wave4', 'hc-down64-k4', 'hc-down128-wave4', 'hc-down-coalesced', 'staged-weights', 'code-reuse', 'half-wave', 'half-wave-permlane', 'hc-prefetch', 'hc-prefetch2', 'hc-decode8', 'hc-decode16', 'hc-decode32', 'affine-palette', 'hc-fragment-bound', 'hc-stage-bound', 'hc-direct', 'hc-chain-waves', 'hc-chain-coalesced', 'hc-library-down', 'hc-input', 'hc-up-chains', 'hc-down-wide', 'hc-down-wide-k1', 'hc-down-wide-coalesced') and args.mode != 'q2-bench':
        p.error('MMQ-changing source selection requires q2-bench')
    if not re.fullmatch(r'q2-[a-z0-9-]{1,48}', args.label):
        p.error('Label must start with q2- and contain lowercase letters/digits/hyphens')
    if args.mode == 'status':
        script = 'from pathlib import Path; import json; p=Path('+repr(REMOTE+args.label+'/results')+'); j=json.loads((p/"result.json").read_text()); print(json.dumps({k:j.get(k) for k in ["state","mode","pid","started_at","finished_at","commands","error","postflight_kfd"]},indent=2)); logs=sorted(p.glob("*.log")); print(logs[-1].read_text()[-3000:] if logs else "")'
        raise SystemExit(subprocess.run(['ssh','-F','/dev/null','-o','BatchMode=yes',HOST,'python3 -c '+shlex.quote(script)]).returncode)
    if args.mode == 'collect':
        out = ROOT/'evidence'/args.label
        archive_path = out/'results.tar.gz'
        if (out/'results').exists() or (out/'collection.json').exists():
            raise ValueError('Refusing to overwrite collected results')
        if not args.existing_collection:
            script = 'import tarfile,sys; a=tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz"); a.add('+repr(REMOTE+args.label+'/results')+',arcname="results"); a.close()'
            with archive_path.open('xb') as stream:
                rc = subprocess.run(['ssh','-F','/dev/null','-o','BatchMode=yes',HOST,'python3 -c '+shlex.quote(script)],stdout=stream).returncode
            if rc: raise SystemExit(rc)
        with tarfile.open(archive_path) as a:
            receipt=collection_receipt(a)
            a.extractall(out,filter='data')
        for name,meta in receipt.get('artifacts',{}).items():
            if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('Unsafe artifact name')
            payload=(out/'results'/name).read_bytes()
            if len(payload)!=meta['bytes'] or hashlib.sha256(payload).hexdigest()!=meta['sha256']:
                raise ValueError('Artifact integrity mismatch')
        collected={'collected':str(archive_path),'sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                   'verified_artifacts':len(receipt.get('artifacts',{})),
                   'existing_archive':args.existing_collection}
        (out/'collection.json').write_text(json.dumps(collected,indent=2)+'\n')
        print(json.dumps(collected))
        return
    out = ROOT / 'evidence' / args.label
    out.mkdir()
    capsule = out / 'source.tar.gz'
    with tarfile.open(capsule, 'w:gz') as archive:
        for name in ['CMakeLists.txt', 'cmake', 'tests', 'config', 'experiments/ple_flow.c', 'experiments/ple_flow.h', 'tools/q2-runner.py', 'tools/q2-remote.py', 'tools/q2_process.py', 'tools/q2_thermal.py', 'tools/q2_reuse.py', 'tools/analyze-q2-profile.py', 'tools/q2-resource-report.py', 'tools/analyze-q2-hc-up.py']:
            archive.add(ROOT / name, arcname=name)
        source = '.deps/gufo-base' if args.mode in ('ud-base','ud-profile','ud-bench2k') else '.deps/gufo-q2-register-reference' if args.mode == 'operators-reference' else '.deps/gufo-q2'
        if args.source_variant != 'qualified':
            source = '.deps/gufo-q2-bench-' + args.source_variant
        if args.mode in ('ple-cpu', 'q2-ple', 'ud-ple'):
            source = '.deps/gufo-ple-' + ('ud' if args.mode == 'ud-ple' else 'q2')
        if args.mode in ('ple-io-cpu', 'q2-ple-io', 'ud-ple-io'):
            source = '.deps/gufo-ple-io-' + ('ud' if args.mode == 'ud-ple-io' else 'q2')
        if args.mode in ('ple-cache-cpu', 'q2-ple-cache64k'):
            source = '.deps/gufo-ple-cache64k'
        if args.mode in ('ple-lookahead-cpu', 'q2-ple-lookahead', 'q2-ple-first-access'):
            source = '.deps/gufo-q2-bench-ple-lookahead'
        archive.add(ROOT / source, arcname='source')
    dest = REMOTE + args.label
    # Exclusive destination and data-only extraction. No model or foreign path.
    script = '\n'.join([
        'import os,pathlib,sys,tarfile',
        'root=pathlib.Path(' + repr(dest) + ')',
        'root.mkdir()',
        'with tarfile.open(fileobj=sys.stdin.buffer,mode="r|gz") as archive:',
        ' for item in archive:',
        '  path=pathlib.PurePosixPath(item.name)',
        '  if path.is_absolute() or ".." in path.parts or not (item.isdir() or item.isfile()): raise ValueError("unsafe member")',
        '  if item.size>16000000: raise ValueError("oversized source file")',
        '  archive.extract(item,root,filter="data")',
        'os.execv(sys.executable,[sys.executable,str(root/"tools/q2-runner.py"),' + repr(args.mode) + (',' + repr('--rebuild-mmq') if args.rebuild_mmq else '') + '])',
    ])
    argv = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', HOST,
            'python3 -c ' + shlex.quote(script)]
    result = {'mode': args.mode, 'source_variant': args.source_variant, 'source_path': source, 'rebuild_mmq': args.rebuild_mmq, 'label': args.label, 'remote': dest,
              'capsule_sha256': hashlib.sha256(capsule.read_bytes()).hexdigest(),
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with capsule.open('rb') as inp, (out/'remote.log').open('wb') as log:
        run = subprocess.run(argv, stdin=inp, stdout=log, stderr=subprocess.STDOUT)
    result['exit_code'] = run.returncode
    result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out/'transport.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result), flush=True)
    print((out/'remote.log').read_text()[-7000:], flush=True)
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
