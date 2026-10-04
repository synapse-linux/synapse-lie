# SPDX-License-Identifier: MIT
"""Receipt admission tests, never GPU execution."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from gufo_build_policy import validate_target

class TargetTests(unittest.TestCase):
    def test_explicit_targets(self):
        for arch in ('gfx1150', 'gfx1151'):
            validate_target({'hip_architecture': arch},
                            f'CMAKE_HIP_ARCHITECTURES:STRING={arch}\nLIE_HIP_ARCHITECTURE:STRING={arch}\n', arch)

    def test_reject_cross_target_and_unbound_archives(self):
        for target, receipt, cache in (
            ('gfx1150', {'hip_architecture':'gfx1150'}, 'gfx1151'),
            ('gfx1151', {'hip_architecture':'gfx1150'}, 'gfx1151'),
            ('gfx1150', {}, 'gfx1150'),
            ('gfx1150', {'hip_architecture':'gfx1150'}, 'gfx1150;gfx1151'),
            ('gfx1150', {'hip_architecture':'gfx1150'}, ''),
            ('gfx1152', {'hip_architecture':'gfx1152'}, 'gfx1152'),
        ):
            with self.subTest(target=target, receipt=receipt, cache=cache), self.assertRaises(ValueError):
                validate_target(receipt, f'CMAKE_HIP_ARCHITECTURES:STRING={cache}\n', target)

    def test_legacy_halo_requires_matching_cache(self):
        validate_target({}, 'CMAKE_HIP_ARCHITECTURES:STRING=gfx1151\n', 'gfx1151')
        with self.assertRaises(ValueError):
            validate_target({}, '', 'gfx1151')

    def test_duplicate_and_conflicting_policy(self):
        base='CMAKE_HIP_ARCHITECTURES:STRING=gfx1150\n'
        for extra in (base, 'LIE_HIP_ARCHITECTURE:STRING=gfx1151\n'):
            with self.assertRaises(ValueError):
                validate_target({'hip_architecture':'gfx1150'}, base+extra, 'gfx1150')

if __name__ == '__main__':
    unittest.main()
