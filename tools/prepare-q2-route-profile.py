#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record existing host expert counts without changing routing or arithmetic."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = 'src/models/qwen38_flash_next/kernels/rocm/executor.cpp'
HEADER = 'q2_route_profile.hpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected executor anchor: '+old[:80])
    return text.replace(old, new, 1)


def main():
    parent_path = ROOT/'config/q2-iq2-signs-ordered-asm-source.json'
    parent = json.loads(parent_path.read_text())
    base = ROOT/parent['candidate']
    if inventory(base) != parent['files']:
        raise ValueError('Measured ordered provider changed')
    out = ROOT/'.deps/gufo-q2-curve-route-profile'
    manifest = ROOT/'config/q2-route-profile-source.json'
    if out.exists() or manifest.exists():
        raise ValueError('Refusing to overwrite a source composition')
    source = (base/EXECUTOR).read_text()
    begin = source.index('bool Executor::Forward(Session& session,')
    end = source.index('\nbool Executor::ForwardBody(', begin)
    body = source[begin:end]
    body = once(body, '  const bool speculative =',
                '  q2routes::Span route_span{mode == ForwardMode::kPrefill, session.position(),\n'
                '                            static_cast<std::uint32_t>(tokens.size()), config().num_layers};\n'
                '  const bool speculative =')
    if not body.endswith('  return true;\n}\n'):
        raise ValueError('Unexpected Forward completion')
    body = body[:-len('  return true;\n}\n')]+'  route_span.completed = true;\n  return true;\n}\n'
    source = '#include "q2_route_profile.hpp"\n'+source[:begin]+body+source[end:]
    source = once(source, '  if (iq2_wmma) {\n',
        '  if (ExpertMatrixRows(n_tokens)) {\n'
        '    const bool pair = n_tokens >= 1024 && routed_tile_rows_ == 48;\n'
        '    q2routes::Observe(iq2_wmma, counts_host_, c.num_experts, used, n_tokens,\n'
        '                      routed_tile_rows_, routed_n_tiles_,\n'
        '                      pair ? routed_pair_rows_ : routed_tile_rows_,\n'
        '                      pair ? routed_pair_tiles_ : routed_n_tiles_);\n'
        '  }\n  if (iq2_wmma) {\n')
    shutil.copytree(base, out)
    (out/EXECUTOR).write_text(source)
    shutil.copyfile(ROOT/'experiments'/HEADER, out/HEADER)
    files = inventory(out)
    changed = [k for k in parent['files'] if files[k] != parent['files'][k]]
    if changed != [EXECUTOR] or files.keys()-parent['files'].keys() != {HEADER}:
        raise ValueError('Unexpected diagnostic delta')
    patch = ''.join(difflib.unified_diff((base/EXECUTOR).read_text().splitlines(True),
                    source.splitlines(True), fromfile='a/'+EXECUTOR, tofile='b/'+EXECUTOR))
    patch += ''.join(difflib.unified_diff([], (out/HEADER).read_text().splitlines(True),
                                       fromfile='/dev/null', tofile='b/'+HEADER))
    patch_path = ROOT/'experiments/q2-route-profile.patch'
    patch_path.write_text(patch)
    report = dict(schema='synapse-lie.q2-route-profile-source.v1',
        base=parent['candidate'], candidate=str(out.relative_to(ROOT)), files=files,
        parent_manifest_sha256=sha(parent_path), changed_files=changed, added_files=[HEADER],
        unchanged_files=len(parent['files'])-1, patch_sha256=sha(patch_path),
        scope='Existing CPU counts after their original event; no new GPU transfer, routing change, kernel edit or numerical change. Full canonical HTTP workload; diagnostic rates excluded.',
        gpu_runtime_validated=False, headline_eligible=False, promoted=False, goal_met=False)
    manifest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('candidate','changed_files','unchanged_files')}))


if __name__ == '__main__':
    main()
