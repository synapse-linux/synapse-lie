#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic source identity fixtures; no remote artifacts or GPU access."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from q2_reuse import HC_KERNEL, verify_sources


class ReuseTests(unittest.TestCase):
    def test_only_hc_may_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'old', Path(tmp) / 'new'
            for root in (a, b):
                (root / HC_KERNEL).parent.mkdir(parents=True)
                (root / HC_KERNEL).write_text('kernel')
                (root / 'mmq').write_text('original')
            self.assertEqual(verify_sources(a, b)['changed'], [])
            (b / HC_KERNEL).write_text('candidate')
            self.assertEqual(verify_sources(a, b)['changed'], [HC_KERNEL])
            (b / 'mmq').write_text('changed')
            with self.assertRaisesRegex(RuntimeError, 'outside the HC kernel'):
                verify_sources(a, b)
            (b / 'mmq').unlink()
            with self.assertRaisesRegex(RuntimeError, 'identical source inventories'):
                verify_sources(a, b)
            (a / 'mmq').unlink()
            (a / HC_KERNEL).unlink()
            (b / HC_KERNEL).unlink()
            with self.assertRaisesRegex(RuntimeError, 'identical source inventories'):
                verify_sources(a, b)


if __name__ == '__main__':
    unittest.main()
