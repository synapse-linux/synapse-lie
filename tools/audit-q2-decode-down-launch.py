#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline address-domain review of the frozen scalar Q2 down integration.

This is source/ELF bookkeeping, not a GPU execution or numerical check.
"""

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'config/q2-decode-down-rows-model-source.json'
    manifest = json.loads(manifest_path.read_text())
    provider = ROOT / manifest['source']
    rel = 'src/models/qwen38_flash_next/kernels/rocm/'
    reviewed = ['executor.cpp', 'q2_decode_down_rows.hip',
                'q2_decode_down_rows.inc', 'mmq/qfn_mmq.hip.cpp',
                'mmq/mmvq.hip.cpp', 'mmq/common.hpp', 'mmq/ggml-common.h']
    digests = {name: sha(provider / (rel + name)) for name in reviewed}
    if any(digest != manifest['files'][rel + name]
           for name, digest in digests.items()):
        raise ValueError('Reviewed source differs from frozen model capsule')
    build_path = ROOT / 'config/q2-decode-down-rows-build.json'
    build = json.loads(build_path.read_text())
    binary = ROOT / build['server']
    if sha(binary) != build['server_sha256']:
        raise ValueError('Frozen server differs')
    nm = subprocess.run(['nm', '-C', str(binary)], text=True,
                        capture_output=True, check=True)
    symbols = [line for line in nm.stdout.splitlines()
               if 'get_ctx_for_device' in line or 'Q2DecodeDownRows4' in line]
    contexts = [line for line in symbols
                if ' T qfn_mmq::get_ctx_for_device(int)' in line]
    if len(contexts) != 1:
        raise ValueError('Expected one original shared MMQ context entry')

    # Reviewed launch: grid(640,1,2), block(32,8); inactive token waves return.
    rows, slots, experts = 2560, 10, 512
    writes = [slot * rows + block * 4 + lane
              for z in range(2) for y in range(8)
              if (slot := z * 8 + y) < slots
              for block in range(640) for lane in range(4)]
    if len(writes) != rows * slots or sorted(writes) != list(range(rows * slots)):
        raise ValueError('Output domain is not complete and singly owned')
    q2_blocks = experts * rows * (768 // 256)
    report = {
        'schema': 'synapse-lie.q2-decode-down-launch-review.v1',
        'source_manifest_sha256': sha(manifest_path),
        'build_manifest_sha256': sha(build_path),
        'reviewed_source_sha256': digests,
        'server_sha256': build['server_sha256'],
        'context_and_wrapper_symbols': symbols,
        'original_and_candidate_quantizer_dimensions':
            [640, 640, 640, 6400, 1024, 1, 10, 1],
        'original_and_candidate_consumer_dimensions':
            [768, 2560, 3, 32, 2560, 7680, 2560, 10, 1],
        'input_f32_bytes': slots * 640 * 4,
        'packed_q8_1_pool_bytes': slots * (1024 // 32) * 36,
        'output_f32_bytes': slots * rows * 4,
        'output_elements_singly_owned': len(writes),
        'expert_id_elements_read': slots,
        'max_q2_block_index_for_id_511': q2_blocks - 1,
        'weight_tensor_bytes': q2_blocks * 84,
        'original_blocks': 1280 * 2,
        'candidate_blocks': 640 * 2,
        'new_persistent_allocations': 0,
        'source_review': 'Same original context, pool reservation and RAII release; same stream and quantizer. Only rows per wave and x-grid differ.',
        'assumptions': ['Router IDs are negative (inactive) or in [0,511], as required by the original path.',
                        'Original device allocations cover the declared model geometry.'],
        'limits': ['Argument lists are a source review, not runtime packet capture.',
                   'Address-domain accounting does not execute the quantized dot product or allocator.',
                   'No GPU fault, numerical, performance or task-quality qualification.',
                   'The outstanding .157 model run still requires logs and verified closure.'],
        'gpu_executed': False,
        'model_accessed': False,
        'audit_tool_sha256': sha(Path(__file__))}
    output = ROOT / 'config/q2-decode-down-launch-review.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
