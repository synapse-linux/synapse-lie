#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create private 4K/8K providers; never edit either retained source capsule."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'src/models/qwen38_flash_next/'
HIP = MODEL + 'kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Nonunique source anchor: ' + old)
    return text.replace(old, new, 1)


def main():
    parents = [('provider', 'config/q2-decode-down-rows-model-source.json',
                'source', 'files', '.deps/gufo-q2-prefill-chunks'),
               ('core', 'config/q2-curve128-source.json',
                'core_source', 'core_files', '.deps/lie-q2-prefill-chunks')]
    report = dict(schema='synapse-lie.q2-prefill-chunks-source.v1',
                  chunk_sizes=[2048, 4096, 8192], default_chunk=2048,
                  source_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
                  GPU_admission=False, runtime_qualified=False,
                  generator_sha256=sha(Path(__file__)))
    for kind, manifest_name, path_key, files_key, destination in parents:
        parent = json.loads((ROOT / manifest_name).read_text())
        source, output = ROOT / parent[path_key], ROOT / destination
        for name, digest in parent[files_key].items():
            if sha(source / name) != digest:
                raise ValueError('Retained source changed: ' + name)
        if output.exists():
            raise ValueError('Preserve existing private source: ' + str(output))
        edits = {}

        def edit(name, old, new):
            edits[name] = once(edits.get(name, (source / name).read_text()), old, new)

        if kind == 'provider':
            edit(MODEL + 'engine.hpp', '  std::uint32_t max_context = 4096;',
                 '  std::uint32_t max_context = 4096;\n'
                 '  /// Explicit bounded prefill capacity; default preserves the retained path.\n'
                 '  std::uint32_t prefill_chunk_tokens = 2048;')
            edit(MODEL + 'engine.cpp',
                 '// gfx1151 pp4096 at depths 0/4096: the 512/1024/2048/4096 sweep favored\n'
                 '// 2048; larger chunks used more scratch without improving throughput.\n'
                 'constexpr std::uint32_t kPrefillChunkTokens = 2048;\n',
                 '// The serving owner selects scratch capacity explicitly.\n')
            edit(MODEL + 'engine.cpp', '  m->options_ = options;',
                 '  if (!options.prefill_chunk_tokens || options.prefill_chunk_tokens > 8192) {\n'
                 '    AssignError(error_msg, "prefill chunk must be between one and 8192");\n'
                 '    return nullptr;\n  }\n  m->options_ = options;')
            edit(MODEL + 'engine.cpp',
                 'return std::min(kPrefillChunkTokens, options_.max_context);',
                 'return std::min(options_.prefill_chunk_tokens, options_.max_context);')
            edit(HIP + 'executor.cpp', 'n_tokens >= 1024 && n_tokens <= 4096 &&',
                 'n_tokens >= 1024 && n_tokens <= 8192 &&')
            for prefix in ('!wide_mixer_ && ', 'iq2_wmma && !wide_mixer_ && '):
                old = prefix + 'n_tokens == 2048 &&'
                # The shorter anchor occurs in both expressions. Anchor the
                # declarations, so each replacement has an unambiguous owner.
                if prefix == '!wide_mixer_ && ':
                    old = 'const bool produce_half =\n      ' + old
                    new = 'const bool produce_half =\n      !wide_mixer_ && lie_q2_deferred_norm_rows(n_tokens) &&'
                else:
                    old = 'const bool compact_down = ' + old
                    new = 'const bool compact_down = iq2_wmma && !wide_mixer_ && lie_q2_deferred_norm_rows(n_tokens) &&'
                edit(HIP + 'executor.cpp', old, new)
            name = HIP + 'lie_q2_deferred_norm_state.h'
            edit(name, 'static inline void lie_q2_deferred_norm_clear(',
                 '/* Only selected full chunk shapes; other partial rows retain their fallback. */\n'
                 'static inline bool lie_q2_deferred_norm_rows(uint32_t rows) {\n'
                 '    return rows == 2048 || rows == 4096 || rows == 8192;\n}\n\n'
                 'static inline void lie_q2_deferred_norm_clear(')
            edit(name, 'rows != 2048)', '!lie_q2_deferred_norm_rows(rows))')
            edit(name, 'state->rows == 2048 &&', 'lie_q2_deferred_norm_rows(state->rows) &&')
            edit(HIP + 'iq2_mixed_tiles.c', 'tokens > 4096', 'tokens > 8192')
            edit(HIP + 'iq2_mixed_tiles.h', '<=4096 tokens.', '<=8192 tokens.')
            edit(HIP + 'q2_hc_down_bk256.inc', 'batch > 2048', 'batch > 8192')
        else:
            for name, old in [('adapters/gufo.cpp', 'o->prefill_chunk_tokens > 2048'),
                              ('src/worker.c', 'o->chunk>2048'),
                              ('src/server.c', 'options.chunk > 2048')]:
                edit(name, old, old.replace('2048', '8192'))
            edit('adapters/gufo.cpp', 'options.max_context = o->context_tokens;',
                 'options.max_context = o->context_tokens;\n'
                 '        options.prefill_chunk_tokens = o->prefill_chunk_tokens;')
        shutil.copytree(source, output)
        patches = []
        for name, value in sorted(edits.items()):
            (output / name).write_text(value)
            if kind == 'provider':
                subprocess.run(['clang-format', '-i', str(output / name)], check=True)
            patches.append(''.join(difflib.unified_diff(
                (source / name).read_text().splitlines(True),
                (output / name).read_text().splitlines(True),
                fromfile='a/' + name, tofile='b/' + name)))
        patch = ROOT / ('experiments/q2-prefill-chunks-' + kind + '.patch')
        patch.write_text(''.join(patches))
        report[kind] = dict(source=destination, parent_manifest=manifest_name,
            parent_manifest_sha256=sha(ROOT / manifest_name),
            files={name: sha(output / name) for name in parent[files_key]},
            changed_files=sorted(edits), patch=str(patch.relative_to(ROOT)),
            patch_sha256=sha(patch))
    (ROOT / 'config/q2-prefill-chunks-source.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k]['changed_files'] for k in ('core', 'provider')}))


if __name__ == '__main__':
    main()
