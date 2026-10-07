#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional independent review of a native diagnostic; never runs inference.

The production builder/core remain C17 and Python-free. This development oracle
checks actual process success, complete raw rows and independently reconstructed
directions. Valid captures do not establish steering quality or performance.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

COMPONENTS = {'attention': 1, 'ffn': 2, 'both': 3}
BANKS = {1: 'direction.attention.f32', 2: 'direction.ffn.f32'}
SETTINGS = {'context', 'prefill_chunk', 'components', 'rope', 'prompt_format',
            'max_pairs', 'max_host_bytes', 'max_output_bytes', 'timeout_seconds'}
REL_TOLERANCE = 2e-6
ABS_TOLERANCE = 2e-8
NORM_TOLERANCE = 1e-6


def validate_settings(value):
    if type(value) is not dict or set(value) != SETTINGS:
        raise ValueError('Expected complete bounded steering build settings')
    for name, low, high in (('context', 1, 8192), ('prefill_chunk', 1, 8192),
                           ('max_pairs', 1, 32), ('max_host_bytes', 65536, 512 * 2**20),
                           ('max_output_bytes', 65536, 64 * 2**20), ('timeout_seconds', 1, 3600)):
        if type(value[name]) is not int or not low <= value[name] <= high:
            raise ValueError('Invalid steering build bound: ' + name)
    if (any(type(value[name]) is not str for name in ('components', 'rope', 'prompt_format')) or
            value['prefill_chunk'] > value['context'] or
            value['components'] not in COMPONENTS or value['rope'] not in ('native', 'yarn2', 'yarn4') or
            value['prompt_format'] not in ('chat', 'raw')):
        raise ValueError('Invalid steering build selection')
    return dict(value)


def regular(path, maximum):
    path = Path(path)
    if path.resolve() != path:
        raise RuntimeError('Capture path must be canonical without symlinks')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                not 1 <= before.st_size <= maximum):
            raise RuntimeError('Invalid bounded regular steering artifact')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(maximum + 1)
        after = os.fstat(fd)
        named = path.stat(follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if (len(data) != before.st_size or not stat.S_ISREG(named.st_mode) or
                any(getattr(before, key) != getattr(after, key) for key in fields) or
                any(getattr(after, key) != getattr(named, key) for key in fields)):
            raise RuntimeError('Steering artifact changed during review')
        return data, {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    finally:
        os.close(fd)


def input_pair(directory, max_pairs):
    found = {}
    counts = []
    for side in ('target', 'contrast'):
        data, identity = regular(Path(directory) / (side + '-prompts.txt'), 32 * 2**20)
        text = data.decode('utf-8')
        if '\0' in text:
            raise RuntimeError('NUL in steering prompt dataset')
        lines = text.split('\n')
        if lines[-1] == '':
            lines.pop()
        for line in lines:
            content = line[:-1] if line.endswith('\r') else line
            if not content.strip(' \t\r') or len(content.encode('utf-8')) > 65536:
                raise RuntimeError('Empty or oversized steering prompt line')
        if not 1 <= len(lines) <= max_pairs:
            raise RuntimeError('Steering pair limit exceeded')
        found[side + '-prompts.txt'] = identity
        counts.append(len(lines))
    if counts[0] != counts[1]:
        raise RuntimeError('Target and contrast prompt counts differ')
    return found, counts[0]


def strict_object(items):
    result = {}
    for name, value in items:
        if name in result:
            raise RuntimeError('Duplicate steering journal key')
        result[name] = value
    return result


def invalid_constant(_value):
    raise RuntimeError('Nonfinite JSON constant in steering journal')


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise RuntimeError('Invalid steering integer: ' + name)
    return value


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def matches(row, expected):
    return all(type(row.get(key)) is type(value) and row.get(key) == value for key, value in expected.items())


def validate(directory, settings, sources, pairs, actual_exit, build_id, source_pin,
             model, *, expected_synthetic=False):
    settings = validate_settings(settings)
    if type(actual_exit) is not int or actual_exit != 0:
        raise RuntimeError('Actual native steering builder exit must be zero')
    integer(pairs, 1, settings['max_pairs'], 'pairs')
    directory = Path(directory)
    if not directory.is_dir() or directory.resolve() != directory:
        raise RuntimeError('Steering capture directory must be canonical')
    copied, copied_pairs = input_pair(directory, settings['max_pairs'])
    if copied != sources or copied_pairs != pairs:
        raise RuntimeError('Native source copies do not match admitted dataset')
    journal, journal_identity = regular(directory / 'build.jsonl', min(16 * 2**20, settings['max_output_bytes']))
    raw, raw_identity = regular(directory / 'activations.f32le', settings['max_output_bytes'])
    if not journal.endswith(b'\n') or len(raw) % 4:
        raise RuntimeError('Incomplete journal or raw binary32 payload')
    rows = [json.loads(line, object_pairs_hook=strict_object, parse_constant=invalid_constant)
            for line in journal.decode('utf-8').splitlines()]
    if not rows or any(type(row) is not dict for row in rows):
        raise RuntimeError('Steering journal must contain objects')
    at = 0

    def take(event):
        nonlocal at
        if at >= len(rows) or rows[at].get('event') != event:
            raise RuntimeError('Missing, duplicate or out-of-order steering event: ' + event)
        result = rows[at]
        at += 1
        return result

    identity = take('identity')
    expected = {'schema': 'synapse-lie.steering-build.v1', 'program': 'lie-steering-build',
                'build_id': build_id, 'source_pin': source_pin, 'synthetic': expected_synthetic,
                'classification': 'NOT-INFERENCE' if expected_synthetic else 'ACTIVATION-CAPTURE-QUALITY-UNQUALIFIED',
                'encoding': 'headerless IEEE754-F32-little-endian', 'model': model,
                'target_sha256': sources['target-prompts.txt']['sha256'],
                'contrast_sha256': sources['contrast-prompts.txt']['sha256'],
                'pairs': pairs, 'components': COMPONENTS[settings['components']],
                'context': settings['context'], 'prefill_chunk': settings['prefill_chunk'],
                'rope': settings['rope'], 'prompt_format': 'raw' if settings['prompt_format'] == 'raw' else 'chat-thinking-disabled',
                'max_host_bytes': settings['max_host_bytes'], 'max_output_bytes': settings['max_output_bytes']}
    if (not matches(identity, expected) or
            not isinstance(identity.get('engine'), str) or not identity['engine']):
        raise RuntimeError('Unexpected native steering identity or controls')
    geometry = take('geometry')
    layers = integer(geometry.get('layers'), 1, 512, 'layers')
    width = integer(geometry.get('width'), 1, 65536, 'width')
    branches = integer(geometry.get('ffn_branches'), 1, 64, 'ffn_branches')
    selected = tuple(c for c in (2, 1) if c & COMPONENTS[settings['components']])
    coordinate_count = layers * width
    expected_rows = layers * len(selected)
    # All represented coordinates must already fit the bounded raw artifact.
    if coordinate_count * len(selected) * pairs * 2 * 4 > len(raw):
        raise RuntimeError('Steering geometry exceeds captured payload')
    row_bytes = width * (branches if 2 in selected else 1) * 4
    if not matches(geometry, {'observer_row_bytes': row_bytes}):
        raise RuntimeError('Wrong native observer row reservation')
    terms = {c: [[] for _ in range(coordinate_count)] for c in selected}
    cursor = 0
    prompts = []
    for pair in range(pairs):
        captures = []
        for side in ('target', 'contrast'):
            begin = take('prompt_begin')
            count = integer(begin.get('physical_tokens'), 1, settings['context'], 'physical_tokens')
            ids = begin.get('token_ids')
            if (not matches(begin, {'pair': pair, 'side': side, 'last_token_position': count - 1}) or
                    type(ids) is not list or len(ids) != count or
                    any(type(token) is not int or not 0 <= token <= 2147483647 for token in ids)):
                raise RuntimeError('Incorrect prompt identity or physical token IDs')
            values = {c: [None] * layers for c in selected}
            for _ in range(expected_rows):
                row = take('activation_row')
                component = row.get('component')
                layer = integer(row.get('layer'), 0, layers - 1, 'layer')
                row_branches = branches if component == 2 else 1
                value_count = width * row_branches
                byte_count = value_count * 4
                expected_row = {'pair': pair, 'side': side, 'capture_status': 0,
                                'component': component, 'layer': layer, 'width': width,
                                'branches': row_branches, 'values': value_count, 'bytes': byte_count,
                                'token_position': count - 1, 'offset_bytes': cursor}
                if (type(component) is not int or component not in selected or
                        values[component][layer] is not None or
                        not matches(row, expected_row) or
                        cursor + byte_count > len(raw)):
                    raise RuntimeError('Refused, duplicate, incomplete or wrong-position activation row')
                floats = struct.unpack_from('<' + str(value_count) + 'f', raw, cursor)
                if any(not math.isfinite(value) for value in floats):
                    raise RuntimeError('Nonfinite raw activation')
                values[component][layer] = [f32(math.fsum(floats[b * width + i] for b in range(row_branches)) / row_branches)
                                            for i in range(width)]
                cursor += byte_count
            end = take('prompt_end')
            expected_end = {'pair': pair, 'side': side, 'prefill_attempted': True, 'prefill_status': 0,
                            'completed_prefix_tokens': count, 'rows': expected_rows, 'expected_rows': expected_rows,
                            'accepted': True, 'error': ''}
            if not matches(end, expected_end):
                raise RuntimeError('Activation rows do not prove complete successful prefill')
            captures.append(values)
            prompts.append({'pair': pair, 'side': side, 'physical_tokens': count,
                            'physical_ids_sha256': hashlib.sha256(b''.join(struct.pack('<i', token) for token in ids)).hexdigest(),
                            'one_token_tail': (count - 1) % settings['prefill_chunk'] == 0})
        for component in selected:
            for layer in range(layers):
                for i in range(width):
                    terms[component][layer * width + i].append(captures[0][component][layer][i] - captures[1][component][layer][i])
        accepted = take('pair_accepted')
        if not matches(accepted, {'pair': pair, 'accepted_pairs': pair + 1}):
            raise RuntimeError('Incomplete target/contrast pair acceptance')
    raw_complete = take('raw_complete')
    if (cursor != len(raw) or not matches(raw_complete, {'file': 'activations.f32le',
            'bytes': len(raw), 'sha256': raw_identity['sha256']})):
        raise RuntimeError('Raw activation bytes or hash do not match complete capture')
    banks = {}
    for component in selected:
        bank = take('bank')
        filename = BANKS[component]
        data, binding = regular(directory / filename, settings['max_output_bytes'])
        if (len(data) != coordinate_count * 4 or not matches(bank, {'file': filename,
                'layers': layers, 'width': width, 'pairs': pairs, 'bytes': len(data), 'sha256': binding['sha256']})):
            raise RuntimeError('Published DS4-format bank does not match journal/geometry')
        actual = struct.unpack('<' + str(coordinate_count) + 'f', data)
        maximum_error = 0.0
        maximum_norm_error = 0.0
        for layer in range(layers):
            sums = [math.fsum(terms[component][layer * width + i]) for i in range(width)]
            norm = math.hypot(*sums)
            if not math.isfinite(norm) or not norm:
                raise RuntimeError('Zero or invalid independently learned layer')
            layer_values = actual[layer * width:(layer + 1) * width]
            norm_error = abs(math.hypot(*layer_values) - 1)
            if not math.isfinite(norm_error) or norm_error > NORM_TOLERANCE:
                raise RuntimeError('Published direction layer does not have unit L2 norm')
            maximum_norm_error = max(maximum_norm_error, norm_error)
            for value, total in zip(layer_values, sums):
                expected_value = f32(total / norm)
                error = abs(value - expected_value)
                if not math.isfinite(value) or not math.isclose(value, expected_value, rel_tol=REL_TOLERANCE, abs_tol=ABS_TOLERANCE):
                    raise RuntimeError('Published bank differs from independent raw-row direction')
                maximum_error = max(maximum_error, error)
        banks[filename] = {**binding, 'independent_max_absolute_error': maximum_error,
                           'maximum_layer_unit_norm_error': maximum_norm_error}
    terminal = take('complete')
    integer(terminal.get('owned_host_peak_bytes'), 1, settings['max_host_bytes'], 'owned_host_peak_bytes')
    if (at != len(rows) or not matches(terminal, {'exit_code': 0, 'accepted_pairs': pairs,
            'raw_bytes': len(raw), 'error': ''})):
        raise RuntimeError('Incomplete or failed terminal native steering record')
    expected_files = {'target-prompts.txt', 'contrast-prompts.txt', 'build.jsonl', 'activations.f32le', *banks}
    if {path.name for path in directory.iterdir()} != expected_files:
        raise RuntimeError('Unexpected partial or foreign file in accepted capture')
    if sum(path.stat().st_size for path in directory.iterdir()) > settings['max_output_bytes']:
        raise RuntimeError('Native outputs exceed admitted output byte budget')
    return {'schema': 'synapse-lie.point-steering-build.v1', 'state': 'PASSED',
            'classification': 'SYNTHETIC_HOST_ORACLE_NOT_INFERENCE' if expected_synthetic else 'ORIGINAL_ACTIVATION_CAPTURE_LEARNED_QUALITY_UNQUALIFIED',
            'actual_native_exit_code': actual_exit, 'pairs': pairs, 'prompts': prompts,
            'captured_rows': expected_rows * pairs * 2, 'layers': layers, 'width': width,
            'ffn_branches': branches, 'settings': settings, 'native_identity': identity,
            'source_inputs': sources, 'journal': journal_identity, 'raw': raw_identity, 'banks': banks,
            'independent_oracle': 'raw LE-F32 branch means rounded to F32; math.fsum target-minus-contrast; math.hypot unit L2 per layer',
            'tolerances': {'relative': REL_TOLERANCE, 'absolute': ABS_TOLERANCE, 'unit_norm_absolute': NORM_TOLERANCE},
            'model_generation_or_quality_tested': False, 'performance_comparison': False}
