#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare saved native ELF device functions without rebuilding or running them."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from elftools.elf.elffile import ELFFile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(path, output):
    # ROCm objdump extracts persistent offload bundles beside its input ELF.
    result = subprocess.run(['/opt/rocm/llvm/bin/llvm-objdump', '--offloading', str(path)],
                            capture_output=True, text=True)
    Path(str(output) + '.stdout').write_text(result.stdout)
    Path(str(output) + '.stderr').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError('Offload extraction failed: ' + str(result.returncode))
    functions, comments, bundles = {}, {}, {}
    for bundle in sorted(path.parent.glob(path.name + '.*.hipv4-*')):
        bundle_id = bundle.name.split('.')[-2]
        bundles[bundle_id] = {'bytes': bundle.stat().st_size,
                              'sha256': sha(bundle.read_bytes())}
        with bundle.open('rb') as stream:
            elf = ELFFile(stream)
            comment = elf.get_section_by_name('.comment')
            comments[bundle_id] = comment.data().decode(errors='replace') if comment else None
            symbols = elf.get_section_by_name('.symtab')
            resources = {symbol.name: symbol['st_value'] for symbol in symbols.iter_symbols()
                         if symbol['st_shndx'] == 'SHN_ABS'}
            for symbol in symbols.iter_symbols():
                if (symbol['st_info']['type'] != 'STT_FUNC' or not symbol['st_size'] or
                        not isinstance(symbol['st_shndx'], int)):
                    continue
                section = elf.get_section(symbol['st_shndx'])
                start = symbol['st_value'] - section['sh_addr']
                data = section.data()[start:start + symbol['st_size']]
                if len(data) != symbol['st_size']:
                    raise ValueError('Invalid function extent: ' + symbol.name)
                entry = {'sha256': sha(data), 'bytes': len(data), 'bundle': bundle_id,
                         'resources': {key: resources.get(symbol.name + '.' + key)
                                       for key in ('num_vgpr', 'num_agpr', 'private_seg_size')}}
                if symbol.name in functions and functions[symbol.name]['sha256'] != entry['sha256']:
                    raise ValueError('Different duplicate device function: ' + symbol.name)
                functions[symbol.name] = entry
    if not functions:
        raise ValueError('No device functions found')
    return {'path': str(path), 'sha256': sha(path.read_bytes()), 'bundles': bundles,
            'compiler_comments': comments, 'functions': functions, 'extraction_exit_code': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saved', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    old = inspect(args.saved, args.output.with_suffix('.saved'))
    new = inspect(args.candidate, args.output.with_suffix('.candidate'))
    a, b = old['functions'], new['functions']
    common = sorted(set(a) & set(b))
    changed = [name for name in common if a[name]['sha256'] != b[name]['sha256']]
    report = {'schema': 'synapse-lie.q2-native-device-code.v1', 'saved': old, 'candidate': new,
              'common_functions': len(common), 'byte_exact_functions': len(common) - len(changed),
              'changed_functions': changed,
              'changed_function_sizes': [n for n in common if a[n]['bytes'] != b[n]['bytes']],
              'changed_resources': [n for n in common if a[n]['resources'] != b[n]['resources']],
              'added_functions': sorted(set(b) - set(a)), 'removed_functions': sorted(set(a) - set(b)),
              'gpu_run': False,
              'limits': ['Raw function differences can include relocated address literals.',
                         'Exact function bytes alone do not prove runtime dispatch or performance.']}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: len(value) if isinstance(value, list) else value
                      for key, value in report.items() if key not in ('saved', 'candidate')}))


if __name__ == '__main__':
    main()
