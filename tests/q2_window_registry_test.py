#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from q2_window_registry import active_window


class WindowRegistryTest(unittest.TestCase):
    def test_owned_terminal_cohorts_follow_active_admission(self):
        admit=dict(event='window_admit',owner='synapse-lie-q2',receipt_sha256='bound',at='04:12')
        rows=[dict(event='window_release',owner='foreign',at='03:30'),admit,
            dict(event='start',owner='synapse-lie-q2',at='04:13'),
            dict(event='end',owner='synapse-lie-q2',at='04:14')]
        self.assertEqual(active_window(rows,'bound','04:12'),admit)
    def test_missing_released_changed_and_foreign_events_are_refused(self):
        admit=dict(event='window_admit',owner='synapse-lie-q2',receipt_sha256='bound',at='04:12')
        for rows,digest,at in [([], 'bound','04:12'),([admit], 'other','04:12'),
            ([admit], 'bound','04:11'),([admit,dict(event='window_release',owner='synapse-lie-q2',at='04:15')],'bound','04:12'),
            ([admit,dict(event='start',owner='foreign',at='04:14')],'bound','04:12'),
            ([admit,dict(event='window_admit',owner='foreign',receipt_sha256='bound',at='04:15')],'bound','04:12')]:
            with self.subTest(rows=rows,digest=digest,at=at):
                with self.assertRaises(ValueError):active_window(rows,digest,at)


if __name__=='__main__':unittest.main()
