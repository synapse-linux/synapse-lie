#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the same first-party serving profile for all three Q2 arithmetic arms."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / '.deps/lie-terminal-core'
dest = ROOT / '.deps/lie-terminal-core-bench'
manifest_path = ROOT / 'config/q2-terminal-core-source.json'
manifest = json.loads(manifest_path.read_text())
if dest.exists():
    raise SystemExit('Refusing to overwrite the prepared core')
for name, expected in manifest['files'].items():
    if hashlib.sha256((base / name).read_bytes()).hexdigest() != expected:
        raise SystemExit('Frozen core identity changed: ' + name)
shutil.copytree(base, dest)
edits = {
    'src/chat.c': [('out->max_tokens = 128;', 'out->max_tokens = LIE_CHAT_MAX_OUTPUT;')],
    'tests/test_chat.c': [('r.max_tokens==128', 'r.max_tokens==LIE_CHAT_MAX_OUTPUT')],
    'src/server.c': [(
        '                json_object_object_add(m,"owned_by",json_object_new_string(lie_backend_name()));',
        '                json_object_object_add(m,"owned_by",json_object_new_string(lie_backend_name()));\n'
        '                lie_worker_info model_info; lie_worker_snapshot(s->worker,&model_info);\n'
        '                json_object_object_add(m,"context_length",json_object_new_int64(model_info.model.context_tokens));\n'
        '                json_object_object_add(m,"max_output_tokens",json_object_new_int64(LIE_CHAT_MAX_OUTPUT));')],
}
patch = []
for name, replacements in edits.items():
    before = (base / name).read_text()
    after = before
    for old, new in replacements:
        if after.count(old) != 1:
            raise SystemExit('Ambiguous source anchor: ' + name)
        after = after.replace(old, new)
    (dest / name).write_text(after)
    patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                    fromfile='a/' + name, tofile='b/' + name))
(ROOT / 'experiments/q2-terminal-core.patch').write_text(''.join(patch))
manifest['base_files'] = manifest['files']
manifest['files'] = {str(p.relative_to(dest)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(dest.rglob('*')) if p.is_file()}
manifest['variant'] = 'terminal-context-metadata-default4096-v1'
manifest['scope'] = ('Frozen C17 serving profile, unchanged numerical adapter; advertise actual '
                     'context capacity and default to the existing 4096 output-token ceiling. '
                     'No qualified source or core worktree modification.')
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'source': str(dest), 'changed_files': list(edits), 'commit': manifest['commit']}))
