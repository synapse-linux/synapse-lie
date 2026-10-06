#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bound only the selector launch grid; preserve score pitch and every kernel."""
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prior',ROOT/'tools/prepare-q2-ssm-row-group.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
sha,once=prior.sha,prior.once


def main():
    manifest=ROOT/'config/q2-iq2-fixed-bounds-source.json'
    parent=json.loads(manifest.read_text())['variants']['iq2-fixed-bounds']
    base=ROOT/parent['source'];assert prior.inventory(base)==parent['files']
    text=(base/prior.REL).read_text();a=text.index('void SelectBlocks(');b=text.index('void Attention(',a)
    body=text[a:b].replace('void SelectBlocks(', 'void SelectBlocksLiveGrid(')
    body=once(body,'std::uint32_t max_blocks, hipStream_t stream)',
              'std::uint32_t max_blocks, std::uint32_t live_blocks, hipStream_t stream)')
    body=once(body,'const dim3 grid(n_tokens, (max_blocks + kThreads - 1) / kThreads);',
              'const dim3 grid(n_tokens, (std::min(live_blocks, max_blocks) + kThreads - 1) / kThreads);')
    body=body.replace('// Grids are sized by max_blocks so a captured decode graph replays at any\n  // position; blocks past the live range return at once.',
              '// Eager prefill knows the last live block. Keep the allocated score pitch\n  // and mask stride; only blocks that always return without effects are omitted.\n  // Captured decode must keep its original capacity grid.')
    out=ROOT/'evidence/q2-select-live-grid-preparation';inc=ROOT/'experiments/q2-select-live-grid.inc'
    assert not out.exists() and not inc.exists();out.mkdir()
    formatted=subprocess.run(['clang-format','--style=file:'+str(base/'.clang-format')],
        input='// SPDX-License-Identifier: MIT\n// Derived from the pinned Gufo selector launch; unchanged GPU kernels.\n'+body,text=True,capture_output=True)
    assert formatted.returncode==0,formatted.stderr;inc.write_text(formatted.stdout)
    (out/'draft.inc').write_bytes(inc.read_bytes());probe=out/'probe.hip.cpp'
    probe.write_text('// SPDX-License-Identifier: MIT\n#include "../../'+parent['source']+'/'+prior.REL+'"\n'
        'namespace gufo::models::qwen38_flash_next::rocm {\n#include "draft.inc"\n}\n')
    argv=json.loads((ROOT/'evidence/q2-iq2-fixed-bounds-preparation/assembly-argv.json').read_text())
    argv[argv.index('-S')+1]=str(probe.relative_to(ROOT));assembly=out/'candidate.s'
    argv[argv.index('-o')+1]=str(assembly.relative_to(ROOT))
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out/'assembly.stdout').open('x') as stdout,(out/'assembly.stderr').open('x') as stderr:
        result=subprocess.run(argv,cwd=ROOT,stdout=stdout,stderr=stderr)
    report=dict(argv=argv,started_at=started,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        exit_code=result.returncode,draft=str(inc.relative_to(ROOT)),draft_sha256=sha(inc),
        parent_manifest_sha256=sha(manifest),assembly_sha256=sha(assembly) if assembly.exists() else None,
        numerical_kernels_changed=False,score_pitch_changed=False,mask_stride_changed=False,
        topk_changed=False,GPU_run=False,production_selector=False,model_speedup=False)
    (out/'assembly-command.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(exit_code=result.returncode,GPU_run=False)));return result.returncode


if __name__=='__main__':
    raise SystemExit(main())
