#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze the retained Q2 provider and common HTTP core for the 256K curve."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def main():
    previous_path = ROOT / 'config/q2-curve-source.json'
    previous = json.loads(previous_path.read_text())
    parent_path = ROOT / 'config/q2-iq2-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-fixed-bounds']
    core = ROOT / previous['core_source']
    assert inventory(core) == previous['core_files']
    assert inventory(ROOT / parent['source']) == parent['files']
    assert inventory(ROOT / previous['variants']['ud']['source']) == previous['variants']['ud']['files']
    for name in ('access-edits.json', 'sampling-edits.json'):
        for edit in json.loads((core / 'adapters/gufo-state' / name).read_text())['edits']:
            assert (ROOT / parent['source'] / edit['path']).read_text().count(edit['new']) == 1
    output = ROOT / 'config/q2-curve256-source.json'
    candidate = ROOT / '.deps/lie-q2-curve256-core'
    assert not output.exists() and not candidate.exists()
    shutil.copytree(core, candidate)
    path = candidate / 'include/lie/core.h'
    text = path.read_text()
    assert text.count('#define LIE_CORE_MAX_CONTEXT 262144u') == 1
    path.write_text(text.replace('#define LIE_CORE_MAX_CONTEXT 262144u', '#define LIE_CORE_MAX_CONTEXT 266240u'))
    path = candidate / 'src/server.c'
    text = path.read_text()
    assert text.count('128..262144]') == 1
    path.write_text(text.replace('128..262144]', '128..266240]'))
    path = candidate / 'CMakeLists.txt'
    with path.open('a') as stream:
        stream.write('''
# SPDX-License-Identifier: MIT
# Private 256K-curve host gate; no model/GPU use.
if(BUILD_TESTING)
  add_test(NAME q2-curve256-launch-contract
    COMMAND python3 "${CMAKE_SOURCE_DIR}/../tests/q2_remote_test.py")
  set_tests_properties(q2-curve256-launch-contract PROPERTIES TIMEOUT 120)
endif()
''')
    files = inventory(candidate)
    delta = sorted(name for name in files if files[name] != previous['core_files'].get(name))
    assert delta == ['CMakeLists.txt', 'include/lie/core.h', 'src/server.c']
    report = dict(schema='synapse-lie.q2-curve256-source.v1',
        source_pin=previous['source_pin'], core_source=str(candidate.relative_to(ROOT)),
        core_files=files, core_changed_files=delta,
        original_core_manifest=str(previous_path.relative_to(ROOT)), original_core_manifest_sha256=sha(previous_path),
        retained_parent_manifest=str(parent_path.relative_to(ROOT)), retained_parent_manifest_sha256=sha(parent_path),
        variants={'q2':dict(source=parent['source'], files=parent['files'], numerical_changes=False),
                  'ud':previous['variants']['ud']},
        generator='tools/prepare-q2-curve256.py', generator_sha256=sha(Path(__file__)),
        context_capacity=266240, prefix_depth_max=262144, new_prompt_tokens=2048, output_tokens=128,
        scope='Common C17 core changes only private capacity ceiling/help plus a no-model launch test. Retained Q2 and saved pristine-UD provider sources are unchanged. Capacity leaves space for the 256K prefix and new tokens.',
        GPU_admission=False, model_inference=False)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(core_files=len(files), changed=delta,
        providers={k:len(v['files']) for k,v in report['variants'].items()}, model_inference=False)))


if __name__ == '__main__':
    main()
